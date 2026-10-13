"""V3.2 exterior world-grid geometry: no folded ground ribbons.

Offline mesh-ray tests from the generated triangles, NOT string assertions.
OpenGL screenshots and GTX 1070 frametimes still require physical testing.
"""
import math
import unittest
import numpy as np
from test_v26_obstacles import runtime_geometry
from test_v31_no_surface_overlap import layers_at


class ExteriorWorldTerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()
        cls.mesh={float(c):cls.g['make_chunk'](float(c))
                  for c in (0,80,160,240,320)}

    def test_every_world_grid_triangle_is_small(self):
        for start,data in self.mesh.items():
            tris=data.reshape(-1,3,9)
            outdoor=tris[tris[:,0,8].astype(int)==22,:,:3]
            self.assertGreater(len(outdoor),80,(start,len(outdoor)))
            dx=np.ptp(outdoor[:,:,0],axis=1)
            dz=np.ptp(outdoor[:,:,2],axis=1)
            self.assertLessEqual(float(dx.max()),3.00001)
            self.assertLessEqual(float(dz.max()),3.00001)

    def test_exterior_ground_has_one_height_not_folded_layers(self):
        g=self.g
        values=list(self.mesh.values())
        inspected=0; coverage=0;multi=0
        # Continuous offsets beyond the trench, away from dugout junctions.
        for s in (12.37,22.61,39.31,90.73,105.39,119.57,
                  150.24,172.83,197.29,227.53,249.69,272.23,
                  289.38,335.47,379.23):
            for side in (-1,1):
                for off in (3.2,5.3,7.7,11.2,16.1,24.7,36.3):
                    x,z=g['sides'](s,side*off)
                    hits=layers_at(values,x,z,[22])
                    self.assertLessEqual(len(hits),1,(s,side,off,hits))
                    inspected+=1
                    coverage+=bool(hits)
                    multi+=len(hits)>1
        self.assertGreater(inspected,160)
        # Branch excavation footprints deliberately have no outdoor ground.
        self.assertGreater(coverage,inspected*.80,(coverage,inspected))
        self.assertEqual(multi,0)

    def test_world_grid_does_not_cross_player_corridor(self):
        g=self.g
        values=list(self.mesh.values())
        n=0
        for s in np.arange(3.17,390.,5.37):
            for across in (-.18,0.,.18):
                x,z=g['sides'](float(s),across)
                heights=layers_at(values,x,z,[22])
                self.assertFalse(heights,(s,across,heights))
                n+=1
        self.assertGreater(n,170)

    def test_dugout_shell_excludes_outdoor_layer_under_its_skin(self):
        g=self.g
        values=list(self.mesh.values())
        # Previously a world-grid ground patch pierced the cave overburden.
        for i in (0,4):
            if g['branch_type'](i)!='dugout': continue
            for side in g['junction_sides'](i):
                for along in (2.5,4.5,6.5):
                    if along>g['branch_length'](i)-1:continue
                    width=g['branch_half_width'](i,along)
                    x,y,z=g['branch_point'](i,side,along,width+.7,0.)
                    ground=layers_at(values,x,z,[22])
                    self.assertFalse(ground,(i,side,along,width,ground))

    def test_grid_ownership_is_seed_reproducible(self):
        g=self.g
        mesh=g['make_chunk'](160.0)
        self.assertTrue(np.array_equal(mesh,self.mesh[160.]))

if __name__=='__main__': unittest.main()
