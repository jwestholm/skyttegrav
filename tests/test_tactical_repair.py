import unittest
from pathlib import Path
import numpy as np
from gltf_actor import TacticalEnemyRenderer as Renderer,GLBCharacter
from enemy_system import EnemyAgent,EnemySpec
from skeletal_pose import _bind_joints

class RepairTests(unittest.TestCase):
 def setUp(self):
  self.r=Renderer.__new__(Renderer)
  self.r.asset=GLBCharacter(Path(__file__).resolve().parents[1]/'assets/characters/tactical/soldier.glb')
  self.a=EnemyAgent(EnemySpec(0,5.,0.,'unaware'))
 def sample(self):return self.r.collect_instances([self.a],lambda s:(0.,0.,0.),lambda s:0.)[0][1]
 def test_rifle_size_and_two_hand_grip(self):
  gun=self.r.asset.primitives[-1].vertices
  self.assertLess(float(np.ptp(gun[:,2])),.9)
  b=_bind_joints()
  for mode in ('stand','walk','run','aim','fire'):
   for t in (0.,.2,.4,.8):
    self.a.total_time=t;p=self.r.living_palette(self.a,mode)
    for i in range(2):
     hand=(p[5+i*3]@np.r_[b['hands'][i],1])[:3]
     grip=(p[15]@np.array((.02,1.02,.45 if i==0 else .27,1)))[:3]
     self.assertLess(np.linalg.norm(hand-grip),.025)
     shoulder=(p[3+i*3]@np.r_[b['shoulders'][i],1])[:3]
     elbow=(p[4+i*3]@np.r_[b['elbows'][i],1])[:3]
     self.assertLess(abs(np.linalg.norm(elbow-shoulder)-np.linalg.norm(b['elbows'][i]-b['shoulders'][i])),1e-5)
 def test_death_preserves_body_shape_and_final_pose(self):
  live=self.sample();before=self.r._posed_points(live,self.r.asset.primitives[:-1])
  self.a.eliminate('manual_demo')
  final=None
  for t in (.0,.2,.7,1.5,6.):
   self.a.state_time=t;p=self.sample();after=self.r._posed_points(p,self.r.asset.primitives[:-1])
   self.assertGreaterEqual(float(after[:,1].min()),0.)
   # Whole-body rigid transform: sampled pair distances cannot collapse.
   np.testing.assert_allclose(np.linalg.norm(after[::97]-after[0],axis=1),np.linalg.norm(before[::97]-before[0],axis=1),atol=2e-6)
   if t==1.5:
    final=p.copy();self.assertGreater(float(np.ptp(after[:,2])),1.6)
   if t==6.:np.testing.assert_array_equal(final,p)
  self.r.collect_instances([],lambda s:(0,0,0),lambda s:0)
  self.assertFalse(self.r._fallen);self.assertFalse(self.r._alive_palette)
if __name__=='__main__':unittest.main()
