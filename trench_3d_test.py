"""Standalone actual-GPU 3D trench proof of concept (Pygame + ModernGL).
No interaction with Skjutbanan's hit detection, settings, menu or rendering.
Run: python3 trench_3d_test.py
"""
from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import moderngl
    import numpy as np
    import pygame
    from PIL import Image
except ImportError as exc:
    raise SystemExit(f"Missing dependency: {exc}. Install: python3 -m pip install pygame moderngl numpy pillow") from exc

ROOT = Path(__file__).resolve().parent
W, H = 1120, 630
SEED = 1944
SEGMENT = 1.0
CHUNK_LEN = 80.0
WALL_HALF_WIDTH = 1.22
FAR = 260.0

MOVES = [
    ('STÅR STILLA', 0.0, 1.55, 0.0),
    ('KNÄSTÅENDE', 0.0, 1.00, 0.0),
    ('LIGGANDE', 0.0, 0.43, 0.0),
    ('KRYPER', 0.30, 0.46, 0.48),
    ('GÅR PÅ HUK', 0.68, 1.04, 0.48),
    ('GÅR', 1.15, 1.55, 0.66),
    ('SNABBGÅR', 1.65, 1.55, 0.74),
    ('JOGGAR', 2.30, 1.53, 0.88),
    ('SPRINGER', 3.35, 1.50, 1.08),
]

VERT = '''#version 330
in vec3 in_pos;
in vec3 in_normal;
in vec2 in_uv;
in float in_layer;
uniform mat4 mvp;
out vec3 v_normal;
out vec2 v_uv;
flat out int v_layer;
out float v_distance;
out vec3 v_world;
uniform vec3 camera_position;
void main(){
    gl_Position=mvp*vec4(in_pos,1.0);
    v_world=in_pos;
    v_normal=in_normal;
    v_uv=in_uv;
    v_layer=int(in_layer+0.5);
    v_distance=length(in_pos-camera_position);
}
'''
FRAG = '''#version 330
in vec3 v_normal;
in vec2 v_uv;
flat in int v_layer;
in float v_distance;
in vec3 v_world;
uniform sampler2DArray materials;
out vec4 f_color;
void main(){
    vec3 n=normalize(v_normal);
    vec3 sun=normalize(vec3(-0.4,0.9,0.45));
    float diffuse=max(dot(n,sun),0.0);
    float brightness=0.58+0.46*diffuse;
    // Subtle animated light from lamps, approximate until shadow-map pass.
    float lantern=pow(max(0.0, sin(v_world.z*0.09+2.0)),12.0);
    brightness += 0.09*lantern*max(0.0, 1.0-v_distance/15.0);
    vec3 col=texture(materials,vec3(v_uv,float(v_layer))).rgb*brightness;
    col=pow(col,vec3(.93));
    if (v_layer==11) col=vec3(1.0,.54,.16)*1.9; // lantern flame emission
    if (v_layer==12) col=mix(col,vec3(.10,.07,.045),.4); // wet pools
    float fog=1.0-exp(-pow(v_distance/170.0,2.0));
    col=mix(col,vec3(.57,.51,.47),clamp(fog,0.,.87));
    f_color=vec4(col,1.0);
}
'''
SKYVERT = '''#version 330
in vec2 xy;
out vec2 uv;
void main(){uv=xy*.5+.5;gl_Position=vec4(xy,0.9999,1.0);}
'''
SKYFRAG = '''#version 330
in vec2 uv;
out vec4 f_color;
uniform float horizon;
void main(){
 float y=uv.y;
 vec3 top=vec3(.17,.23,.29);
 vec3 low=vec3(.61,.49,.43);
 vec3 col=mix(low,top,smoothstep(.14,.95,y));
 float sun=1.-smoothstep(.027,.033,length((uv-vec2(.73,.51))*vec2(1.75,1.0)));
 col=mix(col,vec3(.94,.62,.38),sun*.85);
 // Earth-coloured backstop below the visual horizon: hides sky-blue bleed
 // through tiny cracks. This is a visual fallback, NOT a geometry repair.
 vec3 soil=vec3(.095,.073,.055);
 float soil_mask=1.0-smoothstep(.39,.48,y);
 col=mix(col,soil,soil_mask);
 f_color=vec4(col,1.);
}
'''

def smooth(a, b, t):
    return a + (b-a)*t

# Seeded route in actual X/Z world space. Route distance is arc length, not world Z.
def noise(i, salt=0):
    v=math.sin((i+SEED*.31+salt*17.71)*127.1)*43758.5453
    return v-math.floor(v)


def eased(t):
    t=max(0.,min(1.,t))
    return t*t*(3-2*t)


def turn_for_meter(s):
    # A curve/corner is spread over metres, preventing a heading jump.
    block=int((s-20)//55)
    if block<0:return 0.0
    start=20+55*block
    magnitude=(.38+noise(block,2)*.44) * (-1 if noise(block,3)<.5 else 1)
    if block%4==2: magnitude*=1.85  # occasional broad right-angle corner
    duration=13.0 if block%4==2 else 24.0
    return magnitude*(eased((s-start)/duration)-eased((s-start-1)/duration))


# Cache integer-metre centreline positions. Each step rotates smoothly.
_ROUTE=[(0.,0.,0.)]  # x,z,heading

def route(s):
    s=max(0.,float(s));i=int(s)
    while len(_ROUTE)<=i+1:
        j=len(_ROUTE)
        x,z,h=_ROUTE[-1]
        h+=turn_for_meter(j-.5)
        _ROUTE.append((x+math.sin(h),z+math.cos(h),h))
    x,z,h=_ROUTE[i]
    x2,z2,h2=_ROUTE[i+1]
    f=s-i
    return (x+(x2-x)*f,z+(z2-z)*f,h+(h2-h)*f)


def wall_height(s, side):
    """Terrain surface relative to trench floor, deterministic in route metres.

    Large, slow changes make noticeably shallow and deep trenches, with smaller
    irregularities on top. Left and right share the large-scale profile so the
    trench doesn't look like a sawtooth or open on only one side.
    """
    shared = (0.79 * math.sin(.032 * s + .55)
              + 0.43 * math.sin(.071 * s - .95)
              + 0.18 * math.sin(.145 * s + .8))
    bank = 0.16 * math.sin(.064 * s + side * 1.2)
    return max(1.0, min(3.0, 2.0 + shared + bank))


def sides(s,offset):
    x,z,h=route(s)
    return (x+math.cos(h)*offset,z-math.sin(h)*offset)


def world(s,offset,y):
    x,z=sides(s,offset)
    return (x,y,z)


def junction(s):
    # A branch roughly every 130 m; branches are NOT part of the travelled path yet.
    nearest=round((s-96.)/130.)
    if nearest<0:return None
    marker=96.+130.*nearest
    if abs(s-marker)>=2.0:return None
    return (marker,1 if noise(nearest,23)>.5 else -1)


class MeshBuilder:
    def __init__(self):self.vertices=[]
    def quad(self,a,b,c,d,layer,uv):
        for p,q,r,st in ((a,b,c,(uv[0],uv[1],uv[2])),(a,c,d,(uv[0],uv[2],uv[3]))):
            normal=vec_normal(p,q,r)
            for pos,tc in zip((p,q,r),st):self.vertices.extend((*pos,*normal,*tc,float(layer)))
    def as_array(self):return np.asarray(self.vertices,dtype='f4').reshape(-1,9)


def vec_normal(a,b,c):
    v=np.cross(np.array(b)-a,np.array(c)-a)
    d=np.linalg.norm(v)
    return v/d if d>.00001 else np.array([0.,1.,0.])


def wall_width(s,side):
    return WALL_HALF_WIDTH+ .055*math.sin(s*.52+side)+.026*math.sin(s*1.87+side*.9)


def hill_y(s,side,offset):
    # Real heightfield outside both trench edges, defined in world-space.
    d=max(0,abs(offset)-WALL_HALF_WIDTH)
    base = wall_height(s, side) - .055
    # Start exactly at the lip of the excavation; roll gently into broad hills.
    roll = 1.0 - math.exp(-d / 8.0)
    return (base + roll * (
        0.22 * math.sin(s * .046 + side * .8 + offset * .085)
        + 0.32 * math.sin(offset * .073 + s * .028)
        + 0.12 * math.sin(s * .12 + offset * .17)))


# --- V1.5 deterministic outdoor scenery, no separate game engine ---

def world_on_ground(s, offset, lift=0.0):
    side = -1 if offset < 0 else 1
    return world(s, offset, hill_y(s, side, offset) + lift)


def bar(mesh, p, q, radius, material, facets=5, repeat=.28):
    """World-space low-poly cylinder between points (trunks, branches, wire)."""
    import numpy as _np
    a=_np.array(p,dtype=float); b=_np.array(q,dtype=float)
    axis=b-a; length=float(_np.linalg.norm(axis))
    if length<.0001: return
    direction=axis/length
    helper=_np.array((0.,1.,0.)) if abs(direction[1])<.87 else _np.array((1.,0.,0.))
    u=_np.cross(direction,helper); u/=max(1e-9,_np.linalg.norm(u))
    v=_np.cross(direction,u)
    for j in range(facets):
        an=2*math.pi*j/facets;bn=2*math.pi*(j+1)/facets
        c=a+radius*(math.cos(an)*u+math.sin(an)*v)
        d=a+radius*(math.cos(bn)*u+math.sin(bn)*v)
        e=b+radius*(math.cos(bn)*u+math.sin(bn)*v)
        f=b+radius*(math.cos(an)*u+math.sin(an)*v)
        mesh.quad(c,d,e,f,material,((j/facets,0),((j+1)/facets,0),((j+1)/facets,length/repeat),(j/facets,length/repeat)))


def blob(mesh, center, radii, layer, segments=7, rows=3, phase=0.0):
    """Convex low-poly irregular ellipsoid. No translucent billboard artifacts."""
    cx,cy,cz=center; rx,ry,rz=radii
    def pt(theta,phi):
        ripple=1+.12*math.sin(phi*5+phase)*math.sin(theta*3+phase)
        return (cx+rx*ripple*math.sin(theta)*math.cos(phi),
                cy+ry*ripple*math.cos(theta),
                cz+rz*ripple*math.sin(theta)*math.sin(phi))
    for iy in range(rows):
        th0=math.pi*iy/rows;th1=math.pi*(iy+1)/rows
        for j in range(segments):
            f0=2*math.pi*j/segments;f1=2*math.pi*(j+1)/segments
            mesh.quad(pt(th0,f0),pt(th1,f0),pt(th1,f1),pt(th0,f1),layer,
                      ((j/segments,iy/rows),(j/segments,(iy+1)/rows),
                       ((j+1)/segments,(iy+1)/rows),((j+1)/segments,iy/rows)))


def scenery_chunk(mesh, start):
    """Trees, snapped trunks, shrubs, stones and broken wire outside the trench.

    Positions depend only on global world distance + SEED, NOT on chunk loads.
    Places deliberately avoid openings around T junctions.
    """
    rng = random.Random(SEED*1123 + int(start/CHUNK_LEN)*191)
    # Layout is an outdoor strip, excluding the path and its mouth openings.
    for s_index in range(int(start)+2,int(start+CHUNK_LEN)-2,4):
        s=float(s_index)+rng.uniform(-.5,.5)
        if abs((s-96+65)%130-65)<10:continue
        for side in (-1,1):
            if rng.random()>.65: continue
            dist=rng.uniform(3.5,22.0)
            off=side*dist
            ground=world_on_ground(s,off)
            choice=rng.random()
            scale=rng.uniform(.7,1.35)
            if choice<.28:  # whole tree: textured bark + irregular leafy crown
                height=rng.uniform(4.5,8.5)*scale
                top=(ground[0],ground[1]+height,ground[2])
                bar(mesh,ground,top,.13*scale,5,7,1.0)
                for k in range(2):
                    yy=ground[1]+height*(.45+.16*k)
                    ang=rng.uniform(-math.pi,math.pi)
                    branch_end=(ground[0]+math.cos(ang)*1.35*scale, yy+.65*scale,
                                ground[2]+math.sin(ang)*1.35*scale)
                    bar(mesh,(ground[0],yy,ground[2]),branch_end,.06*scale,5,5,.65)
                blob(mesh,(top[0],top[1]-.55*scale,top[2]),
                     (1.35*scale,1.7*scale,1.35*scale),6,8,4,rng.random()*7)
                # detached clumps add asymmetry
                for k in range(2):
                    ang=rng.uniform(-math.pi,math.pi)
                    d=rng.uniform(.5,1.3)*scale
                    blob(mesh,(top[0]+math.cos(ang)*d,top[1]-1.0*scale,
                               top[2]+math.sin(ang)*d),(.75*scale,.83*scale,.8*scale),6,7,3,rng.random()*7)
            elif choice<.51: # snapped and splintered trunk
                height=rng.uniform(1.7,4.8)*scale
                top=(ground[0]+rng.uniform(-.27,.27),ground[1]+height,ground[2]+rng.uniform(-.27,.27))
                bar(mesh,ground,top,.16*scale,5,7,.8)
                for k in range(2):
                    t=.55+.18*k; ay=ground[1]+height*t
                    end=(ground[0]+rng.uniform(-1.4,1.4)*scale,ay+rng.uniform(.1,.6),
                         ground[2]+rng.uniform(-1.4,1.4)*scale)
                    bar(mesh,(ground[0],ay,ground[2]),end,.06*scale,5,5,.6)
                # broken top gets a smaller angled splinter
                bar(mesh,top,(top[0]+.22*scale,top[1]+.3*scale,top[2]-.16*scale),.06*scale,5,4,.5)
            elif choice<.72: # bush, different size + number of clumps
                for k in range(rng.randint(2,4)):
                    ang=rng.uniform(-math.pi,math.pi)
                    rr=rng.uniform(.05,.6)*scale
                    blob(mesh,(ground[0]+math.cos(ang)*rr,ground[1]+.45*scale,ground[2]+math.sin(ang)*rr),
                         (.64*scale,.58*scale,.72*scale),6,7,3,rng.random()*5)
            else: # surface stone / small boulder: visible ground contact
                rad=rng.uniform(.23,.87)*scale
                blob(mesh,(ground[0],ground[1]+rad*.38,ground[2]),
                     (rad,rad*.68,rad*rng.uniform(.7,1.35)),7,7,3,rng.random()*5)
    # Old field wire — twisted wire between irregular short stakes, safely
    # *outside* the trench. Repeated every ~28 m, not a continuous wall.
    for base in range(int(start//28)*28,int((start+CHUNK_LEN)//28)*28+1,28):
        if not start<=base<start+CHUNK_LEN-7:continue
        if abs((base-96+65)%130-65)<12:continue
        side=-1 if noise(base,77)<.5 else 1
        offs=side*(rng.uniform(3.8,6.0))
        posts=[]
        for j in range(3):
            ss=base+j*3
            p=world_on_ground(ss,offs)
            top=(p[0]+rng.uniform(-.12,.12),p[1]+1.15+rng.uniform(-.2,.2),p[2]+rng.uniform(-.12,.12))
            bar(mesh,p,top,.045,5,5,.5)
            posts.append((p,top))
        for i in range(2):
            for level in (.47,.82):
                a,b=posts[i],posts[i+1]
                q1=tuple(a[0][k]*(1-level)+a[1][k]*level for k in range(3))
                q2=tuple(b[0][k]*(1-level)+b[1][k]*level for k in range(3))
                bar(mesh,q1,q2,.011,7,4,.6)
                # Barbs are short, readable silhouettes at close distance.
                for j in range(1,5):
                    t=j/5
                    middle=tuple(q1[k]*(1-t)+q2[k]*t for k in range(3))
                    end=(middle[0]+.1, middle[1]+.075,middle[2]-.065)
                    bar(mesh,middle,end,.013,7,3,.25)


# --- V1.7 scenic construction, determined by route metres rather than frames ---
# Themes are deliberately long stretches so the world reads as places, not random props.
SCENES = ('fortified', 'exposed', 'ruined', 'marsh', 'forest', 'rocky')
def scene_at(s):
    idx=max(0,int(s//145))
    # staggered but deterministic world zones
    return SCENES[(idx*5 + idx//3)%len(SCENES)]


def box(mesh, center, dims, material, uv_scale=1.0):
    """Axis-aligned 3-D model prototype; real GLB props can replace later."""
    x,y,z=center;dx,dy,dz=(v*.5 for v in dims)
    p=[(x-dx,y-dy,z-dz),(x+dx,y-dy,z-dz),(x+dx,y+dy,z-dz),(x-dx,y+dy,z-dz),
       (x-dx,y-dy,z+dz),(x+dx,y-dy,z+dz),(x+dx,y+dy,z+dz),(x-dx,y+dy,z+dz)]
    t=((0,0),(uv_scale,0),(uv_scale,uv_scale),(0,uv_scale))
    for a,b,c,d in ((0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(3,7,6,2),(0,1,5,4)):
        mesh.quad(p[a],p[b],p[c],p[d],material,t)


def local_box(mesh, s, lateral, y, length, width, height, material):
    """Rectangular object aligned to route tangent, with world-stable UV."""
    def pt(ds,dl,h): return world(s+ds,lateral+dl,y+h)
    a=length*.5;b=width*.5;h=height
    # quad on each side; prevents flat timber silhouettes
    p=[pt(-a,-b,0),pt(a,-b,0),pt(a,b,0),pt(-a,b,0),
       pt(-a,-b,h),pt(a,-b,h),pt(a,b,h),pt(-a,b,h)]
    uv=((0,0),(length,0),(length,width),(0,width))
    for ia,ib,ic,id in ((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)):
        mesh.quad(p[ia],p[ib],p[ic],p[id],material,uv)


def beam_world(mesh, a, b, thickness=.10, material=8):
    bar(mesh,a,b,thickness,material,facets=7,repeat=.7)


def environment_chunk(mesh,start):
    """Rugged trench life: timber revetment, duckboards, sandbags, puddles,
    crates, lanterns, signs. All positioned in true world coordinates."""
    rng=random.Random(SEED*5501+round(start/CHUNK_LEN)*7919)
    # Alternate reinforced and bare earth segments. No objects across side
    # branches or on the soldier's walking centreline except flat duckboards.
    for k in range(int(start)+1,int(start+CHUNK_LEN)-1):
        s=float(k)
        theme=scene_at(s)
        near_junction=any(abs(s-(96+130*j))<5 for j in range(max(0,int(s/130)-1),int(s/130)+2))
        if near_junction: continue
        if theme in ('fortified','ruined','marsh','forest') and k%2==0:
            # duckboards differ in length/rotation slightly, sit flush with mud
            width=1.83+rng.uniform(-.16,.13)
            local_box(mesh,s,0,-.040,.79,width,.055,8)
        if theme in ('marsh','ruined') and k%5==2:
            # dark reflective-looking wet mud patches, slightly above the floor
            local_box(mesh,s,rng.uniform(-.42,.42),-.029,rng.uniform(.7,1.65),
                      rng.uniform(.42,.98),.012,12)
        if theme in ('fortified','ruined','forest') and k%3==0:
            for side in (-1,1):
                w=wall_width(s,side)
                h=wall_height(s,side)
                # supports only on semi-reinforced sections; posts perpendicular to floor
                if rng.random()<(.9 if theme=='fortified' else .58):
                    b=world(s,side*(w-.08),-.025)
                    t=world(s,side*(w-.08),min(h-.13,2.1))
                    beam_world(mesh,b,t,.082 if theme!='ruined' else .072)
        if theme in ('fortified','ruined') and k%7==0:
            for side in (-1,1):
                h=wall_height(s,side)
                # Horizontal wall boarding actually travels ALONG route tangent
                for yfactor in (.32,.63):
                    beam_world(mesh,world(s-1.8,side*(WALL_HALF_WIDTH-.11),min(h*.9,h*yfactor)),
                               world(s+1.8,side*(WALL_HALF_WIDTH-.11),min(h*.9,h*yfactor)),.065)
        if theme in ('fortified','ruined') and k%23==11:
            side=1 if rng.random()<.5 else -1
            w=wall_width(s,side)
            local_box(mesh,s,side*(w-.28),-.035,.8,.42,.58,9) # crate, side-mounted
        if theme in ('fortified','ruined') and k%19==9:
            side=1 if rng.random()<.5 else -1
            h=wall_height(s,side)
            # sandbag mound on the wall's lip, not in player path
            for r in range(2):
                for q in range(3):
                    base=world(s+(q-1)*.47,side*(wall_width(s,side)+.16),h+.11+r*.20)
                    blob(mesh,base,(.37,.16,.26),9,10,4,rng.random()*10)
        if theme=='fortified' and k%37==16:
            side=-1 if rng.random()<.5 else 1
            w=wall_width(s,side)
            h=min(1.8,wall_height(s,side)-.1)
            # lantern on an actual metal bracket, with emissive inner bulb
            foot=world(s,side*(w-.08),h)
            edge=world(s,side*(w-.42),h+.08)
            beam_world(mesh,foot,edge,.025,10)
            base=world(s,side*(w-.44),h-.20)
            box(mesh,base,(.18,.32,.17),10)
            flame=world(s,side*(w-.45),h-.18)
            blob(mesh,flame,(.07,.095,.066),11,9,4)
    # Behind the trench: an intentionally subdued battlefield skyline.
    # Visible only above the wall, built out of dark silhouettes.
    for i in range(6):
        s=start+6+i*12
        theme=scene_at(s)
        if theme not in ('ruined','fortified'): continue
        side=-1 if rng.random()<.5 else 1
        d=rng.uniform(11,29)
        point=world_on_ground(s,side*d)
        if i%2==0:
            local_box(mesh,s,side*d,point[1],rng.uniform(1.5,3.0),1.4,rng.uniform(2,4.2),10)


def make_chunk(start):
    mesh=MeshBuilder()
    stride=SEGMENT
    for i in range(int(CHUNK_LEN/stride)):
        s0=start+i*stride;s1=s0+stride
        floor_half=WALL_HALF_WIDTH+.15
        mesh.quad(world(s0,-floor_half,-.045),world(s0,floor_half,-.045),
                  world(s1,floor_half,-.045),world(s1,-floor_half,-.045),4,
                  ((-floor_half,s0*.84),(floor_half,s0*.84),
                   (floor_half,s1*.84),(-floor_half,s1*.84)))
        for side in (-1,1):
            w0,w1=wall_width(s0,side),wall_width(s1,side)
            h0,h1=wall_height(s0,side),wall_height(s1,side)
            # Open the side wall where an actual T junction branches off.
            crossing=junction((s0+s1)*.5)
            cut=crossing is not None and crossing[1]==side
            def layers(s,h):
                return [0.,h*(.23+.025*math.sin(s*.048+side)),
                        h*(.58+.022*math.sin(s*.059-2*side)),
                        h*(.83+.018*math.sin(s*.041+side)),h]
            a,b=layers(s0,h0),layers(s1,h1)
            if not cut:
                for band,mat in enumerate((0,1,2,3)):
                    mesh.quad(world(s0,side*w0,a[band]),world(s0,side*w0,a[band+1]),
                              world(s1,side*w1,b[band+1]),world(s1,side*w1,b[band]),mat,
                              ((s0*1.12,a[band]),(s0*1.12,a[band+1]),
                               (s1*1.12,b[band+1]),(s1*1.12,b[band])))
            # Ground is a genuine continuous mesh tied to the lip. At a
            # junction, remove ALL terrain spanning the excavated branch,
            # not just the first ring (that produced the see-through strips).
            offsets0=[w0-.035,3.5,7.0,12.0,18.0,32.0,60.0]
            offsets1=[w1-.035,3.5,7.0,12.0,18.0,32.0,60.0]
            for k in range(len(offsets0)-1):
                oa,ob=offsets0[k:k+2];oc,od=offsets1[k:k+2]
                if cut and min(oa,oc)<12.0:
                    continue
                y0=h0-.055 if k==0 else hill_y(s0,side,side*oa)
                y1=h1-.055 if k==0 else hill_y(s1,side,side*oc)
                y2=hill_y(s0,side,side*ob)
                y3=hill_y(s1,side,side*od)
                mesh.quad(world(s0,side*oa,y0),world(s0,side*ob,y2),
                          world(s1,side*od,y3),world(s1,side*oc,y1),3,
                          ((s0*.18,oa*.22),(s0*.18,ob*.22),
                           (s1*.18,od*.22),(s1*.18,oc*.22)))
        # Fixed-position, subtle crossing timbers for visible forward movement.
        if int(s0)%8==0:
            lo,hi=world(s0,-1.09,.005),world(s0,1.09,.005)
            lo2,hi2=world(s0+.16,-1.09,.005),world(s0+.16,1.09,.005)
            mesh.quad(lo,hi,hi2,lo2,2,((0,0),(2.1,0),(2.1,.18),(0,.18)))
    # Excavated T-junction side branches. Their mouths precisely match the
    # four-metre wall gap (route marker +/- 2m). The branch floor is below the
    # main floor, the upper landscape is cut out above it, and there is a real
    # end wall: no unfinished geometry / distant slit to show the clear color.
    for marker in range(96, int(start+CHUNK_LEN)+1, 130):
        if not start <= marker < start+CHUNK_LEN:
            continue
        branch_side=1 if noise((marker-96)//130,23)>.5 else -1
        x,z,h=route(marker)
        right=(math.cos(h),-math.sin(h))
        forward=(math.sin(h),math.cos(h))
        sideheight=max(1.25, wall_height(marker, branch_side))
        mouth_width=2.0  # same half width as wall cut
        outer=12.0
        near_edge=WALL_HALF_WIDTH-0.13  # overlay by ~13 cm with main floor
        def bp(along, across, height):
            dist=near_edge+along
            return (x+branch_side*right[0]*dist+forward[0]*across,height,
                    z+branch_side*right[1]*dist+forward[1]*across)
        for n in range(12):
            a=float(n);b=a+1.0
            mesh.quad(bp(a,-mouth_width,-.048),bp(a,mouth_width,-.048),
                      bp(b,mouth_width,-.048),bp(b,-mouth_width,-.048),4,
                      ((a*.8,-mouth_width),(a*.8,mouth_width),
                       (b*.8,mouth_width),(b*.8,-mouth_width)))
            # Start side walls where the main trench lip ends. These mesh
            # walls also close the exposed faces at the two mouth corners.
            for flank in (-1,1):
                ytop=sideheight + .08*math.sin(a*.33+flank)
                ytop2=sideheight + .08*math.sin(b*.33+flank)
                mesh.quad(bp(a,flank*mouth_width,-.04),
                          bp(a,flank*mouth_width,ytop),
                          bp(b,flank*mouth_width,ytop2),
                          bp(b,flank*mouth_width,-.04),1,
                          ((a,-.04),(a,ytop),(b,ytop2),(b,-.04)))
        # Fully cap the side passage rather than leave an open sky-colored slit.
        mesh.quad(bp(outer,-mouth_width,-.04),
                  bp(outer,-mouth_width,sideheight),
                  bp(outer,mouth_width,sideheight),
                  bp(outer,mouth_width,-.04),1,
                  ((-mouth_width,-.04),(-mouth_width,sideheight),
                   (mouth_width,sideheight),(mouth_width,-.04)))
    scenery_chunk(mesh,start)
    environment_chunk(mesh,start)
    return mesh.as_array()


def perspective(fov,aspect,near,far):
    f=1/math.tan(math.radians(fov)/2)
    return np.array([[f/aspect,0,0,0],[0,f,0,0],[0,0,-(far+near)/(far-near),-2*far*near/(far-near)],[0,0,-1,0]],dtype='f4')

def view_from(position,target):
    # OpenGL right-handed: view looks along negative Z.
    eye=np.asarray(position,dtype='f4'); focus=np.asarray(target,dtype='f4')
    f=focus-eye; f/=np.linalg.norm(f)
    up=np.array([0,1,0],dtype='f4')
    s=np.cross(f,up);s/=np.linalg.norm(s)
    u=np.cross(s,f)
    result=np.eye(4,dtype='f4');result[0,:3]=s;result[1,:3]=u;result[2,:3]=-f
    result[:3,3]= -result[:3,:3]@eye
    return result

class Trench:
    def __init__(self):
        pygame.init()
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION,3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION,3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE,24)
        pygame.display.set_mode((W,H),pygame.OPENGL|pygame.DOUBLEBUF|pygame.RESIZABLE)
        pygame.display.set_caption('Oändlig skyttegrav — riktig 3D / ModernGL')
        self.ctx=moderngl.create_context(require=330)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.prog=self.ctx.program(vertex_shader=VERT,fragment_shader=FRAG)
        self.sky_prog=self.ctx.program(vertex_shader=SKYVERT,fragment_shader=SKYFRAG)
        self.sky_buffer=self.ctx.buffer(np.array([-1,-1,3,-1,-1,3],dtype='f4').tobytes())
        self.sky_vao=self.ctx.vertex_array(self.sky_prog,[(self.sky_buffer,'2f','xy')])
        self.texture=self.load_textures()
        self.prog['materials']=0
        self.chunks={}
        self.distance=0.;self.speed=0.;self.mode=5;self.auto=True
        self.auto_timer=0.;self.step_distance=0.;self.look=0.;self.height=1.55
        self.elapsed=0.;self.paused=False;self.fps=0.;self.ui_timer=0.
        self.last=time.monotonic();self.running=True
        self.frame_size=(W,H)
    def load_textures(self):
        names=['clay.png','gravel.png','loam.png','humus.png','mud.png','bark.png','foliage.png','stone.png','timber.png','canvas.png','metal.png','flame.png','wet.png']
        frames=[]
        for name in names:
            with Image.open(ROOT/'assets'/name) as im:
                frames.append(im.convert('RGB').transpose(Image.FLIP_TOP_BOTTOM).tobytes())
        tex=self.ctx.texture_array((512,512,len(frames)),3,data=b''.join(frames))
        tex.repeat_x=True;tex.repeat_y=True
        tex.build_mipmaps()
        tex.filter=(moderngl.LINEAR_MIPMAP_LINEAR,moderngl.LINEAR)
        try:tex.anisotropy=8.0
        except Exception:pass
        return tex
    def chunk(self,index):
        data=make_chunk(index*CHUNK_LEN)
        vbo=self.ctx.buffer(data.tobytes())
        vao=self.ctx.vertex_array(self.prog,[(vbo,'3f 3f 2f 1f','in_pos','in_normal','in_uv','in_layer')])
        return (vbo,vao,len(data))
    def keep_chunks(self):
        current=math.floor(self.distance/CHUNK_LEN)
        wanted=set(range(max(0,current-1),current+4))
        for i in list(self.chunks):
            if i not in wanted:
                vbo,vao,_=self.chunks.pop(i);vao.release();vbo.release()
        for i in sorted(wanted):
            if i not in self.chunks:self.chunks[i]=self.chunk(i)
    def handle(self):
        for event in pygame.event.get():
            if event.type==pygame.QUIT:self.running=False
            if event.type==pygame.VIDEORESIZE:
                self.frame_size=(max(400,event.w),max(260,event.h))
            if event.type!=pygame.KEYDOWN:continue
            if event.key==pygame.K_ESCAPE:self.running=False
            elif event.key in (pygame.K_SPACE,pygame.K_p):self.paused=not self.paused
            elif event.key==pygame.K_r:self.distance=0;self.elapsed=0;self.step_distance=0;self.speed=0
            elif event.key==pygame.K_0:self.auto=True
            elif pygame.K_1<=event.key<=pygame.K_9:
                self.auto=False;self.mode=event.key-pygame.K_1
    def update(self,dt):
        if self.paused:return
        self.elapsed+=dt
        keys=pygame.key.get_pressed()
        self.look+=(float(keys[pygame.K_d])-float(keys[pygame.K_a]))*dt*.75
        self.look*=math.exp(-1.7*dt)
        if self.auto:
            # Gait selection driven primarily by the next corner, interleaved with
            # demonstration poses, rather than fixed loops at full speed.
            upcoming=abs(route(self.distance+13)[2]-route(self.distance)[2])
            at_junction=any(abs(self.distance-(96+130*i))<5 for i in range(max(0,int(self.distance/130)-1),int(self.distance/130)+3))
            if at_junction:self.mode=4
            elif upcoming>.27:self.mode=5
            elif upcoming>.10:self.mode=6
            else:self.mode=8 if (int(self.distance//95)%3==1) else 7
            stage=self.elapsed%92
            if 37<stage<40:self.mode=0
            elif 40<=stage<43:self.mode=1
            elif 43<=stage<46:self.mode=2
            elif 46<=stage<54:self.mode=3
            elif 54<=stage<60:self.mode=4
        name,target,height,stride=MOVES[self.mode]
        self.speed=smooth(self.speed,target,1-math.exp(-dt*(1.25 if target>self.speed else 2.6)))
        advanced=self.speed*dt
        self.distance+=advanced;self.step_distance+=advanced
        self.height=smooth(self.height,height,1-math.exp(-dt*3.2))

    def camera(self):
        x,z,heading=route(self.distance)
        stride=MOVES[self.mode][3]
        moving=min(1.,self.speed/.65)
        amp=(.006 if self.speed<.01 else .009 if self.speed<1.8 else .018)*moving
        bob=amp*math.cos(2*math.pi*self.step_distance/max(.45,stride)) if stride and moving else 0
        # Breathing continues in still positions, slowed after recovery.
        breath=(.0036+.002*min(1.,self.speed/3))*math.sin(self.elapsed*1.55)
        lateral=.006*moving*math.sin(math.pi*self.step_distance/max(.45,stride)) if stride else 0
        x+=math.cos(heading)*lateral;z-=math.sin(heading)*lateral
        eye=(x,self.height+bob+breath,z)
        heading=route(self.distance+3.6)[2]+self.look
        aim=(x+math.sin(heading)*12,self.height-.085,z+math.cos(heading)*12)
        return eye,aim

    def draw(self):
        ww,hh=pygame.display.get_surface().get_size()
        self.ctx.viewport=(0,0,ww,hh)
        self.ctx.clear(.18,.23,.29,1.0,depth=1.0)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.sky_vao.render(moderngl.TRIANGLES)
        self.ctx.enable(moderngl.DEPTH_TEST)
        eye,aim=self.camera()
        mat=perspective(74,ww/hh,.045,FAR) @ view_from(eye,aim)
        self.prog['mvp'].write(mat.T.tobytes())
        self.prog['camera_position'].value=eye
        self.texture.use(location=0)
        for i in sorted(self.chunks):self.chunks[i][1].render()
        pygame.display.flip()
    def run(self):
        try:
            while self.running:
                now=time.monotonic();dt=min(.055,now-self.last);self.last=now
                self.handle();self.update(dt);self.keep_chunks();self.draw()
                fps=1/max(.001,dt);self.fps=.9*self.fps+.1*fps if self.fps else fps
                self.ui_timer+=dt
                if self.ui_timer>.3:
                    self.ui_timer=0
                    name=MOVES[self.mode][0]
                    pygame.display.set_caption(f'3D SKYTTEGRAV V1.7 | {self.distance:06.0f} m | {name} {self.speed:.1f} m/s | {self.fps:.0f} FPS | 0 AUTO · 1–9 TEST · A/D TITTA · SPACE PAUS · R RESET · ESC AVSLUTA')
                pygame.time.wait(1)
        finally:
            for vbo,vao,_ in self.chunks.values():vao.release();vbo.release()
            self.texture.release();self.prog.release();self.sky_prog.release()
            pygame.quit()

if __name__=='__main__':
    try:Trench().run()
    except Exception as error:
        print(f'3D-test could not start: {type(error).__name__}: {error}',file=sys.stderr)
        raise
