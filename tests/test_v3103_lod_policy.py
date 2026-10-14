"""LOD V1: deterministic, conservative geometry quality, no ballistic rewrite."""
import unittest
import numpy as np
import world_lod
import trench_3d_test as game


class TestLODPolicy(unittest.TestCase):
    def test_conservative_lod_thresholds(self):
        self.assertIs(world_lod.lod_from_min_distance(5), world_lod.NEAR)
        self.assertIs(world_lod.lod_from_min_distance(14), world_lod.NEAR)
        self.assertIs(world_lod.lod_from_min_distance(35,2), world_lod.MID)
        self.assertIs(world_lod.lod_from_min_distance(80,2), world_lod.FAR)

    def test_projected_coverage_decreases_with_distance(self):
        near=world_lod.screen_coverage_px(3.0,8.,1080,80.)
        far=world_lod.screen_coverage_px(3.0,300.,1080,80.)
        self.assertGreater(near,far*30)

    def test_low_distance_canopy_is_cheaper_than_high(self):
        import random
        high=game.MeshBuilder(); low=game.MeshBuilder()
        base=(10.,0.,50.)
        game.conifer_canopy(high,base,8.,1.5,random.Random(44),world_lod.NEAR)
        game.conifer_canopy(low,base,8.,1.5,random.Random(44),world_lod.FAR)
        self.assertLess(len(low.vertices),len(high.vertices))
        self.assertGreater(len(low.vertices),0)

    def test_distant_tree_layout_determinism(self):
        a=game.MeshBuilder();b=game.MeshBuilder()
        game.distant_treeline_chunk(a,0.0)
        game.distant_treeline_chunk(b,0.0)
        self.assertTrue(np.array_equal(a.as_array(),b.as_array()))
        self.assertGreater(len(a.vertices),0)
        self.assertTrue(np.isfinite(a.as_array()).all())

    def test_bullet_mesh_format_unchanged(self):
        from shot_geometry import WorldShotMesh
        data=game.make_chunk(0.)
        self.assertEqual(data.shape[1],9)
        self.assertTrue(np.isfinite(data).all())
        self.assertIsInstance(WorldShotMesh(data),WorldShotMesh)


if __name__=='__main__': unittest.main()
