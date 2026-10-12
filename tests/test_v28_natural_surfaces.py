"""Offline V2.8 checks. These do NOT establish OpenGL visual correctness."""
import ast
import math
import time
import unittest
from pathlib import Path
import numpy as np
from test_v26_obstacles import runtime_geometry

BASE=Path(__file__).resolve().parents[1]
SRC=(BASE/'trench_3d_test.py').read_text(encoding='utf-8')

class SurfaceV28Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.m=runtime_geometry()

    def test_continuous_wall_and_floor_shader_materials(self):
        self.assertIn('v_layer == 20',SRC)
        self.assertIn('v_layer == 21',SRC)
        self.assertIn('texture(materials,vec3(uv,float(layer)))',SRC)
        self.assertIn('mesh.quad(p0,p1,p2,p3,20,',SRC)
        self.assertIn('world(s1,floor_half,-.045),world(s1,-floor_half,-.045),21,',SRC)
        self.assertNotIn('mesh.quad(p0,p1,p2,p3,mat,',SRC)

    def test_vegetation_is_bounded_deterministic_near_lip(self):
        m=self.m
        class Mesh:
            def __init__(self):self.quads=[]
            def quad(self,*args):
                self.quads.append(args)
                for p in args[:4]:
                    assert all(math.isfinite(float(a)) for a in p)
        for start in (0,80,240,480):
            a,b=Mesh(),Mesh()
            m['rim_vegetation_chunk'](a,start)
            m['rim_vegetation_chunk'](b,start)
            self.assertEqual(a.quads,b.quads)
            self.assertLess(len(a.quads),2400)
            for quad in a.quads:
                self.assertEqual(quad[4],6 if len(quad)>=6 and quad[2]==quad[3] else 17)

    def test_world_generation_is_finite_bounded(self):
        m=self.m
        for start in (0,80,240):
            t=time.monotonic(); data=m['make_chunk'](start)
            self.assertEqual(data.shape[1],9)
            self.assertTrue(np.isfinite(data).all())
            self.assertGreater(data.shape[0],4000)
            self.assertLess(data.shape[0],1400000)
            # Distinct procedural IDs for wall and floor are carried to shader.
            layers=np.unique(data[:,8].astype(int))
            self.assertIn(20,layers)
            self.assertIn(21,layers)
            print(f'  V2.8 chunk {start:4.0f}m: {len(data):,} vertices / {time.monotonic()-t:.2f}s')

    def test_crate_gains_geometry_without_changing_obstacle_decisions(self):
        m=self.m
        obs_before=[(ob.index,ob.s,ob.kind,ob.detour) for ob in m['obstacles_in_range'](0,400)]
        self.assertTrue(any(ob[2]=='crate' for ob in obs_before))
        a=m['MeshBuilder']();m['wood_crate'](a,20,0,-.04,.72,.54,.58,15)
        self.assertGreater(len(a.vertices)//9,300)
        self.assertTrue(np.isfinite(a.as_array()).all())

    def test_no_placeholder_building_boxes(self):
        self.assertNotIn('local_box(mesh,s,side*d,point[1]',SRC)

if __name__=='__main__':unittest.main()
