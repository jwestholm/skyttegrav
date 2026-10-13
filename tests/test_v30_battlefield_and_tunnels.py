"""V3.0 offline regression of floor, sloping tunnels, crater geometry and caves.

CPU-only: renderer/GTX 1070 screenshot still needed before calling it validated.
"""
import math
import unittest
import numpy as np
from test_v26_obstacles import runtime_geometry


class BattlefieldV30Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()

    def test_floor_is_uneven_but_walkable_and_stitches(self):
        f=self.g['floor_y']
        y=np.array([f(s) for s in np.arange(0,500,.20)])
        self.assertGreater(float(np.ptp(y)),.65)  # entrance ramp is real
        self.assertLess(float(np.max(np.abs(np.diff(y)))),.08)
        a=np.array([f(s,0.) for s in np.arange(1,30,.2)])
        self.assertGreater(float(np.ptp(a)),.07)  # ordinary packed ground too
        for s in range(80,481,80):
            self.assertAlmostEqual(f(s-1e-5),f(s+1e-5),delta=.0005)

    def test_tunnels_are_between_real_junctions(self):
        g=self.g
        for gap in (3,10,17):
            marker=g['junction_marker'](gap)
            self.assertAlmostEqual(g['tunnel_open'](marker),0.,delta=1e-9)
            self.assertAlmostEqual(g['tunnel_open'](marker+72),0.,delta=1e-9)
            self.assertGreater(g['tunnel_open'](marker+32),.95)
            self.assertLess(g['tunnel_drop'](marker+32),-.69)
            self.assertAlmostEqual(g['tunnel_drop'](marker+65),0.,delta=1e-9)
            for s in np.arange(marker+16,marker+51,1):
                if g['tunnel_open'](s)>.5:
                    # No close active crossroad while soldier goes underground.
                    other=g['nearest_junction'](s)
                    self.assertGreater(abs(s-other[0]),17.)

    def test_route_changes_real_compass_direction(self):
        g=self.g
        headings=np.array([g['route'](float(s))[2] for s in range(0,650,5)])
        self.assertGreater(float(np.ptp(headings)),2.1)
        # Check actual travelled segments; no teleport at heading change.
        for s in range(5,620,5):
            x,z,_=g['route'](s)
            xp,zp,_=g['route'](s+.1)
            self.assertLess(math.hypot(xp-x,zp-z),.14)

    def test_craters_remain_off_walkable_trench(self):
        g=self.g
        for s in np.arange(0,600,4):
            self.assertEqual(g['crater_height'](s,0.),0.0)
        rim=[]
        for s in np.arange(0,270,2):
            for side in (-1,1):
                rim.append(g['crater_height'](s,side*15.))
        self.assertLess(min(rim),-.17)
        self.assertGreater(max(rim),.06)

    def test_seeded_cover_crates_have_escape_corridor(self):
        g=self.g
        objs=g['obstacles_in_range'](0,25000)
        large=[ob for ob in objs if ob.kind=='crate' and ob.height>1.]
        self.assertGreater(len(large),10)
        for ob in large:
            self.assertGreater(ob.length,1.0)
            self.assertNotEqual(ob.detour,0.0)
            self.assertGreaterEqual(abs(ob.detour-ob.lateral),ob.width*.5+.24)
            self.assertAlmostEqual(g['obstacle_steering'](ob.s),ob.detour,delta=.0001)

    def test_bunker_observation_is_purposeful_and_time_bounded(self):
        g=self.g
        brain=g['SoldierBrain']()
        i=next(i for i in range(20) if g['branch_type'](i)=='dugout')
        brain.branch_index=i
        brain.branch_side=g['junction_side'](i)
        brain.state='explore'
        brain.investigate_depth=brain._depth_to_check(i)
        self.assertLess(brain.investigate_depth,g['branch_length'](i)-1.95)
        brain.branch_progress=brain.investigate_depth-.01
        brain.advance(g['junction_marker'](i),.5)
        self.assertEqual(brain.state,'dugout_clear')
        self.assertGreater(brain.wait,1.0)
        brain.choose(g['junction_marker'](i),.10)
        self.assertEqual(brain.state,'dugout_clear')
        for _ in range(50):brain.choose(g['junction_marker'](i),.08)
        self.assertEqual(brain.state,'turn_back')

    def test_no_floating_terrain_inside_first_dugouts(self):
        """Sample the ACTUAL triangles where the camera walks.

        The pre-V3.1 test inspected every mesh centroid but was painfully
        slow and still missed long triangles crossing roofed corridors.
        Barycentric X/Z intersections catch those crossings directly.
        """
        from test_v31_no_surface_overlap import layers_at
        g=self.g
        inspected=0
        for i in (0,3,4,5,6):
            if g['branch_type'](i)!='dugout':continue
            marker=g['junction_marker'](i)
            mesh=g['make_chunk'](math.floor(marker/80)*80)
            for side in g['junction_sides'](i):
                for along in (3.35,5.25,7.15):
                    if along>g['branch_length'](i)-1.0:continue
                    for lateral in (-.22,0.,.22):
                        x,_,z=g['branch_point'](i,side,along,lateral,0.)
                        heights=layers_at([mesh],x,z,[3,20,21,22])
                        roofs=[y for y,layer in heights if layer==20 and y>1.2]
                        self.assertTrue(roofs,(i,side,along,heights))
                        roof=min(roofs)
                        self.assertGreater(roof-g['floor_y'](marker,0.),2.05)
                        intrusions=[y for y,layer in heights if layer in (3,22)
                                    and g['floor_y'](marker,0.)+.12<y<roof+.06]
                        self.assertFalse(intrusions,(i,side,along,intrusions))
                        inspected+=1
        self.assertGreater(inspected,20)


if __name__=='__main__':unittest.main()
