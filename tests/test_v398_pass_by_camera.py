"""V3.9.9 regression of V3.9.8: eye-only pass plus a real stopped check.

The original V3.9.8 demand of NEVER stopping at an unconfirmed opening
was rejected after physical video review. Keep the safety/continuity checks.
"""
import math
import unittest
from test_v391_atomic_streaming import game


class PassByCameraTests(unittest.TestCase):
    def drive(self, brain, start, seconds=18, hz=60):
        distance=float(start)
        dt=1.0/hz
        frames=[]
        for _ in range(round(seconds*hz)):
            old_yaw=brain.look_offset
            mode=brain.choose(distance,dt)
            camera_x,camera_z,heading=brain.camera_pose(distance)
            speed=game.MOVES[mode][1]*brain.speed_factor
            next_distance,_=brain.advance(distance,speed*dt)
            frames.append((distance,brain.state,brain.look_offset,old_yaw,
                           brain.peek_shift,brain.peek_forward,heading,speed,
                           camera_x,camera_z))
            distance=next_distance
        return frames,distance

    def test_first_dugout_stopped_check_followed_by_watched_pass(self):
        b=game.SoldierBrain()
        marker=game.junction_marker(0)
        frames,end=self.drive(b,marker-6.15,seconds=19.)
        self.assertGreater(end,marker+4.0)
        self.assertEqual(b.last_branch_decision,(0,'observe_only'))
        states=[f[1] for f in frames]
        self.assertIn('observe_peek',states)
        self.assertIn('observe_assess',states)
        self.assertTrue(all(f[7]==0 for f in frames if f[1]=='observe_peek'))
        self.assertTrue(any(f[1]=='main' and f[0]>marker and abs(f[2])>.65 for f in frames))
        self.assertIn(0,b.visited)
        self.assertIsNone(b.passing_branch)
        self.assertLess(abs(b.look_offset),.10)

    def test_camera_head_turn_is_rate_limited_and_small_lean(self):
        b=game.SoldierBrain()
        marker=game.junction_marker(0)
        frames,_=self.drive(b,marker-6.2,seconds=19.)
        side=game.junction_side(0)
        self.assertTrue(any(side*f[2]>.9 for f in frames))
        self.assertLess(max(abs(f[2]) for f in frames),1.26)
        self.assertLess(max(abs(f[4]) for f in frames),.059)
        self.assertLess(max(abs(f[5]) for f in frames),.062)
        for f in frames:
            self.assertLessEqual(abs(f[2]-f[3]),1.2/60+1.e-6)
            self.assertTrue(math.isfinite(f[8]) and math.isfinite(f[9]))

    def test_suspected_branch_keeps_cautious_search_sequence(self):
        b=game.SoldierBrain()
        b.report_branch_evidence(0,'localized_sound',.9)
        marker=game.junction_marker(0)
        phases=[]
        for _ in range(160):
            b.choose(marker-2.25,1/60)
            phases.append(b.state)
        self.assertEqual(b.last_branch_decision,(0,'investigate'))
        self.assertIn('peek',phases)
        self.assertIn('move_to_mouth',phases)
        self.assertIsNone(b.passing_branch)

    def test_weak_evidence_causes_check_not_entry(self):
        b=game.SoldierBrain()
        b.report_branch_evidence(0,'movement',.4)
        frames,_=self.drive(b,game.junction_marker(0)-6.2,seconds=19)
        self.assertIn('observe_peek',[f[1] for f in frames])
        self.assertEqual(b.last_branch_decision,(0,'observe_only'))
        self.assertNotIn('turn_in',[f[1] for f in frames])

    def test_body_remains_inside_actual_main_trench_lane(self):
        b=game.SoldierBrain()
        marker=game.junction_marker(0)
        frames,_=self.drive(b,marker-6.2,seconds=19)
        for route_m,state,_,_,_,_,_,_,cx,cz in frames:
            rx,rz,heading=game.route(route_m)
            lateral=(cx-rx)*math.cos(heading)-(cz-rz)*math.sin(heading)
            side=1 if lateral>=0 else -1
            self.assertLessEqual(abs(lateral),game.cover_distance(route_m,side)+.01)
            self.assertNotIn(state,('turn_in','explore','backtrack'))

    def test_rate_limit_never_fails_with_large_dt(self):
        b=game.SoldierBrain()
        b.look_target=1.1
        for dt in (.016,.04,.08,.2):
            before=b.look_offset
            b._tick_pose(dt)
            self.assertLessEqual(abs(b.look_offset-before),dt*1.2+1.e-8)

if __name__=='__main__':
    unittest.main()
