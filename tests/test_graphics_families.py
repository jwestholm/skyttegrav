"""Six construction silhouettes and resident-caster/texel-grid regressions."""
import random
import unittest
from unittest import mock
import numpy as np
from test_v391_atomic_streaming import game
from shot_geometry import WorldShotMesh, NON_BALLISTIC_LAYERS
from shadow_lighting import directional_matrix, ShadowRenderer
from test_v392_shadows import FakeCtx, FakeBuffer
import types

class FamilyTests(unittest.TestCase):
    def test_six_coherent_families_for_multiple_seeds(self):
        for seed in (1944,37,902):
            with mock.patch.object(game,'SEED',seed):
                self.assertEqual({game.lining_section(i*24+12)[0] for i in range(6)},set(range(6)))
                for i in range(12):
                    self.assertEqual(game.lining_section(i*24+6),game.lining_section(i*24+18))

    def test_family_geometry_and_real_gaps(self):
        signatures=[];hits=[]
        s,side,height,index=next(game.wall_dressing_layout(0.))
        for family in range(6):
            m=game.MeshBuilder()
            with mock.patch.object(game,'lining_section',return_value=(family,0)),mock.patch.object(game,'wall_dressing_layout',return_value=[(s,side,1.5,index)]):
                game.wall_dressing_chunk(m,0.)
            v=m.as_array();self.assertTrue(np.isfinite(v).all())
            shot=WorldShotMesh(v)
            self.assertEqual(len(shot.layers),np.count_nonzero(~np.isin(v[::3,8],tuple(NON_BALLISTIC_LAYERS))))
            signatures.append((len(v),v[:,:3].tobytes()))
            # Through a deliberate board gap; base soil is NOT part of this fixture.
            t=s+.22;y=game.floor_y(t,0)+.9
            a=np.array(game.world(t,0,y));b=np.array(game.world(t,side*2,y))
            hits.append(shot.first_hit(a,b-a,np.linalg.norm(b-a)) is not None)
            route=np.array([game.world(t,0,0) for t in np.linspace(s-2,s+2,121)])[:,[0,2]]
            dist=np.sqrt(((v[:,None,[0,2]]-route[None,:,:])**2).sum(axis=2)).min()
            self.assertGreater(dist,.70)
        self.assertEqual(len(set(signatures)),6)
        self.assertTrue(hits[0]);self.assertFalse(hits[3]);self.assertFalse(hits[4]);self.assertTrue(hits[5])

    def test_within_family_age_variation_is_seeded_without_rng_changes(self):
        # Same fixture/camera, different real section identities. Changing the
        # section must affect construction, not merely translate the mesh.
        bay=next(game.wall_dressing_layout(0.))
        for family in range(6):
            variants=[]
            for zone in (4,10):
                outputs=[]
                for repeat in range(2):
                    state=random.getstate();m=game.MeshBuilder()
                    with mock.patch.object(game,'lining_section',return_value=(family,zone)),mock.patch.object(game,'wall_dressing_layout',return_value=[bay]):
                        game.wall_dressing_chunk(m,0.)
                    self.assertEqual(state,random.getstate())
                    outputs.append(m.as_array())
                np.testing.assert_array_equal(*outputs)
                variants.append(outputs[0])
            self.assertFalse(np.array_equal(*variants),family)
            # Existing photographed grey/dirt timber, not random RGB tint.
            self.assertIn(16.,variants[0][:,8])
            self.assertIn(18.,variants[1][:,8])

    def test_shortened_bays_keep_grounded_feet_and_global_ownership(self):
        for start in (0.,240.,320.):
            for bay in list(game.wall_dressing_layout(start))[:3]:
                m=game.MeshBuilder()
                with mock.patch.object(game,'wall_dressing_layout',return_value=[bay]):
                    game.wall_dressing_chunk(m,start)
                v=m.as_array()
                s=bay[0]
                # Embedded feet remain below the sampled local floor; no
                # shrink/age transform may lift an entire panel off the earth.
                floor=min(game.floor_y(s+d,bay[1]*game.lining_bank(s+d,bay[1])) for d in (-1.5,0.,1.5))
                self.assertLess(v[:,1].min(),floor+.06)

class ShadowStabilityTests(unittest.TestCase):
    def test_texel_steps_sun_and_moon(self):
        for resolution,direction in ((1536,(.35,.085,.93)),(1024,(-.38,.4,-.69))):
            xy=np.array([directional_matrix((x,1.55,-4),direction,resolution=resolution)[:2,3]*resolution*.5 for x in np.linspace(.2,.3,101)])
            np.testing.assert_allclose(xy,np.round(xy),atol=1e-4)
            self.assertLessEqual(abs(np.diff(xy,axis=0)).max(),1.0001)

    def test_loaded_remote_route_caster_immediate_and_eviction_safe(self):
        gl=types.SimpleNamespace(NEAREST=1,BLEND=2,DEPTH_TEST=3,TRIANGLES=4)
        with mock.patch.dict('sys.modules',{'moderngl':gl}):
            ctx=FakeCtx();renderer=ShadowRenderer(ctx,(.35,.085,.93),(-.38,.4,-.69))
            chunks={2:(FakeBuffer(),None,6)}
            renderer.draw_maps(chunks,None,[],(0,1.55,0),[],(800,600),0,0.)
            vao=renderer.world_vaos[2][1];self.assertEqual(vao.calls,2)
            renderer.draw_maps(chunks,None,[],(0,1.55,0),[],(800,600),1,0.)
            self.assertEqual(vao.calls,4)
            renderer.draw_maps({},None,[],(0,1.55,0),[],(800,600),1,0.)
            self.assertTrue(vao.released);renderer.release()

if __name__=='__main__':unittest.main()
