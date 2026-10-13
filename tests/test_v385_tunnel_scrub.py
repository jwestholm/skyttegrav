"""Offline V3.8.5: route scrub + seeded side passage variations.

Does not establish visual OpenGL/GTX quality or solve roof/terrain overlaps.
"""
import math
import unittest
from unittest.mock import Mock
import numpy as np
from test_v26_obstacles import runtime_geometry


class TunnelScrubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()

    def test_branch_mouth_stable_clear_and_continuous(self):
        g=self.g
        for idx in range(24):
            width=g['branch_half_width'](idx,0.)
            self.assertAlmostEqual(width,2.,delta=2e-6)
            self.assertAlmostEqual(g['branch_center_shift'](idx,0.),0.,places=7)
            vals=[g['branch_half_width'](idx,i*.05) for i in range(1,321)]
            self.assertGreater(min(vals),1.05)
            self.assertLess(max(vals),2.10)
            self.assertLess(max(abs(a-b) for a,b in zip(vals,vals[1:])),.045)
            center=[g['branch_center_shift'](idx,i*.05) for i in range(1,321)]
            self.assertLess(max(abs(a-b) for a,b in zip(center,center[1:])),.11)

    def test_tunnels_seeded_nonidentical(self):
        g=self.g
        samples=[]
        for idx in range(9):
            v=tuple(round(g['branch_half_width'](idx,s),4) for s in (4.,6.,8.,10.))
            samples.append(v)
        self.assertGreater(len(set(samples)),6)
        self.assertEqual(samples,[tuple(round(g['branch_half_width'](idx,s),4) for s in (4.,6.,8.,10.)) for idx in range(9)])

    def test_rag_is_hung_not_blob(self):
        from pathlib import Path
        src=(Path(__file__).resolve().parents[1]/'trench_3d_test.py').read_text()
        part=src[src.index('def dugout_furnishings'):src.index('def lantern_side')]
        self.assertNotIn('blob(mesh,p,(.29,.35,.07),9',part)
        self.assertIn('spot(a,-.965,top_y)',part)
        self.assertIn('spot(b,-.927,top_y-vb)',part)

    def test_scrub_reinitializes_camera_nav_and_threat_without_writing_world(self):
        # Import the *actual* Pygame handler class; existing test suite stubs
        # pygame/moderngl for offline execution.
        import sys,types,importlib.util
        if importlib.util.find_spec('moderngl') is None:
            sys.modules.setdefault('moderngl',types.ModuleType('moderngl'))
        if importlib.util.find_spec('pygame') is None:
            sys.modules.setdefault('pygame',types.ModuleType('pygame'))
        import trench_3d_test as game
        from enemy_system import EnemyDirector
        test=object.__new__(game.Trench)
        test._invalidate_chunk_generation=Mock()
        test.distance=32.0
        test.speed=4.0
        test.step_distance=333.0
        test.gait_strength=0.9
        test.gait_lateral=0.01
        test.gait_vertical=0.01
        test.gait_roll=0.01
        test.camera_roll=.2
        test.height=.8
        test.view_heading=2.1
        test.look=.5
        test.obstacle_camera_lift=.1
        test.terrain_eye_base=10.0
        test.brain=game.SoldierBrain()
        test.brain.visited.add(1)
        test.enemies=EnemyDirector()
        test.enemies.update(.03,27.)
        test.enemy_death_pause=.8
        test.last_enemy_frame=object()
        test.last_camera_viewproj=object()
        test.auto=False
        test.mode=1
        test.paused=True
        test.last_dt=.03
        target=test.debug_jump(25.)
        self.assertEqual(target,57.)
        self.assertEqual(test.distance,57.)
        self.assertEqual(test.step_distance,57.)
        self.assertEqual(test.speed,0.)
        self.assertIsNone(test.view_heading)
        self.assertEqual(test.height,1.55)
        self.assertEqual(test.brain.state,'main')
        self.assertFalse(test.brain.visited)
        self.assertFalse(test.enemies.active)
        self.assertTrue(test.auto)
        self.assertFalse(test.paused)
        self.assertIsNone(test.last_enemy_frame)
        test._invalidate_chunk_generation.assert_called_once()
        self.assertEqual(test.debug_jump(-999.),0.)
        self.assertEqual(test.distance,0.)


if __name__=='__main__':unittest.main()
