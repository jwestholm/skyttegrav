"""Standalone actual-GPU 3D trench proof of concept (Pygame + ModernGL).
No interaction with Skjutbanan's hit detection, settings, menu or rendering.
Run: python3 trench_3d_test.py
"""
from __future__ import annotations

import math
import queue
import threading
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
# Skjutbana defaults to 800x600 (4:3); the calibrated viewport can differ.
# This is a standalone *window default*, not the physical camera calibration.
W, H = 800, 600
CAMERA_VERTICAL_FOV = 80.0  # Camera geometry remains independent of physical shooting distance.
TEXTURE_SIZE = 1024  # Keep GTX 1070 streaming budget; extra detail via world-space blends.
SUN_DIRECTION = (0.35, 0.085, 0.93)  # Stable world-space celestial direction.
MOON_DIRECTION = (-0.38, 0.40, -0.69)
FOG_DENSITY = 1.0  # Atmospheric haze; close-range aiming remains unobstructed.

# Initial lift from desktop/window-manager placement; F9/F10 move in 12px steps.
WINDOW_RAISE_PIXELS = 28
OBSTACLE_SPACING = 13.0  # sparse, legible traversals without cluttering blind corners
SEED = 1944
SEGMENT = 1.0
CHUNK_LEN = 80.0
JUNCTION_FIRST = 64
JUNCTION_SPACING = 72  # For now all branching remains local; no global graph/A* yet.
BRANCH_LENGTH = 12.0  # base length; individual dead ends vary
CORNER_DEPTH = 1.50   # physical depth into branch reached by curved corner traversal
CORNER_MAIN_OFFSET = 1.15  # metres before junction to start continuous bend
COVER_EYE_CLEARANCE = 0.49  # avoid scraping eye against soil bank
BEND_FIRST = 11
BEND_SPACING = 34
# Stream world geometry in the background; only the main thread touches OpenGL.
PREFETCH_AHEAD = 5
RETAIN_BEHIND = 2
UPLOADS_PER_FRAME = 1
WALL_HALF_WIDTH = 1.12
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
uniform sampler2DArray material_normals;
uniform int use_pbr_normals;
uniform int lamp_count;
uniform vec3 lamp_positions[8];
uniform float fog_strength;
out vec4 f_color;

// 20 = excavated earth, 21 = trench floor: shader-only material IDs.
// They deliberately do NOT index the 20-layer texture array.
float terrain_pattern(vec3 p) {
    return 0.31*sin(p.x*1.75+p.z*0.87+0.63*sin(p.y*3.0))
         + 0.28*cos(p.z*2.31-p.y*1.82+p.x*0.49)
         + 0.23*sin(p.x*4.12+p.y*3.17-p.z*2.92)
         + 0.11*cos(p.z*7.08+p.y*5.91);
}
vec3 sample_color(vec2 uv,int layer) {
    return texture(materials,vec3(uv,float(layer))).rgb;
}
void main(){
    vec3 n=normalize(v_normal);
    vec3 col;
    vec2 uv=v_uv;
    if (v_layer == 20) {
        // Organic deposits measured in world space, NEVER 4 flat material bands.
        // Smooth weights remain continuous at every chunk boundary and mesh edge.
        float organic=terrain_pattern(v_world);
        float rock=smoothstep(-.13,.49,organic + .13*sin(v_world.y*1.71+v_world.x*.93));
        float clay=smoothstep(.06,.69,-organic + .17*cos(v_world.z*.71+v_world.y*2.16));
        float humus=smoothstep(.23,.79,terrain_pattern(v_world*.63+vec3(3.2,1.7,0.7)));
        col=mix(sample_color(uv,0),sample_color(uv*.87,1),rock*.68);
        col=mix(col,sample_color(uv*1.17,2),clay*.60);
        col=mix(col,sample_color(uv*.72,3),humus*.25);
    } else if (v_layer == 21) {
        // Real floor variation: damp mud, fine gravel and darker footprint zones.
        float n1=terrain_pattern(v_world*vec3(.64,1.0,.64));
        float n2=terrain_pattern(v_world*vec3(1.74,1.0,1.74)+vec3(6.,0.,2.));
        float pebbles=smoothstep(-.10,.48,n1+n2*.30);
        float wet=smoothstep(.13,.60,-n1+n2*.35);
        col=mix(sample_color(uv,4),sample_color(uv*.84,1),pebbles*.58);
        col=mix(col,sample_color(uv*1.13,12),wet*.41);
    } else {
        col=sample_color(uv,v_layer);
    }
    // Surface-detail normals are used on actual PBR-covered materials, not on
    // procedural IDs (where the albedo is a multi-material blend).
    if (use_pbr_normals == 1 && v_layer >= 0) {
        // Organic wall and floor blends reuse the leading photographed normal.
        int normal_layer = v_layer == 20 ? 0 : (v_layer == 21 ? 4 : v_layer);
        vec3 tangent_norm=texture(material_normals,vec3(uv,float(normal_layer))).xyz*2.0-1.0;
        vec3 dp1=dFdx(v_world),dp2=dFdy(v_world);
        vec2 duv1=dFdx(uv),duv2=dFdy(uv);
        float determinant=duv1.x*duv2.y-duv1.y*duv2.x;
        if (abs(determinant)>0.000001) {
            vec3 t=normalize((dp1*duv2.y-dp2*duv1.y)/determinant);
            t=normalize(t-n*dot(n,t));
            vec3 b=normalize(cross(n,t))*sign(determinant);
            n=normalize(mat3(t,b,n)*vec3(tangent_norm.xy*.72,tangent_norm.z));
        }
    }
    vec3 sun=normalize(vec3(0.35,0.085,0.93));
    vec3 moon=normalize(vec3(-0.38,0.40,-0.69));
    float diffuse=max(dot(n,sun),0.0);
    float moonlight=max(dot(n,moon),0.0);
    // Dusk: muted ambient earth, directional sunlight and cool moon fill.
    float brightness=.37 + .52*diffuse + .10*moonlight;
    col*=brightness;
    for (int i=0; i<8; i++) {
        if(i>=lamp_count) break;
        vec3 delta=lamp_positions[i]-v_world;
        float r2=dot(delta,delta);
        float nearLamp=pow(max(0.0,1.0-r2/42.25),2.0);
        float facing=max(dot(n,normalize(delta)),0.0);
        col+=vec3(.31,.19,.075)*nearLamp*(.23+.77*facing);
    }
    col=pow(max(col,vec3(0.0)),vec3(.96));
    if (v_layer==11) col=vec3(1.0,.54,.16)*1.8;
    if (v_layer==12) col=mix(col,vec3(.10,.07,.045),.4);
    // Mist stays light in the trench and is denser over open ground.
    float groundMist=smoothstep(.9,3.5,v_world.y);
    float smoke=.5+.5*sin(v_world.x*.062+sin(v_world.z*.041)*1.9);
    float distanceBeyond=max(0.0,v_distance-13.0);
    float density=(.0053 + .012*groundMist + .0037*smoke)*fog_strength;
    float fog=1.0-exp(-distanceBeyond*density);
    col=mix(col,vec3(.38,.36,.36),clamp(fog,0.,.70));
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
uniform vec3 sky_right;
uniform vec3 sky_up;
uniform vec3 sky_forward;
uniform vec3 sun_direction;
uniform vec3 moon_direction;
uniform float tan_half_fov;
uniform float view_aspect;
void main(){
    // A true infinitely distant sky: camera TRANSLATION must not affect it.
    // Derive one world-space viewing ray per pixel using camera orientation.
    vec2 ndc = uv*2.0-1.0;
    vec3 ray = normalize(sky_forward
      + sky_right*(ndc.x*tan_half_fov*view_aspect)
      + sky_up*(ndc.y*tan_half_fov));
    vec3 sun=normalize(sun_direction);
    float altitude=ray.y;
    vec3 horizon=vec3(.48,.40,.37);
    vec3 high=vec3(.13,.19,.25);
    float sky_height=smoothstep(-.03,.70,altitude);
    vec3 col=mix(horizon,high,sky_height);
    float sun_angle=acos(clamp(dot(ray,sun),-1.0,1.0));
    float disc=1.0-smoothstep(.017,.024,sun_angle);
    float glow=exp(-sun_angle*sun_angle/0.018);
    col+=vec3(.27,.13,.06)*glow;
    col=mix(col,vec3(.96,.69,.44),disc*.90);
    vec3 moon=normalize(moon_direction);
    float moonAngle=acos(clamp(dot(ray,moon),-1.0,1.0));
    float moonDisc=1.0-smoothstep(.007,.011,moonAngle);
    col=mix(col,vec3(.68,.74,.82),moonDisc*.70);
    // Atmospheric distant clouds/haze stay fixed in WORLD viewing direction.
    float haze=pow(1.0-smoothstep(-.015,.22,altitude),2.0);
    col=mix(col,vec3(.36,.34,.35),.19*haze);
    // Dark earth backstop is only a last-resort mask for tiny geometry gaps.
    // Its boundary also follows world-space horizon, not screen UVs.
    vec3 soil=vec3(.095,.073,.055);
    col=mix(col,soil,1.0-smoothstep(-.085,-.012,altitude));
    f_color=vec4(col,1.0);
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
    """Repeated angular Z/W traverses, separated by calmer stretches.

    Every bend is eased over several metres; exact integral is independent of
    frame rate and chunks. Paired turns prevent endless turning in one direction.
    """
    block=int((s-11)//34)
    if block<0:return 0.0
    start=11+34*block
    pattern=(.87,-1.40,.87,-.82,1.34,-.82)
    magnitude=pattern[block%len(pattern)]*(.82+.27*noise(block,2))
    duration=9.0+noise(block,4)*7.0
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


def junction_marker(index):
    return JUNCTION_FIRST+JUNCTION_SPACING*index


def nearest_junction(s):
    i=round((s-JUNCTION_FIRST)/JUNCTION_SPACING)
    if i<0:return None
    return (junction_marker(i), i)


def junction(s):
    candidate=nearest_junction(s)
    if candidate is None:return None
    marker,i=candidate
    if abs(s-marker)>=2.0:return None
    return (marker,1 if noise(i,23)>.5 else -1)


def junction_side(index):
    # When both sides exist, the SoldierBrain selects one reproducibly.
    return 1 if noise(index,23)>.5 else -1


def junction_kind(index):
    """Local junction topology: one open continuation, T, Y or X.

    'I' sections occur between junctions. This does not imply that side
    branches yet connect into a globally navigable graph.
    """
    return ('T','Y','T','X','T','Y','X','T')[index % 8]


def junction_sides(index):
    return (-1,1) if junction_kind(index)=='X' else (junction_side(index),)


def branch_type(index):
    return 'dugout' if noise(index,1103)<.78 else 'open'


def branch_half_width(index, along):
    # Four-metre excavation at the mouth connects precisely to the wall cut.
    # It narrows over the first 3m to a human-scale passage.
    width=2.0 + (1.12-2.0)*eased(along/3.4)
    # A little widening beneath the bank reads as an excavated dugout
    # rather than a uniform pipe; main entrance and camera clearance stay safe.
    if branch_type(index)=='dugout':
        room_at=7.4 + 1.2*noise(index,1281)
        width+=.28*math.exp(-((along-room_at)/2.15)**2)
    return max(1.06, width + .035*math.sin(along*.8+index)*eased(along/2.0))


def branch_length(index):
    return 9 + int(noise(index,92)*8)  # 9–16m exploratory side tunnels


def branch_center_shift(index, along):
    # Small offset makes side tunnels bent rather than ruler-straight.
    progression=eased((along-3.0)/9.0)
    skew=(.32 if noise(index,1173)>.5 else -.32)*max(0.0,along-3.0) if junction_kind(index)=='Y' else 0.0
    return (noise(index,93)-.5)*2.0*progression + skew


def cover_distance(s, side):
    """Eye position is inset from bank even in the narrowest trench.

    This is a cautious geometric clearance rule, not object collision.
    """
    return max(0., min(.58, wall_width(s, side)-COVER_EYE_CLEARANCE))


def bend_marker(index):
    return BEND_FIRST + BEND_SPACING * index


def bend_direction(index):
    """Turn signed from actual generated main route, not assumed from seed."""
    start=bend_marker(index)
    before=route(max(0.,start-1.0))[2]
    after=route(start+15.0)[2]
    return math.atan2(math.sin(after-before), math.cos(after-before))


def near_junction(s, radius=12.):
    candidate=nearest_junction(s)
    return candidate is not None and abs(s-candidate[0])<radius


class MeshBuilder:
    def __init__(self):self.vertices=[]
    def smooth_quad(self,a,b,c,d,layer,uv,center,radii):
        # Radial normals for curved foliage; original quad retains flat faces
        # needed for trench planks, broken rocks and hard corners.
        cx,cy,cz=center
        rx,ry,rz=radii
        for p,q,r,st in ((a,b,c,(uv[0],uv[1],uv[2])),(a,c,d,(uv[0],uv[2],uv[3]))):
            for pos,tc in zip((p,q,r),st):
                x,y,z=pos
                normal=np.array(((x-cx)/(rx*rx),(y-cy)/(ry*ry),(z-cz)/(rz*rz)),dtype=float)
                norm=np.linalg.norm(normal)
                if norm<1e-5:normal=np.array((0.,1.,0.))
                else:normal/=norm
                self.vertices.extend((*pos,*normal,*tc,float(layer)))
    def quad(self,a,b,c,d,layer,uv):
        for p,q,r,st in ((a,b,c,(uv[0],uv[1],uv[2])),(a,c,d,(uv[0],uv[2],uv[3]))):
            normal=vec_normal(p,q,r)
            for pos,tc in zip((p,q,r),st):self.vertices.extend((*pos,*normal,*tc,float(layer)))
    def as_array(self):return np.asarray(self.vertices,dtype='f4').reshape(-1,9)


def vec_normal(a,b,c):
    v=np.cross(np.array(b)-a,np.array(c)-a)
    d=np.linalg.norm(v)
    return v/d if d>.00001 else np.array([0.,1.,0.])


def landscape_type(s):
    # Long regions with soft transitions. The trench walls reflect local soil.
    return int(max(0.,s)//155.) % 5


def wall_width(s, side):
    """Trench half-width: coherent narrowing/widening, asymmetric banks.

    The variation is slow enough to be walkable and deterministic across chunks.
    Width from ~1.55m to ~2.95m overall, with short irregularities.
    """
    valley = (.25 * math.sin(s*.026 + .6)
              + .15 * math.sin(s*.071 - .9)
              + .09 * math.sin(s*.13 + side*1.8))
    bias = .14 * math.sin(s*.035 + side*.8)
    width = WALL_HALF_WIDTH + valley + bias + .035 * math.sin(s*.83+side)
    return max(.77, min(1.58, width))


def wall_offset(s, side, y, height):
    """Actual soil bank surface, with uneven overhangs, undercuts and bedding.

    All vertices at the same world (s, y) use identical coordinates, so
    neighbouring chunks and material bands stitch without T-shaped seams.
    """
    u=max(0.,min(1.,y/max(.1,height)))
    main=wall_width(s,side)
    # The excavation gets wider near the rim, but not uniformly.
    shape=(.14 * u*u - .065 * math.sin(u*math.pi))
    ripple=(.085*math.sin(s*.75 + u*11.1 + side)
            +.042*math.sin(s*2.06 - u*23.0 + side*2))
    # Gradually decrease texture displacement at the floor and lip: adjacent
    # floor and terrain meshes retain an overlapping watertight transition.
    ripple *= math.sin(math.pi*u)**.7
    return max(.68,main+shape+ripple)


def surface_material(s, side, height_fraction):
    # Rocks at the lower cut, deeper clay and loam above, depending on region.
    biome=landscape_type(s)
    if biome==2: return (1, 0, 1, 2)  # rocky rise
    if biome==3: return (0, 1, 2, 3)  # cultivated open field
    if biome==4: return (1, 0, 2, 3)  # shattered / damp terrain
    if biome==1: return (0, 2, 3, 3)  # woodland humus
    return (1, 0, 2, 3)

def hill_y(s,side,offset):
    # Real heightfield outside both trench edges, defined in world-space.
    d=max(0,abs(offset)-wall_width(s,side))
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


def bar(mesh, p, q, radius, material, facets=10, repeat=.28):
    """Textured irregular cylindrical timber. Caps + tapered rings avoid tubes.

    No GL state or random calls; deterministic from endpoints and seed.
    Costs are bounded to at most two axial spans per prop for chunk streaming.
    """
    a=np.asarray(p,dtype=float);b=np.asarray(q,dtype=float)
    axis=b-a; length=float(np.linalg.norm(axis))
    if length<.0001:return
    direction=axis/length
    helper=np.array((0.,1.,0.)) if abs(direction[1])<.87 else np.array((1.,0.,0.))
    u=np.cross(direction,helper); u/=max(1e-9,float(np.linalg.norm(u)))
    v=np.cross(direction,u)
    facets=max(6,int(facets))
    spans=2 if radius>=.050 and length>.85 else 1
    seed_phase=a[0]*1.77+a[1]*2.49+a[2]*.81+b[2]*.31
    rings=[]
    for k in range(spans+1):
        t=k/spans
        spine=a+axis*t
        # Minute lateral bend creates real wood silhouettes without camera snap.
        if 0<k<spans:spine+=radius*.12*math.sin(seed_phase*3.0)*u
        ring=[]
        for j in range(facets):
            angle=2*math.pi*j/facets
            irregular=1.0+.065*math.sin(seed_phase*2+j*2.57+k*.63)
            taper=1.0-.07*t
            point=spine+radius*irregular*taper*(math.cos(angle)*u+math.sin(angle)*v)
            ring.append(tuple(point))
        rings.append(ring)
    for k in range(spans):
        for j in range(facets):
            nj=(j+1)%facets
            mesh.quad(rings[k][j],rings[k][nj],rings[k+1][nj],rings[k+1][j],material,
                      ((j/facets,k*length/(spans*repeat)),
                       ((j+1)/facets,k*length/(spans*repeat)),
                       ((j+1)/facets,(k+1)*length/(spans*repeat)),
                       (j/facets,(k+1)*length/(spans*repeat))))
    # Chopped ends: no hollow cylinders visible near camera.
    for end_idx,center in ((0,a),(-1,b)):
        for j in range(facets):
            nj=(j+1)%facets
            # A narrow strip across the cap; face has wood grain rather than sky.
            mesh.quad(tuple(center),rings[end_idx][j],rings[end_idx][nj],tuple(center),material,
                      ((.5,.5),(j/facets,0),((j+1)/facets,0),(.5,.5)))


def blob(mesh, center, radii, layer, segments=12, rows=5, phase=0.0):
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
            uvs=((j/segments,iy/rows),(j/segments,(iy+1)/rows),
                 ((j+1)/segments,(iy+1)/rows),((j+1)/segments,iy/rows))
            if layer==6 and hasattr(mesh,'smooth_quad'):
                mesh.smooth_quad(pt(th0,f0),pt(th1,f0),pt(th1,f1),pt(th0,f1),layer,uvs,center,radii)
            else:
                mesh.quad(pt(th0,f0),pt(th1,f0),pt(th1,f1),pt(th0,f1),layer,uvs)


def grass_tuft(mesh, s, lateral, height, seed_index, size=1.0):
    """A few tapered *3D* leaves at the trench lip (no transparency/alpha).

    Strands use crossed vertical leaf triangles so silhouettes look organic.
    Deterministic global spacing avoids chunk seam pops and reloading changes.
    These are decorative, cannot obstruct the soldier or overwrite collision.
    """
    rng=random.Random(SEED*811+seed_index*1777)
    cx,cy,cz=world(s,lateral,height)
    count=rng.randint(8,15)
    for i in range(count):
        ang=2*math.pi*(i+.26*rng.random())/count
        blade_height=(.075+.13*rng.random())*size
        w=(.004+.009*rng.random())*size
        lean=(.022+.07*rng.random())*size
        ax,az=math.cos(ang),math.sin(ang)
        bx,bz=-az,ax
        base=(cx+ax*.028,cy,cz+az*.028)
        p0=(base[0]+bx*w,base[1],base[2]+bz*w)
        p1=(base[0]-bx*w,base[1],base[2]-bz*w)
        tip=(base[0]+ax*lean,cy+blade_height,base[2]+az*lean)
        # One triangle. Culling is disabled; the second degenerate triangle
        # prevents double-sided foliage from becoming opaque rectangles.
        mesh.quad(p0,p1,tip,tip,6,((0.,0.),(.8,0.),(.43,1.),(.43,1.)))


def rim_vegetation_chunk(mesh, start):
    """Mixed sparse clumps, rough stones and leaf litter on either bank rim.

    Only a short world-distance interval is generated for each 80m chunk.
    Fixed global indices make all objects stable on chunk eviction/rebuild.
    """
    first=max(0,math.floor((start-1.3)/2.6)-1)
    last=math.ceil((start+CHUNK_LEN-1.3)/2.6)+1
    for i in range(max(0,first),last+1):
        s=1.3+2.6*i + .32*(noise(i,704)-.5)
        if not start<=s<start+CHUNK_LEN or near_junction(s,4.5):continue
        theme=scene_at(s)
        for side in (-1,1):
            # Some bare stretches preserve the war-torn appearance.
            density=.78 if theme=='forest' else .62 if theme=='marsh' else .25 if theme=='rocky' else .43
            if noise(i,720+side)>density:continue
            off=side*(wall_width(s,side)+.17+.40*noise(i,730+side))
            y=hill_y(s,side,off)
            scale=.65+.80*noise(i,740+side)
            grass_tuft(mesh,s,off,y-.015,i*5+side,scale)
            if noise(i,750+side)>.68:
                p=world(s+.19,off+side*.10,y+.015)
                blob(mesh,p,(.13,.075,.11),17,12,5,i*.67)


def scenery_chunk(mesh, start):
    """Trees, snapped trunks, shrubs, stones and broken wire outside the trench.

    Positions depend only on global world distance + SEED, NOT on chunk loads.
    Places deliberately avoid openings around T junctions.
    """
    rng = random.Random(SEED*1123 + int(start/CHUNK_LEN)*191)
    # Layout is an outdoor strip, excluding the path and its mouth openings.
    for s_index in range(int(start)+2,int(start+CHUNK_LEN)-2,4):
        s=float(s_index)+rng.uniform(-.5,.5)
        if near_junction(s,10):continue
        theme=scene_at(s)
        density={'forest':.91,'rocky':.78,'exposed':.22,'ruined':.65,
                 'marsh':.49,'fortified':.40}[theme]
        for side in (-1,1):
            if rng.random()>density: continue
            dist=rng.uniform(3.5,22.0)
            off=side*dist
            ground=world_on_ground(s,off)
            # Preserve coherent BIOMES instead of equal tree/rock probabilities
            # everywhere. No preloaded world; theme can be recomputed per chunk.
            choice=rng.random()
            if theme=='rocky':choice=.75+choice*.25
            elif theme=='ruined':choice=.29+choice*.25 if choice<.74 else .80+choice*.20
            elif theme=='forest':choice=choice*.70
            elif theme=='exposed':choice=.49+choice*.51
            scale=rng.uniform(.7,1.35)
            if choice<.28:  # whole tree: textured bark + irregular leafy crown
                height=rng.uniform(4.5,8.5)*scale
                top=(ground[0],ground[1]+height,ground[2])
                bar(mesh,ground,top,.13*scale,13 if rng.random()<.58 else 14,12 if dist<12 else 8,1.0)
                for k in range(2):
                    yy=ground[1]+height*(.45+.16*k)
                    ang=rng.uniform(-math.pi,math.pi)
                    branch_end=(ground[0]+math.cos(ang)*1.35*scale, yy+.65*scale,
                                ground[2]+math.sin(ang)*1.35*scale)
                    bar(mesh,(ground[0],yy,ground[2]),branch_end,.06*scale,13 if k else 14,9,.65)
                blob(mesh,(top[0],top[1]-.55*scale,top[2]),
                     (1.15*scale,1.48*scale,1.18*scale),6,20 if dist<12 else 11,8 if dist<12 else 5,rng.random()*7)
                # detached clumps add asymmetry
                for k in range(2):
                    ang=rng.uniform(-math.pi,math.pi)
                    d=rng.uniform(.5,1.3)*scale
                    blob(mesh,(top[0]+math.cos(ang)*d,top[1]-1.0*scale,
                               top[2]+math.sin(ang)*d),(.76*scale,.78*scale,.78*scale),6,16 if dist<12 else 9,7 if dist<12 else 4,rng.random()*7)
            elif choice<.51: # snapped and splintered trunk
                height=rng.uniform(1.7,4.8)*scale
                top=(ground[0]+rng.uniform(-.27,.27),ground[1]+height,ground[2]+rng.uniform(-.27,.27))
                bar(mesh,ground,top,.16*scale,13 if rng.random()<.5 else 14,12 if dist<12 else 8,.8)
                for k in range(2):
                    t=.55+.18*k; ay=ground[1]+height*t
                    end=(ground[0]+rng.uniform(-1.4,1.4)*scale,ay+rng.uniform(.1,.6),
                         ground[2]+rng.uniform(-1.4,1.4)*scale)
                    bar(mesh,(ground[0],ay,ground[2]),end,.06*scale,13,9,.6)
                # broken top gets a smaller angled splinter
                bar(mesh,top,(top[0]+.22*scale,top[1]+.3*scale,top[2]-.16*scale),.06*scale,16,8,.5)
            elif choice<.72: # bush, different size + number of clumps
                for k in range(rng.randint(2,4)):
                    ang=rng.uniform(-math.pi,math.pi)
                    rr=rng.uniform(.05,.6)*scale
                    blob(mesh,(ground[0]+math.cos(ang)*rr,ground[1]+.45*scale,ground[2]+math.sin(ang)*rr),
                         (.64*scale,.58*scale,.72*scale),6,11 if dist<12 else 8,5 if dist<12 else 3,rng.random()*5)
            else: # surface stone / small boulder: visible ground contact
                rad=rng.uniform(.23,.87)*scale
                blob(mesh,(ground[0],ground[1]+rad*.38,ground[2]),
                     (rad,rad*.68,rad*rng.uniform(.7,1.35)),17 if rng.random()<.62 else 7,13 if dist<12 else 9,5 if dist<12 else 4,rng.random()*5)
    # Old field wire — twisted wire between irregular short stakes, safely
    # *outside* the trench. Repeated every ~28 m, not a continuous wall.
    for base in range(int(start//28)*28,int((start+CHUNK_LEN)//28)*28+1,28):
        if not start<=base<start+CHUNK_LEN-7:continue
        if near_junction(base,12):continue
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


@dataclass(frozen=True)
class TrenchObstacle:
    """One seeded world object is shared by rendering and local navigation.

    `detour` is a signed lateral target in route metres. A zero detour means
    a step-over/cosmetic object; never misrepresent such a prop as a hard wall.
    """
    index: int
    s: float
    kind: str
    lateral: float
    length: float
    width: float
    height: float
    detour: float = 0.0


def trench_obstacle(index):
    """Deterministic obstruction with measured walking clearance.

    Skips junctions and actual Z/W turns. Never place an impassable crate in
    a tight excavation; objects are not randomly teleported on chunk reload.
    """
    if index < 0:
        return None
    s = 15.0 + OBSTACLE_SPACING*index + (noise(index,401)-.5)*4.0
    j=nearest_junction(s)
    if j is not None and abs(j[0]-s)<9.0:
        return None
    near=int(round((s-BEND_FIRST)/BEND_SPACING))
    if near >= 0 and abs(bend_marker(near)-s)<8.0:
        return None
    choice=noise(index,402)
    kind=('crate' if choice<.26 else
          'rubble' if choice<.48 else
          'timber' if choice<.69 else
          'sandbags' if choice<.84 else 'puddle')
    lateral=(noise(index,403)-.5)*.17
    if kind in ('crate','rubble'):
        width=.54 if kind=='crate' else .62
        length=.72 if kind=='crate' else .95
        height=.58 if kind=='crate' else .42
        # Eye/camera may follow either side if there is genuine lateral room.
        # Account for changing width a few metres before and after obstacle.
        clearance=.245
        # Use the exact eye-position limits from SoldierBrain. We must not
        # plan a detour the steering controller later clamps into the prop.
        right_limit=min(cover_distance(s+d,1) for d in (-3.,-1.,0.,1.,3.))
        left_limit=min(cover_distance(s+d,-1) for d in (-3.,-1.,0.,1.,3.))
        right=lateral+width*.5+clearance
        left=lateral-width*.5-clearance
        possibilities=[]
        if right<right_limit-.035: possibilities.append((right,right_limit-right))
        if left>-left_limit+.035: possibilities.append((left,left_limit+left))
        if not possibilities: return None
        # Prefer the widest available lane, not necessarily the same side.
        possibilities.sort(key=lambda option:option[1],reverse=True)
        detour=possibilities[0][0]
    else:
        width=min(1.32,2*min(wall_width(s,1),wall_width(s,-1))-.36) if kind=='timber' else (.78 if kind=='sandbags' else .86)
        length=.24 if kind=='timber' else (.70 if kind=='sandbags' else 1.30)
        height=.22 if kind=='timber' else (.29 if kind=='sandbags' else .02)
        detour=0.0
    return TrenchObstacle(index,s,kind,lateral,length,width,height,detour)


def obstacles_in_range(start, end):
    """Stable lookup across GPU chunk boundaries and save/reload cycles."""
    first=max(0,math.floor((start-17.0)/OBSTACLE_SPACING)-1)
    last=max(0,math.ceil((end-13.0)/OBSTACLE_SPACING)+1)
    result=[]
    for i in range(first,last+1):
        ob=trench_obstacle(i)
        if ob is not None and start<=ob.s<=end:
            result.append(ob)
    return result


def obstacle_steering(s):
    """Smooth walk-around path, zero before and after each obstruction."""
    offset=0.0
    for ob in obstacles_in_range(s-4.0,s+4.0):
        if not ob.detour:continue
        d=s-ob.s
        if -3.9<d<-1.0:
            factor=eased((d+3.9)/2.9)
        elif -1.0<=d<=1.0:
            factor=1.0
        elif 1.0<d<3.9:
            factor=1.0-eased((d-1.0)/2.9)
        else:factor=0.
        offset+=ob.detour*factor
    return offset


def wood_crate(mesh,s,lateral,y,length,width,height,weathered=15):
    """Timber-box silhouette with individual planks, structural strips and straps.

    Same bounding footprint as local_box -> existing SoldierBrain steering valid.
    The geometry is decorative; this does NOT introduce unregistered blockers.
    """
    local_box(mesh,s,lateral,y,length,width,height,weathered)
    # Raised slats on visible sides; very thin to keep silhouette legible.
    for k in range(3):
        h=y+.045+(k+.5)*(height-.09)/3.
        for side in (-1,1):
            # Outside side walls, parallel with the corridor.
            local_box(mesh,s,lateral+side*(width*.5+.009),h,length*.96,.014,.024,18)
        for end in (-1,1):
            local_box(mesh,s+end*(length*.5+.008),lateral,h,.015,width*.91,.022,18)
    # Corner braces darker than planking, making cube read as a crate.
    for side in (-1,1):
        for end in (-1,1):
            local_box(mesh,s+end*length*.45,lateral+side*width*.45,y-.01,.040,.038,height+.03,13)
    local_box(mesh,s,lateral,y+height-.025,length*.97,width*.97,.035,16)


def draw_trench_obstacles(mesh,start):
    """Small reusable primitives; higher-quality GLB assets can replace them."""
    for ob in obstacles_in_range(start,start+CHUNK_LEN-0.0001):
        s,c=ob.s,ob.lateral
        rng=random.Random(SEED*89+ob.index*113)
        if ob.kind=='crate':
            wood_crate(mesh,s,c,-.04,ob.length,ob.width,ob.height,15 if rng.random()<.6 else 18)
            # Dark corner straps and raised edge rails make silhouette readable.
            for ds in (-ob.length*.37,ob.length*.37):
                local_box(mesh,s+ds,c,ob.height-.04,.055,ob.width+.025,.045,10)
            for dc in (-ob.width*.37,ob.width*.37):
                local_box(mesh,s,c+dc,ob.height-.04,ob.length,.040,.045,8)
        elif ob.kind=='rubble':
            for j in range(9):
                ds=rng.uniform(-ob.length*.42,ob.length*.42)
                dc=rng.uniform(-ob.width*.22,ob.width*.22)
                r=rng.uniform(.095,.17)
                p=world(s+ds,c+dc,r*.52)
                blob(mesh,p,(r,r*.84,r*.82),17 if j%3 else 1,12,5,j+.3)
            # A broken board poking out of the earth heap.
            beam_world(mesh,world(s-.32,c-.13,.10),world(s+.18,c+.22,.38),.047,8)
        elif ob.kind=='timber':
            p=world(s,c-ob.width*.5,.13)
            q=world(s,c+ob.width*.5,.13)
            beam_world(mesh,p,q,.115,8)
            beam_world(mesh,world(s+.27,c-ob.width*.25,.06),
                       world(s-.26,c+ob.width*.30,.08),.045,8)
        elif ob.kind=='sandbags':
            for row in range(2):
                for j in range(3-row):
                    dc=(j-(2-row)/2)*.29
                    center=world(s+(row-.5)*.15,c+dc,.11+row*.14)
                    blob(mesh,center,(.23,.115,.19),19,13,5,rng.random()*10)
        else:  # shallow water; no collision requirement
            local_box(mesh,s,c,-.035,ob.length,ob.width,.015,12)
    # Decorative, NON-colliding fragments stay close to the dirt wall. Their
    # placement is independent of obstruction decisions / streaming order.
    for index in range(int(start//11)-1,int((start+CHUNK_LEN)//11)+2):
        if index<0:continue
        ss=7.0+11.0*index+(noise(index,715)-.5)*3.0
        if not start <= ss < start+CHUNK_LEN:continue
        if near_junction(ss,5.0):continue
        side=1 if noise(index,716)>.5 else -1
        inset=max(.65,wall_width(ss,side)-.115)
        lateral=side*inset
        r=.10+.065*noise(index,717)
        blob(mesh,world(ss,lateral,.035),(.14,r,.16),17,11,4,index*.17)
        if noise(index,718)>.38:
            a=world(ss-.32,lateral,.065)
            b=world(ss+.48,lateral-side*.045,.082)
            beam_world(mesh,a,b,.039,8)


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
    # Only sizeable logs receive rounded cross-sections. Thin wires stay cheap.
    bar(mesh,a,b,thickness,material,facets=11 if thickness>=.06 else 7,repeat=.76)



def lantern_side(k):
    return 1 if noise(k,1882)>.5 else -1


def branch_point(index, side, along, across=0.0, height=1.5):
    """Shared geometric anchor for dugout decorations and nearby lights."""
    marker=junction_marker(index)
    x,z,h=route(marker)
    near=max(wall_width(marker,side),wall_width(marker-2,side),
             wall_width(marker+2,side))-.18
    depth=near+along
    shift=across+branch_center_shift(index,along)
    return (x+side*math.cos(h)*depth+math.sin(h)*shift,
            height,
            z-side*math.sin(h)*depth+math.cos(h)*shift)


def nearby_lanterns(s, radius=35.0):
    """Exactly the same seeded lamps as the geometry; no global lamp cache."""
    first=max(0,int(math.floor((s-radius-16)/37)))
    last=int(math.ceil((s+radius-16)/37))+1
    result=[]
    for n in range(first,last+1):
        k=16+n*37
        if abs(k-s)>radius or scene_at(k)!='fortified': continue
        side=lantern_side(k)
        w=wall_width(k,side)
        h=min(1.8,wall_height(k,side)-.1)
        result.append(world(k,side*(w-.45),h-.18))
    # Distant branches are not tracked. Only local, still-visible dugouts
    # contribute a warm accent light around their entrance.
    candidate=nearest_junction(s)
    if candidate is not None and abs(candidate[0]-s)<radius:
        i=int(candidate[1])
        if branch_type(i)=='dugout':
            for side in junction_sides(i):
                result.append(branch_point(i,side,5.0,-.78,1.72))
    return result[:8]

def environment_chunk(mesh,start):
    """Rugged trench life: timber revetment, duckboards, sandbags, puddles,
    crates, lanterns, signs. All positioned in true world coordinates."""
    rng=random.Random(SEED*5501+round(start/CHUNK_LEN)*7919)
    # Alternate reinforced and bare earth segments. No objects across side
    # branches or on the soldier's walking centreline except flat duckboards.
    for k in range(int(start)+1,int(start+CHUNK_LEN)-1):
        s=float(k)
        theme=scene_at(s)
        near_branch=near_junction(s,5)
        if near_branch: continue
        if theme in ('fortified','ruined','marsh','forest') and k%2==0:
            # duckboards differ in length/rotation slightly, sit flush with mud
            width=max(1.0,2*min(wall_width(s,-1),wall_width(s,1))-.30)+rng.uniform(-.06,.06)
            local_box(mesh,s+(rng.random()-.5)*.09,0,-.040,.78,width,.055,
                      15 if rng.random()<.37 else 16 if rng.random()<.63 else 18)
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
                    b=world(s,side*(wall_offset(s,side,0,h)-.09),-.025)
                    t=world(s,side*(wall_offset(s,side,min(h-.13,2.1),h)-.09),min(h-.13,2.1))
                    beam_world(mesh,b,t,.082 if theme!='ruined' else .072, 13 if noise(k+side,801)<.4 else 14)
        # Revetments are substantial, irregular sections of actual timber,
        # not evenly repeated corridor rails. Follow each bank's current width.
        if theme in ('fortified','ruined','forest') and k%4==0:
            for side in (-1,1):
                zone=int((s+side*3.0)//15.0)
                style=noise(zone, 900+side)
                if theme=='forest' and noise(zone,914+side)>.78: continue
                if style<.16:  # sometimes raw earth, not a corridor of endless rails
                    continue
                if style<.72:  # tight split-log shoring alternating with open broken timber
                    packed=style<.40
                    tiers=9 if packed else 5
                    for j in range(tiers):
                        if not packed and noise(zone*17+j,850+side)<.16:continue
                        jf=(j+.8)/(tiers+.8)
                        sy=s-1.90; ey=s+1.90
                        hs=wall_height(sy,side);he=wall_height(ey,side)
                        drift=(noise(zone*11+j,810)-.5)*.035
                        ys=hs*(jf+drift);ye=he*(jf+drift)
                        a=world(sy,side*(wall_offset(sy,side,ys,hs)-.10),ys)
                        b=world(ey,side*(wall_offset(ey,side,ye,he)-.10),ye)
                        tone=(13 if noise(zone+j,812)<.40 else
                              14 if noise(zone+j,813)<.47 else
                              8 if noise(zone+j,814)<.62 else 15)
                        beam_world(mesh,a,b,.103 if packed else .078,tone)
                else:  # weathered vertical plank shoring, with narrow irregular gaps
                    for idx in range(5):
                        ss=s-1.65+idx*.78
                        hs=wall_height(ss,side)
                        ytop=min(2.3,hs-.12) *(.85+.13*noise(zone*23+idx,811))
                        w=wall_offset(ss,side,ytop*.45,hs)-.13
                        local_box(mesh,ss,side*w,-.018,.58,.085,ytop,
                                  15 if noise(zone*33+idx,817)<.34 else 16 if noise(zone*33+idx,818)<.52 else 18)
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
                    blob(mesh,base,(.37,.16,.26),19,13,5,rng.random()*10)
        if theme=='fortified' and k%37==16:
            side=lantern_side(k)
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
    # V2.8: remove bare grey box "buildings" from the skyline.
    # A real ruin asset with windows/damage should replace these later.

def trench_detail_props(mesh, start):
    """Bounded, seed-stable scene dressing close to bank, not artificial blockers.

    Real traversal obstacles are STILL emitted by draw_trench_obstacles and read
    by SoldierBrain. Everything here fits in a shallow wall-side visual strip.
    The small variation library is a placeholder for future GLB asset instances.
    """
    first=max(0,int((start-10.0)//6.7)-1)
    last=int((start+CHUNK_LEN-10.0)//6.7)+2
    for index in range(first,last):
        s=10.0+index*6.7+(noise(index,1001)-.5)*2.0
        if not start<=s<start+CHUNK_LEN:continue
        if near_junction(s,5.0):continue
        side=-1 if noise(index,1002)<.5 else 1
        w=wall_width(s,side)
        h=wall_height(s,side)
        # Keep the object at wall edge. This is cosmetic dressing only.
        edge=side*max(.65,w-.13)
        rng=random.Random(SEED*917+index*1051)
        choice=noise(index,1003)
        if choice<.16:  # weathered ladder against trench wall
            top=min(h-.1,1.8)
            a=world(s-.32,edge-side*.08,.025)
            b=world(s-.32,edge+side*.015,top)
            c=world(s+.32,edge-side*.08,.025)
            d=world(s+.32,edge+side*.015,top)
            beam_world(mesh,a,b,.042,13)
            beam_world(mesh,c,d,.042,14)
            for i in range(1,max(2,int(top/.32))):
                y=i*.32
                lateral=edge-side*.08+side*.095*(y/top)
                beam_world(mesh,world(s-.32,lateral,y),world(s+.32,lateral,y),.030,18)
        elif choice<.34:  # abandoned kit and small ammunition case
            wood_crate(mesh,s,edge-side*.09,-.04,.38,.28,.28,15)
            local_box(mesh,s,edge-side*.09,.24,.36,.29,.024,18)
            # simple dark metal clasps
            local_box(mesh,s+.16,edge-side*.10,.09,.025,.22,.11,10)
        elif choice<.52:  # fallen split boards and stones
            for k in range(3):
                ss=s+(k-1)*.24
                p=world(ss-.3,edge-side*.045,.045)
                q=world(ss+.35,edge-side*(.06+.06*k),.11+.035*k)
                beam_world(mesh,p,q,.030,15 if k%2 else 16)
            for k in range(2):
                ss=s+(k-.5)*.24
                blob(mesh,world(ss,edge-side*.07,.05),(.12,.09,.15),17,10,4,k*.8)
        elif choice<.69:  # rolled muddy tarp tucked against reinforcement
            length=.7+.23*rng.random()
            y=.47+.22*rng.random()
            a=world(s-length*.5,edge,.02)
            b=world(s+length*.5,edge,.02)
            c=world(s+length*.49,edge-side*.02,y)
            d=world(s-length*.48,edge-side*.02,y*.82)
            mesh.quad(a,b,c,d,19,((0,0),(1.1,0),(1.1,.9),(0,.9)))
            beam_world(mesh,world(s-length*.49,edge,y*.65),world(s+length*.49,edge,y*.65),.012,10)
        elif choice<.83:  # battered small iron barrel / container
            pos=world(s,edge-side*.1,.015)
            top=(pos[0],pos[1]+.50,pos[2])
            bar(mesh,pos,top,.16,10,14,.45)
            for y in (.12,.38):
                center=(pos[0],pos[1]+y,pos[2])
                # bent bands approximate hoop, without expensive torus meshes
                for j in range(12):
                    t=j*math.tau/12;t2=(j+1)*math.tau/12
                    a=(center[0]+.164*math.cos(t),center[1],center[2]+.164*math.sin(t))
                    b=(center[0]+.164*math.cos(t2),center[1],center[2]+.164*math.sin(t2))
                    bar(mesh,a,b,.012,10,5,.2)
        else:  # bank-side sandbag roll and rope
            for k in range(3):
                ss=s+(k-1)*.30
                p=world(ss,edge-side*.05,.13)
                blob(mesh,p,(.21,.12,.20),19,12,5,k*.9)
            a=world(s-.48,edge,.33)
            b=world(s+.43,edge-side*.09,.25)
            bar(mesh,a,b,.018,16,7,.28)

def trench_floor_litter(mesh, start):
    """Tiny stones and compacted clumps, kept close to walls and off nav path."""
    for i in range(max(0,int(start//3.3)-1),int((start+CHUNK_LEN)//3.3)+2):
        s=1.15+i*3.3+.35*(noise(i,1802)-.5)
        if not start<=s<start+CHUNK_LEN or near_junction(s,3.5):continue
        side=-1 if noise(i,1803)>.5 else 1
        offset=side*min(.88,wall_width(s,side)-.15)
        if noise(i,1804)>.38:
            r=.045+.06*noise(i,1805)
            blob(mesh,world(s,offset,r*.52-.035),(r*1.45,r*.59,r),17,10,4,i*.47)


def make_chunk(start):
    mesh=MeshBuilder()
    stride=SEGMENT
    for i in range(int(CHUNK_LEN/stride)):
        s0=start+i*stride;s1=s0+stride
        floor_half=1.95  # underlaps even the widest banks; prevents exposed ground seams
        mesh.quad(world(s0,-floor_half,-.045),world(s0,floor_half,-.045),
                  world(s1,floor_half,-.045),world(s1,-floor_half,-.045),21,
                  ((-floor_half,s0*.84),(floor_half,s0*.84),
                   (floor_half,s1*.84),(-floor_half,s1*.84)))
        for side in (-1,1):
            w0,w1=wall_width(s0,side),wall_width(s1,side)
            h0,h1=wall_height(s0,side),wall_height(s1,side)
            # Open the side wall where an actual T junction branches off.
            crossing=nearest_junction((s0+s1)*.5)
            cut=(crossing is not None and abs((s0+s1)*.5-crossing[0])<2.0
                 and side in junction_sides(crossing[1]))
            def layers(s,h):
                # Non-parallel geological strata; vertical segmentation permits
                # rough excavation faces instead of flat corridor slabs.
                return [0.,h*(.20+.035*math.sin(s*.053+side)),
                        h*(.49+.040*math.sin(s*.073-side)),
                        h*(.77+.028*math.sin(s*.045+side)),h]
            a,b=layers(s0,h0),layers(s1,h1)
            if not cut:
                mats=surface_material((s0+s1)*.5,side,0)
                for band,mat in enumerate(mats):
                    for j in range(5):
                        t0=j/5.; t1=(j+1)/5.
                        y00=smooth(a[band],a[band+1],t0)
                        y01=smooth(a[band],a[band+1],t1)
                        y10=smooth(b[band],b[band+1],t0)
                        y11=smooth(b[band],b[band+1],t1)
                        # Real uneven cross section, different at each level.
                        p0=world(s0,side*wall_offset(s0,side,y00,h0),y00)
                        p1=world(s0,side*wall_offset(s0,side,y01,h0),y01)
                        p2=world(s1,side*wall_offset(s1,side,y11,h1),y11)
                        p3=world(s1,side*wall_offset(s1,side,y10,h1),y10)
                        mesh.quad(p0,p1,p2,p3,20,
                                  ((s0*1.12,y00*1.2),(s0*1.12,y01*1.2),
                                   (s1*1.12,y11*1.2),(s1*1.12,y10*1.2)))
            # Ground is a genuine continuous mesh tied to the lip. At a
            # junction, remove ALL terrain spanning the excavated branch,
            # not just the first ring (that produced the see-through strips).
            offsets0=[wall_offset(s0,side,h0,h0)-.05,3.5,7.0,12.0,18.0,32.0,60.0]
            offsets1=[wall_offset(s1,side,h1,h1)-.05,3.5,7.0,12.0,18.0,32.0,60.0]
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
            lo,hi=world(s0,-min(.91,wall_width(s0,-1)-.1),.005),world(s0,min(.91,wall_width(s0,1)-.1),.005)
            lo2,hi2=world(s0+.16,-min(.91,wall_width(s0+.16,-1)-.1),.005),world(s0+.16,min(.91,wall_width(s0+.16,1)-.1),.005)
            mesh.quad(lo,hi,hi2,lo2,2,((0,0),(2.1,0),(2.1,.18),(0,.18)))
    # Seeded T/Y/X side passages. Cave roof and banks are real 3D surfaces;
    # never draw a large rectangular room or an exposed square cutout.
    for marker in range(JUNCTION_FIRST, int(start+CHUNK_LEN)+1, JUNCTION_SPACING):
        if not start <= marker < start+CHUNK_LEN:
            continue
        branch_idx=(marker-JUNCTION_FIRST)//JUNCTION_SPACING
        x,z,h=route(marker)
        right=(math.cos(h),-math.sin(h))
        forward=(math.sin(h),math.cos(h))
        outer=float(branch_length(branch_idx))
        roofed=branch_type(branch_idx)=='dugout'
        for branch_side in junction_sides(branch_idx):
            sideheight=max(1.58,wall_height(marker,branch_side))
            near_edge=max(wall_width(marker,branch_side),
                          wall_width(marker-2,branch_side),
                          wall_width(marker+2,branch_side))-.18
            def bp(along, across, height):
                dist=near_edge+along
                shifted=across+branch_center_shift(branch_idx,along)
                return (x+branch_side*right[0]*dist+forward[0]*shifted,height,
                        z+branch_side*right[1]*dist+forward[1]*shifted)

            def hw(along):return branch_half_width(branch_idx,along)
            def shoulder(along):return 1.27+.08*math.sin(along*.47+branch_idx)
            def crown(along):return max(1.94, min(2.22,sideheight+.30))+.07*math.sin(along*.51+branch_idx)
            def vaulted(along,ratio):
                # ratio:-1..+1. A broken irregular ellipse/cave arch.
                r=max(-1.0,min(1.0,ratio))
                return shoulder(along)+(crown(along)-shoulder(along))*pow(max(0.0,1.0-r*r),.62)

            for n in range(int(outer)):
                a=float(n);b=a+1.0
                wa,wb=hw(a),hw(b)
                mesh.quad(bp(a,-wa,-.052),bp(a,wa,-.052),
                          bp(b,wb,-.052),bp(b,-wb,-.052),21,
                          ((a*.81,-wa),(a*.81,wa),(b*.81,wb),(b*.81,-wb)))
                # Narrow, irregular walls: not a box with four flat sides.
                for flank in (-1,1):
                    ya=shoulder(a) if roofed else sideheight+.08*math.sin(a*.3+flank)
                    yb=shoulder(b) if roofed else sideheight+.08*math.sin(b*.3+flank)
                    for j in range(4):
                        t0=j/4.;t1=(j+1)/4.
                        aa=wa+(.035*math.sin(a*.9+j*1.4+flank))*t0
                        ab=wa+(.035*math.sin(a*.9+(j+1)*1.4+flank))*t1
                        ba=wb+(.035*math.sin(b*.9+j*1.4+flank))*t0
                        bb=wb+(.035*math.sin(b*.9+(j+1)*1.4+flank))*t1
                        mesh.quad(bp(a,flank*aa,-.04+(ya+.04)*t0),
                                  bp(a,flank*ab,-.04+(ya+.04)*t1),
                                  bp(b,flank*bb,-.04+(yb+.04)*t1),
                                  bp(b,flank*ba,-.04+(yb+.04)*t0),20,
                                  ((a,t0*ya),(a,t1*ya),(b,t1*yb),(b,t0*yb)))
                if roofed and n==5:
                    # One enclosed, wall-mounted lantern and a tiny shelf.
                    # Same location is passed to GPU lighting via nearby_lanterns.
                    anchor=bp(a,-.78,1.68)
                    bracket=bp(a,-.78,1.88)
                    beam_world(mesh,anchor,bracket,.017,10)
                    blob(mesh,bp(a,-.78,1.72),(.060,.090,.060),11,10,4)
                    box(mesh,bp(a,-.78,1.59),(.19,.07,.20),10)
                if roofed:
                    # Curved vaulted roof: 10 subdivisions, with uneven timber
                    # beams to suggest hand-excavated dugouts.
                    for j in range(10):
                        ra=-1.+2*j/10.; rb=-1.+2*(j+1)/10.
                        # Wind inward normals toward the cave floor; an
                        # excavated ceiling should not face the bright sun.
                        mesh.quad(bp(a,wa*ra,vaulted(a,ra)),
                                  bp(b,wb*ra,vaulted(b,ra)),
                                  bp(b,wb*rb,vaulted(b,rb)),
                                  bp(a,wa*rb,vaulted(a,rb)),20,
                                  ((a,j*.24),(b,j*.24),
                                   (b,(j+1)*.24),(a,(j+1)*.24)))
                    if n in (1,4,7,10,13):
                        # Posts and arch frame members follow roof, not a flat lid.
                        for flank in (-1,1):
                            top=bp(a,flank*wa,vaulted(a,flank))
                            bottom=bp(a,flank*(wa-.045),0.0)
                            beam_world(mesh,bottom,top,.065,13 if n%2 else 14)
                        for j in range(6):
                            ra=-1.+2*j/6.;rb=-1.+2*(j+1)/6.
                            a1=bp(a,wa*ra,vaulted(a,ra)-.045)
                            b1=bp(a,wa*rb,vaulted(a,rb)-.045)
                            beam_world(mesh,a1,b1,.05,15 if n%2 else 13)
                # A few seeded uneven floor boards inside buried sections.
                if roofed and n%3==1 and n>2:
                    width=max(.9,2*min(wa,wb)-.17)
                    mesh.quad(bp(a,-width*.5,-.024),bp(a,width*.5,-.024),
                              bp(a+.58,width*.5,-.024),bp(a+.58,-width*.5,-.024),15,
                              ((0,0),(width,0),(width,.58),(0,.58)))
            # The end is sealed by an arched cave face; no square end wall.
            end_width=hw(outer)
            if roofed:
                for j in range(10):
                    r0=-1.+2*j/10.;r1=-1.+2*(j+1)/10.
                    y0=vaulted(outer,r0);y1=vaulted(outer,r1)
                    mesh.quad(bp(outer,r0*end_width,-.04),
                              bp(outer,r0*end_width,y0),
                              bp(outer,r1*end_width,y1),
                              bp(outer,r1*end_width,-.04),20,
                              ((r0*end_width,0),(r0*end_width,y0),
                               (r1*end_width,y1),(r1*end_width,0)))
            else:
                mesh.quad(bp(outer,-end_width,-.04),
                          bp(outer,-end_width,sideheight),
                          bp(outer,end_width,sideheight),
                          bp(outer,end_width,-.04),20,
                          ((-end_width,0),(-end_width,sideheight),
                           (end_width,sideheight),(end_width,0)))
    scenery_chunk(mesh,start)
    rim_vegetation_chunk(mesh,start)
    environment_chunk(mesh,start)
    draw_trench_obstacles(mesh,start)
    trench_detail_props(mesh,start)
    trench_floor_litter(mesh,start)
    return mesh.as_array()


def gait_targets(mode, speed, stride, travelled, strength):
    """Target camera micro-motion for one LEFT+RIGHT footfall pair.

    Distance-driven, small and deliberately stabilized: this describes the
    viewpoint, not a skeleton animation. No GUI/OpenGL dependency.
    """
    if stride<=0.0 or strength<=0.0:
        return 0.0,0.0,0.0
    full_cycle=max(.70,2.0*stride)
    phase=2.0*math.pi*travelled/full_cycle
    crouched=mode in (3,4)
    lateral_amp=(.0009 if crouched else .0016 if speed<1.8 else
                 .0022 if speed<2.8 else .0028)
    bob_amp=(.0015 if crouched else .0024 if speed<1.8 else .0038)
    lateral=lateral_amp*strength*math.sin(phase)
    bob=bob_amp*strength*(.55+.45*math.cos(2.0*phase))
    roll=(.0005 if crouched else .0010)*strength*math.sin(phase-.4)
    return lateral,bob,roll


def perspective(fov,aspect,near,far):
    f=1/math.tan(math.radians(fov)/2)
    return np.array([[f/aspect,0,0,0],[0,f,0,0],[0,0,-(far+near)/(far-near),-2*far*near/(far-near)],[0,0,-1,0]],dtype='f4')

def view_from(position,target,roll=0.):
    # OpenGL right-handed: view looks along negative Z.
    eye=np.asarray(position,dtype='f4'); focus=np.asarray(target,dtype='f4')
    f=focus-eye; f/=np.linalg.norm(f)
    up=np.array([math.sin(roll), math.cos(roll),0],dtype='f4')
    s=np.cross(f,up);s/=np.linalg.norm(s)
    u=np.cross(s,f)
    result=np.eye(4,dtype='f4');result[0,:3]=s;result[1,:3]=u;result[2,:3]=-f
    result[:3,3]= -result[:3,:3]@eye
    return result

class SoldierBrain:
    """Deterministic tactical traversal controller.

    Decisions own body travel, stance, heading, eye scan and lean.
    Rendering only interpolates the requested pose. This is tactical staging,
    not geometric visibility/raycasting or an enemy detector.
    """
    def __init__(self):
        self.state='main'
        self.phase='avancerar'
        self.visited=set()
        self.checked_bends=set()
        self.bend_index=None
        self.bend_side=0
        self.bend_stop=0.0
        self.branch_index=None
        self.branch_side=0
        self.branch_progress=0.0
        self.investigate_depth=0.0
        self.wait=0.0
        self.inspect_duration=0.0
        self.look_offset=0.0
        self.roll=0.0
        self.peek_shift=0.0
        self.peek_forward=0.0
        self.forward_target=0.0
        self.heading_offset=0.0
        self.heading_actual=None
        self.turn_preference=0.0
        self.look_target=0.0
        self.roll_target=0.0
        self.shift_target=0.0
        self.stance=5
        self.visit_count=0
        self._last_distance=0.0
        self.corner_progress=0.0
        self.corner_length=0.0
        self.corner_cumulative=(0.0,)
        self.corner_points=()
        self.corner_outbound=True
        self.obstacle_active=None
        self.speed_factor=1.0
        self.step_lift=0.0
        self.gaze_pitch=0.0

    def reset(self):
        self.__init__()

    def _depth_to_check(self,index):
        """Prototype estimate only: not physical visibility."""
        length=float(branch_length(index))
        if branch_type(index)=='dugout':
            # The end is hidden beneath an arch, so walking in briefly is sane.
            return min(length-2.0, 3.9 + 2.4*noise(index,1179))
        bend=abs(branch_center_shift(index,length))
        if bend < .43:
            return 0.0 if noise(index,155)<.7 else max(CORNER_DEPTH+0.6,min(length-2.,1.3+noise(index,157)*1.8))
        return max(CORNER_DEPTH+0.6,min(length-2.0,2.4+noise(index,159)*3.9))

    def _start(self,state,duration,phase):
        self.state=state
        self.wait=max(.02,float(duration))
        self.inspect_duration=self.wait
        self.phase=phase

    def _close_to_junction(self,distance):
        i=max(0,math.ceil((distance-JUNCTION_FIRST-0.00001)/JUNCTION_SPACING))
        return i,junction_marker(i)

    def _pose_for_state(self):
        side=self.bend_side if self.state.startswith('bend_') else self.branch_side
        # Look (radians), head tilt (radians), side lean (metres), forward lean (metres).
        targets={
            'main':(0.,0.,0.,0.),
            'approach':(side*.12,0.,0.,0.),
            'edge':(side*.22,-side*.013,side*.07,.035),
            'peek':(side*.89,-side*.060,side*.17,.18),
            'retract':(side*.33,-side*.015,side*.04,.025),
            'assess':(side*.19,0.,side*.02,0.),
            'move_to_mouth':(side*.26,0.,side*.12,0.),
            'turn_in':(0.,0.,0.,0.),
            'dash':(0.,0.,0.,0.),
            'kneel_scan':(0.,-side*.018,0.,0.),
            'explore':(0.,0.,0.,0.),
            'turn_back':(0.,0.,0.,0.),
            'backtrack':(0.,0.,0.,0.),
            'turn_main':(0.,0.,0.,0.),
            'rejoin':(0.,0.,0.,0.),
            'bend_approach':(side*.10,0.,0.,0.),
            'bend_settle':(side*.15,0.,0.,0.),
            'bend_peek':(side*.66,-side*.035,side*.13,.13),
            'bend_retract':(side*.18,-side*.010,side*.035,0.),
            'bend_assess':(side*.20,0.,0.,0.),
        }
        self.look_target,self.roll_target,self.shift_target,self.forward_target=targets.get(self.state,(0.,0.,0.,0.))

    def _tick_pose(self,dt):
        # Small, time-based angular and shoulder changes; never snap.
        alpha=1-math.exp(-dt*4.0)
        self.look_offset=smooth(self.look_offset,self.look_target,alpha)
        self.roll=smooth(self.roll,self.roll_target,alpha)
        self.peek_shift=smooth(self.peek_shift,self.shift_target,alpha)
        self.peek_forward=smooth(self.peek_forward,self.forward_target,alpha)

    def _branch_position(self,progress):
        """Branch centreline matches the excavated floor centre, including near edge."""
        marker=junction_marker(self.branch_index)
        x,z,h=route(marker)
        side=self.branch_side
        near=max(wall_width(marker,side),wall_width(marker-2,side),
                 wall_width(marker+2,side))-.18
        lateral=side*(near+progress)
        shifted=branch_center_shift(self.branch_index,progress)
        return (x+math.cos(h)*lateral+math.sin(h)*shifted,
                z-math.sin(h)*lateral+math.cos(h)*shifted)

    def _junction_cover(self, s, marker, side):
        """Smooth wall-hugging lane from approach through departure.

        The offset is also evaluated in 'main', BEFORE SoldierBrain first
        registers the junction, so the camera never jumps into cover.
        """
        if s < marker-7.0 or s > marker+4.5:
            return 0.0
        if s < marker-2.25:
            blend=eased((s-(marker-7.0))/4.75)
        elif s <= marker+1.25:
            blend=1.0
        else:
            blend=1.0-eased((s-(marker+1.25))/3.25)
        return side*cover_distance(s,side)*blend

    def _bend_cover(self,s,index,side):
        marker=bend_marker(index)
        if s<marker-7.0 or s>marker+10.: return 0.0
        if s<marker-2.2: blend=eased((s-(marker-7.))/4.8)
        elif s<marker+5.: blend=1.0
        else: blend=1.0-eased((s-(marker+5.))/5.0)
        return side*cover_distance(s,side)*.78*blend

    def _main_offset(self,s):
        """Compose overlapping cover lanes smoothly, never jump between them.

        A Z/W bend can lie within metres of a T junction. Giving either
        lane hard precedence made the camera teleport sideways at that seam.
        """
        offset=0.0
        i,mark=self._close_to_junction(s)
        if i not in self.visited and mark-7.<=s<=mark+1.25:
            offset+=self._junction_cover(s,mark,junction_side(i))
        if self.branch_index is not None:
            previous=junction_marker(self.branch_index)
            if previous-7.<=s<=previous+4.5:
                offset+=self._junction_cover(s,previous,self.branch_side)
        base=max(0,int((s-BEND_FIRST)//BEND_SPACING))
        for k in range(max(0,base-1),base+2):
            m=bend_marker(k)
            if m-7.<=s<=m+10.:
                direction=bend_direction(k)
                if abs(direction)>.42:
                    offset+=self._bend_cover(s,k,1 if direction>0 else -1)
        # Reuse the same seeded obstacle target as the rendered geometry.
        # Obstacle sites are kept outside bend/junction manoeuvre regions.
        offset += obstacle_steering(s)
        if abs(offset)<1.e-9:
            return 0.0
        side=1 if offset>0 else -1
        return max(-cover_distance(s,side),min(cover_distance(s,side),offset))

    def _curve_controls(self,outbound):
        """Quarter-turn joins the *same wall-side lane* used by the approach."""
        marker=junction_marker(self.branch_index)
        a=marker-CORNER_MAIN_OFFSET
        exit_s=marker+1.25
        entrance=route(a)
        start=(entrance[0]+math.cos(entrance[2])*self._main_offset(a),
               entrance[1]-math.sin(entrance[2])*self._main_offset(a))
        join=route(exit_s)
        finish=(join[0]+math.cos(join[2])*self._main_offset(exit_s),
                join[1]-math.sin(join[2])*self._main_offset(exit_s))
        # Tangents toward the opening and out of it; no centreline jump.
        guide_out=route(marker-.04)
        g_out=(guide_out[0]+math.cos(guide_out[2])*self._main_offset(marker-.04),
               guide_out[1]-math.sin(guide_out[2])*self._main_offset(marker-.04))
        guide_in=route(marker+.32)
        g_in=(guide_in[0]+math.cos(guide_in[2])*self._main_offset(marker+.32),
              guide_in[1]-math.sin(guide_in[2])*self._main_offset(marker+.32))
        branch0=self._branch_position(0.0)
        branch1=self._branch_position(CORNER_DEPTH)
        if outbound:
            return (start,g_out,branch0,branch1)
        return (branch1,branch0,g_in,finish)

    @staticmethod
    def _bezier(points,t):
        a,b,c,d=points;u=1.-t
        return (u*u*u*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t*t*t*d[0],
                u*u*u*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t*t*t*d[1])

    @staticmethod
    def _bezier_heading(points,t):
        a,b,c,d=points;u=1.-t
        dx=3*u*u*(b[0]-a[0])+6*u*t*(c[0]-b[0])+3*t*t*(d[0]-c[0])
        dz=3*u*u*(b[1]-a[1])+6*u*t*(c[1]-b[1])+3*t*t*(d[1]-c[1])
        return math.atan2(dx,dz)

    def _start_corner(self,outbound):
        self.corner_outbound=outbound
        self.corner_points=self._curve_controls(outbound)
        length=[0.]
        last=self._bezier(self.corner_points,0.)
        # Arc-length lookup: travelled metres, not a timed canned animation.
        for k in range(1,41):
            current=self._bezier(self.corner_points,k/40.)
            length.append(length[-1]+math.hypot(current[0]-last[0],current[1]-last[1]))
            last=current
        self.corner_cumulative=tuple(length)
        self.corner_length=length[-1]
        self.corner_progress=0.

    def _corner_pose(self):
        progress=min(self.corner_length,max(0.,self.corner_progress))
        arr=self.corner_cumulative
        idx=1
        while idx<len(arr)-1 and arr[idx]<progress:idx+=1
        f=(progress-arr[idx-1])/max(1.e-6,arr[idx]-arr[idx-1])
        t=((idx-1)+f)/(len(arr)-1)
        x,z=self._bezier(self.corner_points,t)
        return x,z,self._bezier_heading(self.corner_points,t)

    def choose(self,distance,dt):
        dt=max(0.,min(.08,dt))
        self._last_distance=distance
        self.speed_factor=1.0
        self.obstacle_active=None
        self.step_lift=0.0
        self.gaze_pitch=0.0
        # The soldier brain, not the renderer, decides how long each
        # preparation step lasts. The order is observable and testable.
        if self.state=='main':
            # Treat *every* new generated Z/W bend as unknown ground.
            # A bend only becomes safe after an actual stop/peek/retract.
            first=max(0,int((distance-BEND_FIRST)//BEND_SPACING))
            for k in (first,first+1):
                bm=bend_marker(k)
                delta=bend_direction(k)
                if (k not in self.checked_bends and abs(delta)>.82
                        and min(wall_height(bm,-1),wall_height(bm,1))>1.45
                        and bm-7.0<=distance<bm+1.0):
                    self.bend_index=k
                    self.bend_side=1 if delta>0 else -1
                    self.bend_stop=bm-2.2
                    self._start('bend_approach',.0,'bromsar inför osäkert hörn')
                    break
            if self.state=='main':
                i,marker=self._close_to_junction(distance)
            else:
                i,marker=-1,-10000
            if i not in self.visited and distance>=marker-6.5 and distance<marker+.15:
                self.visited.add(i)
                self.branch_index=i
                self.branch_side=junction_side(i)
                self.branch_progress=0.
                self.visit_count+=1
                self._start('approach',.35+noise(i,201)*.45,'bromsar före öppning')
        elif self.wait>0:
            self.wait=max(0.,self.wait-dt)
            if self.wait==0.:
                i=self.branch_index
                if self.state=='bend_settle':
                    self._start('bend_peek',.30+noise(self.bend_index,311)*.19,
                                'kikar försiktigt runt nytt hörn')
                elif self.state=='bend_peek':
                    self._start('bend_retract',.15+noise(self.bend_index,312)*.13,
                                'drar tillbaka huvudet')
                elif self.state=='bend_retract':
                    self._start('bend_assess',.12+noise(self.bend_index,313)*.17,
                                'bedömer passage')
                elif self.state=='bend_assess':
                    self.checked_bends.add(self.bend_index)
                    self.state='main'
                    self.phase='fortsätter försiktigt runt hörnet'
                elif self.state=='approach':
                    if distance < junction_marker(i)-2.26:
                        self.wait=.10
                    else:
                        self._start('edge',.3+noise(i,202)*.35,'ställer sig vid väggen')
                elif self.state=='edge':
                    self._start('peek',.42+noise(i,203)*.33,'kikar snabbt runt hörnet')
                elif self.state=='peek':
                    self._start('retract',.22+noise(i,204)*.22,'drar tillbaka huvudet')
                elif self.state=='retract':
                    self._start('assess',.35+noise(i,205)*.45,'bedömer gången')
                elif self.state=='assess':
                    self.investigate_depth=self._depth_to_check(i)
                    if self.investigate_depth<.15:
                        self.state='main'
                        self.phase='återvändsgränd synlig — går vidare'
                    else:
                        self._start('move_to_mouth',.12,'förflyttar sig till öppningen')
                elif self.state=='kneel_scan':
                    self.state='explore'
                    self.phase='undersöker bortre hörnet'
                elif self.state=='rejoin':
                    self.state='main'
                    self.phase='fortsätter längs huvudgången'
        self._pose_for_state()
        self._tick_pose(dt)
        if self.state=='main':
            # Look/slow down for an actual obstruction, not random idle scans.
            nearby=obstacles_in_range(distance-1.5,distance+4.1)
            ob=min(nearby,key=lambda obj:abs(obj.s-distance)) if nearby else None
            if ob is not None and -1.5 <= ob.s-distance <= 4.1:
                self.obstacle_active=ob
                proximity=ob.s-distance
                if ob.kind in ('crate','rubble'):
                    self.speed_factor=.55 if proximity<2.1 else .78
                    self.phase='går runt '+('låda' if ob.kind=='crate' else 'ras/bråte')
                elif ob.kind=='puddle':
                    self.speed_factor=.7
                    self.phase='passerar vatten och lera'
                else:
                    self.speed_factor=.49 if proximity<1.3 else .70
                    self.phase='kliver över '+('stock' if ob.kind=='timber' else 'sandsäckar')
                    d=distance-ob.s
                    if abs(d)<.72:
                        # A single controlled rise/step, not a sudden teleport.
                        self.step_lift=.078*math.sin(math.pi*eased((d+.72)/1.44))
                    self.gaze_pitch=-.055*eased((4.1-proximity)/4.1)
                return 5  # walk, not a crouch animation for every obstruction
            bend=abs(math.atan2(math.sin(route(distance+8)[2]-route(distance)[2]),
                                math.cos(route(distance+8)[2]-route(distance)[2])))
            self.phase='avancerar försiktigt' if bend>.45 else 'avancerar'
            return 4 if bend>.45 else (5 if bend>.17 else 7)
        if self.state in ('bend_approach','bend_settle','bend_peek','bend_retract','bend_assess'):
            return 4 if self.state=='bend_approach' else 1
        if self.state in ('approach','edge','peek','retract','assess','move_to_mouth','turn_in','turn_back','turn_main','rejoin'):
            return 4 if self.state in ('approach','move_to_mouth','turn_in','turn_main') else (1 if self.state in ('edge','peek','retract','assess') else 0)
        if self.state=='dash':return 8
        if self.state=='kneel_scan':return 1
        if self.state=='explore':return 4
        if self.state=='backtrack':return 5
        return 0

    def advance(self,distance,movement):
        # Distance on the trunk is separate from travelled side-branch distance.
        if self.state=='bend_approach':
            travel=min(movement,max(0.,self.bend_stop-distance))
            if distance+travel>=self.bend_stop-.015:
                self._start('bend_settle',.12+noise(self.bend_index,310)*.15,
                            'stannar i skydd vid hörnet')
            return distance+travel,travel
        if self.state=='main':
            i,marker=self._close_to_junction(distance)
            if i not in self.visited and distance<marker:
                movement=min(movement,max(0.,marker-2.30-distance))
            return distance+movement,movement
        if self.state=='approach':
            marker=junction_marker(self.branch_index)
            travel=min(movement,max(0.,marker-2.25-distance))
            return distance+travel,travel
        if self.state=='move_to_mouth':
            marker=junction_marker(self.branch_index)
            travel=min(movement,max(0.,marker-CORNER_MAIN_OFFSET-distance))
            if distance+travel>=marker-CORNER_MAIN_OFFSET-.012:
                self._start_corner(True)
                self.state='turn_in'
                self.phase='rundar hörnet i rörelse'
            return distance+travel,travel
        if self.state=='turn_in':
            travel=min(movement,max(0.,self.corner_length-self.corner_progress))
            self.corner_progress+=travel
            if self.corner_progress>=self.corner_length-.012:
                self.corner_progress=self.corner_length
                self.branch_progress=CORNER_DEPTH
                self.state='dash'
                self.phase='tar sig snabbt vidare i sidogången'
            return distance,travel
        if self.state=='dash':
            stop=min(self.investigate_depth,max(1.9,min(3.3,self.investigate_depth*.6)))
            travel=min(movement,max(0.,stop-self.branch_progress))
            self.branch_progress+=travel
            if self.branch_progress>=stop-.015:
                self._start('kneel_scan',.75+noise(self.branch_index,206)*.8,'går ned på knä och söker av')
            return distance,travel
        if self.state=='explore':
            travel=min(movement,max(0.,self.investigate_depth-self.branch_progress))
            self.branch_progress+=travel
            if self.branch_progress>=self.investigate_depth-.015:
                self.state='turn_back'
                self.wait=0.0
                self.phase='vänder kroppen kontrollerat'
            return distance,travel
        if self.state=='turn_back':
            if self._heading_aligned(distance,goal='back'):
                self.state='backtrack'
                self.phase='går tillbaka till korsningen'
            return distance,0.
        if self.state=='backtrack':
            travel=min(movement,max(0.,self.branch_progress-CORNER_DEPTH))
            self.branch_progress-=travel
            if self.branch_progress<=CORNER_DEPTH+.015:
                self.branch_progress=CORNER_DEPTH
                self._start_corner(False)
                self.state='turn_main'
                self.phase='rundar tillbaka till huvudgången'
            return distance,travel
        if self.state=='turn_main':
            travel=min(movement,max(0.,self.corner_length-self.corner_progress))
            self.corner_progress+=travel
            if self.corner_progress>=self.corner_length-.012:
                self.corner_progress=self.corner_length
                distance=junction_marker(self.branch_index)+1.25
                self._start('rejoin',.35+noise(self.branch_index,207)*.3,
                            'kontrollerar huvudgången')
            return distance,travel
        return distance,0.

    def _desired_heading(self,distance,goal=None):
        if self.state in ('turn_in','turn_main') and self.corner_points:
            return self._corner_pose()[2]
        if goal=='main' or self.state in ('main','approach','edge','peek','retract','assess','move_to_mouth','rejoin',
                                          'bend_approach','bend_settle','bend_peek','bend_retract','bend_assess'):
            return route(distance+3.2)[2]
        i=self.branch_index
        main_heading=route(junction_marker(i))[2]
        direction=self.branch_side*math.pi/2
        if goal=='back' or self.state in ('turn_back','backtrack'):
            return main_heading+direction+math.pi
        return main_heading+direction

    def _heading_aligned(self,distance,goal):
        if self.heading_actual is None:return False
        target=self._desired_heading(distance,goal)
        error=math.atan2(math.sin(target-self.heading_actual),math.cos(target-self.heading_actual))
        return abs(error)<.12

    def camera_pose(self,main_distance):
        if self.state in ('turn_in','turn_main') and self.corner_points:
            return self._corner_pose()
        if self.state in ('main','approach','edge','peek','retract','assess','move_to_mouth','rejoin',
                          'bend_approach','bend_settle','bend_peek','bend_retract','bend_assess'):
            x,z,h=route(main_distance)
            lateral=self._main_offset(main_distance)
            return (x+math.cos(h)*lateral,
                    z-math.sin(h)*lateral,
                    self._desired_heading(main_distance))
        x,z=self._branch_position(self.branch_progress)
        return x,z,self._desired_heading(main_distance)

class Trench:
    def __init__(self):
        pygame.init()
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION,3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION,3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE,24)
        pygame.display.set_mode((W,H),pygame.OPENGL|pygame.DOUBLEBUF|pygame.RESIZABLE)
        self._projector_window=None
        try:
            from pygame._sdl2.video import Window
            self._projector_window=Window.from_display_module()
            px,py=self._projector_window.position
            self._projector_window.position=(px,py-WINDOW_RAISE_PIXELS)
            print(f'Projektorfönster: flyttat {WINDOW_RAISE_PIXELS} px upp (F9/F10 justerar)')
        except Exception as exc:
            print(f'Projektorfönster: automatisk förflyttning stöds inte här ({exc}); dra manuellt')
        pygame.display.set_caption('Oändlig skyttegrav — riktig 3D / ModernGL')
        self.ctx=moderngl.create_context(require=330)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.prog=self.ctx.program(vertex_shader=VERT,fragment_shader=FRAG)
        self.sky_prog=self.ctx.program(vertex_shader=SKYVERT,fragment_shader=SKYFRAG)
        self.sky_buffer=self.ctx.buffer(np.array([-1,-1,3,-1,-1,3],dtype='f4').tobytes())
        self.sky_vao=self.ctx.vertex_array(self.sky_prog,[(self.sky_buffer,'2f','xy')])
        self.sky_prog['sun_direction'].value=SUN_DIRECTION
        self.sky_prog['moon_direction'].value=MOON_DIRECTION
        self.sky_prog['tan_half_fov'].value=math.tan(math.radians(CAMERA_VERTICAL_FOV)*.5)
        self.texture,self.normal_texture,self.has_pbr_normals=self.load_textures()
        self.prog['materials']=0
        self.prog['material_normals']=1
        self.prog['use_pbr_normals']=int(self.has_pbr_normals)
        self.fog_strength=FOG_DENSITY
        self.prog['fog_strength'].value=self.fog_strength
        self.prog['lamp_count'].value=0
        # Driver/ModernGL versions disagree on array uniform member names.
        # Query the program once; never throw KeyError on the first draw call.
        try:self.lamp_uniform=self.prog['lamp_positions']
        except KeyError:self.lamp_uniform=self.prog['lamp_positions[0]']
        self.chunks={}
        self.todo=queue.Queue(maxsize=16)
        self.ready=queue.Queue(maxsize=16)
        self.pending=set()
        self.generation=0
        self.worker_stop=threading.Event()
        self.worker=threading.Thread(target=self._chunk_worker,daemon=True,name='trench-mesh-builder')
        self.worker.start()
        self.chunk_upload_ms=0.0
        self.frame_max_ms=0.0
        self.frame_mean_ms=0.0
        # Initial scene is loaded once before entering the real-time loop.
        for i in range(0,4):
            self.chunks[i]=self.chunk(i)
        self.distance=0.;self.speed=0.;self.mode=5;self.auto=True
        self.brain=SoldierBrain()
        self.auto_timer=0.;self.step_distance=0.;self.look=0.;self.height=1.55
        self.gait_strength=0.0;self.last_moved=0.0
        self.gait_lateral=0.0;self.gait_vertical=0.0;self.gait_roll=0.0
        self.elapsed=0.;self.paused=False;self.fps=0.;self.ui_timer=0.
        self.obstacle_camera_lift=0.0
        self.view_heading=None;self.last_dt=1/60;self.camera_roll=0.0
        self.last=time.monotonic();self.running=True
        self.frame_size=(W,H)
    def load_textures(self):
        # Texture-array layers are stable: the original first 13 retain their IDs.
        # Extra DETAIL layers have local 1K fallback images in this delta.
        base_names=['clay.png','gravel.png','loam.png','humus.png','mud.png',
                    'bark.png','foliage.png','stone.png','timber.png','canvas.png',
                    'metal.png','flame.png','wet.png']
        detail_names=['pine_bark','bark_willow','wood_planks','wood_planks_grey',
                      'mossy_rock','wood_planks_dirt','sandbag_mud']
        # Earth originals from V1.9 + six NEW optional Poly Haven originals.
        ph_overrides={0:'brown_mud',1:'roots',2:'mud_forest',3:'mud_forest',4:'brown_mud_02',
                      13:'pine_bark',14:'bark_willow',15:'wood_planks',
                      16:'wood_planks_grey',17:'mossy_rock',18:'wood_planks_dirt'}
        ph_folder=ROOT/'assets'/'polyhaven'
        detail_folder=ROOT/'assets'/'detail'
        frames=[];normals=[];have_normals=False
        loaded_color=0;loaded_normal=0;loaded_local_normals=0
        blank_normal=bytes([128,128,255])*(TEXTURE_SIZE*TEXTURE_SIZE)
        for index in range(20):
            fallback=(ROOT/'assets'/base_names[index] if index<13 else
                      detail_folder/(detail_names[index-13]+'.png'))
            asset=ph_overrides.get(index)
            color=ph_folder/(asset+'_diff.png') if asset else None
            normal=ph_folder/(asset+'_nor_gl.png') if asset else None
            source=color if color is not None and color.is_file() else fallback
            if color is not None and source==color:loaded_color+=1
            with Image.open(source) as im:
                frames.append(im.convert('RGB').resize((TEXTURE_SIZE,TEXTURE_SIZE),Image.BICUBIC)
                              .transpose(Image.FLIP_TOP_BOTTOM).tobytes())
            chosen_normal=None
            if normal is not None and source==color and normal.is_file():
                chosen_normal=normal
                loaded_normal+=1
            elif index>=13 and source==fallback:
                # Never pair a downloaded photographic albedo with an unrelated
                # procedural fallback normal map.
                local_n=detail_folder/(detail_names[index-13]+'_nor_gl.png')
                if local_n.is_file():
                    chosen_normal=local_n
                    loaded_local_normals+=1
            if chosen_normal is not None:
                with Image.open(chosen_normal) as im:
                    normals.append(im.convert('RGB').resize((TEXTURE_SIZE,TEXTURE_SIZE),Image.BICUBIC)
                                   .transpose(Image.FLIP_TOP_BOTTOM).tobytes())
                have_normals=True
            else:
                normals.append(blank_normal)
        tex=self.ctx.texture_array((TEXTURE_SIZE,TEXTURE_SIZE,len(frames)),3,data=b''.join(frames))
        ntex=self.ctx.texture_array((TEXTURE_SIZE,TEXTURE_SIZE,len(normals)),3,data=b''.join(normals))
        for item in (tex,ntex):
            item.repeat_x=True;item.repeat_y=True
            item.build_mipmaps()
            item.filter=(moderngl.LINEAR_MIPMAP_LINEAR,moderngl.LINEAR)
            try:item.anisotropy=16.0
            except Exception:pass
        print(f'Material: {TEXTURE_SIZE}px; Poly Haven {loaded_color} colors / {loaded_normal} normals; '
              f'{loaded_local_normals} bundled detail normals; 20 layers total')
        return tex,ntex,have_normals

    def chunk(self,index,data=None):
        if data is None:
            data=make_chunk(index*CHUNK_LEN)
        vbo=self.ctx.buffer(data.tobytes())
        vao=self.ctx.vertex_array(self.prog,[(vbo,'3f 3f 2f 1f','in_pos','in_normal','in_uv','in_layer')])
        return (vbo,vao,len(data))

    def _chunk_worker(self):
        while not self.worker_stop.is_set():
            try: generation,index=self.todo.get(timeout=.15)
            except queue.Empty:continue
            if generation!=self.generation:
                continue
            try:
                data=make_chunk(index*CHUNK_LEN)
                if generation==self.generation:
                    self.ready.put((generation,index,data),timeout=.5)
            except queue.Full:
                pass
            except Exception as exc:
                print(f'Chunk {index} mesh generation failed: {exc}',file=sys.stderr)
                self.ready.put((generation,index,None))

    def keep_chunks(self):
        current=max(0,math.floor(self.distance/CHUNK_LEN))
        wanted=set(range(max(0,current-RETAIN_BEHIND),current+PREFETCH_AHEAD+1))
        # Process at most one completed upload each frame, minimizing GPU stalls.
        for _ in range(UPLOADS_PER_FRAME):
            try: gen,index,data=self.ready.get_nowait()
            except queue.Empty:break
            self.pending.discard(index)
            if gen==self.generation and index in wanted and index not in self.chunks and data is not None:
                start=time.perf_counter()
                self.chunks[index]=self.chunk(index,data)
                self.chunk_upload_ms=(time.perf_counter()-start)*1000
        for i in list(self.chunks):
            if i not in wanted:
                vbo,vao,_=self.chunks.pop(i);vao.release();vbo.release()
        # Prefetch closest missing chunks first. Worker never uses OpenGL.
        order=sorted(wanted,key=lambda x:(abs(x-current),x))
        for i in order:
            if i not in self.chunks and i not in self.pending:
                try:self.todo.put_nowait((self.generation,i))
                except queue.Full:break
                self.pending.add(i)

    def handle(self):
        for event in pygame.event.get():
            if event.type==pygame.QUIT:self.running=False
            if event.type==pygame.VIDEORESIZE:
                self.frame_size=(max(400,event.w),max(260,event.h))
            if event.type!=pygame.KEYDOWN:continue
            if event.key==pygame.K_ESCAPE:self.running=False
            elif event.key in (pygame.K_F9, pygame.K_F10):
                if self._projector_window is not None:
                    x,y=self._projector_window.position
                    try:
                        self._projector_window.position=(x,y+(-12 if event.key==pygame.K_F9 else 12))
                    except Exception as exc:
                        print(f'Kunde inte flytta fönstret: {exc}')
                        self._projector_window=None
            elif event.key==pygame.K_F7:
                self.fog_strength=max(0.,self.fog_strength-.2)
                print(f'Dimma: {self.fog_strength:.1f} (F7 mindre, F8 mer)')
            elif event.key==pygame.K_F8:
                self.fog_strength=min(3.,self.fog_strength+.2)
                print(f'Dimma: {self.fog_strength:.1f} (F7 mindre, F8 mer)')
            elif event.key in (pygame.K_SPACE,pygame.K_p):self.paused=not self.paused
            elif event.key==pygame.K_r:self.distance=0;self.elapsed=0;self.step_distance=0;self.speed=0;self.gait_strength=0;self.last_moved=0;self.gait_lateral=0;self.gait_vertical=0;self.gait_roll=0;self.brain.reset();self.view_heading=None;self.obstacle_camera_lift=0.0
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
            self.mode=self.brain.choose(self.distance,dt)
        name,target,height,stride=MOVES[self.mode]
        # SoldierBrain plans tempo; render loop only follows the target speed.
        if self.auto:
            target *= self.brain.speed_factor
        self.speed=smooth(self.speed,target,1-math.exp(-dt*(1.25 if target>self.speed else 2.6)))
        advanced=self.speed*dt
        if self.auto:
            self.distance,moved=self.brain.advance(self.distance,advanced)
            self.step_distance+=moved
            self.last_moved=moved
        else:
            self.distance+=advanced;self.step_distance+=advanced
            self.last_moved=advanced
        self.gait_strength=smooth(self.gait_strength,
                                  min(1., self.last_moved / max(0.0001,dt) / .75),
                                  1-math.exp(-dt*(7.0 if self.last_moved>0.0001 else 5.0)))
        self.height=smooth(self.height,height,1-math.exp(-dt*3.2))
        lift=self.brain.step_lift if self.auto else 0.0
        self.obstacle_camera_lift=smooth(self.obstacle_camera_lift,lift,1-math.exp(-dt*7.5))

    def camera(self):
        x,z,desired=self.brain.camera_pose(self.distance) if self.auto else route(self.distance)
        # A human head cannot instantaneously reverse 180 degrees.
        if self.view_heading is None:
            self.view_heading=desired
        delta=math.atan2(math.sin(desired-self.view_heading),math.cos(desired-self.view_heading))
        dt=min(.10,max(.0,self.last_dt))
        # Head movement faster than body turning, but never snaps.
        # Body turns slowly when inspecting or reversing, faster in a moving arc.
        turn_rate=(1.15 if self.auto and self.brain.state=='turn_back' else
                   1.75 if self.auto else 2.25)
        step=max(-turn_rate*dt,min(turn_rate*dt,delta))
        self.view_heading+=step
        if self.auto:self.brain.heading_actual=self.view_heading
        heading=self.view_heading
        stride=MOVES[self.mode][3]
        targets=gait_targets(self.mode,self.speed,stride,self.step_distance,
                             self.gait_strength)
        gait_alpha=1.-math.exp(-dt*6.0)
        self.gait_lateral=smooth(self.gait_lateral,targets[0],gait_alpha)
        self.gait_vertical=smooth(self.gait_vertical,targets[1],gait_alpha)
        self.gait_roll=smooth(self.gait_roll,targets[2],gait_alpha)
        # Apply the current frame's stabilized lean, not the previous one.
        roll_target=(self.brain.roll if self.auto else 0.)+self.gait_roll
        self.camera_roll=smooth(self.camera_roll,roll_target,
                                1.-math.exp(-dt*4.0))
        lateral=self.gait_lateral
        bob=self.gait_vertical
        breath=(.0036+.002*min(1.,self.speed/3))*math.sin(self.elapsed*1.55)
        x+=math.cos(heading)*lateral
        z-=math.sin(heading)*lateral
        # SoldierBrain owns both the head lean and the forward/side peek.
        # All components settle smoothly when the inspection ends.
        if self.auto:
            shoulder=self.brain.peek_shift
            forward_lean=self.brain.peek_forward
            x+=math.cos(heading)*shoulder+math.sin(heading)*forward_lean
            z-=math.sin(heading)*shoulder-math.cos(heading)*forward_lean
        # Hunched movement keeps the head *low and slightly forward*, rather
        # than rocking the whole camera sideways like upright running.
        crouch=max(0.,min(1.,(1.42-self.height)/.40))
        x+=math.sin(heading)*.075*crouch
        z+=math.cos(heading)*.075*crouch
        eye=(x,self.height+bob+breath+self.obstacle_camera_lift,z)
        heading=heading+self.look+(self.brain.look_offset if self.auto else 0.)
        eye_y=eye[1]
        pitch=self.brain.gaze_pitch if self.auto else 0.0
        aim=(x+math.sin(heading)*12,
             eye_y-.085-.14*crouch+math.tan(pitch)*12,
             z+math.cos(heading)*12)
        return eye,aim

    def draw(self):
        ww,hh=pygame.display.get_surface().get_size()
        self.ctx.viewport=(0,0,ww,hh)
        self.ctx.clear(.18,.23,.29,1.0,depth=1.0)
        eye,aim=self.camera()
        # Sun and sky have no translational parallax. Only orientation matters.
        forward=np.asarray(aim,dtype='f4')-np.asarray(eye,dtype='f4')
        forward/=max(1e-8,float(np.linalg.norm(forward)))
        nominal_up=np.array((math.sin(self.camera_roll),math.cos(self.camera_roll),0.0),dtype='f4')
        right=np.cross(forward,nominal_up)
        right/=max(1e-8,float(np.linalg.norm(right)))
        up=np.cross(right,forward)
        self.sky_prog['sky_right'].value=tuple(float(v) for v in right)
        self.sky_prog['sky_up'].value=tuple(float(v) for v in up)
        self.sky_prog['sky_forward'].value=tuple(float(v) for v in forward)
        self.sky_prog['view_aspect'].value=ww/hh
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.sky_vao.render(moderngl.TRIANGLES)
        self.ctx.enable(moderngl.DEPTH_TEST)
        mat=perspective(CAMERA_VERTICAL_FOV,ww/hh,.045,FAR) @ view_from(eye,aim,self.camera_roll)
        self.prog['mvp'].write(mat.T.tobytes())
        self.prog['camera_position'].value=eye
        self.prog['fog_strength'].value=self.fog_strength
        # Eight nearest deterministic lights; GPU only gets a bounded payload.
        emitters=nearby_lanterns(self.distance,35.0)
        self.prog['lamp_count'].value=len(emitters)
        if emitters:
            # ModernGL array members may be exposed via base name or [0].
            self.lamp_uniform.write(np.asarray(emitters+[(0.,0.,0.)]*(8-len(emitters)),dtype='f4').tobytes())
        self.texture.use(location=0)
        self.normal_texture.use(location=1)
        for i in sorted(self.chunks):self.chunks[i][1].render()
        pygame.display.flip()
    def run(self):
        try:
            while self.running:
                now=time.monotonic();dt=min(.055,now-self.last);self.last=now
                self.handle();self.update(dt);self.keep_chunks();self.draw()
                fps=1/max(.001,dt);self.fps=.9*self.fps+.1*fps if self.fps else fps
                ms=dt*1000
                self.frame_max_ms=max(ms,self.frame_max_ms)
                self.frame_mean_ms=.95*self.frame_mean_ms+.05*ms if self.frame_mean_ms else ms
                self.ui_timer+=dt
                if self.ui_timer>.3:
                    self.ui_timer=0
                    name=MOVES[self.mode][0]
                    pygame.display.set_caption(f'3D SKYTTEGRAV V2.9 | {self.distance:06.0f} m | {self.brain.phase if self.auto else name} | {name} {self.speed:.1f} m/s | {self.fps:.0f} FPS | max {self.frame_max_ms:.0f}ms · upload {self.chunk_upload_ms:.0f}ms | 0 AUTO · F9/F10 FLYTTA · SPACE PAUS · R RESET · ESC AVSLUTA')
                pygame.time.wait(1)
        finally:
            for vbo,vao,_ in self.chunks.values():vao.release();vbo.release()
            self.worker_stop.set();self.worker.join(timeout=1.0)
            self.normal_texture.release();self.texture.release();self.prog.release();self.sky_prog.release()
            pygame.quit()

if __name__=='__main__':
    try:Trench().run()
    except Exception as error:
        print(f'3D-test could not start: {type(error).__name__}: {error}',file=sys.stderr)
        raise
