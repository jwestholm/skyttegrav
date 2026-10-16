"""Small deterministic prop envelopes and the real shot-mesh contract."""
import random
import unittest

import numpy as np

from test_v391_atomic_streaming import game
from shot_geometry import WorldShotMesh, NON_BALLISTIC_LAYERS


class FieldworkTests(unittest.TestCase):
    def test_five_families_are_bounded_solid_and_seed_stable(self):
        for family in range(5):
            a=game.MeshBuilder(); b=game.MeshBuilder()
            spot=lambda x,z,y:(x,y,z)
            state=random.getstate()
            game.fieldwork_prop(a,spot,family,37)
            game.fieldwork_prop(b,spot,family,37)
            self.assertEqual(state,random.getstate())
            v=a.as_array()
            np.testing.assert_array_equal(v,b.as_array())
            self.assertTrue(np.isfinite(v).all())
            self.assertEqual(v.shape[1],9)
            self.assertLessEqual(abs(v[:,0]).max(),.47)
            self.assertLessEqual(abs(v[:,2]).max(),.14)
            self.assertLessEqual(v[:,1].max(),.55)
            self.assertGreaterEqual(v[:,1].min(),0.)
            self.assertFalse(set(v[:,8]) & NON_BALLISTIC_LAYERS)
            self.assertEqual(len(WorldShotMesh(v).layers),len(v)//3)

    def test_layout_clearance_ownership_and_covered_passages(self):
        samples=[]
        for start in (0.,80.,160.,240.,320.):
            layout=list(game.fieldwork_layout(start))
            self.assertEqual(layout,list(game.fieldwork_layout(start)))
            samples.extend(layout)
            for s,edge,family,index in layout:
                self.assertTrue(start<=s<start+game.CHUNK_LEN)
                self.assertGreaterEqual(abs(edge)-.14,.68)
                self.assertFalse(game.near_junction(s,6.))
                self.assertFalse(game.obstacles_in_range(s-1.5,s+1.5))
                side=-1 if edge<0 else 1
                for dx in (-.5,0,.5):
                    bank=game.wall_offset(s+dx,side,game.floor_y(s+dx,0)+.25,
                                          game.wall_height(s+dx,side))
                    self.assertLess(abs(edge)+.14,bank)
        self.assertGreater(len(samples),5)
        self.assertTrue(any(game.tunnel_drop(s)<-.1 for s,_,_,_ in samples))
        # A shifted streaming window must select identical global anchors.
        shifted=list(game.fieldwork_layout(40.))
        self.assertEqual([v for v in samples if 40<=v[0]<120],shifted)
        self.assertEqual(len({v[3] for v in samples}),len(samples))

    def test_tray_is_hollow_and_pail_has_no_solid_lid(self):
        for family,origin in ((0,(0.,.8,0.)),(1,(0.,.8,0.))):
            mesh=game.MeshBuilder()
            game.fieldwork_prop(mesh,lambda x,z,y:(x,y,z),family,37)
            v=mesh.as_array().reshape(-1,3,9)
            # Only the pail handle crosses the top; there is no top-cover face.
            upward=np.abs(v[:,:,4].mean(axis=1))>.9
            high=v[:,:,1].min(axis=1)>.23
            if family==0:
                self.assertFalse(np.any(upward & high))
            else:
                self.assertFalse(np.any(upward & high & (np.ptp(v[:,:,0],axis=1)>.1)))

    def test_eye_height_wall_bays_are_visible_seeded_and_clear(self):
        from unittest import mock
        bays=list(game.wall_dressing_layout(0.))
        self.assertGreaterEqual(len(bays),3)
        self.assertLess(bays[0][0],7.)
        self.assertTrue(all(h>=.65 for _,_,h,_ in bays))
        for bay in bays[:3]:
            a=game.MeshBuilder();b=game.MeshBuilder()
            with mock.patch.object(game,'wall_dressing_layout',return_value=[bay]):
                game.wall_dressing_chunk(a,0.)
                game.wall_dressing_chunk(b,0.)
            v=a.as_array()
            np.testing.assert_array_equal(v,b.as_array())
            self.assertTrue(np.isfinite(v).all())
            self.assertGreater(len(v),0)
            self.assertLess(len(v),16000)
            self.assertGreater(np.ptp(v[:,1]),1.)
            # Actual emitted geometry, including hanging kit, stays clear.
            route=np.array([game.world(t,0.,0.) for t in
                            np.linspace(bay[0]-2.,bay[0]+2.,121)])[:,[0,2]]
            distance=np.sqrt(((v[:,None,[0,2]]-route[None,:,:])**2).sum(axis=2)).min(axis=1)
            self.assertGreater(distance.min(),.70)
            solid=~np.isin(v[::3,8],tuple(NON_BALLISTIC_LAYERS))
            self.assertEqual(len(WorldShotMesh(v).layers),int(solid.sum()))
        shifted=list(game.wall_dressing_layout(40.))
        combined=bays+list(game.wall_dressing_layout(80.))
        self.assertEqual(shifted,[b for b in combined if 40<=b[0]<120])


if __name__=='__main__':unittest.main()
