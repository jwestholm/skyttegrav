"""V2.9 regression: generated branching/arched excavation and atmospheric shaders.

This checks pure CPU geometry, determinism, and shader source contracts.
The included headless Mesa link test is performed separately at packaging time.
"""
import math
from pathlib import Path
import unittest
import numpy as np
from test_v26_obstacles import runtime_geometry

SRC=(Path(__file__).resolve().parents[1]/'trench_3d_test.py').read_text()

class V29DugoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.g=runtime_geometry()

    def test_crossroad_y_junctions_and_t(self):
        g=self.g
        patterns=[g['junction_kind'](i) for i in range(32)]
        self.assertTrue({'T','X','Y'} <= set(patterns))
        for i in range(32):
            opts=g['junction_sides'](i)
            self.assertIn(g['junction_side'](i),opts)
            self.assertEqual(len(opts),2 if patterns[i]=='X' else 1)
            if patterns[i]=='Y':
                # Angled branching begins deeper than the excavation mouth.
                self.assertAlmostEqual(g['branch_center_shift'](i,2.5),0.,delta=.12)
                self.assertGreater(abs(g['branch_center_shift'](i,11.)-
                                       g['branch_center_shift'](i,3.0)),1.2)

    def test_dugout_narrows_from_mouth_and_has_headroom(self):
        g=self.g
        for i in range(32):
            self.assertAlmostEqual(g['branch_half_width'](i,0),2.0,delta=.08)
            self.assertLess(g['branch_half_width'](i,5),1.35)
            self.assertGreater(g['branch_half_width'](i,5),1.04)
        self.assertIn('def vaulted(along,ratio):',SRC)
        self.assertIn('for j in range(10):',SRC)
        self.assertIn('max(1.94, min(2.22,sideheight+.30))',SRC)
        self.assertIn('if roofed:',SRC)
        # Branch floor, wall, and ceiling remain distinct material areas.
        self.assertIn('mesh.quad(bp(a,-wa,-.052)',SRC)
        self.assertIn('mesh.quad(bp(a,wa*ra,vaulted(a,ra))',SRC)
        self.assertNotIn('mouth_width=2.0  # same half width as wall cut',SRC)

    def test_model_lights_match_local_lanterns_seed(self):
        g=self.g
        for dist in (0,64,280,500,900,1900):
            a=g['nearby_lanterns'](dist)
            b=g['nearby_lanterns'](dist)
            self.assertEqual(a,b)
            self.assertLessEqual(len(a),8)
            for item in a:
                self.assertEqual(len(item),3)
                self.assertTrue(all(math.isfinite(v) for v in item))
        self.assertIn('uniform vec3 lamp_positions[8];',SRC)
        self.assertIn('uniform float fog_strength;',SRC)
        self.assertIn('MOON_DIRECTION',SRC)
        self.assertIn('K_F7',SRC)
        self.assertIn('K_F8',SRC)
        self.assertNotIn('sin(v_world.z*.09+2.0)',SRC)

    def test_branch_geometry_bounded_and_reproducible(self):
        g=self.g
        # Check a T, a Y and an X junction chunk plus a further stretch.
        for i in (0,1,3,6):
            marker=g['junction_marker'](i)
            start=80*int(marker//80)
            a=g['make_chunk'](float(start))
            self.assertTrue(np.isfinite(a).all())
            self.assertGreater(len(a),4000)
            self.assertLess(len(a),450_000)
            self.assertIn(20,set(a[:,8].astype(int)))
            self.assertIn(21,set(a[:,8].astype(int)))
        # Separate branch-position map equals a base route plus a local offset.
        i=3; side=g['junction_side'](i)
        p=g['branch_point'](i,side,5.,.2,1.55)
        self.assertEqual(len(p),3)
        self.assertTrue(all(math.isfinite(x) for x in p))
        self.assertAlmostEqual(p[1],1.55)

if __name__=='__main__': unittest.main()
