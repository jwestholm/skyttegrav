import ast,random,unittest,math
from pathlib import Path
import numpy as np
from test_v391_atomic_streaming import game as g
from test_demo_polish import SeedTests
from test_soldier_grounding import GroundingTests
from shadow_lighting import closest_shadow_lamp,lamp_shadow_weight
from enemy_system import encounter_spec,EnemyAgent,EnemySpec

class TopologyTests(unittest.TestCase):
 def tearDown(self):g.set_world_seed(1944)
 def test_real_paths_spawns_reproducibility_and_default_compatibility(self):
  old=next(n for n in ast.parse(Path('seed_shadow_validation/before_game.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='turn_for_meter')
  ns=vars(g).copy();exec(compile(ast.Module(body=[old],type_ignores=[]),'before','exec'),ns)
  state=random.getstate();paths=[];spawns=[]
  for seed in (1944,98765,44123,44223,20261016):
   g.set_world_seed(seed)
   a=np.array([g.route(s) for s in range(251)]);paths.append(a)
   t=g.Trench.__new__(g.Trench);spawns.append([t.enemy_position(encounter_spec(i,seed)) for i in (0,1)])
   if seed==1944:
    for s in np.arange(0,251,.5):self.assertEqual(g.turn_for_meter(s),ns['turn_for_meter'](s))
   g.set_world_seed(-100);g.set_world_seed(seed)
   for anchor in (240,80,160,0):g.route(anchor)
   np.testing.assert_array_equal(a,[g.route(s) for s in range(251)])
   np.testing.assert_allclose(np.linalg.norm(np.diff(a[:,:2],axis=0),axis=1),1.,atol=1e-12)
   if seed!=1944:
    distant=np.array([g.route(s) for s in range(2001)])
    self.assertGreater(np.diff(distant[:,1]).min(),.65)
    self.assertLess(np.abs(np.diff(distant[:,2])).max(),.22)
  for i,a in enumerate(paths):
   for j,b in enumerate(paths[i+1:],i+1):
    self.assertGreater(np.linalg.norm(a[-1,:2]-b[-1,:2]),5.)
    self.assertLess(np.mean(np.all(np.isclose(a,b,atol=1e-7),axis=1)),.1)
    for x,y in zip(spawns[i],spawns[j]):self.assertGreater(np.linalg.norm(np.array(x)-y),.5)
  self.assertEqual(random.getstate(),state)
 def test_s_reset_changes_route_and_r_preserves_it(self):
  from unittest import mock
  helper=SeedTests();t=helper.world();original=g.route(200)
  with mock.patch.object(g.moderngl,'DEPTH_TEST',2,create=True),mock.patch.object(g,'StartupScreen'),mock.patch.object(g,'make_chunk',return_value=np.zeros((6,9),dtype='f4')):
   t.restart_world(98765)
  changed=g.route(200);self.assertNotEqual(original,changed)
  self.assertEqual(t.enemies.world_seed,98765)
  t.restart_world();self.assertEqual(g.route(200),changed)

class LampTests(unittest.TestCase):
 def test_old_cutoff_now_fully_ready_and_switch_continuous(self):
  lights=[(0.,1.8,0.)]
  for distance in (7.49,7.51,11.9):
   camera=(0.,1.8,distance);idx=closest_shadow_lamp(lights,camera)
   self.assertEqual(idx,0);self.assertEqual(lamp_shadow_weight(lights,camera,idx),1.)
  weights=[lamp_shadow_weight(lights,(0.,1.8,d),closest_shadow_lamp(lights,(0.,1.8,d))) for d in np.arange(0,20,.05)]
  self.assertLess(np.max(np.abs(np.diff(weights))),.013)
  lights=[(0.,1.8,0.),(8.,1.8,0.)]
  for x in (3.9999,4,4.0001):
   self.assertLess(lamp_shadow_weight(lights,(x,1.8,0),closest_shadow_lamp(lights,(x,1.8,0))),1e-6)

class RifleTests(GroundingTests):
 def test_grounded_flat_rifle_across_yaw_height_and_ids(self):
  samples=[]
  for uid in (0,7,12345):
   for yaw in (-2.4,0.,1.5):
    for height,slope in ((0.,0.),(1.2,.08),(-.3,-.08)):
     self.a=EnemyAgent(EnemySpec(uid,4.,0.,'unaware'));self.r._fallen={};self.r._alive_palette={}
     self.r.ground_height=lambda a,x,z:height+slope*z
     def sample():return self.r.collect_instances([self.a],lambda s:(0,height,0),lambda s:yaw)[0]
     sample();self.a.eliminate('manual_demo')
     for tm in (0.,.5,1.5,4.):
      self.a.state_time=tm;model,p,_=sample();q=self.r._posed_points(p,self.r.asset.primitives[-1:]);w=q@model[:3,:3].T+model[:3,3]
      self.assertTrue(np.isfinite(w).all())
      gap=w[:,1]-height-slope*w[:,2]
      self.assertGreater(gap.min(),-.012)
      if tm>=1.5:
       self.assertLess(np.ptp(gap),.20);self.assertLess(gap.min(),.025)
       np.testing.assert_array_equal(p,sample()[1])
     samples.append(p[15].copy())
  self.assertFalse(np.array_equal(samples[0],samples[9]))

class EncounterTests(unittest.TestCase):
 def test_seed_plan_density_progression_and_no_respawn(self):
  from enemy_system import EnemyDirector,encounter_partner_spec
  from combat_tactics import difficulty_at
  signatures=[]
  for seed in (1944,98765,44123,44223,20261016):
   leads=[encounter_spec(i,seed) for i in range(30)]
   early=[s.route_m for s in leads if s.route_m<250]
   self.assertGreaterEqual(len(early),4);self.assertGreater(early[0],25)
   self.assertLess(max(np.diff(early+[250.])),80)
   self.assertLess(max(np.diff([s.route_m for s in leads])),80)
   signatures.append(tuple(early))
   counts=[]
   for lo,hi in ((0,250),(250,500),(500,1000)):
    selected=[s for s in leads if lo<=s.route_m<hi]
    n=sum(1+(encounter_partner_spec(s.enemy_id,seed) is not None) for s in selected)
    counts.append(n/(hi-lo))
   self.assertGreater(counts[2],counts[0])
   self.assertGreater(difficulty_at(900).accuracy_scale,difficulty_at(50).accuracy_scale)
   self.assertGreaterEqual(difficulty_at(900).reaction_grace,1.4)
   d=EnemyDirector(seed);d.update(0,20,lambda a:False)
   original=d.active[0].spec;d.active[0].eliminate('test');d.update(0,20,lambda a:False)
   d.update(0,2000,lambda a:False);d.update(0,20,lambda a:False)
   self.assertNotIn(0,d.active)
   d.reset();d.update(0,20,lambda a:False);self.assertEqual(d.active[0].spec,original)
   d.update(0,20,lambda a:False);self.assertEqual(len(d.active),len(set(d.active)))
  self.assertEqual(len(set(signatures)),5)

if __name__=='__main__':unittest.main()
