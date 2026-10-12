"""Headless tactical brain smoke tests; pygame/ModernGL not required."""
import ast
import math
from pathlib import Path
import unittest


def load_brain():
    path=Path(__file__).resolve().parents[1]/'trench_3d_test.py'
    parsed=ast.parse(path.read_text(encoding='utf-8'))
    node=next(n for n in parsed.body if isinstance(n,ast.ClassDef) and n.name=='SoldierBrain')
    env={
        'math':math,'JUNCTION_FIRST':64,'JUNCTION_SPACING':72,
        'CORNER_DEPTH':1.50,'CORNER_MAIN_OFFSET':1.15,
        'BEND_FIRST':11,'BEND_SPACING':34,'COVER_EYE_CLEARANCE':.49,
        'eased':lambda t:max(0.,min(1.,t))**2*(3-2*max(0.,min(1.,t))),
        'cover_distance':lambda s,side:.58,
        'bend_marker':lambda i:11+34*i,
        'bend_direction':lambda i:0.0,
        'wall_width':lambda s,side:1.18,
        'junction_marker':lambda i:64+72*i,
        'junction_side':lambda i:1 if i%2 else -1,
        'branch_length':lambda i:12.,
        'branch_center_shift':lambda i,d:.7,
        'route':lambda distance:(0.,float(distance),0.),
        'noise':lambda i,salt:((i*23+salt*37)%97)/97.,
        'smooth':lambda a,b,t:a+(b-a)*t,
    }
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
    return env['SoldierBrain']


class TacticalTests(unittest.TestCase):
    def test_never_dashes_before_peeking_and_aligning(self):
        brain=load_brain()()
        distance=0.
        heading=0.
        observed=[]
        for _ in range(18000):
            dt=.025
            mode=brain.choose(distance,dt)
            desired=brain.camera_pose(distance)[2]
            error=math.atan2(math.sin(desired-heading),math.cos(desired-heading))
            heading+=max(-2.25*dt,min(2.25*dt,error))
            brain.heading_actual=heading
            speeds={0:0.,1:0.,4:.68,5:1.15,7:2.3,8:3.35}
            distance,_=brain.advance(distance,speeds[mode]*dt)
            if brain.branch_index==1 and (not observed or observed[-1]!=brain.state):
                observed.append(brain.state)
            if distance>140:break
        required=('approach','edge','peek','retract','assess','move_to_mouth',
                  'turn_in','dash','kneel_scan','explore','turn_back','backtrack',
                  'turn_main','rejoin','main')
        self.assertEqual(observed, list(required))
        self.assertGreater(distance,140.)

    def test_repeated_runs_are_deterministic(self):
        a=load_brain()()
        b=load_brain()()
        for _ in range(10):
            self.assertEqual(a.choose(61.1,.05),b.choose(61.1,.05))
            self.assertEqual(a.state,b.state)
            self.assertEqual(a.camera_pose(61.1),b.camera_pose(61.1))


if __name__=='__main__':
    unittest.main()

class CornerPoseTests(unittest.TestCase):
    def test_peek_has_physical_side_and_forward_shift(self):
        brain=load_brain()()
        brain.branch_side=1
        brain.state='peek'
        for _ in range(80):
            brain._pose_for_state()
            brain._tick_pose(.016)
        self.assertGreater(brain.peek_shift,.12)
        self.assertGreater(brain.peek_forward,.16)
        self.assertGreater(brain.look_offset,.80)
        brain.state='retract'
        for _ in range(90):
            brain._pose_for_state()
            brain._tick_pose(.016)
        self.assertLess(brain.peek_forward,.04)

    def test_approach_stays_behind_wall_corner(self):
        brain=load_brain()()
        distance=60.01  # marker at 64
        brain.choose(distance,.02)
        self.assertEqual(brain.state,'approach')
        for _ in range(60):
            distance,_=brain.advance(distance,.12)
        self.assertLessEqual(distance,64-2.25+1e-6)
