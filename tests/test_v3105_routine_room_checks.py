"""V3.10.5: no-evidence room search uses existing real branch FSM.

No imaginary enemy evidence, no teleport and no change to first four
well-validated junctions. Offline navigation != live rendering.
"""
import math
import unittest
from test_v391_atomic_streaming import game


class RoutineRoomChecks(unittest.TestCase):
    def test_sparse_deterministic_occupied_or_empty_room_policy(self):
        brain=game.SoldierBrain()
        self.assertFalse(any(brain._routine_room_check(i) for i in range(6)))
        chosen=[i for i in range(6,45) if brain._routine_room_check(i)]
        self.assertEqual(chosen,[8,14,20,26,32,38,44])
        self.assertTrue(all(game.branch_type(i)=='dugout' for i in chosen))
        self.assertEqual(brain.branch_evidence,{})
        self.assertFalse(brain._should_enter_branch(8))

    def test_random_no_evidence_room_search_enters_then_rejoins_real_route(self):
        b=game.SoldierBrain()
        idx=8
        for earlier in range(idx):b.visited.add(earlier)
        marker=game.junction_marker(idx)
        distance=marker-6.
        heading=game.route(distance)[2]
        observed_states=set()
        prior=(distance,0.)
        for step in range(60*55):
            dt=1./60.
            mode=b.choose(distance,dt)
            target=b.camera_pose(distance)[2]
            heading=game.turn_heading_toward(heading,target,dt,
                              1.15 if b.state=='turn_back' else 1.75)
            b.heading_actual=heading
            new_distance,moved=b.advance(distance,game.MOVES[mode][1]*b.speed_factor*dt)
            self.assertLessEqual(moved,game.MOVES[mode][1]*dt+.0001)
            self.assertGreaterEqual(new_distance+1.e-8,distance)
            self.assertTrue(math.isfinite(heading))
            observed_states.add(b.state)
            distance=new_distance
            if distance>marker+4.5:break
        else:
            self.fail('SoldierBrain stuck: routine room search did not rejoin')
        self.assertEqual(b.last_branch_decision,(idx,'routine_search'))
        self.assertEqual(b.routine_rooms_cleared,1)
        self.assertEqual(b.branch_evidence,{})
        self.assertIn('turn_in',observed_states)
        self.assertIn('dash',observed_states)
        self.assertIn('kneel_scan',observed_states)
        self.assertIn('explore',observed_states)
        self.assertIn('dugout_clear',observed_states)
        self.assertIn('turn_back',observed_states)
        self.assertIn('backtrack',observed_states)
        self.assertIn('turn_main',observed_states)
        self.assertEqual(b.state,'main')

    def test_actual_evidence_keeps_priority_over_routine_entry(self):
        b=game.SoldierBrain()
        self.assertTrue(b.report_branch_evidence(8,'movement',.85))
        self.assertTrue(b._should_enter_branch(8))
        self.assertTrue(b._routine_room_check(8))
        # Player still has the old ability to report actual evidence; routine
        # choices must NEVER create such reports without sight/sound.
        self.assertEqual(b.branch_evidence[8],('movement',.85))


if __name__=='__main__':unittest.main()
