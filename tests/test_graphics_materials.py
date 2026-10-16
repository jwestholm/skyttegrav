"""Material-coordinate and shading-normal invariants, without moving cover."""
import unittest
import numpy as np
from test_v391_atomic_streaming import game


class MaterialSurfaceTests(unittest.TestCase):
    def test_smooth_quad_preserves_triangle_positions_uv_and_layer(self):
        points=((0.,0.,0.),(0.,1.,0.),(1.,1.,.1),(1.,0.,0.))
        uv=((0.,0.),(0.,1.),(1.,1.),(1.,0.))
        a=game.MeshBuilder();b=game.MeshBuilder()
        a.quad(*points,20,uv)
        normals=((0.,0.,1.),)*4
        b.quad(*points,20,uv,normals=normals)
        x=a.as_array();y=b.as_array()
        np.testing.assert_array_equal(x[:,[0,1,2,6,7,8]],y[:,[0,1,2,6,7,8]])
        np.testing.assert_array_equal(y[:,3:6],np.tile((0,0,1),(6,1)))

    def test_global_surface_normals_are_finite_inward_and_unit(self):
        for s in (0.,8.,15.,79.999,80.,80.001,298.,307.):
            floor=game.earth_surface_normal(s,.1)
            self.assertGreater(floor[1],.8)
            for side in (-1,1):
                y=game.floor_y(s,0)+1.
                n=game.earth_surface_normal(s,y,side)
                p=np.array(game.world(s,side*game.wall_offset(s,side,y,game.wall_height(s,side)),y))
                toward=np.array(game.world(s,0,y))-p
                self.assertTrue(np.isfinite(n).all())
                self.assertAlmostEqual(np.linalg.norm(n),1.,places=6)
                self.assertGreater(np.dot(n,toward),0.)
        # Global derivatives do not depend on which chunk owns a border vertex.
        np.testing.assert_allclose(game.earth_surface_normal(79.999,1.,1),
                                   game.earth_surface_normal(80.001,1.,1),atol=.01)

    def test_long_plank_top_grain_uses_real_dimensions(self):
        m=game.MeshBuilder()
        game.local_box(m,10.,0.,0.,1.2,.2,.05,18)
        v=m.as_array()
        top=v[6:12,6:8]
        self.assertAlmostEqual(np.ptp(top[:,0]),.2/1.6,places=6)
        self.assertAlmostEqual(np.ptp(top[:,1]),1.2/2.4,places=6)
        side=v[12:18,6:8]
        self.assertAlmostEqual(np.ptp(side[:,0]),.05/1.6,places=6)
        self.assertAlmostEqual(np.ptp(side[:,1]),1.2/2.4,places=6)
        self.assertEqual(set(v[:,8]),{18.})

if __name__=='__main__':unittest.main()
