"""No-display skeletal animation, shadow and root-collision regressions."""
import importlib,math,sys,types,unittest
from unittest.mock import patch
import numpy as np
from enemy_system import EnemyAgent,EnemySpec,EnemyDirector,actor_joints,enemy_parts
from skeletal_pose import BONES,POSE_LAB,bone_matrices
from rig_renderer import to_bind_mesh,bone_for_part,SKIN_VERT,SKIN_SHADOW_VERT,SkeletalEnemyRenderer


def enemy(kit=0):
    return EnemyAgent(EnemySpec(kit,32.,-.18,'unaware'))

class FakeBuffer:
    def __init__(self,data):self.data=data;self.size=len(data);self.released=False
    def release(self):self.released=True
class FakeUniform:
    def __init__(self):self._value=None;self.payloads=[]
    def write(self,data):self.payloads.append(bytes(data))
    @property
    def value(self):return self._value
    @value.setter
    def value(self,x):self._value=x
class FakeProgram:
    def __init__(self,**kw):self.source=kw;self.uniforms={};self.released=False
    def __getitem__(self,k):return self.uniforms.setdefault(k,FakeUniform())
    def release(self):self.released=True
class FakeVAO:
    def __init__(self):self.draws=0;self.released=False
    def render(self,*args,**kw):self.draws+=1
    def release(self):self.released=True
class FakeContext:
    def __init__(self):self.programs=[];self.buffers=[];self.vaos=[]
    def program(self,**kw):
        p=FakeProgram(**kw);self.programs.append(p);return p
    def buffer(self,data):
        b=FakeBuffer(data);self.buffers.append(b);return b
    def vertex_array(self,p,layouts):
        v=FakeVAO();self.vaos.append(v);return v

class GPUSkeletonRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(sys.modules,{'moderngl':types.ModuleType('moderngl'),
                                     'pygame':types.ModuleType('pygame')}):
            cls.game=importlib.import_module('trench_3d_test')
        cls.actor=enemy()
        cls.parts=enemy_parts(cls.actor)
        cls.shapes={part[:2]:cls.game._rig_shape_template(*part[:2]) for part in cls.parts}
        for key in [('cylinder',13),('cube',10),('oval',11)]:
            cls.shapes.setdefault(key,cls.game._rig_shape_template(*key))
        cls.raw=to_bind_mesh(cls.parts,cls.shapes,cls.game.EnemyRenderer.part_model)

    def test_bind_geometry_resident_and_bounded(self):
        a=self.raw
        self.assertEqual(a.ndim,2)
        self.assertEqual(a.shape[1],11)
        self.assertLess(a.nbytes,2_000_000)
        self.assertEqual(set(a[:,9].astype(int)),set(range(16)))
        self.assertEqual(set(a[:,10].astype(int)),set(range(4)))
        self.assertTrue(np.isfinite(a).all())
        self.assertTrue(np.all((a[:,9]>=0)&(a[:,9]<len(BONES))))

    def test_all_pose_modes_have_finite_matrices(self):
        self.assertEqual(len(POSE_LAB),12)
        for name in POSE_LAB:
            with self.subTest(name=name):
                b=bone_matrices(self.actor,name)
                self.assertEqual(b.shape,(16,4,4))
                self.assertTrue(np.isfinite(b).all())
                self.assertTrue(np.allclose(b[:,3,:],(0,0,0,1)))

    def test_all_postures_grounded_no_body_below_floor(self):
        verts=np.column_stack((self.raw[:,:3],np.ones(len(self.raw))))
        bones=self.raw[:,9].astype(int)
        body=(self.raw[:,10]==0)
        for name in POSE_LAB:
            b=bone_matrices(self.actor,name)
            y=np.einsum('nij,nj->ni',b[bones],verts)[:,1]
            with self.subTest(name=name):
                self.assertGreaterEqual(float(y[body].min()),-.025)
                self.assertLess(float(y[body].max()),2.7)

    def test_low_postures_have_appropriate_height(self):
        verts=np.column_stack((self.raw[:,:3],np.ones(len(self.raw))))
        bones=self.raw[:,9].astype(int);body=(self.raw[:,10]==0)
        maxima={}
        for name in ('stand','kneel','prone','supine_sleep','fear_curl'):
            b=bone_matrices(self.actor,name)
            y=np.einsum('nij,nj->ni',b[bones],verts)[:,1]
            maxima[name]=y[body].max()
        self.assertGreater(maxima['stand'],maxima['kneel']+.12)
        self.assertGreater(maxima['kneel'],maxima['prone']+.30)
        self.assertLess(maxima['supine_sleep'],.9)
        self.assertLess(maxima['fear_curl'],1.4)

    def test_actual_gait_not_timer_only(self):
        actor=enemy();actor.hear_shot(8.)
        for i in range(10):actor.update(.05,visible=True,player_route=8.)
        moving=bone_matrices(actor)
        pos=actor.route_m
        # Drawing a second time without advancing physics must be deterministic.
        self.assertTrue(np.array_equal(moving,bone_matrices(actor)))
        self.assertEqual(actor.route_m,pos)

    def test_death_transition_is_continuous(self):
        a=enemy();old=bone_matrices(a)
        a.eliminate('torso')
        start=bone_matrices(a)
        self.assertTrue(np.allclose(old,start,atol=.02))
        a.update(.4);middle=bone_matrices(a)
        a.update(.9);end=bone_matrices(a)
        self.assertFalse(np.allclose(start,middle))
        self.assertFalse(np.allclose(middle,end))
        self.assertEqual(a.hit_regions((0.,0.,0.)),())

    def test_gpu_mesh_one_draw_per_actor_and_per_shadow_pass(self):
        c=FakeContext()
        r=SkeletalEnemyRenderer(c,self.game._rig_shape_template,
               self.game.EnemyRenderer.part_model,self.game.ACTOR_FRAG,
               self.game.SUN_DIRECTION,self.game.MOON_DIRECTION)
        try:
            self.assertLess(r.gpu_bytes,6_000_000)
            self.assertEqual(len(c.buffers),3)
            actors=[enemy(0),enemy(1),enemy(2)]
            for i,a in enumerate(actors):a.route_m=32+i*2
            cb=lambda spec:(0.,0.,spec.route_m)
            instances=r.collect_instances(actors,cb,lambda s:0.)
            self.assertEqual(len(instances),3)
            self.assertEqual(sum(v.draws for _,v,_,_ in r.models.values()),0)
            gl=types.ModuleType('moderngl');gl.TRIANGLES=4
            with patch.dict(sys.modules,{'moderngl':gl}):
                r.draw(actors,cb,lambda s:0.,np.eye(4,dtype='f4'),(0,1.5,0),1.,True,[],instances)
                r.draw_skeletal_shadows(np.eye(4,dtype='f4'),instances)
            self.assertEqual(sum(v.draws for _,v,_,_ in r.models.values()),3)
            self.assertEqual(sum(v.draws for _,_,v,_ in r.models.values()),3)
            self.assertEqual(len(r.bones_uniform.payloads),3)
            self.assertEqual(len(r.shadow_bones_uniform.payloads),3)
            self.assertTrue(all(len(data)==16*16*4 for data in r.bones_uniform.payloads))
        finally:r.release()
        self.assertTrue(all(b.released for b in c.buffers))

    def test_shadow_shader_uses_same_bone_palette(self):
        self.assertIn('bones[16]',SKIN_VERT)
        self.assertIn('bones[16]',SKIN_SHADOW_VERT)
        self.assertIn('in_prop',SKIN_SHADOW_VERT)

    def test_enemy_world_follows_shared_corridor_and_avoids_crate(self):
        g=self.game
        trench=g.Trench.__new__(g.Trench)
        trench.enemies=EnemyDirector()
        for idx in (38,50):
            ob=g.trench_obstacle(idx)
            self.assertEqual(ob.kind,'crate')
            for side in (-.18,.14):
                a=EnemyAgent(EnemySpec(23,ob.s,side,'cover'))
                trench.enemies.active[23]=a
                x,y,z=trench.enemy_position(a.spec)
                cx,cz,h=g.route(ob.s)
                lateral=(x-cx)*math.cos(h)-(z-cz)*math.sin(h)
                self.assertGreaterEqual(abs(lateral-ob.lateral),ob.width*.5+.30)
                self.assertLessEqual(lateral,g.wall_width(ob.s,1)-.35)
                self.assertGreaterEqual(lateral,-g.wall_width(ob.s,-1)+.35)

    def test_no_new_physical_hit_or_ai_authority(self):
        a=enemy()
        before=(a.route_m,a.state,a.dead)
        for state in POSE_LAB:bone_matrices(a,state)
        self.assertEqual(before,(a.route_m,a.state,a.dead))
        self.assertEqual(len(a.hit_regions((0,0,0.))),5)

if __name__=='__main__':unittest.main()
