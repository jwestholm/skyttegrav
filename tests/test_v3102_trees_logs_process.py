"""V3.10.2: deterministic foliage / floor clutter and no-GIL process worker.

These tests are CPU-only; actual GPU frame pacing is separately validated on GTX 1070.
"""
from __future__ import annotations
import math
import queue
import threading
import unittest
from unittest import mock

import numpy as np
from test_v391_atomic_streaming import game
from shot_geometry import WorldShotMesh, NON_BALLISTIC_LAYERS


class TreeAndFloorTests(unittest.TestCase):
    def test_ground_clutter_is_seed_reproducible_and_avoids_playable_centre(self):
        for start in (0.,80.,400.,960.):
            with self.subTest(start=start):
                items=list(game.fallen_wood_layout(start))
                self.assertEqual(items,list(game.fallen_wood_layout(start)))
                for s,offset,length,radius,skew,i in items:
                    self.assertTrue(start<=s<start+game.CHUNK_LEN)
                    self.assertGreaterEqual(abs(offset),.70)
                    self.assertLessEqual(abs(offset),game.wall_width(s,1 if offset>0 else -1)-.21)
                    self.assertFalse(game.near_junction(s,5.5))
                    self.assertFalse(game.obstacles_in_range(s-1.4,s+1.4))
                    self.assertLessEqual(radius,.073)
                    self.assertLessEqual(length,1.71)

    def test_trees_are_distinct_geometry_without_new_gpu_draw_calls(self):
        mesh=game.MeshBuilder()
        import random
        game.conifer_canopy(mesh,(0.,0.,0.),7.0,1.6,random.Random(31))
        conifer=mesh.as_array()
        self.assertGreater(len(conifer),200)
        self.assertLess(len(conifer),1200)
        self.assertTrue(np.isfinite(conifer).all())
        self.assertEqual(set(np.unique(conifer[:,8])),{6.,13.})
        self.assertIn(6,NON_BALLISTIC_LAYERS)
        branch=game.MeshBuilder()
        game.broadleaf_canopy(branch,(0.,6.,0.),1.0,random.Random(35))
        broadleaf=branch.as_array()
        self.assertGreater(len(broadleaf),0)
        self.assertTrue(np.isfinite(broadleaf).all())
        self.assertFalse(np.array_equal(conifer,broadleaf))

    def test_fallen_wood_uses_existing_bark_materials_and_is_low_profile(self):
        m=game.MeshBuilder()
        game.trench_fallen_wood_chunk(m,0.0)
        arr=m.as_array()
        self.assertGreater(len(arr),0)
        self.assertTrue(np.isfinite(arr).all())
        self.assertTrue(set(np.unique(arr[:,8])).issubset({13.,14.}))
        self.assertLess(len(arr),25000,'fallen floor wood should be cheap baked geometry')

    def test_complete_chunk_keeps_ballistic_mesh_compatible(self):
        data=game.make_chunk(0.0)
        self.assertEqual(data.shape[1],9)
        self.assertTrue(np.isfinite(data).all())
        soup=WorldShotMesh(data)
        self.assertGreater(len(soup.layers),5000)
        self.assertFalse(any(v in NON_BALLISTIC_LAYERS for v in np.unique(soup.layers)))


class ProcessStreamingTests(unittest.TestCase):
    def test_process_worker_runs_one_job_and_publishes_frozen_geometry(self):
        t=game.Trench.__new__(game.Trench)
        t.todo=queue.Queue()
        t.todo.put((0,3))
        t.worker_stop=threading.Event()
        t.generation=0
        t.worker_current_chunk=None
        t.worker_last_ms=0.
        results=[]
        def published(generation,index,payload):
            results.append((generation,index,payload))
            t.worker_stop.set()
            return True
        t._publish_chunk_result=published
        class FakeFuture:
            def result(self,timeout=None):
                return np.zeros((6,9),dtype='f4')
        class FakePool:
            def __init__(self,*args,**kw):
                self.args=kw
            def submit(self,fn,route):
                self.fn=fn
                self.route=route
                self.assert_valid()
                return FakeFuture()
            def assert_valid(self):
                assert self.fn is game.generate_chunk_array
                assert self.route==3*game.CHUNK_LEN
            def shutdown(self,**kw):pass
        with mock.patch.object(game,'ProcessPoolExecutor',FakePool):
            t._chunk_worker_process()
        self.assertEqual(len(results),1)
        gen,idx,(verts,shot)=results[0]
        self.assertEqual((gen,idx),(0,3))
        self.assertIsInstance(shot,WorldShotMesh)
        self.assertEqual(t.worker_current_chunk,None)
        self.assertGreaterEqual(t.worker_last_ms,0.)

    def test_broken_process_falls_back_to_original_thread_worker(self):
        t=game.Trench.__new__(game.Trench)
        called=[]
        def original_worker():called.append(True)
        t._chunk_worker=original_worker
        with mock.patch.object(game,'ProcessPoolExecutor',side_effect=RuntimeError('spawn unavailable')):
            t._chunk_worker_process()
        self.assertEqual(called,[True])


if __name__=='__main__':unittest.main()
