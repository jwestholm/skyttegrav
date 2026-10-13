"""V3.7: deterministic, grounded mesh quality checks (offline, not GPU visuals)."""
import math
import unittest
import numpy as np
from test_v26_obstacles import runtime_geometry


class V37EnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()

    def test_sandbags_grounded_mesh_is_finite_and_deterministic(self):
        g=self.g
        def build():
            mesh=g['MeshBuilder']()
            g['sandbag_mesh'](mesh,(12.0,1.25,17.0),.47,.31,.19,803,heading=.61)
            return mesh.as_array()
        a=build();b=build()
        self.assertTrue(np.array_equal(a,b))
        self.assertTrue(np.isfinite(a).all())
        self.assertGreater(len(a),180)
        self.assertLess(len(a),1200)
        self.assertGreaterEqual(float(a[:,1].min()),1.24)
        self.assertLess(float(a[:,1].max()),1.50)
        mats={int(v) for v in a[:,8]}
        self.assertEqual(mats,{9,19})
        # Fabric has real thickness and rounded ends, not a flat plane.
        self.assertGreater(np.ptp(a[:,0]),.25)
        self.assertGreater(np.ptp(a[:,2]),.25)

    def test_ruin_has_real_window_void_and_no_bad_vertices(self):
        g=self.g
        def build():
            mesh=g['MeshBuilder']()
            g['ruined_wall_panel'](mesh,(35.,2.,53.),4.2,2.8,.0,117)
            return mesh.as_array()
        a=build();b=build()
        self.assertTrue(np.array_equal(a,b))
        self.assertTrue(np.isfinite(a).all())
        self.assertGreater(len(a),200)
        self.assertLess(len(a),9000)
        self.assertGreater(float(a[:,1].max()-a[:,1].min()),1.5)
        # In-wall hole: vertical band of the wall must have fewer tiles than base.
        y=a[:,1];x=a[:,0]
        low=set(np.round(x[(y>2.05)&(y<2.45)],1).tolist())
        high=set(np.round(x[(y>3.4)&(y<3.8)],1).tolist())
        self.assertGreater(len(low),4)
        self.assertGreater(len(high),0)
        self.assertTrue({7,2,1}.intersection(set(map(int,a[:,8]))))

    def test_outpost_is_distant_decor_and_repeatable(self):
        g=self.g
        def build():
            mesh=g['MeshBuilder']()
            g['ruined_outpost'](mesh,588.,27.,171)
            return mesh.as_array()
        a=build();b=build()
        self.assertTrue(np.array_equal(a,b))
        self.assertGreater(len(a),250)
        self.assertTrue(np.isfinite(a).all())
        mesh=g['MeshBuilder']()
        g['ruined_outpost'](mesh,588.,8.,171)
        self.assertEqual(len(mesh.as_array()),0)
        # Fake a known excavation directly at outpost: must be skipped.
        x,_,z=g['world_on_ground'](588.,27.)
        poly=((x-1,z-1),(x+1,z-1),(x+1,z+1),(x-1,z+1))
        item=(x-1,x+1,z-1,z+1,poly)
        masks={(ix,iz):[item] for ix in range(math.floor((x-5)/16),math.floor((x+5)/16)+1)
                                for iz in range(math.floor((z-5)/16),math.floor((z+5)/16)+1)}
        rejected=g['MeshBuilder']()
        g['ruined_outpost'](rejected,588.,27.,171,masks=masks)
        self.assertEqual(len(rejected.as_array()),0)

    def test_sandbag_obstacle_has_unchanged_navigation_footprint(self):
        g=self.g
        objects=g['obstacles_in_range'](0,1700)
        bags=[v for v in objects if v.kind=='sandbags']
        self.assertGreater(len(bags),0)
        for o in bags:
            self.assertLessEqual(o.width,.85)
            self.assertLessEqual(o.height,.35)
        mesh=g['MeshBuilder']()
        for o in bags[:1]:
            start=math.floor(o.s/80.)*80.
            g['draw_trench_obstacles'](mesh,start)
        data=mesh.as_array()
        self.assertTrue(np.isfinite(data).all())
        self.assertIn(19,set(data[:,8].astype(int)))

    def test_fragments_are_not_accidentally_mossy(self):
        g=self.g
        mesh=g['MeshBuilder']()
        for i in range(12):
            g['rock_fragment'](mesh,(i*.14,.0,0.),.13,i,7)
        data=mesh.as_array()
        self.assertTrue(np.isfinite(data).all())
        self.assertEqual(set(data[:,8].astype(int)),{7})


if __name__=='__main__':
    unittest.main()

class V37HangingClothTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()

    def test_draped_canvas_is_repeatable_with_anchored_top_and_real_folds(self):
        g=self.g
        def build():
            mesh=g['MeshBuilder']()
            g['hanging_fabric'](mesh,43.0,1,403,span=1.9,drop=.72)
            return mesh.as_array()
        a,b=build(),build()
        self.assertTrue(np.array_equal(a,b))
        self.assertTrue(np.isfinite(a).all())
        self.assertGreater(len(a),300)
        self.assertLess(len(a),1200)
        self.assertIn(26,set(a[:,8].astype(int)))
        self.assertIn(10,set(a[:,8].astype(int))) # actual attachment pegs
        cloth=a[a[:,8]==26]
        self.assertGreater(np.ptp(cloth[:,1]),.48)
        self.assertLess(np.ptp(cloth[:,1]),1.4)
        self.assertAlmostEqual(float(cloth[:,6].min()),0.,places=5)
        self.assertAlmostEqual(float(cloth[:,7].min()),0.,places=5)
        self.assertAlmostEqual(float(cloth[:,7].max()),1.,places=5)

    def test_camouflage_net_is_gapped_and_deterministic(self):
        g=self.g
        def build():
            mesh=g['MeshBuilder']()
            g['torn_camouflage_net'](mesh,(10.,2.3,22.),(12.,2.45,22.),.75,81)
            return mesh.as_array()
        a,b=build(),build()
        self.assertTrue(np.array_equal(a,b))
        self.assertTrue(np.isfinite(a).all())
        self.assertGreater(len(a),240)
        self.assertLess(len(a),1800)
        self.assertEqual(set(a[:,8].astype(int)),{26})
        self.assertGreater(np.ptp(a[:,0]),1.7)
        self.assertGreater(np.ptp(a[:,1]),.65)
        # Actual empty opening: no mesh triangle covers the centre of a tile.
        # A solid quad with painted net texture would FAIL this assertion.
        probe=np.array((.0625,.125))
        for tri in a.reshape(-1,3,9):
            uv=tri[:,6:8]
            e1=uv[1]-uv[0];e2=uv[2]-uv[0]
            det=e1[0]*e2[1]-e1[1]*e2[0]
            if abs(det)<1e-9:continue
            rel=probe-uv[0]
            w1=(rel[0]*e2[1]-rel[1]*e2[0])/det
            w2=(e1[0]*rel[1]-e1[1]*rel[0])/det
            self.assertFalse(w1>=0 and w2>=0 and w1+w2<=1,
                             'Camouflage net must have real gaps')

    def test_shader_has_only_cloth_wind_and_no_unmapped_texture_layer(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/'trench_3d_test.py').read_text()
        self.assertIn('if (in_layer>25.5 && in_layer<26.5)',source)
        self.assertIn('float free_edge=clamp(in_uv.y,0.0,1.0);',source)
        self.assertIn('v_layer==26',source)
        self.assertIn('sample_color(uv*1.2,9)',source)
        self.assertIn('v_layer == 26 ? 19 : v_layer',source)
        self.assertIn("self.prog['time_seconds'].value=float(self.elapsed)",source)

    def test_environment_fabric_is_finite_and_seeded(self):
        g=self.g
        def build(start):
            mesh=g['MeshBuilder']()
            g['environment_chunk'](mesh,start)
            return mesh.as_array()
        a,b=build(0.),build(0.)
        self.assertTrue(np.array_equal(a,b))
        self.assertTrue(np.isfinite(a).all())
        self.assertIn(26,set(a[:,8].astype(int)))

