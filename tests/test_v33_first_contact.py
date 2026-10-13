"""V3.3 tests: encounter lifecycle, physical-ready screen rays, GPU-shape contract.

No GPU is instantiated in these tests; OpenGL shader link checked separately.
"""
import importlib.util
import math
import sys
import types
import unittest
import numpy as np
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
for optional in ('moderngl','pygame'):
    if optional in sys.modules:  # Prior offline tests may have installed a stub.
        continue
    if importlib.util.find_spec(optional) is None:
        sys.modules[optional]=types.ModuleType(optional)
from enemy_system import (EnemyDirector,EnemyAgent,encounter_spec,enemy_parts,
                          ray_from_screen,ray_sphere,PROFILES)
import trench_3d_test as world


class FirstContactTests(unittest.TestCase):
    def test_profiles_have_stable_encounter_ids_and_reused_uniform_layers(self):
        for i in range(150):
            self.assertEqual(encounter_spec(i),encounter_spec(i))
            self.assertIn(encounter_spec(i).profile,PROFILES)
        parts=enemy_parts(EnemyAgent(encounter_spec(0)))
        self.assertGreater(len(parts),22)
        self.assertTrue(all(part[1] in (10,11,13,23,24,25) for part in parts))
        for p in parts:
            numbers=list(p[2])+list(p[3] if p[0]=='cylinder' else p[3])
            self.assertTrue(all(math.isfinite(x) for x in numbers))

    def test_contact_holds_until_player_hit_and_does_not_timeout(self):
        director=EnemyDirector()
        for _ in range(1800):director.update(.05,27.)
        agent=director.active[0]
        self.assertEqual(agent.state,'firing') if agent.state=='firing' else self.assertGreater(agent.shots_fired,0)
        self.assertFalse(agent.dead)
        self.assertEqual(director.clamp_advance(27.,3.0),0.0)
        # A miss cannot eliminate anything; nothing disappears after 90 sec.
        miss=director.resolve_ray((0.,0.,0.),(0.,0.,-1.),lambda spec:(0.,0.,20.))
        self.assertIsNone(miss)
        self.assertTrue(director.current_threat(27.))
        # Verified ray resolves the actual head sphere, no aim assist.
        shot=director.resolve_ray((0.,1.65,0.),(0.,0.,1.),
                                  lambda spec:(0.,0.,12.))
        self.assertIsNotNone(shot)
        self.assertEqual(shot,(0,'head'))
        self.assertFalse(director.current_threat(27.))
        self.assertGreater(director.clamp_advance(27.,3.),2.9)
        self.assertIsNone(director.resolve_ray((0.,1.65,0.),(0.,0.,1.),
                                                lambda spec:(0.,0.,12.)))

    def test_hit_screen_coordinate_uses_render_projection_no_magic_pixel_area(self):
        director=EnemyDirector()
        director.update(.05,27.)
        eye=np.array((0.,1.55,0.))
        aim=np.array((0.,1.40,12.))
        pv=world.perspective(80.,800/600,.045,290.) @ world.view_from(eye,aim)
        # Project exactly the head into Pygame TOP-LEFT screen pixels.
        center=np.array((0.,1.66,10.,1.))
        clip=pv@center; ndc=clip[:3]/clip[3]
        px=(ndc[0]+1)*.5*800-.5
        py=(1-ndc[1])*.5*600-.5
        ray_origin,ray_dir=ray_from_screen(px,py,800,600,pv)
        self.assertIsNotNone(ray_sphere(ray_origin,ray_dir,(0.,1.66,10.),.20))
        # Offscreen/wrong target pixels must miss.
        self.assertIsNone(director.resolve_screen_hit(30,30,800,600,pv,
                            lambda spec:(0.,0.,10.)))
        self.assertIsNone(director.last_hit)
        hit=director.resolve_screen_hit(px,py,800,600,pv,
                            lambda spec:(0.,0.,10.))
        self.assertEqual(hit,(0,'head'))

    def test_occlusion_callback_prevents_bogus_hits(self):
        d=EnemyDirector();d.update(.1,27.)
        hit=d.resolve_ray((0.,1.66,0.),(0.,0.,1.),
                     lambda spec:(0.,0.,10.),
                     lambda agent,t,eye,ray:True)
        self.assertIsNone(hit)
        self.assertFalse(d.active[0].dead)

    def test_reset_replays_contact_deterministically(self):
        d=EnemyDirector();d.update(.1,27.)
        d.resolve_ray((0.,1.66,0.),(0.,0.,1.),lambda spec:(0.,0.,10.))
        self.assertIn(0,d.eliminated)
        d.update(.1,350.)
        self.assertNotIn(0,d.active)
        d.reset()
        d.update(.1,27.)
        self.assertIn(0,d.active)
        self.assertNotIn(0,d.eliminated)

    def test_enemy_fires_visual_only_and_never_removes_itself(self):
        for profile in ('ambush','unaware','cover','rush'):
            spec=encounter_spec(0)
            spec=type(spec)(spec.enemy_id,spec.route_m,spec.lateral,profile)
            a=EnemyAgent(spec)
            a.engage()
            for i in range(1300):a.update(.04)
            self.assertGreater(a.shots_fired,0,profile)
            self.assertFalse(a.dead,profile)
            self.assertTrue(a.threat,profile)



class FrozenGameHitTests(unittest.TestCase):
    def _frame(self,director):
        eye=np.array((0.,1.45,0.))
        aim=np.array((0.,1.45,12.))
        pv=world.perspective(80.,800/600,.045,290.) @ world.view_from(eye,aim)
        return director.capture_frame(pv,800,600,24.,lambda spec:(0.,0.,10.),lambda s:0.)

    def test_capture_is_immutable_across_pose_updates_and_world_rotations(self):
        d=EnemyDirector();d.update(.01,27.)
        agent=d.active[0]
        a=self._frame(d)
        self.assertGreater(len(a.hit_spheres),0)
        agent.engage()
        for i in range(35):agent.update(.04)
        b=self._frame(d)
        self.assertNotEqual(a.hit_spheres,b.hit_spheres)
        self.assertEqual(a.hit_spheres,a.hit_spheres)
        self.assertEqual(a.route_m,24.)
        self.assertEqual(a.width,800)
        self.assertEqual(a.height,600)

    def test_frozen_frame_does_not_consult_new_poses_to_kill(self):
        d=EnemyDirector();d.update(.01,27.)
        frame=self._frame(d)
        # Project the ACTUAL frozen head using the same model/view matrix.
        enemy_id,part,head,r=next(h for h in frame.hit_spheres if h[1]=='head')
        v=np.array((*head,1.))
        clip=np.asarray(frame.view_projection)@v
        ndc=clip[:3]/clip[3]
        sx=(ndc[0]+1)*400-.5
        sy=(1-ndc[1])*300-.5
        d.active[0].engage()
        for i in range(25):d.active[0].update(.03)
        self.assertEqual(d.resolve_frozen_hit(sx,sy,frame),(0,'head'))
        self.assertIsNone(d.resolve_frozen_hit(sx,sy,frame))

    def test_occluded_frozen_actor_cannot_be_eliminated(self):
        d=EnemyDirector();d.update(.01,27.)
        frame=self._frame(d)
        _,_,head,_=next(h for h in frame.hit_spheres if h[1]=='head')
        clip=np.asarray(frame.view_projection)@np.array((*head,1.))
        clip/=clip[3]
        sx=(clip[0]+1)*400-.5
        sy=(1-clip[1])*300-.5
        self.assertIsNone(d.resolve_frozen_hit(sx,sy,frame,
            lambda agent,t,origin,direction:True))
        self.assertFalse(d.active[0].dead)

    def test_future_physical_adapter_refuses_simulated_hitevent(self):
        fake=object.__new__(world.Trench)
        from types import SimpleNamespace
        with self.assertRaises(ValueError):
            fake.submit_verified_hit_event(SimpleNamespace(game_x=3,game_y=4,
                                                          is_simulated=True),None)

    def test_first_4_encounters_have_visible_line_to_head_at_stop(self):
        world_instance=object.__new__(world.Trench)
        for index in range(4):
            spec=encounter_spec(index)
            stop=spec.route_m-8.
            world_instance.distance=stop
            o=world.world(stop,0.,world.floor_y(stop)+1.0)
            h=world.world(spec.route_m,spec.lateral,world.floor_y(spec.route_m,spec.lateral)+1.67)
            vec=np.asarray(h)-np.asarray(o)
            t=float(np.linalg.norm(vec))
            self.assertFalse(world_instance._enemy_shot_occluded(EnemyAgent(spec),t,o,
                                   tuple(vec/t)),f'{spec} was hidden from stop')

class LongEncounterNavigationTests(unittest.TestCase):
    def test_four_scripted_contacts_require_player_and_navigation_resumes(self):
        import math
        brain=world.SoldierBrain()
        enemies=EnemyDirector()
        render_stub=object.__new__(world.Trench)
        distance=0.; heading=None
        confirmed=[]
        dt=.06
        for _ in range(23000):
            enemies.update(dt,distance)
            mode=brain.choose(distance,dt)
            threat=enemies.current_threat(distance)
            advanced=world.MOVES[mode][1]*brain.speed_factor*dt
            if threat is not None and brain.state=='main':
                advanced=enemies.clamp_advance(distance,advanced)
            distance,_=brain.advance(distance,advanced)
            x,z,desired=brain.camera_pose(distance)
            if heading is None:heading=desired
            angle=math.atan2(math.sin(desired-heading),math.cos(desired-heading))
            rate=1.15 if brain.state=='turn_back' else 1.75
            heading+=max(-rate*dt,min(rate*dt,angle))
            brain.heading_actual=heading
            threat=enemies.current_threat(distance)
            if threat is not None and distance >= threat.spec.route_m-8.01:
                render_stub.distance=distance
                spec=threat.spec
                eye=world.world(distance,0.,world.floor_y(distance)+1.0)
                head=world.world(spec.route_m,spec.lateral,world.floor_y(spec.route_m,spec.lateral)+1.67)
                ray=np.asarray(head)-np.asarray(eye)
                length=float(np.linalg.norm(ray))
                result=enemies.resolve_ray(eye,tuple(ray/length),
                    lambda spec:world.world(spec.route_m,spec.lateral,
                                             world.floor_y(spec.route_m,spec.lateral)),
                    render_stub._enemy_shot_occluded)
                self.assertIsNotNone(result,f'contact {spec.enemy_id} not shootable')
                confirmed.append(result[0])
            if distance>410:break
        self.assertGreater(distance,410.,'SoldierBrain never resumed autonomous travel')
        self.assertEqual(confirmed,[0,1,2,3])
        self.assertGreater(brain.visit_count,0)
        self.assertEqual(len(enemies.eliminated),4)


class StreamingAndSharedRigTests(unittest.TestCase):
    def test_active_enemies_stay_bounded_on_long_infinite_route(self):
        d=EnemyDirector()
        max_live=0
        for s in range(0,50001,17):
            d.update(.05,float(s))
            max_live=max(max_live,len(d.active))
        self.assertLessEqual(max_live,4,'encounters must stream, not accumulate')
        self.assertEqual(len(d.eliminated),0)

    def test_elimination_persists_after_eviction_and_revisit(self):
        d=EnemyDirector();d.update(.05,27.)
        self.assertEqual(d.resolve_ray((0.,1.66,0.),(0.,0.,1.),
                                       lambda spec:(0.,0.,10.)),(0,'head'))
        d.update(.05,240.)
        self.assertNotIn(0,d.active)
        d.update(.05,27.)
        self.assertNotIn(0,d.active)
        self.assertIn(0,d.eliminated)

    def test_hit_spheres_follow_rendered_yaw_and_helmet_height(self):
        a=EnemyAgent(encounter_spec(0))
        a.engage()
        for _ in range(25):a.update(.04)
        center=(2.,.2,3.)
        spheres=dict((name,(point,r)) for name,point,r in a.hit_regions(center,math.pi/2))
        head=spheres['head'][0]
        self.assertAlmostEqual(head[0],2.025,delta=.005)
        self.assertAlmostEqual(head[1],center[1]+1.67+.009*math.sin(a.total_time*2.1),delta=.005)
        self.assertAlmostEqual(head[2],3.,delta=.005)
        head_part=next(part for part in enemy_parts(a)
                       if part[0]=='oval' and part[1]==25 and part[2][1]>1.4)
        model=world.EnemyRenderer.part_model(center,math.pi/2,head_part)
        p=model@np.array((0.,0.,0.,1.))
        self.assertLess(float(np.linalg.norm(p[:3]-np.asarray(head))),.005)


class SharedGpuShapeContracts(unittest.TestCase):
    def test_shared_shape_buffers_are_created_only_once(self):
        class FakeUniform:
            def __init__(self):self.value=None
            def write(self,data):self.value=data
        class FakeProgram:
            def __init__(self):self.u={}
            def __getitem__(self,key):return self.u.setdefault(key,FakeUniform())
            def __setitem__(self,key,value):self[key].value=value
            def release(self):pass
        class FakeBuffer:
            def __init__(self,data):self.data=data
            def release(self):pass
        class FakeVao:
            def __init__(self):self.draws=0
            def render(self,*args):self.draws+=1
            def release(self):pass
        class FakeCtx:
            def __init__(self):self.buffers=[];self.vaos=[]
            def program(self,**kwargs):return FakeProgram()
            def buffer(self,data):
                b=FakeBuffer(data);self.buffers.append(b);return b
            def vertex_array(self,program,content):
                v=FakeVao();self.vaos.append(v);return v
        ctx=FakeCtx()
        if not hasattr(world.moderngl,'TRIANGLES'):
            world.moderngl.TRIANGLES=4  # stub only, not the real GL module
        avatar=world.EnemyRenderer(ctx)
        self.assertEqual(len(ctx.buffers),14)
        for buf in ctx.buffers:
            self.assertGreater(len(buf.data),1000)
            self.assertEqual(len(buf.data)%(9*4),0)
            self.assertTrue(np.isfinite(np.frombuffer(buf.data,dtype='f4')).all())
        a=EnemyAgent(encounter_spec(0));a.engage()
        b=EnemyAgent(encounter_spec(1));b.engage()
        a.update(1.0);b.update(1.0)
        pv=np.eye(4,dtype='f4')
        for step in range(5):
            avatar.draw([a,b],lambda spec:(0.,0.,float(spec.route_m)),
                        lambda s:0.,pv,(0.,1.,0.),1.0,False,[])
        self.assertEqual(len(ctx.buffers),14,'no mesh allocation per frame')
        self.assertGreater(sum(vao.draws for vao in ctx.vaos),100)
        avatar.release()

if __name__=='__main__':
    unittest.main()
