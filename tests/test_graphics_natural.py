"""Bounded excavation changes: fixed foot/lip, clear lane, covered profile."""
import math
import unittest
from unittest import mock
from test_v391_atomic_streaming import game


def previous_bank(s,side,y,h):
    u=max(0.,min(1.,y/max(.1,h)))
    ripple=(.085*math.sin(s*.75+u*11.1+side)+.042*math.sin(s*2.06-u*23.+side*2))
    return max(.68,game.wall_width(s,side)+.14*u*u-.065*math.sin(u*math.pi)+ripple*math.sin(math.pi*u)**.7)

class NaturalBankTests(unittest.TestCase):
    def test_erosion_only_recedes_and_keeps_foot_lip_and_tunnel(self):
        for seed in (1944,37,902):
            with mock.patch.object(game,'SEED',seed):
                for s in (0.,8.,79.5,80.,126.,149.,298.,307.,345.,625.):
                    for side in (-1,1):
                        h=game.wall_height(s,side)
                        for y in (0.,.3,h*.4,h*.7,h):
                            delta=game.wall_offset(s,side,y,h)-previous_bank(s,side,y,h)
                            self.assertGreaterEqual(delta,-1e-10)
                            self.assertLessEqual(delta,.220001)
                            if y<=.35 or y==h or game.tunnel_open(s)>=.25:
                                self.assertAlmostEqual(delta,0.,places=9)

    def test_earth_normals_and_chunk_boundary_are_continuous(self):
        for s in (80.,160.,240.,320.):
            for side in (-1,1):
                a=game.wall_offset(s-1e-5,side,1.,game.wall_height(s-1e-5,side))
                b=game.wall_offset(s+1e-5,side,1.,game.wall_height(s+1e-5,side))
                self.assertLess(abs(a-b),1e-4)
                # Adjacent surface masks have exactly the same end cross-section.
                left=game._main_route_footprint(s-.5,s)
                right=game._main_route_footprint(s,s+.5)
                self.assertEqual(left[2],right[1]);self.assertEqual(left[3],right[0])

    def test_section_boundaries_not_periodic_and_wattle_not_bilateral(self):
        changes=[s for s in range(1,400) if game.lining_section(s)[1]!=game.lining_section(s-1)[1]]
        self.assertGreater(len(set(b-a for a,b in zip(changes,changes[1:]))),3)
        for s,side,h,_ in game.wall_dressing_layout(0.):
            if game.lining_section(s)[0]==1 and side>0:self.assertLessEqual(h,1.18)

if __name__=='__main__':unittest.main()
