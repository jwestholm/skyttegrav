import unittest
from pathlib import Path
import numpy as np
from gltf_actor import TacticalEnemyRenderer as Renderer,GLBCharacter
from enemy_system import EnemyAgent,EnemySpec
from skeletal_pose import _bind_joints

class GroundingTests(unittest.TestCase):
 def setUp(self):
  self.r=Renderer.__new__(Renderer)
  self.r.asset=GLBCharacter(Path(__file__).resolve().parents[1]/'assets/characters/tactical/soldier.glb')
  self.r._prepare_contacts()
  self.a=EnemyAgent(EnemySpec(0,4.,0.,'unaware'))
 def sample(self,y=0):return self.r.collect_instances([self.a],lambda s:(0.,y,0.),lambda s:0.)[0]
 def test_leg_lengths_and_forward_knees(self):
  b=_bind_joints()
  for mode in ('stand','walk','run'):
   for t in np.linspace(0,1,13):
    self.a.total_time=float(t);p=self.r.living_palette(self.a,mode)
    np.testing.assert_array_equal(p,self.r.living_palette(self.a,mode))
    for i in range(2):
     k=9+i*3
     hip=(p[k]@np.r_[b['hips'][i],1])[:3]
     knee=(p[k+1]@np.r_[b['knees'][i],1])[:3]
     ankle=(p[k+2]@np.r_[b['ankles'][i],1])[:3]
     self.assertLess(abs(np.linalg.norm(knee-hip)-np.linalg.norm(b['knees'][i]-b['hips'][i])),1e-5)
     self.assertLess(abs(np.linalg.norm(ankle-knee)-np.linalg.norm(b['ankles'][i]-b['knees'][i])),1e-5)
     axis=ankle-hip;axis/=np.linalg.norm(axis)
     bend=knee-hip-axis*np.dot(knee-hip,axis)
     self.assertGreater(bend[2],0.)
     self.assertGreater(ankle[1],.14)
     self.assertLess(abs(knee[0]-hip[0]),.025)
     self.assertGreater(knee[0]*(1 if i else -1),.1)
 def test_corpse_world_pose_does_not_follow_later_gaze(self):
  self.sample();self.a.eliminate('manual_demo');self.a.state_time=2.
  model,p,_=self.sample()
  later=self.r.collect_instances([self.a],lambda s:(0.,0.,0.),lambda s:.6)[0]
  np.testing.assert_allclose(model[None]@p,later[0][None]@later[1],atol=2e-6)
 def test_boot_bind_yaw_corrected_only_while_moving(self):
  p=self.r.living_palette(self.a,'run')
  for i,original in enumerate((-.5168,.1858)):
   axis=np.array((np.sin(original),0.,np.cos(original)))
   corrected=p[11+3*i,:3,:3]@axis
   self.assertLess(abs(np.arctan2(corrected[0],corrected[2])),.12)
 def test_full_visible_mesh_floor_and_stable_corpse(self):
  vertices=np.concatenate([p.vertices for p in self.r.asset.primitives[:-1]])
  owner=vertices[np.arange(len(vertices)),8+vertices[:,12:16].argmax(1)].astype(int)
  for height,slope in ((0.,0.),(1.7,0.),(-.4,.12)):
   self.r._fallen={};self.a.dead=False;self.a.state='idle';self.sample(height)
   self.r.ground_height=lambda a,x,z:height+slope*z
   self.a.eliminate('manual_demo')
   for tm in (0.,.4,.9,1.5,5.):
    self.a.state_time=tm;model,p,_=self.sample(height)
    q=self.r._posed_points(p,self.r.asset.primitives[:-1]);w=q@model[:3,:3].T+model[:3,3]
    gap=w[:,1]-(height+slope*w[:,2])
    self.assertGreater(gap.min(),-.012)
    if tm>=1.5:
     self.assertLess(gap.min(),.05)
     self.assertLess(gap[owner==1].min(),.05)
     if tm==1.5:final=p.copy()
     else:np.testing.assert_array_equal(p,final)
  self.assertLess(len(self.r._contact_parts[0][0]),500)
if __name__=='__main__':unittest.main()
