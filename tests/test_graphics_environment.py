"""Connected revetment: ownership, shallow banks, actual solid clearance."""
import unittest
from unittest import mock
import numpy as np
from test_v391_atomic_streaming import game
from shot_geometry import WorldShotMesh, NON_BALLISTIC_LAYERS

class EnvironmentTests(unittest.TestCase):
    def test_global_sections_and_streaming_ownership(self):
        for seed in (1944,37,902):
            with mock.patch.object(game,'SEED',seed):
                for zone in range(30):
                    self.assertEqual(game.lining_section(zone*24+6)[1],zone)
                    self.assertEqual(game.lining_section(zone*24+18)[1],zone)
                a=list(game.wall_dressing_layout(0.))+list(game.wall_dressing_layout(80.))
                self.assertEqual([b for b in a if 40<=b[0]<120],list(game.wall_dressing_layout(40.)))
                self.assertEqual(len(a),len({(b[0],b[1]) for b in a}))
                self.assertTrue(any(b[0]-a0[0]==3 and b[1]==a0[1] for a0,b in zip(a,a[1:])))

    def test_shallow_retaining_wall_and_portals(self):
        bays=list(game.wall_dressing_layout(320.))
        self.assertTrue(any(abs(s-345)<6 and h<1.06 for s,_,h,_ in bays))
        for start in (0.,80.,240.,320.,560.):
            for s,side,h,_ in game.wall_dressing_layout(start):
                junction=game.nearest_junction(s)
                if junction and side in game.junction_sides(junction[1]):
                    self.assertGreaterEqual(abs(s-junction[0]),4.6)
                self.assertFalse(any(ob.lateral*side>0 and abs(ob.s-s)<ob.length*.5+1.7
                                     for ob in game.obstacles_in_range(s-3,s+3)))
                self.assertLessEqual(h,game.wall_height(s,side)-game.floor_y(s,0)-.15)

    def test_emitted_geometry_clearance_and_ballistic_contract(self):
        for start,target in ((0.,8.),(240.,250.),(240.,298.),(320.,345.)):
            bay=min(game.wall_dressing_layout(start),key=lambda b:abs(b[0]-target))
            meshes=[]
            for _ in range(2):
                m=game.MeshBuilder()
                with mock.patch.object(game,'wall_dressing_layout',return_value=[bay]):
                    game.wall_dressing_chunk(m,start)
                meshes.append(m.as_array())
            v=meshes[0];np.testing.assert_array_equal(v,meshes[1])
            self.assertEqual(v.shape[1],9);self.assertTrue(np.isfinite(v).all())
            route=np.array([game.world(t,0.,0.) for t in np.linspace(bay[0]-2,bay[0]+2,121)])[:,[0,2]]
            distance=np.sqrt(((v[:,None,[0,2]]-route[None,:,:])**2).sum(axis=2)).min(axis=1)
            self.assertGreater(distance.min(),.70)
            shot=WorldShotMesh(v)
            self.assertEqual(len(shot.layers),np.count_nonzero(~np.isin(v[::3,8],tuple(NON_BALLISTIC_LAYERS))))
            # Axial shots within the walking lane cannot hit new wall lining.
            for across in (-.4,0.,.4):
                a=np.array(game.world(bay[0]-1,across,game.floor_y(bay[0],0)+1.55))
                b=np.array(game.world(bay[0]+1,across,a[1]))
                delta=b-a;length=np.linalg.norm(delta)
                self.assertIsNone(shot.first_hit(a,delta/length,length))

if __name__=='__main__':unittest.main()
