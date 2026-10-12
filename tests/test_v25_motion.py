"""Behavior/geometry tests for V2.5. No OpenGL context required."""
import ast
import math
from pathlib import Path
import unittest
from test_real_corner_clearance import real_brain


def gait_function():
    src=Path(__file__).resolve().parents[1]/'trench_3d_test.py'
    t=ast.parse(src.read_text(encoding='utf-8'))
    f=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='gait_targets')
    env={'math':math}
    exec(compile(ast.Module(body=[f],type_ignores=[]),str(src),'exec'),env)
    return env['gait_targets']


class MotionV25Tests(unittest.TestCase):
    def test_two_footfalls_make_one_left_right_cycle(self):
        gait=gait_function(); stride=.66
        a=gait(5,1.15,stride,.25,1.)
        b=gait(5,1.15,stride,.25+stride,1.)
        c=gait(5,1.15,stride,.25+2*stride,1.)
        self.assertAlmostEqual(a[0],-b[0],places=8)
        self.assertAlmostEqual(a[0],c[0],places=8)
        self.assertLess(abs(a[0]),.003)
        self.assertLess(abs(a[2]),.0012)

    def test_crouching_stays_lower_and_stabler(self):
        gait=gait_function()
        crouch=gait(4,.68,.48,.17,1.)
        run=gait(8,3.35,1.08,.17,1.)
        self.assertLess(abs(crouch[0]),abs(run[0]))
        self.assertLessEqual(abs(crouch[2]),.00051)
        self.assertLessEqual(abs(run[2]),.00101)
        self.assertEqual(gait(4,.68,.48,.17,0.),(0.,0.,0.))

    def test_generated_bends_are_checked_before_passage(self):
        m=real_brain();brain=m['SoldierBrain']()
        distance=0.; heading=0.;seen=set();previous=None;max_jump=0.;last_h=0.
        for frame in range(16000):
            dt=.033
            mode=brain.choose(distance,dt)
            x,z,target=brain.camera_pose(distance)
            if previous is not None:
                jump=math.hypot(x-previous[0],z-previous[1]);max_jump=max(max_jump,jump)
                self.assertLess(jump,.23,f'{brain.state} at {distance:.2f}m jump {jump:.2f}')
            previous=(x,z)
            # Same heading rate limiter as camera; verifies turns complete.
            diff=math.atan2(math.sin(target-heading),math.cos(target-heading))
            rate=1.15 if brain.state=='turn_back' else 1.75
            heading+=max(-rate*dt,min(rate*dt,diff))
            brain.heading_actual=heading
            seen.add(brain.state)
            speeds={0:0.,1:0.,4:.68,5:1.15,7:2.3,8:3.35}
            distance,_=brain.advance(distance,speeds[mode]*dt)
            if distance>160: break
        self.assertGreater(distance,160,f'stuck at {distance:.2f}m {brain.state}')
        self.assertIn('bend_settle',seen)
        self.assertIn('bend_peek',seen)
        self.assertIn('bend_retract',seen)
        self.assertIn('turn_in',seen)
        self.assertIn('turn_main',seen)
        self.assertGreaterEqual(len(brain.checked_bends),3)
        self.assertLess(max_jump,.23)

    def test_wall_lane_blends_even_when_bend_near_junction(self):
        m=real_brain()
        for i in range(24):
            brain=m['SoldierBrain']()
            brain.branch_index=i
            brain.branch_side=m['junction_side'](i)
            brain.visited.add(i)
            marker=m['junction_marker'](i)
            last=None
            for step in range(380):
                s=marker-8.0+step*.05
                o=brain._main_offset(s)
                if last is not None:
                    self.assertLess(abs(o-last),.09, f'wall lane jump junction {i} at {s:.2f}')
                side=1 if o>=0 else -1
                self.assertLessEqual(abs(o),m['cover_distance'](s,side)+1e-9)
                last=o

    def test_wall_hugging_is_continuous_through_junction(self):
        m=real_brain();brain=m['SoldierBrain']()
        i=0;marker=m['junction_marker'](i)
        brain.branch_index=i;brain.branch_side=m['junction_side'](i)
        samples=[]
        for k in range(1201):
            s=marker-8.0+k*.011
            offset=brain._main_offset(s)
            limit=m['wall_width'](s,brain.branch_side)
            self.assertLessEqual(abs(offset),limit-.36)
            samples.append(offset)
        self.assertLess(max(abs(b-a) for a,b in zip(samples,samples[1:])),.04)
        # Outbound curve must begin exactly at the main-cover camera position.
        brain._start_corner(True)
        start=brain._corner_pose()
        s=marker-m['CORNER_MAIN_OFFSET']
        cx,cz,h=m['route'](s)
        o=brain._main_offset(s)
        self.assertAlmostEqual(start[0],cx+math.cos(h)*o,places=6)
        self.assertAlmostEqual(start[1],cz-math.sin(h)*o,places=6)

if __name__=='__main__':unittest.main()
