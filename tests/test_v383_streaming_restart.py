"""V3.8.3: prove chunk backpressure, reset invalidation and camera reset.

Pure CPU/offline test of the exact Trench class methods. No Pygame/OpenGL
installation or display required, and no 80m mesh is generated.
"""
import ast
import queue
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'trench_3d_test.py'
TREE=ast.parse(SOURCE.read_text(encoding='utf-8'))
TRENCH=next(t for t in TREE.body if isinstance(t,ast.ClassDef) and t.name=='Trench')
NAMES={
    '_publish_chunk_result', '_chunk_worker', '_invalidate_chunk_generation',
    'keep_chunks', 'handle',
}
SELECTED=[node for node in TRENCH.body if isinstance(node,ast.FunctionDef) and node.name in NAMES]
assert {n.name for n in SELECTED}==NAMES
CLASS=ast.ClassDef(name='TrenchStub',bases=[],keywords=[],body=SELECTED,decorator_list=[])
CLASS=ast.fix_missing_locations(CLASS)


def stub_klass(make_chunk=lambda s: (s, 'mesh')):
    name_space={
        'queue':queue,'time':time,'math':__import__('math'),
        'CHUNK_LEN':80.,'RETAIN_BEHIND':2,'PREFETCH_AHEAD':5,
        'UPLOADS_PER_FRAME':1,'make_chunk':make_chunk,
    }
    exec(compile(ast.Module(body=[CLASS], type_ignores=[]),str(SOURCE),'exec'),name_space)
    return name_space['TrenchStub'],name_space


class SimpleGpu:
    def __init__(self):self.released=0
    def release(self):self.released+=1


class RestartStreamingTests(unittest.TestCase):
    def new_trench(self,*,ready_size=16):
        cls,ns=stub_klass()
        obj=cls()
        obj.worker_stop=threading.Event()
        obj.generation=0
        obj.todo=queue.Queue(maxsize=16)
        obj.ready=queue.Queue(maxsize=ready_size)
        obj.pending=set()
        obj.chunks={0:(SimpleGpu(),SimpleGpu(),12)}
        obj.distance=0.
        obj.chunk=lambda i,data=None:(SimpleGpu(),SimpleGpu(),12)
        return obj,ns

    def test_full_result_queue_waits_instead_of_discarding_completed_mesh(self):
        obj,_=self.new_trench(ready_size=1)
        obj.ready.put((0,999,'older result'))
        obj.todo.put((0,5))
        obj.pending.add(5)
        worker=threading.Thread(target=obj._chunk_worker,daemon=True)
        worker.start()
        # This deliberately lasts longer than the former 0.5 second timeout.
        time.sleep(.57)
        self.assertTrue(worker.is_alive())
        self.assertEqual(obj.ready.get_nowait()[1],999)
        try:
            generated=obj.ready.get(timeout=1.)
            self.assertEqual(generated,(0,5,(400.,'mesh')))
        finally:
            obj.worker_stop.set();worker.join(timeout=1.)
        self.assertFalse(worker.is_alive())

    def test_restart_discards_old_queues_and_invalidates_in_flight_work(self):
        obj,_=self.new_trench()
        obj.pending.update((4,5))
        obj.todo.put((0,4));obj.todo.put((0,5))
        obj.ready.put((0,7,'stale'))
        obj._invalidate_chunk_generation()
        self.assertEqual(obj.generation,1)
        self.assertEqual(obj.pending,set())
        self.assertTrue(obj.todo.empty())
        self.assertTrue(obj.ready.empty())

    def test_stale_result_must_not_discard_new_generation_pending_id(self):
        obj,_=self.new_trench()
        obj.generation=2
        obj.pending.add(3)
        obj.ready.put((1,3,'stale generation'))
        obj.keep_chunks()
        self.assertIn(3,obj.pending)
        jobs=[]
        while not obj.todo.empty():jobs.append(obj.todo.get_nowait())
        self.assertNotIn((2,3),jobs)

    def test_restart_resets_camera_stance_input_and_recreates_initial_chunk(self):
        obj,ns=self.new_trench()
        names='''K_t K_ESCAPE K_F9 K_F10 K_F11 K_F3 K_F4 K_F5 K_F6 K_F2 K_F7 K_F8 K_SPACE K_p K_UP K_DOWN K_r K_0 K_1 K_9'''.split()
        keycodes={name:i+300 for i,name in enumerate(names)}
        pg=types.SimpleNamespace(**keycodes,
             QUIT=1,VIDEORESIZE=2,MOUSEBUTTONDOWN=3,KEYDOWN=4,
             event=types.SimpleNamespace(get=lambda:[types.SimpleNamespace(type=4,key=keycodes['K_r'])]))
        ns['pygame']=pg
        ns['floor_y']=lambda s,*args:-.12
        class Resettable:
            resets=0
            def reset(self):self.resets+=1
        obj.brain=Resettable();obj.enemies=Resettable();obj.battlefield=Resettable()
        obj.distance=2000.
        obj.elapsed=211.
        obj.step_distance=711.
        obj.speed=3.0
        obj.mode=8
        obj.auto=False
        obj.paused=True
        obj.look=.61
        obj.height=.43
        obj.camera_roll=.12
        obj.gait_strength=1.
        obj.last_moved=.1
        obj.gait_lateral=.2
        obj.gait_vertical=.1
        obj.gait_roll=.09
        obj.obstacle_camera_lift=.1
        obj.terrain_eye_base=1.1
        obj.view_heading=3.1
        obj.last_camera_viewproj='old'
        obj.last_enemy_frame='old'
        obj.hit_notification='KILL'
        obj.hit_notification_until=999.
        obj.frame_max_ms=200.
        obj.frame_mean_ms=14.
        obj.chunk_upload_ms=99.
        obj.home_chunk_data=('home mesh',)
        obj.chunks={31:(SimpleGpu(),SimpleGpu(),12)}
        obj.todo.put((0,32))
        obj.ready.put((0,33,'old'))
        obj.pending.add(32)
        seen=[]
        obj.chunk=lambda index,data=None:(seen.append((index,data)) or (SimpleGpu(),SimpleGpu(),12))
        obj.handle()
        self.assertEqual(obj.generation,1)
        self.assertEqual(obj.distance,0.)
        self.assertTrue(obj.auto)
        self.assertFalse(obj.paused)
        self.assertEqual(obj.mode,5)
        self.assertEqual(obj.look,0.)
        self.assertEqual(obj.height,1.55)
        self.assertEqual(obj.camera_roll,0.)
        self.assertIsNone(obj.view_heading)
        self.assertIsNone(obj.last_enemy_frame)
        self.assertEqual(obj.hit_notification,'')
        self.assertTrue(obj.todo.empty())
        self.assertTrue(obj.ready.empty())
        self.assertEqual(obj.pending,set())
        self.assertEqual(seen,[(0,('home mesh',))])
        self.assertIn(0,obj.chunks)
        self.assertEqual((obj.brain.resets,obj.enemies.resets,obj.battlefield.resets),(1,1,1))

    def test_inflight_old_result_cannot_be_treated_as_current_generation(self):
        obj,_=self.new_trench(ready_size=1)
        obj.ready.put((0,999,'full'))
        result=[]
        t=threading.Thread(target=lambda:result.append(obj._publish_chunk_result(0,4,'old')))
        t.start()
        time.sleep(.03)
        obj._invalidate_chunk_generation()
        t.join(timeout=1.)
        self.assertFalse(t.is_alive())
        # A producer may have entered Queue.put before reset; the resulting
        # old-gen message is harmless because keep_chunks checks generation.
        self.assertEqual(len(result),1)
        while not obj.ready.empty():
            message=obj.ready.get_nowait()
            self.assertNotEqual(message[0],obj.generation)


if __name__=='__main__':unittest.main()
