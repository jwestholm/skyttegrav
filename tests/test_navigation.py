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


def advance_and_turn(brain,distance,heading,dt):
    """Offline drive includes the same body-heading feedback as Trench.camera.

    Without it SoldierBrain correctly waits at turn_back forever; the old
    test mistakenly called the brain without ever simulating the renderer.
    """
    mode=brain.choose(distance,dt)
    distance,_=brain.advance(distance,MOVES[mode][1]*brain.speed_factor*dt)
    _,_,desired=brain.camera_pose(distance)
    if heading is None:heading=desired
    error=math.atan2(math.sin(desired-heading),math.cos(desired-heading))
    rate=1.15 if brain.state=='turn_back' else 1.75
    heading+=max(-rate*dt,min(rate*dt,error))
    brain.heading_actual=heading
    return distance,heading


class BrainTests(unittest.TestCase):
    def test_side_branch_rejoins_original_junction(self):
        brain=SoldierBrain()
        distance=0.0;heading=None
        seen_enter=False;seen_return=False;returned=False
        for _ in range(26000):
            distance,heading=advance_and_turn(brain,distance,heading,.05)
            if brain.state=='turn_in':seen_enter=True
            if brain.state in ('backtrack','turn_main'):seen_return=True
            if seen_return and brain.state=='main':
                returned=True
                # Rejoin is just after the junction, not a teleport to
                # its centre (continuous camera arc in 3D world space).
                self.assertAlmostEqual(distance,junction_marker(brain.branch_index)+1.25,delta=.15)
                break
        self.assertTrue(seen_enter and seen_return and returned)
        self.assertTrue(brain.branch_index in brain.visited)
        self.assertGreaterEqual(branch_length(brain.branch_index),9)
        for _ in range(50):
            distance,heading=advance_and_turn(brain,distance,heading,.05)
        self.assertGreater(distance,junction_marker(brain.branch_index)+1.25)

    def test_camera_pose_is_finite_while_exploring(self):
        brain=SoldierBrain()
        distance=0.0
        for _ in range(4000):
            mode=brain.choose(distance,.06)
            distance,_=brain.advance(distance,MOVES[mode][1]*.06)
            self.assertTrue(all(math.isfinite(v) for v in brain.camera_pose(distance)))

    def test_every_opening_receives_head_scan(self):
        brain=SoldierBrain()
        distance=0.0;heading=None
        inspection_count=0;peak_look=0.0;peak_roll=0.0
        for _ in range(24000):
            distance,heading=advance_and_turn(brain,distance,heading,.05)
            if brain.state=='peek':
                peak_look=max(peak_look,abs(brain.look_offset))
                peak_roll=max(peak_roll,abs(brain.roll))
            inspection_count=len(brain.visited)
            if inspection_count>=4 and brain.state=='main' and distance>junction_marker(3)+3:
                break
        self.assertGreaterEqual(inspection_count,4)
        self.assertGreater(peak_look,.35)
        self.assertGreater(peak_roll,.01)

    def test_open_branches_have_shorter_inspection_than_dugouts(self):
        brain=SoldierBrain()
        open_depths=[brain._depth_to_check(i) for i in range(60)
                     if __import__('trench_3d_test').branch_type(i)=='open']
        dugout_depths=[brain._depth_to_check(i) for i in range(60)
                       if __import__('trench_3d_test').branch_type(i)=='dugout']
        self.assertGreater(len(open_depths),5)
        self.assertGreater(len(dugout_depths),5)
        self.assertLess(min(open_depths),min(dugout_depths))
        self.assertGreater(max(open_depths),2.0)
        for i in range(60):
            self.assertLess(brain._depth_to_check(i),branch_length(i)-1.0)
        # Physical line-of-sight/raycasting is NOT implemented yet; don't
        # demand that any particular branch becomes immediately 'visible'.

    def test_generated_mesh_has_no_nan(self):
        import numpy as np
        mesh=make_chunk(0)
        self.assertGreater(len(mesh),1000)
        self.assertTrue(np.isfinite(mesh).all())


if __name__=='__main__':
    unittest.main()
