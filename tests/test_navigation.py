"""Standalone navigation regressions: python3 -m unittest discover -s tests -v."""
import math
import unittest
# Mesh and navigation tests do not instantiate OpenGL or Pygame; permit CI
# environments without a graphics stack while leaving real installs intact.
import importlib.util
import sys
import types
for optional in ('moderngl', 'pygame'):
    if importlib.util.find_spec(optional) is None:
        sys.modules[optional] = types.ModuleType(optional)
from trench_3d_test import SoldierBrain, MOVES, branch_length, junction_marker, make_chunk


class BrainTests(unittest.TestCase):
    def test_side_branch_rejoins_original_junction(self):
        brain=SoldierBrain()
        distance=0.0
        seen_enter=False
        seen_return=False
        returned=False
        for _ in range(16000):
            mode=brain.choose(distance,.06)
            distance,_=brain.advance(distance,MOVES[mode][1]*.06)
            if brain.state=='enter':seen_enter=True
            if brain.state=='return':seen_return=True
            if seen_return and brain.state=='main':
                returned=True
                self.assertAlmostEqual(distance,junction_marker(brain.branch_index),places=4)
                break
        self.assertTrue(seen_enter and seen_return and returned)
        self.assertTrue(brain.branch_index in brain.visited)
        self.assertGreaterEqual(branch_length(brain.branch_index),9)
        for _ in range(50):
            mode=brain.choose(distance,.06)
            distance,_=brain.advance(distance,MOVES[mode][1]*.06)
        self.assertGreater(distance,junction_marker(brain.branch_index))

    def test_camera_pose_is_finite_while_exploring(self):
        brain=SoldierBrain()
        distance=0.0
        for _ in range(4000):
            mode=brain.choose(distance,.06)
            distance,_=brain.advance(distance,MOVES[mode][1]*.06)
            self.assertTrue(all(math.isfinite(v) for v in brain.camera_pose(distance)))

    def test_every_opening_receives_head_scan(self):
        brain=SoldierBrain()
        distance=0.0
        inspection_count=0
        peak_look=0.0
        peak_roll=0.0
        for _ in range(15000):
            mode=brain.choose(distance,.05)
            if brain.state=='inspect':
                peak_look=max(peak_look,abs(brain.look_offset))
                peak_roll=max(peak_roll,abs(brain.roll))
            new_distance,_=brain.advance(distance,MOVES[mode][1]*.05)
            distance=new_distance
            inspection_count=len(brain.visited)
            if inspection_count>=4 and brain.state=='main' and distance>junction_marker(3)+3:
                break
        self.assertGreaterEqual(inspection_count,4)
        self.assertGreater(peak_look,.8)
        self.assertGreater(peak_roll,.04)

    def test_visible_dead_end_does_not_require_full_exploration(self):
        brain=SoldierBrain()
        probes=[brain._depth_to_check(i) for i in range(40)]
        self.assertTrue(any(p==0 for p in probes))
        self.assertTrue(any(p>2 for p in probes))
        for i,p in enumerate(probes):
            self.assertLess(p,branch_length(i)-1.0)

    def test_generated_mesh_has_no_nan(self):
        import numpy as np
        mesh=make_chunk(0)
        self.assertGreater(len(mesh),1000)
        self.assertTrue(np.isfinite(mesh).all())


if __name__=='__main__':
    unittest.main()
