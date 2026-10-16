import ast
import random
import unittest
from pathlib import Path
from unittest import mock
import numpy as np
import pygame
from test_v391_atomic_streaming import game as g
import test_v391_atomic_streaming as atomic
import test_demo_mode as demo
import test_soldier_grounding as grounding

class SeedTests(unittest.TestCase):
 def tearDown(self):g.set_world_seed(g.DEFAULT_SEED)
 def world(self):
  t=atomic.AtomicJumpTests().new_world((0,1,2));t.world_seed=g.SEED
  t.demo_pending=False;t.demo_results=[];t.demo_targets=();t.demo_keys=set()
  t.shot_mesh_cache={8:object()};t.shot_chunk_meshes={0:object()};t.last_world_shot_meshes=(object(),)
  t.mesh_cache[8]=object();t.home_chunk_data=np.zeros((6,9),dtype='f4')
  t.battlefield=mock.Mock();t.enemy_renderer=mock.Mock(_alive_palette={1:object()},_fallen={1:object()})
  t.shadow_renderer=mock.Mock(world_vaos={0:(object(),mock.Mock())})
  t.ctx=mock.Mock();t.prog=mock.Mock()
  t.chunk=mock.Mock(side_effect=lambda index,data=None:(mock.Mock(),mock.Mock(),6))
  return t
 def test_default_generator_and_raycast_source_unchanged(self):
  self.assertEqual(g.DEFAULT_SEED,1944)
  old=ast.parse(Path('manual_validation/before_game.py').read_text());new=ast.parse(Path('trench_3d_test.py').read_text())
  def find(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
  for name in ('noise','route','floor_y','make_chunk','fieldwork_prop'):
   self.assertEqual(ast.dump(find(old,name)),ast.dump(find(new,name)),name)
 def test_new_seed_clears_world_resources_same_seed_retains_world(self):
  t=self.world();old=list(t.chunks.values());shadow=t.shadow_renderer.world_vaos[0][1]
  state=random.getstate()
  t.ready.put((t.generation,8,(np.zeros((6,9),dtype='f4'),object())))
  with mock.patch.object(g.moderngl,'DEPTH_TEST',2,create=True),mock.patch.object(g,'StartupScreen'),mock.patch.object(g,'make_chunk',side_effect=lambda s:np.full((6,9),g.SEED,dtype='f4')):
   self.assertTrue(t.restart_world(98765))
  self.assertEqual(g.SEED,98765);self.assertEqual(t.world_seed,98765)
  self.assertTrue(np.all(t.home_chunk_data==98765))
  self.assertEqual(t.mesh_cache,{});self.assertEqual(t.shot_mesh_cache,{})
  self.assertTrue(t.ready.empty());self.assertTrue(t.todo.empty())
  self.assertEqual(t.last_world_shot_meshes,());self.assertEqual(t.shadow_renderer.world_vaos,{})
  shadow.release.assert_called_once()
  for vbo,vao,_ in old:self.assertTrue(vbo.released);self.assertTrue(vao.released)
  self.assertEqual(t.enemy_renderer._fallen,{})
  self.assertEqual(random.getstate(),state)
  generation=t.generation;home=t.home_chunk_data
  self.assertTrue(t.restart_world());self.assertEqual(g.SEED,98765)
  self.assertIs(t.home_chunk_data,home);self.assertEqual(t.generation,generation+1)
 def test_spawn_entry_explicit_seed_and_reproducibility(self):
  with mock.patch.object(g,'make_chunk',side_effect=lambda s:(g.SEED,g.route(s),list(g.modern_fieldwork_layout(s)))):
   a=g.generate_chunk_array(0,44123);b=g.generate_chunk_array(0,44223);c=g.generate_chunk_array(0,44123)
  self.assertNotEqual(a,b);self.assertEqual(a,c)
 def test_seed_switch_invalidates_integrated_route_cache(self):
  g.set_world_seed(1944);original=g.route(180.)
  g.set_world_seed(98765);self.assertEqual(g._ROUTE,[(0.,0.,0.)])
  changed=g.route(180.);self.assertNotEqual(original,changed)
  g.set_world_seed(1944);self.assertEqual(g.route(180.),original)
  g.set_world_seed(98765);self.assertEqual(g.route(180.),changed)
 def test_pending_shot_blocks_direct_restart(self):
  t=self.world();t.demo_pending=True;generation=t.generation
  self.assertFalse(t.restart_world(7788));self.assertEqual(g.SEED,1944);self.assertEqual(t.generation,generation)
  self.assertIn('SPACE',t.demo_notice)

class InputTests(demo.DemoTests):
 def test_s_r_repeat_and_pending(self):
  with mock.patch.object(self.t,'restart_world') as restart:
   self.send(self.key(pygame.K_s),self.key(pygame.K_s,True),self.key(pygame.K_r))
   self.assertEqual(restart.call_count,1);self.assertNotEqual(restart.call_args.args[0],g.SEED)
   self.send(self.key(pygame.K_s,True));self.assertEqual(restart.call_count,1)
   self.t.demo_pending=True
   self.send(self.key(pygame.K_r));self.assertEqual(restart.call_count,1)

class WeaponTests(grounding.GroundingTests):
 def test_living_grip_and_corpse_body_equal_baseline(self):
  import gltf_actor
  namespace=vars(gltf_actor).copy()
  tree=ast.parse(Path('demo_polish_validation/before_renderer.py').read_text())
  node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TacticalEnemyRenderer')
  exec(compile(ast.Module(body=[node],type_ignores=[]),'baseline','exec'),namespace)
  cls=namespace['TacticalEnemyRenderer'];old=cls.__new__(cls);old.asset=self.r.asset
  def before():return old.collect_instances([self.a],lambda s:(0.,0.,0.),lambda s:0.)[0][1]
  for pose in ('stand','aim','walk','run'):
   self.a.pose_preview=pose;self.a.total_time=.4
   np.testing.assert_array_equal(before(),self.sample()[1])
  self.a.pose_preview=None;self.a.eliminate('manual_demo')
  for tm in (0.,.65,1.5,5.):
   self.a.state_time=tm
   np.testing.assert_array_equal(before()[:15],self.sample()[1][:15])
 def test_released_rifle_lies_low_and_body_unchanged(self):
  self.sample();self.a.eliminate('manual_demo');self.a.state_time=4
  model,p,_=self.sample()
  q=self.r._posed_points(p,self.r.asset.primitives[-1:])
  self.assertLess(np.ptp(q[:,1]),.30)
  self.assertGreater(q[:,1].min(),-.012);self.assertLess(q[:,1].min(),.025)
  self.assertGreater(q[:,0].mean(),.45)
  self.assertLess(abs(p[15,1,2]),.25)
  self.a.state_time=8;np.testing.assert_array_equal(p,self.sample()[1])
if __name__=='__main__':unittest.main()
