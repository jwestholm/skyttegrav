"""V3.9.9 natural corner check: time, geometry, continuity, and real evidence.

All tests run actual SoldierBrain on seed-1944 route math; no fabricated
render frames or gameplay-accuracy claims.
"""
import math
import unittest
from test_v391_atomic_streaming import game

DT=1./60.


def simulate(index=0, evidence_at=None, seconds=24):
    b=game.SoldierBrain()
    marker=game.junction_marker(index)
    # Earlier junctions are already completed; retain the current world's
    # deterministic bend checks, but don't re-check old side openings.
    for i in range(index):
        b.visited.add(i)
    distance=marker-6.15
    records=[]
    for frame in range(round(seconds/DT)):
        if evidence_at is not None and b.state==evidence_at:
            b.report_branch_evidence(index,'localized_sound',.90)
            evidence_at=None
        stance=b.choose(distance,DT)
        cx,cz,heading=b.camera_pose(distance)
        speed=game.MOVES[stance][1]*b.speed_factor
        next_distance,moved=b.advance(distance,speed*DT)
        records.append(dict(time=frame*DT,dist=distance,state=b.state,
                            yaw=b.look_offset,heading=heading,x=cx,z=cz,
                            speed=speed,moved=moved,shift=b.peek_shift,
                            forward=b.peek_forward,phase=b.phase))
        distance=next_distance
        if distance>marker+5.2 or b.state in ('move_to_mouth','turn_in'):
            break
    return b,records


class NaturalCheck(unittest.TestCase):
    def test_real_stop_peek_decide_and_continue(self):
        b,frames=simulate()
        states=[f['state'] for f in frames]
        for needed in ('observe_approach','observe_settle','observe_peek','observe_assess','main'):
            self.assertIn(needed,states)
        i=states.index('observe_peek')
        self.assertLess(states.index('observe_settle'),i)
        self.assertLess(i,states.index('observe_assess'))
        stopped=[f for f in frames if f['state'] in ('observe_settle','observe_peek','observe_assess')]
        self.assertGreater(len(stopped)*DT,2.3)
        self.assertLess(len(stopped)*DT,2.7)
        self.assertTrue(all(abs(f['moved'])<1.e-8 for f in stopped))
        self.assertEqual(b.last_branch_decision,(0,'observe_only'))
        self.assertGreater(frames[-1]['dist'],game.junction_marker(0)+4.5)

    def test_looks_deep_enough_to_see_into_opening(self):
        for i in (0,1,2):
            b,frames=simulate(i)
            side=game.junction_side(i)
            peeks=[f for f in frames if f['state']=='observe_peek']
            self.assertGreater(max(side*f['yaw'] for f in peeks),.91)
            self.assertLess(max(abs(f['yaw']) for f in frames),1.27)
            # Real geometric bearing to 2m into the side room: a 30deg
            # glance was too small. The camera should approach that bearing.
            peak=peeks[-1]
            x,_,z=game.branch_point(i,side,2.0)
            bearing=math.atan2(x-peak['x'],z-peak['z'])
            delta=math.atan2(math.sin(bearing-peak['heading']),
                             math.cos(bearing-peak['heading']))
            self.assertLess(abs(peak['yaw']-delta),.43)

    def test_watch_room_while_actually_passing_it(self):
        marker=game.junction_marker(0)
        b,frames=simulate()
        depart=[f for f in frames if f['state']=='main' and marker-2.2<f['dist']<marker+1.5]
        self.assertTrue(depart)
        self.assertTrue(any(f['speed']>0 and abs(f['yaw'])>.80 for f in depart))
        # After clearing room the head comes back smoothly.
        self.assertLess(abs(frames[-1]['yaw']),.1)
        for a,c in zip(frames,frames[1:]):
            self.assertLessEqual(abs(c['yaw']-a['yaw']),1.2*DT+1.e-6)
            self.assertLess(math.hypot(c['x']-a['x'],c['z']-a['z']),.13)
        self.assertIsNone(b.passing_branch)

    def test_no_entry_without_confirmed_evidence(self):
        b,frames=simulate(index=0)
        forbidden={'move_to_mouth','turn_in','turn_back','explore','backtrack','dugout_clear'}
        self.assertFalse(forbidden.intersection(f['state'] for f in frames))
        self.assertEqual(b.last_branch_decision,(0,'observe_only'))

    def test_evidence_during_peek_can_change_decision(self):
        b,frames=simulate(evidence_at='observe_peek')
        self.assertEqual(b.last_branch_decision,(0,'investigate'))
        self.assertEqual(b.state,'move_to_mouth')
        self.assertIsNone(b.passing_branch)
        self.assertIn('observe_assess',[f['state'] for f in frames])

    def test_restart_during_observation_resets_state(self):
        b=game.SoldierBrain()
        d=game.junction_marker(0)-2.25
        for _ in range(180):
            b.choose(d,DT)
        self.assertIn(0,b.visited)
        b.reset()
        self.assertEqual(b.state,'main')
        self.assertEqual(b.visited,set())
        self.assertIsNone(b.passing_branch)

    def test_blast_requires_new_peek(self):
        b=game.SoldierBrain()
        d=game.junction_marker(0)-2.25
        for _ in range(250):
            b.choose(d,DT)
            if b.state=='observe_peek':break
        self.assertEqual(b.state,'observe_peek')
        self.assertTrue(b.interrupt_for_blast(2,12.))
        seen=[]
        for _ in range(270):
            b.choose(d,DT)
            seen.append(b.state)
        # After interrupted observation, a fresh check is required;
        # this is not a random continuation of stale visual confidence.
        self.assertIn('observe_settle',seen)
        self.assertIn('observe_peek',seen)
        self.assertEqual(b.last_branch_decision,(0,'observe_only'))



if __name__=='__main__':unittest.main()
