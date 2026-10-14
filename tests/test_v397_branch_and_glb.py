"""V3.9.7: no speculative side-clearance and real glTF four-weight skin rig."""
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from test_v391_atomic_streaming import game
from gltf_actor import GLBCharacter,GLBError,GLBDocument,_q_slerp


def synthetic_glb(path):
    """Minimal valid skinned GLB with two joints and an actual animation clip."""
    blob=bytearray();views=[];accessors=[]
    def accessor(array,kind,component=5126):
        array=np.ascontiguousarray(array)
        while len(blob)%4:blob.append(0)
        start=len(blob);blob.extend(array.tobytes())
        view=len(views);views.append(dict(buffer=0,byteOffset=start,byteLength=array.nbytes))
        idx=len(accessors)
        accessors.append(dict(bufferView=view,componentType=component,count=len(array),type=kind))
        return idx
    pos=accessor(np.array([[-.5,0,0],[.5,0,0],[0,1.8,0]],dtype='f4'),'VEC3')
    norm=accessor(np.tile(np.array([0,0,1],dtype='f4'),(3,1)),'VEC3')
    uv=accessor(np.array([[0,0],[1,0],[.5,1]],dtype='f4'),'VEC2')
    joint=accessor(np.array([[0,1,0,0]]*3,dtype='<u2'),'VEC4',5123)
    weight=accessor(np.array([[.5,.5,0,0]]*3,dtype='f4'),'VEC4')
    idx=accessor(np.array([0,1,2],dtype='<u2'),'SCALAR',5123)
    ibm=accessor(np.array([np.eye(4),np.eye(4)],dtype='f4').transpose(0,2,1).reshape((2,16)),'MAT4')
    times=accessor(np.array([0,1],dtype='f4'),'SCALAR')
    quats=accessor(np.array([[0,0,0,1],[0,0,.70710677,.70710677]],dtype='f4'),'VEC4')
    gl=dict(asset=dict(version='2.0'),buffers=[dict(byteLength=len(blob))],
            bufferViews=views,accessors=accessors,
            nodes=[dict(mesh=0,skin=0,children=[1]),dict(children=[2]),dict()],
            meshes=[dict(primitives=[dict(attributes=dict(POSITION=pos,NORMAL=norm,
                     TEXCOORD_0=uv,JOINTS_0=joint,WEIGHTS_0=weight),indices=idx)])],
            skins=[dict(joints=[1,2],inverseBindMatrices=ibm)],
            animations=[dict(name='Walk',samplers=[dict(input=times,output=quats)],
                        channels=[dict(sampler=0,target=dict(node=2,path='rotation'))])],
            scenes=[dict(nodes=[0])],scene=0)
    raw=json.dumps(gl,separators=(',',':')).encode('utf8')
    raw+=b' ' * (-len(raw)%4)
    blob.extend(b'\x00'*((-len(blob))%4))
    data=b'glTF'+struct.pack('<II',2,12+8+len(raw)+8+len(blob))
    data+=struct.pack('<I4s',len(raw),b'JSON')+raw
    data+=struct.pack('<I4s',len(blob),b'BIN\x00')+blob
    path.write_bytes(data)


class BranchDecisionTests(unittest.TestCase):
    def test_unobserved_branch_never_entered_even_if_dugout(self):
        b=game.SoldierBrain();i=0
        m=game.junction_marker(i)
        phases=[]
        s=m-6.1
        for _ in range(1000):
            mode=b.choose(s,1/60)
            phases.append(b.state)
            # The normally advancing soldier must actually traverse the room.
            speed=game.MOVES[mode][1]*b.speed_factor
            s,moved=b.advance(s,speed/60)
            if s>m+4.7:
                b.choose(s,1/60)
                break
        self.assertEqual(b.last_branch_decision,(i,'observe_only'))
        # V3.9.9 intentionally restores a short corner stop before passing.
        self.assertIn('observe_peek',phases)
        self.assertIn('observe_assess',phases)
        self.assertNotIn('explore',phases)
        self.assertGreater(s,m+4.6)
        self.assertIsNone(b.passing_branch)
        self.assertNotIn('move_to_mouth',phases)
        self.assertNotIn('turn_in',phases)
        self.assertNotIn('dash',phases)
        self.assertNotIn('dugout_clear',phases)
        self.assertEqual(b.state,'main')
        self.assertIn(i,b.visited)

    def test_only_real_branch_evidence_allows_entry(self):
        b=game.SoldierBrain();i=0
        self.assertTrue(b.report_branch_evidence(i,'localized_sound',.85))
        m=game.junction_marker(i)
        phases=[]
        for _ in range(75):
            b.choose(m-2.25,.1)
            phases.append(b.state)
            if b.state=='move_to_mouth':break
        self.assertEqual(b.last_branch_decision,(i,'investigate'))
        self.assertIn('peek',phases)
        self.assertEqual(b.state,'move_to_mouth')

    def test_weak_unlocalized_evidence_does_not_force_entry(self):
        b=game.SoldierBrain()
        b.report_branch_evidence(4,'movement',.4)
        self.assertFalse(b._should_enter_branch(4))
        with self.assertRaises(ValueError):b.report_branch_evidence(3,'seeded_enemy_guess',1.)
        with self.assertRaises(ValueError):b.report_branch_evidence(3,'seen_enemy',float('nan'))
        with self.assertRaises(ValueError):b.report_branch_evidence(3,'seen_enemy',1.1)

    def test_memory_bounded_even_in_endless_world(self):
        b=game.SoldierBrain()
        for i in range(300):b.report_branch_evidence(i,'seen_enemy')
        self.assertLessEqual(len(b.branch_evidence),24)
        self.assertIn(299,b.branch_evidence)

    def test_t_y_x_junction_dressing_is_deterministic_and_grounded(self):
        types=set()
        for index in range(16):
            kinds=game.junction_kind(index)
            types.add(kinds)
            def generate():
                builder=game.MeshBuilder()
                for side in game.junction_sides(index):
                    game.junction_decorations(builder,index,side)
                return builder.as_array()
            a,b=generate(),generate()
            self.assertEqual(a.shape,b.shape)
            self.assertTrue(np.array_equal(a,b))
            self.assertTrue(np.isfinite(a).all())
        self.assertTrue({'T','Y','X'}.issubset(types))

    def test_seeded_dugout_styles_reproducible_and_diverse(self):
        styles=[game.dugout_style(i) for i in range(32)]
        self.assertGreaterEqual(len(set(styles)),3)
        self.assertEqual(styles,[game.dugout_style(i) for i in range(32)])
        self.assertTrue(all(s in ('bunk','supply','aid','signal') for s in styles))
        # Geometry is built using already existing world-space anchors.
        for style in ('bunk','aid','supply','signal'):
            idx=next(i for i in range(100) if game.dugout_style(i)==style and game.branch_type(i)=='dugout')
            mesh=game.MeshBuilder()
            game.dugout_furnishings(mesh,idx,game.junction_side(idx),game.branch_length(idx))
            data=mesh.as_array()
            self.assertTrue(np.isfinite(data).all())
            self.assertGreater(len(data),100)


class RealGLBSkinTests(unittest.TestCase):
    def test_real_gltf_weights_and_animation_change_joint_palette(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'humanoid.glb';synthetic_glb(p)
            model=GLBCharacter(p)
            self.assertEqual(model.joint_count,2)
            self.assertEqual(len(model.primitives),1)
            self.assertEqual(model.choose_clip('walk'),'Walk')
            self.assertAlmostEqual(model.primitives[0].vertices[0,12],.5)
            start,mesh=model.matrices('Walk',0.)
            rotated,_=model.matrices('Walk',.5)
            self.assertEqual(start.shape,(2,4,4))
            self.assertTrue(np.isfinite(rotated).all())
            self.assertGreater(np.max(abs(start-rotated)),.15)
            self.assertAlmostEqual(model.height,1.8,places=3)

    def test_clip_blending_and_reaction_without_shearing_joints(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'humanoid.glb';synthetic_glb(p)
            model=GLBCharacter(p)
            first=model.local_pose('Walk',.0)
            other=model.local_pose('Walk',.55)
            for part in (0.,.25,.5,.75,1.):
                blended=model.blend_pose(first,other,part)
                pal,_=model.matrices_for_pose(blended)
                self.assertTrue(np.isfinite(pal).all())
                self.assertAlmostEqual(float(np.linalg.norm(blended[2][1])),1.,places=5)
            with self.assertRaises(ValueError):model.blend_pose(first,other,float('nan'))

    def test_glb_gpu_draw_and_shadow_reuse_same_bone_palette(self):
        from unittest.mock import patch
        from types import ModuleType
        from gltf_actor import GLBSkinnedRenderer
        from enemy_system import EnemyAgent,EnemySpec
        class Resource:
            def __init__(self,size=12):
                self.size=size;self.calls=0;self.value=None;self.filter=None
            def write(self,*a):self.calls+=1
            def use(self,*a,**k):pass
            def render(self,*a):self.calls+=1
            def release(self):pass
            def build_mipmaps(self):pass
            def __getitem__(self,item):return Resource()
        class ShaderProgram:
            def __init__(self):self.uniforms={}
            def __getitem__(self,name):
                if name not in self.uniforms:self.uniforms[name]=Resource()
                return self.uniforms[name]
            def release(self):pass
        class Ctx:
            def program(self,**kw):return ShaderProgram()
            def texture(self,*a,**kw):return Resource()
            def buffer(self,data):return Resource(len(data))
            def vertex_array(self,*a,**kw):return Resource()
        stub=ModuleType('moderngl')
        stub.NEAREST=1;stub.LINEAR=2;stub.TRIANGLES=4
        with tempfile.TemporaryDirectory() as td,patch.dict('sys.modules',{'moderngl':stub}):
            p=Path(td)/'humanoid.glb';synthetic_glb(p)
            r=GLBSkinnedRenderer(Ctx(),p,(.35,.08,.9),(-.3,.4,-.6))
            a=EnemyAgent(EnemySpec(5,32.,0.,'unaware'))
            a.pose_preview='walk';a.total_time=.5
            instances=r.collect_instances([a],lambda spec:(0.,0.,32.),lambda route:0.)
            self.assertEqual(len(instances),1)
            self.assertEqual(instances[0][1].shape,(2,4,4))
            r.draw([a],lambda spec:(0.,0.,32.),lambda route:0.,np.eye(4),
                   (0.,1.,0.),1.,False,[],instances=instances)
            r.draw_skeletal_shadows(np.eye(4),instances)
            self.assertGreaterEqual(r.joint_texture.calls,2)
            a.pose_preview='stand';a.total_time+=.15
            r.collect_instances([a],lambda spec:(0.,0.,32.),lambda route:0.)
            self.assertEqual(len(r._clip_state),1)
            r.collect_instances([],lambda spec:(0.,0.,32.),lambda route:0.)
            self.assertEqual(r._clip_state,{})
            r.release()

    def test_external_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'sample.glb';synthetic_glb(p)
            content=bytearray(p.read_bytes());content[0:4]=b'JUNK';p.write_bytes(content)
            with self.assertRaises(GLBError):GLBDocument(p)

    def test_quaternion_interpolation_unit_length(self):
        a=(0,0,0,1);b=(0,0,.7071068,.7071068)
        for f in (0,.2,.5,.85,1):
            q=_q_slerp(a,b,f)
            self.assertAlmostEqual(float(np.linalg.norm(q)),1.,places=6)

    def test_glb_preview_does_not_replace_live_hitboxes(self):
        import inspect
        from gltf_actor import GLBSkinnedRenderer
        src=inspect.getsource(game.Trench.draw)
        self.assertIn('self.pose_lab_index>=0 else self.enemy_renderer',src)
        self.assertNotIn('self.glb_renderer.resolve_frozen_hit',src)
        self.assertIn('in_weights',inspect.getsource(GLBSkinnedRenderer.__init__))


if __name__=='__main__':unittest.main()
