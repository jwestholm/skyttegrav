"""Headless regression: turns are continuous and each footstep advances in metres."""
import math
import unittest
from test_tactical_brain import load_brain

class CurvedNavigationTests(unittest.TestCase):
    def test_no_teleport_at_side_entrance_or_return(self):
        brain=load_brain()()
        distance=0.0
        heading=0.0
        last=None
        max_jump=0.0
        seen=set()
        for frame in range(22000):
            dt=.025
            mode=brain.choose(distance,dt)
            x,z,target=brain.camera_pose(distance)
            if last is not None:
                jump=math.hypot(x-last[0],z-last[1])
                max_jump=max(max_jump,jump)
                self.assertLess(jump,.18,f'position discontinuity {jump:.3f}m at {brain.state}')
            last=(x,z)
            seen.add(brain.state)
            error=math.atan2(math.sin(target-heading),math.cos(target-heading))
            heading+=max(-2.25*dt,min(2.25*dt,error))
            brain.heading_actual=heading
            speeds={0:0.,1:0.,4:.68,5:1.15,7:2.3,8:3.35}
            distance,_=brain.advance(distance,speeds.get(mode,0.)*dt)
            if distance>140:break
        self.assertIn('turn_in',seen)
        self.assertIn('turn_main',seen)
        self.assertIn('backtrack',seen)
        self.assertGreater(distance,140)
        self.assertGreater(max_jump,0.01)

    def test_corner_heading_changes_progressively(self):
        brain=load_brain()()
        brain.branch_index=1
        brain.branch_side=1
        brain._start_corner(True)
        observed=[]
        for k in range(100):
            brain.corner_progress=brain.corner_length*k/99
            observed.append(brain._corner_pose())
        angles=[p[2] for p in observed]
        differences=[abs(math.atan2(math.sin(b-a),math.cos(b-a)))
                     for a,b in zip(angles,angles[1:])]
        self.assertLess(max(differences),.08)

if __name__=='__main__':
    unittest.main()
