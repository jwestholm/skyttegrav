"""V3.10.1: A real observation hold and prompt return to the forward view.

Deterministic simulation of actual SoldierBrain, seed=1944. This is NOT
physical shooting validation or a real GPU playback test.
"""
import unittest

from test_v399_stop_peek_watch import simulate, DT
from test_v391_atomic_streaming import game


class ObserveAndReturnTests(unittest.TestCase):
    def test_has_a_real_observation_hold_not_only_a_last_frame_glance(self):
        for index in (0, 1, 2):
            with self.subTest(index=index):
                brain, frames = simulate(index)
                side = game.junction_side(index)
                looks = [f for f in frames if f['state'] == 'observe_peek'
                         and side * f['yaw'] > 0.90]
                self.assertGreaterEqual(len(looks) * DT, 0.95)
                self.assertTrue(all(f['moved'] == 0 for f in looks))
                marker = game.junction_marker(index)
                self.assertLessEqual(max(f['dist'] for f in looks), marker - 2.40)
                self.assertEqual(brain.last_branch_decision, (index, 'observe_only'))

    def test_head_returns_forward_promptly_after_crossing(self):
        for index in (0, 1, 2):
            with self.subTest(index=index):
                _, frames = simulate(index)
                marker = game.junction_marker(index)
                before = [f for f in frames if marker <= f['dist'] <= marker + 0.35]
                after = [f for f in frames if marker + 2.8 <= f['dist'] <= marker + 3.5]
                self.assertTrue(before)
                self.assertTrue(after)
                self.assertGreater(max(abs(f['yaw']) for f in before), .90)
                self.assertLess(max(abs(f['yaw']) for f in after), .18)

    def test_no_new_shot_or_enemy_rules_added_in_camera_timing_change(self):
        self.assertEqual(game.BRANCH_SAFE_OBSERVE_BACK, 2.47)
        brain, frames = simulate(0)
        self.assertNotIn('turn_in', {f['state'] for f in frames})
        self.assertNotIn('explore', {f['state'] for f in frames})
        self.assertIsNone(brain.passing_branch)


if __name__ == '__main__':
    unittest.main()
