"""V3.9.1 actual-geometry debug scrubbing tests, without GPU/SDL resources.

The real Trench controller is imported with its optional GL and pygame modules
stubbed, but all tested methods and state transitions are production code.
"""
import importlib
import math
import queue
import sys
import threading
import time
import types
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest import mock
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
with mock.patch.dict(sys.modules,{'pygame':types.ModuleType('pygame'),
                                  'moderngl':types.ModuleType('moderngl')}):
    game=importlib.import_module('trench_3d_test')

class FakeGL:
    def __init__(self):self.released=False
    def release(self):self.released=True
    def render(self):pass

class FakeContext:
    def buffer(self,*args,**kwargs):return FakeGL()
    def vertex_array(self,*args,**kwargs):return FakeGL()

class ResetCounter:
    def __init__(self):self.reset_count=0
    def reset(self):self.reset_count+=1

class AtomicJumpTests(unittest.TestCase):
    def new_world(self,available=(0,1)):
        t=game.Trench.__new__(game.Trench)
        t.ctx=FakeContext();t.prog=object()
        t.chunks={i:(FakeGL(),FakeGL(),6) for i in available}
        t.mesh_cache=OrderedDict()
        t.chunk_failures={}
        t.chunk_retry_after={}
        t.debug_jump_target=None
        t.debug_jump_requested_at=0.0
        t.debug_jump_stream_chunk=None
        t.debug_jump_saved_chunks=set()
        t.todo=queue.Queue(maxsize=16);t.ready=queue.Queue(maxsize=16)
        t.pending=set();t.generation=0;t.worker_stop=threading.Event()
        t.chunk_upload_ms=0.0
        t.distance=0.;t.speed=2.0;t.step_distance=0.
        t.last_moved=0.;t.gait_strength=0.;t.gait_lateral=0.;t.gait_vertical=0.;t.gait_roll=0.
        t.camera_roll=0.;t.height=1.55;t.view_heading=None;t.look=0.
        t.obstacle_camera_lift=0.;t.terrain_eye_base=0.
        t.brain=ResetCounter();t.enemies=ResetCounter();t.arcade=ResetCounter()
        t.player_visibility={};t.player_can_shoot={}
        t.visible_opportunity_seconds={};t.hostile_shot_counts={}
        t.perception_timer=0.;t.footstep_alert_timer=0.;t.enemy_death_pause=0.
        t.last_enemy_frame='old_snapshot';t.last_camera_viewproj='old_projection'
        t.auto=True;t.mode=5;t.paused=False;t.last_dt=1/60;t.death_age=7.
        return t

    @staticmethod
    def settle(t): t.debug_jump_requested_at=time.monotonic()-game.JUMP_KEY_SETTLE_SECONDS-1.

    @staticmethod
    def mesh():return np.zeros((6,9),dtype='f4')

    def test_autorepeat_accumulates_without_rebuilding_or_moving(self):
        t=self.new_world()
        for i in range(18):
            self.assertEqual(t.debug_jump(25),25*(i+1))
            t.keep_chunks()
        self.assertEqual(t.distance,0)
        self.assertEqual(t.debug_jump_target,450)
        self.assertEqual(t.generation,0)
        self.assertEqual(t.todo.qsize(),0)
        self.assertIn(0,t.chunks)

    def test_450_requires_three_loaded_chunks_before_camera_moves(self):
        t=self.new_world()
        t.debug_jump(450);self.settle(t);t.keep_chunks()
        self.assertEqual(t.generation,1)
        self.assertEqual([t.todo.get_nowait()[1] for _ in range(3)],[5,6,4])
        self.assertEqual(t.distance,0)
        for i,idx in enumerate((5,6,4)):
            t.ready.put_nowait((1,idx,self.mesh()))
            t.keep_chunks()
            if i<2:
                self.assertEqual(t.distance,0,'partial geometry may not move camera')
                self.assertIn(0,t.chunks,'old scene must stay alive while staging')
        self.assertEqual(t.distance,450)
        self.assertIsNone(t.debug_jump_target)
        self.assertEqual(t.brain.reset_count,1)
        self.assertEqual(t.enemies.reset_count,1)
        self.assertEqual(t.arcade.reset_count,1)
        self.assertIsNone(t.last_enemy_frame)
        self.assertNotIn(0,t.chunks)
        self.assertTrue({4,5,6}.issubset(t.chunks))

    def test_cached_landing_is_instant_and_does_not_schedule_cpu(self):
        t=self.new_world(available=(0,1,2))
        t.debug_jump(25);self.settle(t);t.keep_chunks()
        self.assertEqual(t.distance,25)
        self.assertEqual(t.generation,0)
        self.assertTrue(all(i not in {0,1} for _,i in list(t.todo.queue)))
        self.assertEqual(t.arcade.reset_count,1)

    def test_missing_cached_mesh_restored_on_main_thread_one_per_frame(self):
        t=self.new_world(available=(0,1))
        for i in (4,5,6):t.mesh_cache[i]=self.mesh()
        t.debug_jump(450);self.settle(t)
        t.keep_chunks();self.assertIn(5,t.chunks)
        self.assertNotIn(6,t.chunks);self.assertEqual(t.distance,0)
        t.keep_chunks();self.assertIn(6,t.chunks)
        self.assertNotIn(4,t.chunks);self.assertEqual(t.distance,0)
        t.keep_chunks();self.assertEqual(t.distance,450)
        self.assertTrue(all(i not in {4,5,6} for _,i in list(t.todo.queue)),
                        'no worker needed for cached landing chunks')

    def test_stale_generation_cannot_authorize_jump(self):
        t=self.new_world()
        t.debug_jump(450);self.settle(t);t.keep_chunks()
        t.ready.put_nowait((0,5,self.mesh()))
        t.keep_chunks()
        self.assertNotIn(5,t.chunks)
        self.assertEqual(t.distance,0)
        t.ready.put_nowait((1,5,self.mesh()))
        t.keep_chunks()
        self.assertIn(5,t.chunks)
        self.assertEqual(t.distance,0)

    def test_changing_target_invalidates_only_after_key_repeat_settles(self):
        t=self.new_world()
        t.debug_jump(450);self.settle(t);t.keep_chunks()
        self.assertEqual(t.generation,1)
        t.debug_jump(25);t.keep_chunks()
        self.assertEqual(t.generation,1)
        self.assertEqual(t.distance,0)
        self.settle(t);t.keep_chunks()
        self.assertEqual(t.generation,1)
        self.assertEqual(t.debug_jump_stream_chunk,5)  # 475 is still 400–480
        t.debug_jump(25);self.settle(t);t.keep_chunks()
        self.assertEqual(t.generation,2)
        self.assertEqual(t.debug_jump_stream_chunk,6)  # now 480–560
        self.assertIn(0,t.chunks)
        self.assertEqual(t.distance,0)

    def test_repeated_mesh_failure_keeps_old_scene_and_stops_retrying(self):
        t=self.new_world()
        t.debug_jump(450);self.settle(t);t.keep_chunks()
        for i in range(game.JUMP_MESH_RETRIES):
            t.ready.put_nowait((t.generation,5,None))
            t.keep_chunks()
        self.assertEqual(t.chunk_failures[5],game.JUMP_MESH_RETRIES)
        self.assertNotIn(5,t.pending)
        self.assertNotIn(5,t.chunks)
        self.assertEqual(t.distance,0)
        self.assertIn(0,t.chunks)
        self.assertIn(5,t.chunk_retry_after)
        # A transient build error is not a permanent hole: retry after cooldown.
        t.chunk_retry_after[5]=time.monotonic()-1
        t.keep_chunks()
        self.assertIn(5,t.pending)
        self.assertNotIn(5,t.chunk_failures)

    def test_cache_is_bounded_and_never_stores_gpu_resources(self):
        t=self.new_world()
        for i in range(20):t._remember_mesh(i,self.mesh())
        self.assertEqual(len(t.mesh_cache),game.MESH_CACHE_CHUNKS)
        self.assertEqual(list(t.mesh_cache),list(range(14,20)))

    def test_normal_streaming_keeps_original_prefetch_bounds(self):
        t=self.new_world(available=(0,1))
        t.keep_chunks()
        self.assertEqual(set(t.pending),set(range(2,game.PREFETCH_AHEAD+1)))
        self.assertEqual(t.distance,0)

    def test_restart_cancels_pending_jump_and_queued_work(self):
        t=self.new_world()
        t.home_chunk_data=self.mesh()
        t.battlefield=ResetCounter()
        t.demo_results=[]
        t.elapsed=5.0;t.hit_notification='old';t.hit_notification_until=3.0
        t.frame_max_ms=99.0;t.frame_mean_ms=33.0
        t.debug_jump(450);self.settle(t);t.keep_chunks()
        self.assertGreater(t.todo.qsize(),0)
        pg=types.SimpleNamespace()
        constants=('QUIT','VIDEORESIZE','MOUSEBUTTONDOWN','KEYDOWN','KEYUP','K_b','K_m','K_t',
            'K_ESCAPE','K_F9','K_F10','K_F11','K_F3','K_F4','K_F5',
            'K_F6','K_F2','K_F7','K_F8','K_UP','K_DOWN','K_SPACE','K_p','K_r','K_s')
        for index,name in enumerate(constants):setattr(pg,name,index+101)
        pg.event=types.SimpleNamespace(get=lambda:[types.SimpleNamespace(type=pg.KEYDOWN,key=pg.K_r)])
        t.ctx.enable=mock.Mock()
        with mock.patch.object(game,'pygame',pg),mock.patch.object(game,'StartupScreen'), \
             mock.patch.object(game.moderngl,'DEPTH_TEST',2,create=True), \
             mock.patch.object(t,'chunk',side_effect=lambda *a:(FakeGL(),FakeGL(),6)):
            t.handle()
        self.assertIsNone(t.debug_jump_target)
        self.assertIsNone(t.debug_jump_stream_chunk)
        self.assertEqual(t.todo.qsize(),0)
        self.assertEqual(t.distance,0)
        self.assertEqual(t.generation,2)
        self.assertEqual(t.arcade.reset_count,1)
        self.assertIn(0,t.chunks)

    def test_game_update_paused_while_jump_pending(self):
        t=self.new_world()
        t.debug_jump(450)
        t.update(.04)
        self.assertEqual(t.last_dt,0.0)
        self.assertEqual(t.distance,0)

    def test_real_worker_builds_and_lands_at_450_without_blank_scene(self):
        """End-to-end real make_chunk background worker + fake GPU upload."""
        t=self.new_world()
        t.worker=threading.Thread(target=t._chunk_worker,name='v391-real-mesh-test',daemon=True)
        t.worker.start()
        try:
            t.debug_jump(450);self.settle(t)
            deadline=time.monotonic()+45.0
            while time.monotonic()<deadline and t.debug_jump_target is not None:
                t.keep_chunks()
                if t.debug_jump_target is not None:
                    self.assertEqual(t.distance,0)
                    self.assertIn(0,t.chunks)
                time.sleep(.03)
            self.assertIsNone(t.debug_jump_target,'real asynchronous meshes did not finish')
            self.assertEqual(t.distance,450)
            self.assertTrue({4,5,6}.issubset(t.chunks))
            self.assertGreater(t.chunks[5][2],150000)
            self.assertGreater(t.chunks[6][2],150000)
        finally:
            t.worker_stop.set()
            t.worker.join(timeout=5.0)

    def test_real_400_and_480_metre_chunks_have_full_meshes(self):
        # Non-synthetic geometry proof: the original generation is available
        # at the exact user-reported disappearance location.
        for s in (400.,480.):
            mesh=game.make_chunk(s)
            self.assertEqual(mesh.shape[1],9)
            self.assertGreater(len(mesh),150000)
            self.assertTrue(np.isfinite(mesh).all())

if __name__=='__main__':unittest.main()
