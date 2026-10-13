"""V3.8.2: camera is the PLAYER'S EYES, not a follow camera.

Offline checks: frame-rate invariance of head turns and source-level
contract that actual frame dt is fed into the render pose. These tests do
not assert anything about actual video quality on the GTX 1070.
"""
import ast
import math
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'trench_3d_test.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
FUNCTION = next(node for node in TREE.body if isinstance(node, ast.FunctionDef)
                and node.name == 'turn_heading_toward')
NAMESPACE = {'math': math}
exec(compile(ast.Module(body=[FUNCTION], type_ignores=[]), str(SOURCE), 'exec'), NAMESPACE)
TURN = NAMESPACE['turn_heading_toward']


class FirstPersonFrameTimeTests(unittest.TestCase):
    def test_one_second_turn_is_same_at_30_60_144_400_fps(self):
        final = []
        for fps in (30, 60, 144, 400):
            heading = 0.0
            for _ in range(fps):
                heading = TURN(heading, 2.5, 1.0/fps, 1.75)
            final.append(heading)
            self.assertAlmostEqual(heading, 1.75, places=8)
        self.assertLess(max(final)-min(final),1e-9)

    def test_per_frame_step_at_400_fps_is_not_sixty_hz_step(self):
        step = TURN(0.0, math.pi/2.0, 1.0/400.0, 1.75)
        self.assertLessEqual(step,1.75/400.0 + 1e-10)
        self.assertLess(step,1.75/60.0)

    def test_shortest_arc_wrap_and_negative_direction(self):
        a = math.radians(179.0)
        b = math.radians(-179.0)
        self.assertAlmostEqual(TURN(a,b,.1,1.0), a+math.radians(2.0), places=7)
        self.assertAlmostEqual(TURN(0.0,-3.0,.1,1.0),-.1,places=8)

    def test_pause_and_zero_rate_freeze_view(self):
        self.assertEqual(TURN(.7,1.9,0.0,1.75),.7)
        self.assertEqual(TURN(.7,1.9,.04,0.0),.7)
        self.assertEqual(TURN(.7,1.9,-.1,1.75),.7)

    def test_invalid_turn_inputs_are_rejected(self):
        for value in (float('inf'),float('nan')):
            with self.assertRaises(ValueError):TURN(0.0,value,.05,1.0)
            with self.assertRaises(ValueError):TURN(0.0,.5,value,1.0)

    def test_real_dt_is_refreshed_and_pause_freezes_camera(self):
        trench = next(node for node in TREE.body if isinstance(node,ast.ClassDef)
                      and node.name=='Trench')
        update = next(n for n in trench.body if isinstance(n,ast.FunctionDef)
                      and n.name=='update')
        camera = next(n for n in trench.body if isinstance(n,ast.FunctionDef)
                      and n.name=='camera')
        update_src=ast.get_source_segment(SOURCE.read_text(encoding='utf-8'),update)
        camera_src=ast.get_source_segment(SOURCE.read_text(encoding='utf-8'),camera)
        self.assertIn('self.last_dt=0.0 if self.paused',update_src)
        self.assertIn('min(.055,float(dt))',update_src)
        self.assertIn('turn_heading_toward(self.view_heading,desired,dt,turn_rate)',camera_src)


if __name__ == '__main__':
    unittest.main()
