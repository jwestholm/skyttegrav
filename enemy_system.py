"""V3.3 First Contact: deterministic enemy encounters and screen-space 3D hit query.

No PyBullet, no OpenGL dependency in the decision logic. 3D display is an
interchangeable mesh-prototype renderer; future GLB rigged avatars plug in here.
Only the player can resolve a living threat.  Enemy fire is visual in V3.3.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EnemyProfile:
    kind: str
    react_time: float
    aim_time: float
    fire_interval: float
    crouch_during_reload: bool = False


PROFILES = {
    'unaware': EnemyProfile('unaware', .95, .90, 1.15),
    'ambush': EnemyProfile('ambush', .38, .52, .92),
    'cover': EnemyProfile('cover', .65, .60, 1.25, True),
    # Rusher behaviour is reserved until collision/approach-path support exists.
    'rush': EnemyProfile('rush', .50, .68, .85),
}


@dataclass(frozen=True)
class EnemySpec:
    enemy_id: int
    route_m: float
    lateral: float
    profile: str


def encounter_spec(index):
    """Stable, bounded lookups; no million-enemy registry or RNG state."""
    if index < 0:
        raise ValueError('encounter index must be non-negative')
    first = (
        (32.0, -.18, 'unaware'),
        (164.0, .14, 'ambush'),
        (258.0, -.15, 'cover'),
        (384.0, .12, 'unaware'),
    )
    if index < len(first):
        s, lateral, kind = first[index]
    else:
        # Main-line patrols after the four stable, manually tested contacts.
        # 72m spacing puts patrols BETWEEN recurring 72m junction markers:
        # first is 516 (junctions 496/568), then 588, 660, ...
        # Side-branch spawns and hiding are deliberately not faked here.
        s = 516.0 + (index-4)*72.0
        lateral = -.12 if index % 2 else .12
        kind = ('ambush','cover','unaware')[index % 3]
    return EnemySpec(index, s, lateral, kind)


def _vec_sub(a,b):
    return tuple(ai-bi for ai,bi in zip(a,b))


def _dot(a,b):
    return sum(ai*bi for ai,bi in zip(a,b))


def _normalize(a):
    length = math.sqrt(max(0.0,_dot(a,a)))
    if length < 1e-9: return (0.,0.,0.)
    return tuple(x/length for x in a)


def ray_sphere(origin,direction,center,radius):
    """Closest positive ray/sphere intersection distance or None."""
    oc = _vec_sub(origin,center)
    b = _dot(oc,direction)
    c = _dot(oc,oc) - radius*radius
    delta = b*b-c
    if delta < 0: return None
    root = math.sqrt(delta)
    for t in (-b-root,-b+root):
        if t > .045: return t
    return None


def ray_from_screen(x,y,width,height,view_projection):
    """Unproject Pygame TOP-left pixel coordinates through the same render MVP.

    This is the future verified physical Game Space -> camera ray adapter.
    Only input changes when integrated with Skjutbanan; physical detection
    stays completely outside this module.
    """
    import numpy as np
    if width <= 0 or height <= 0: raise ValueError('invalid viewport')
    nx = 2.0*(x+.5)/width - 1.0
    ny = 1.0-2.0*(y+.5)/height
    inv = np.linalg.inv(np.asarray(view_projection,dtype='f8'))
    points=[]
    for depth in (-1.,1.):
        p=inv @ np.array([nx,ny,depth,1.],dtype='f8')
        p/=p[3]
        points.append(tuple(float(t) for t in p[:3]))
    return points[0],_normalize(_vec_sub(points[1],points[0]))


class EnemyAgent:
    """Owns one enemy's behavior; no magical knowledge of other combatants."""
    def __init__(self,spec):
        self.spec=spec
        self.profile=PROFILES[spec.profile]
        self.state='idle'
        self.state_time=0.0
        self.total_time=0.0
        self.shots_fired=0
        self.dead=False
        self.injured_part=None
        self.anim_revision=0
        # Continuous visual pose channels; logical combat states are discrete,
        # but weapon/stance must NEVER snap when switching states.
        self.pose_aim=0.0
        self.pose_crouch=0.0
        self.blast_timer=0.0
        self.blast_level=0
        # Current WORLD-route position. Must be used by model AND frozen hit
        # geometry; the seed-original EnemySpec is immutable metadata only.
        self.route_m=float(spec.route_m)
        self.investigation_goal=None
        self.heard_shots=0

    def hear_shot(self,origin_route_m,max_range=78.0):
        """Enter route-following investigation if a NEW gunshot is ahead.

        This early main-route-only perception uses path distance, not magical
        X-ray awareness of off-route dugouts. Do not chase from behind player.
        """
        if self.dead or self.state!='idle':return False
        ahead=self.route_m-float(origin_route_m)
        if not (1.5<ahead<=max_range):return False
        self.investigation_goal=max(float(origin_route_m)+10.,self.route_m-42.)
        self.heard_shots+=1
        self._transition('investigating')
        return True

    def react_to_blast(self,level):
        """A brief suppression reflex. Does NOT spawn/kill/engage a target."""
        level=int(level)
        if level<=0 or self.dead:return False
        self.blast_level=max(self.blast_level,level)
        self.blast_timer=max(self.blast_timer,{1:.40,2:1.05,3:1.65}[self.blast_level])
        return True

    def engage(self):
        if not self.dead and self.state in ('idle','investigating','alert'):
            self._transition('turning')

    def update(self,dt):
        if dt<0:raise ValueError('negative timestep')
        dt=min(dt,.1)
        self.total_time+=dt
        if self.dead:
            # Death pose is driven by state_time. Freezing this clock left
            # eliminated enemies standing forever despite correct hit results.
            self.state_time+=dt
            return
        if self.blast_timer>0.0:
            self.blast_timer=max(0.0,self.blast_timer-dt)
            # Hold the existing combat phase, but suppress firing and duck.
            target_crouch=1.0 if self.blast_level>=2 else .35
            self.pose_crouch+=(target_crouch-self.pose_crouch)*(1.-math.exp(-dt*5.5))
            self.pose_aim+=(0.0-self.pose_aim)*(1.-math.exp(-dt*6.0))
            if self.blast_timer>0.0:
                return
            self.blast_level=0
        self.state_time+=dt
        if self.state=='investigating':
            # Single-lane route-following patrol: no position snapping and no
            # movement before an actual heard shot. Runs at 2.55 m/s until the
            # audible source area, then waits alert, not firing through banks.
            previous=self.route_m
            self.route_m=max(self.investigation_goal,self.route_m-2.55*dt)
            target_crouch=.06
            self.pose_crouch+=(target_crouch-self.pose_crouch)*(1.-math.exp(-dt*5.))
            self.pose_aim+=(0.0-self.pose_aim)*(1.-math.exp(-dt*5.))
            if self.route_m<=self.investigation_goal+1e-5:
                self._transition('alert')
            return
        if self.state=='turning' and self.state_time>=self.profile.react_time:
            self._transition('aiming')
        elif self.state=='aiming' and self.state_time>=self.profile.aim_time:
            # The muzzle flash is visible upon entering FIRING, not when the
            # state expires a second later. Count precisely that visual shot.
            self.shots_fired+=1
            self._transition('firing')
        elif self.state=='firing' and self.state_time>=self.profile.fire_interval:
            # Cover agent actually ducks on reload, other agents re-aim.
            self._transition('cover' if self.profile.crouch_during_reload and self.shots_fired%3==0 else 'aiming')
        elif self.state=='cover' and self.state_time>=1.55:
            self._transition('aiming')
        # Separate target stance from discrete AI. A continuous channel prevents
        # teleporting between crouch and upright or dropping the weapon each
        # time FIRING becomes AIMING. Rates are in inverse seconds.
        target_aim=(1.0 if self.state in ('firing','aiming') else
                    0.38 if self.state=='cover' else 0.0)
        target_crouch=1.0 if self.state=='cover' else 0.0
        self.pose_aim+=(target_aim-self.pose_aim)*(1.-math.exp(-dt*4.8))
        self.pose_crouch+=(target_crouch-self.pose_crouch)*(1.-math.exp(-dt*3.5))

    def _transition(self,state):
        self.state=state
        self.state_time=0.0
        self.anim_revision+=1

    def eliminate(self,part):
        if self.dead:return False
        self.injured_part=part
        self.dead=True
        self._transition('dead')
        return True

    @property
    def threat(self):
        return self.state not in ('idle','alert','dead')

    def turn_fraction(self):
        if self.state=='idle':return 0.
        if self.state=='turning':
            x=max(0.,min(1.,self.state_time/self.profile.react_time))
            return x*x*(3-2*x)
        return 1.

    def aim_fraction(self):
        return self.pose_aim

    def crouch_fraction(self):
        return self.pose_crouch

    def hit_regions(self,center,heading=0.0):
        """Animated body proxies in actual WORLD SPACE, matching the model yaw.

        Placeholder shapes are deliberately approximate until skeletal GLB
        bone hitboxes exist. They never enlarge on a miss for aim assist.
        """
        if self.dead:return ()
        x,y,z=center
        crouch=self.crouch_fraction()
        drop=.27*crouch
        breathing=(.021*math.sin(self.total_time*13.2) if self.state=='investigating'
                   else .009*math.sin(self.total_time*2.1))
        c,si=math.cos(heading),math.sin(heading)
        def pt(dx,dy,dz):
            return (x+c*dx+si*dz,y+dy,z-si*dx+c*dz)
        stride=.16*math.sin(self.total_time*11.) if self.state=='investigating' else 0.
        return (
            ('head',pt(0.,1.67-drop+breathing,.025),.195),
            ('torso',pt(0.,1.17-drop+breathing,0.),.315),
            ('pelvis',pt(0.,.89-drop*.57,0.),.23),
            ('left_leg',pt(-.16,.53-.10*crouch,.055+stride),.145),
            ('right_leg',pt(.16,.53-.10*crouch,.055-stride),.145),
        )


@dataclass(frozen=True)
class FrozenEnemyFrame:
    """The exact 3D pose presented for one frame, independent of later AI updates.

    Store this with a shot-time snapshot when Skjutbanan integrates the game.
    One frame consumes only a handful of tiny tuples, never a texture/mesh.
    Pygame mouse tests use the latest PRESENTED frame, not the next update.
    """
    width: int
    height: int
    view_projection: tuple
    route_m: float
    hit_spheres: tuple  # (enemy_id, part_name, world_center, radius)
    actor_routes: tuple = ()  # immutable (enemy_id, frozen route_m) for LOS


class EnemyDirector:
    """Activates only nearby deterministic encounters; remembers resolved IDs.

    There is no autonomous kill or expiry. Once a threat engages, it holds the
    soldier until a validated Game Space hit eliminates the agent.
    """
    def __init__(self):
        self.active={}
        self.eliminated=set()
        self.contact_count=0
        self.last_hit=None

    def reset(self):
        self.active.clear()
        self.eliminated.clear()
        self.contact_count=0
        self.last_hit=None

    def hear_shot(self,route_m,max_range=78.0):
        """Gunfire is a local cue. Returns IDs of newly alerted patrols.

        An existing patrol only hears after it has been generated into the
        bounded active window. Repeated shots do not re-trigger or teleport.
        """
        alerted=[]
        for idx,agent in sorted(self.active.items()):
            if agent.hear_shot(route_m,max_range):
                alerted.append(idx)
        return tuple(alerted)

    def update(self,dt,route_m):
        # First four remain fixed; later patrols are a denser but bounded 72m
        # grid. Never allocate enemies across the infinite level in advance.
        first=max(4,4+int(math.floor((route_m-105.-516.)/72.)))
        last=max(first+1,4+int(math.ceil((route_m+105.-516.)/72.)))
        for idx in list(range(4))+list(range(first,last+1)):
            spec=encounter_spec(idx)
            if idx in self.eliminated:continue
            if abs(spec.route_m-route_m)<=90.0:
                self.active.setdefault(idx,EnemyAgent(spec))
        gunshots=[]
        for idx,agent in list(self.active.items()):
            if agent.dead:
                self.eliminated.add(idx)
            if agent.route_m<route_m-85 or agent.route_m>route_m+100:
                del self.active[idx]
                continue
            # Visible/nearby patrol reaches combat distance and stops moving
            # even when it was previously following a distant sound.
            if not agent.dead and 0.0<agent.route_m-route_m<=16.0:
                if agent.state in ('idle','investigating','alert'):
                    agent.engage()
                    self.contact_count+=1
            before=agent.shots_fired
            agent.update(dt)
            if agent.shots_fired>before and not agent.dead:
                gunshots.append(agent.route_m)
        # Fired enemy rifles can alert other patrols, but only AFTER this
        # frame's states were updated, preventing order-dependent cascades.
        for source_m in gunshots:
            self.hear_shot(source_m,max_range=82.0)

    def react_to_blast(self,impact_position,strength,level_for_distance,position_at):
        """Apply one blast signal to ACTUALLY nearby active enemies.

        Uses world-space X/Z distance, never the route metre difference.
        Does not change kill state, encounter ids or hit precision.
        """
        x,_,z=impact_position
        count=0
        for agent in self.active.values():
            if agent.dead:continue
            ax,_,az=position_at(agent.spec)
            distance=math.hypot(ax-x,az-z)
            level=level_for_distance(distance,strength)
            if agent.react_to_blast(level):count+=1
        return count

    def current_threat(self,route_m):
        candidates=[a for a in self.active.values()
                    if a.threat and -3 < a.route_m-route_m < 24]
        return min(candidates,key=lambda a:a.route_m-route_m) if candidates else None

    def clamp_advance(self,route_m,travel):
        """No skipping a live encounter at high FPS/sprint speed."""
        threat=self.current_threat(route_m)
        if threat is None:return travel
        stop=threat.route_m-8.0
        return min(travel,max(0.,stop-route_m))

    def capture_frame(self,view_projection,width,height,route_m,position_at,heading_at,visible_radius=65.):
        """Freeze the SHOWN poses for a later verified game coordinate.

        No live AI positions are consulted for the geometry of this frame.
        Dead actors get no hittable spheres, even though their corpses render.
        """
        mat=tuple(tuple(float(x) for x in row) for row in view_projection)
        spheres=[]
        routes=[]
        for agent in sorted(self.active.values(),key=lambda a:a.spec.enemy_id):
            if agent.dead or abs(agent.route_m-route_m)>=visible_radius:continue
            routes.append((agent.spec.enemy_id,float(agent.route_m)))
            p=position_at(agent.spec)
            yaw=actor_facing(agent,heading_at(agent.route_m))
            for name,point,r in agent.hit_regions(p,yaw):
                spheres.append((agent.spec.enemy_id,name,point,float(r)))
        return FrozenEnemyFrame(int(width),int(height),mat,float(route_m),
                                tuple(spheres),tuple(routes))

    def resolve_frozen_hit(self,x,y,frame,occluded=None):
        """Resolve an EXACT game-space point against the captured visible pose.

        The closest intersection is used; optional occlusion protects solid
        level geometry. occluded receives (agent,t,origin,direction).
        This method does not detect physical shots and does not snap coordinates.
        """
        origin,direction=ray_from_screen(x,y,frame.width,frame.height,
                                         frame.view_projection)
        nearest=None
        for enemy_id,part,point,r in frame.hit_spheres:
            agent=self.active.get(enemy_id)
            if agent is None or agent.dead:continue
            t=ray_sphere(origin,direction,point,r)
            if t is None or t>150:continue
            if nearest is None or t<nearest[0]:nearest=(t,agent,part)
        if nearest is None:return None
        t,agent,part=nearest
        if occluded is not None and occluded(agent,t,origin,direction):return None
        if not agent.eliminate(part):return None
        self.eliminated.add(agent.spec.enemy_id)
        self.last_hit=(agent.spec.enemy_id,part)
        return self.last_hit

    def resolve_ray(self,origin,direction,position_at,occluded=None):
        """Nearest living body's 3D proxy. No screen-radius forgiving hit.

        occluded is a pluggable visibility callback(agent, ray_t, origin,
        direction) for geometry depth/cover; DO NOT claim true LOS without one.
        """
        nearest=None
        direction=_normalize(direction)
        for agent in self.active.values():
            if agent.dead:continue
            center=position_at(agent.spec)
            for part,p,radius in agent.hit_regions(center):
                t=ray_sphere(origin,direction,p,radius)
                if t is None or t>150:continue
                if nearest is None or t<nearest[0]:
                    nearest=(t,agent,part)
        if nearest is None:return None
        t,agent,part=nearest
        if occluded and occluded(agent,t,origin,direction):return None
        if agent.eliminate(part):
            self.eliminated.add(agent.spec.enemy_id)
            self.last_hit=(agent.spec.enemy_id,part)
            return self.last_hit
        return None

    def resolve_screen_hit(self,x,y,width,height,view_projection,position_at,occluded=None):
        origin,direction=ray_from_screen(x,y,width,height,view_projection)
        return self.resolve_ray(origin,direction,position_at,occluded)


# ----- Renderer-neutral skeleton pose. A future GLB rig can replace geometry. -----
def _smoothstep01(value):
    value = max(0.0, min(1.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def _rotated_support_bottom(part, angle):
    """Lowest local-space point of a dead actor's protective/body equipment.

    Revolved/box shapes use conservative bounds; rods use their endpoint
    radii. The weapon and muzzle flash are excluded from floor contact.
    This is a *visual* pose adjustment, not a rigid-body physics claim.
    """
    if part[1] not in (10, 23, 24, 25):
        return None
    if part[0] == 'cylinder':
        return min(part[2][1], part[3][1]) - part[4]
    cx,cy,cz=part[2]
    if part[0] == 'jacket':
        # Ring mesh: y [-.39,+.36], z [-.21,+.21] in unit jacket coordinates.
        ry,rz=.40*part[3][1],.22*part[3][2]
    elif part[0] == 'helmet':
        ry,rz=.20*part[3][1],.245*part[3][2]
    else:
        _,ry,rz=part[3]
    return cy - abs(math.cos(angle))*ry - abs(math.sin(angle))*rz


def corpse_ground_clearance(parts, angle):
    """Positive translation needed to place the lowest BODY point on ground.

    Computed from animated parts themselves. No hard-coded backpack pivot or
    magic death height; the exact same translation applies to all parts.
    """
    lows=[v for p in parts if (v:=_rotated_support_bottom(p,angle)) is not None]
    return max(0.0, .012 - min(lows)) if lows else 0.0


def enemy_parts(agent):
    """Compact render-neutral, animated humanoid rig with shared GPU meshes.

    Parts are (shape, material, centre, scale) for ellipsoid/box/jacket/helmet,
    or (cylinder, material, point_a, point_b, radius). During falling the
    non-cylindrical parts gain a fifth ``pitch`` value so geometry AND position
    rotate together. All metre coordinates are relative to the foot-level
    ground anchor shared with the first-person world.

    These models remain procedural stand-ins for proper rigged GLB characters.
    """
    crouch=agent.crouch_fraction()
    aim=agent.aim_fraction()
    dying=_smoothstep01(agent.state_time/1.10) if agent.dead else 0.0
    breath=(.021*math.sin(agent.total_time*13.2) if agent.state=='investigating'
            else .009*math.sin(agent.total_time*2.1) if not agent.dead else 0.0)
    drop=crouch*.25
    torso_y=1.15-drop+breath
    head_y=1.67-drop+breath
    recoil=0.0
    if agent.state == 'firing':
        recoil=.065*math.exp(-agent.state_time*17.0)
    parts=[]
    def oval(mat,center,radii):parts.append(('oval',mat,center,radii))
    def cube(mat,center,radii):parts.append(('cube',mat,center,radii))
    def cyl(mat,a,b,r):parts.append(('cylinder',mat,a,b,r))
    def jacket(mat,center):parts.append(('jacket',mat,center,(1.,1.,1.)))
    def helmet(mat,center):parts.append(('helmet',mat,center,(1.,1.,1.)))

    # Alternating strides while a heard-shot patrol runs toward the player.
    for side in (-1.,1.):
        x=side*.155
        stride=(.16*math.sin(agent.total_time*11.)*side if agent.state=='investigating'
                else 0.)
        foot_lift=(.09*max(0.,math.sin(agent.total_time*11.)*side)
                   if agent.state=='investigating' else 0.)
        cyl(23,(x,.87-drop,0.),(x*1.14,.49-.10*crouch,.025+stride),.128)
        oval(23,(x*1.14,.49-.10*crouch,.025+stride),(.137,.145,.132))
        cyl(23,(x*1.14,.46-.10*crouch,.025+stride),
               (x*1.16,.16+foot_lift,.043+.13*crouch+stride),.102)
        cube(10,(x*1.16,.107+foot_lift,.103+.13*crouch+stride),(.135,.109,.229))
        cube(24,(x*1.16,.22+foot_lift,.048+.13*crouch+stride),(.111,.116,.133))
    # Hips and structured jacket remove the round-rock/teddybear silhouette.
    oval(23,(0.,.88-drop*.72,0.),(.255,.18,.164))
    jacket(23,(0.,torso_y,0.))
    # Padded chest armour on the front, plates and straps.
    cube(24,(0.,torso_y+.005,.215),(.247,.245,.064))
    cube(24,(0.,torso_y-.215,.214),(.261,.041,.079))
    for side in (-1.,1.):
        x=side*.157
        cube(24,(x,torso_y-.18,.294),(.089,.119,.057))  # magazine pouch
        cyl(24,(side*.23,torso_y+.29,.195),
               (side*.12,torso_y-.29,.264),.020)      # harness strap
    cube(10,(0.,torso_y-.315,.175),(.255,.026,.037)) # belt buckle line

    # Backpack follows the spine; compact enough not to prop the corpse upright.
    cube(24,(0.,torso_y-.09,-.236),(.246,.295,.132))
    cube(24,(0.,torso_y+.195,-.232),(.19,.075,.115))
    for side in (-1.,1.):
        cube(24,(side*.223,torso_y-.13,-.233),(.057,.176,.112))
        cyl(24,(side*.20,torso_y+.26,-.14),
               (side*.175,torso_y-.19,-.25),.023)

    # Field kit: small but recognisable asymmetric equipment per encounter.
    # Reuses EXISTING shape/material GPU buffers (no runtime mesh creation).
    kit=agent.spec.enemy_id % 3
    if kit == 0:
        # Canteen clipped to right hip, with short neck/cap.
        oval(24,(.286,.784-drop*.65,-.085),(.096,.131,.083))
        cyl(24,(.286,.90-drop*.65,-.085),(.286,.94-drop*.65,-.085),.032)
    elif kit == 1:
        # Folded bedroll secured on top of the pack; not a large floating lump.
        cyl(13,(-.18,torso_y+.268,-.258),(.18,torso_y+.268,-.258),.071)
        for x in (-.12,.12):
            cube(24,(x,torso_y+.269,-.25),(.018,.082,.091))
    else:
        # Side radio/satchel with lid and retaining strap.
        cube(24,(-.32,torso_y-.20,-.10),(.100,.182,.122))
        cube(10,(-.322,torso_y-.043,-.10),(.097,.023,.125))
        cyl(24,(-.32,torso_y-.03,-.10),(-.32,torso_y+.29,-.16),.014)

    # Shoulders: upper arms and lower arms are continuous, with hands on gun.
    for side in (-1.,1.):
        shoulder=(side*.307,torso_y+.225,-.008)
        elbow=(side*.337,torso_y-.055,.045 if agent.dead else .09+aim*.090)
        hand=((side*.335,torso_y-.225,.065) if agent.dead else
              (side*.115,torso_y-.135+aim*.285,.345+aim*.25-recoil))
        oval(23,shoulder,(.139,.133,.151))
        cyl(23,shoulder,elbow,.113)
        oval(23,elbow,(.112,.109,.110))
        cyl(23,elbow,hand,.090)
        oval(24,hand,(.095,.079,.080))

    # Human face and a flatter combat helmet (not an oversized camo sphere).
    cyl(25,(0.,torso_y+.310,.012),(0.,head_y-.122,.030),.090)
    oval(25,(0.,head_y,.025),(.145,.189,.147))
    oval(25,(0.,head_y-.025,.152),(.115,.120,.066))
    for side in (-1.,1.):
        oval(25,(side*.147,head_y-.025,.035),(.035,.062,.045))
        # Dark eyes, softened by the helmet shadow at 8m distance.
        oval(10,(side*.055,head_y+.024,.207),(.019,.014,.014))
    oval(25,(0.,head_y-.027,.217),(.031,.041,.042))  # nose bridge
    cyl(10,(-.043,head_y-.102,.201),(.043,head_y-.102,.201),.007)
    helmet(24,(0.,head_y+.160,.015))
    # Ear/helmet straps sit OUTSIDE the cheek rather than crossing the face.
    cyl(24,(-.158,head_y+.029,.02),(-.125,head_y-.128,.142),.016)
    cyl(24,( .158,head_y+.029,.02),( .125,head_y-.128,.142),.016)

    # Rifle. Separate barrel, stock, receiver, sights and curved magazine.
    weapon_begin=len(parts)
    gy=torso_y-.17+aim*.32
    gz=.295+aim*.16-recoil
    cyl(10,(-.045,gy+.010,gz-.13),(.005,gy+.035,gz+.49),.046)
    cyl(10,(.005,gy+.035,gz+.44),(.005,gy+.035,gz+.98),.019)
    cyl(13,(-.055,gy,gz-.10),(-.124,gy-.10,gz-.41),.048)
    cyl(13,(.004,gy-.008,gz+.28),(.004,gy-.008,gz+.58),.040)
    cube(10,(-.026,gy+.035,gz+.13),(.055,.077,.161))
    cyl(10,(-.024,gy-.035,gz+.12),(-.012,gy-.20,gz+.18),.036)
    cyl(10,(-.012,gy-.20,gz+.18),(.000,gy-.25,gz+.28),.034)
    cyl(10,(.004,gy+.080,gz+.75),(.004,gy+.11,gz+.75),.013)
    if agent.state=='firing' and agent.state_time<.125:
        oval(11,(.004,gy+.035,gz+1.03),(.07,.073,.14))

    # True rigid pose rotation around the lower-body pivot. Unlike V3.3,
    # backpacks, helmets, VESTS, BOOTS and jacket actually ROTATE too.
    if dying:
        angle=1.52*dying  # tips FORWARD, leaving the backpack facing up
        pivot_y=.13
        pivot_z=.10
        co=math.cos(angle); si=math.sin(angle)
        def rotate(point):
            x,y,z=point
            y-=pivot_y;z-=pivot_z
            return (x, pivot_y+y*co-z*si, pivot_z+y*si+z*co)
        rotated=[]
        for part in parts[:weapon_begin]:
            if part[0]=='cylinder':
                rotated.append((part[0],part[1],rotate(part[2]),rotate(part[3]),part[4]))
            else:
                rotated.append((part[0],part[1],rotate(part[2]),part[3],angle))
        # Only the BODY must support itself against the ground, not a rifle
        # muzzle that otherwise pokes vertically through the terrain.
        lift=corpse_ground_clearance(rotated,angle)
        corrected=[]
        def up(point):return (point[0],point[1]+lift,point[2])
        for part in rotated:
            if part[0]=='cylinder':
                corrected.append((part[0],part[1],up(part[2]),up(part[3]),part[4]))
            else:
                corrected.append((part[0],part[1],up(part[2]),part[3],angle))
        # Drop the rifle to the actor's right. A real animated rig will later
        # provide hand release and angular inertia; this remains deterministic.
        release=_smoothstep01((agent.state_time-.20)/.60)
        def dropped(point):
            return (point[0]+.42, .15+(point[1]-gy)*.20,
                    1.16+(point[2]-gz))
        def weapon_point(point):
            left=up(rotate(point));right=dropped(point)
            return tuple(left[i]*(1.-release)+right[i]*release for i in range(3))
        for part in parts[weapon_begin:]:
            if part[0]=='cylinder':
                corrected.append((part[0],part[1],weapon_point(part[2]),
                                  weapon_point(part[3]),part[4]))
            else:
                # Rifle components should come to rest flat, not remain pitched.
                # Spheres are symmetrical enough for a smooth tip transition.
                corrected.append((part[0],part[1],weapon_point(part[2]),
                                  part[3],angle*(1.-release)))
        return corrected
    return parts


def actor_facing(agent,heading):
    """Facing world yaw; patrol running DOWN the route faces sound source."""
    if agent.state=='investigating':return heading+math.pi
    if agent.spec.profile=='unaware':return heading+math.pi*agent.turn_fraction()
    if agent.spec.profile=='ambush':
        # No sudden 58-degree snap on engage: the lookout had already turned
        # most of the way toward the player before finishing the last sweep.
        return heading+math.pi*(.68+.32*agent.turn_fraction())
    return heading+math.pi
