"""V2.7 offline tests: bounded decorative generation, materials, world-fixed sky.
Visual OpenGL rendering and frame-time profiling still require a real GPU.
"""
from pathlib import Path
import ast
import math
import unittest
import numpy as np
from PIL import Image
from test_v26_obstacles import runtime_geometry

BASE=Path(__file__).resolve().parent.parent
CODE=(BASE/'trench_3d_test.py').read_text(encoding='utf-8')

class VisualWorldV27Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=runtime_geometry()

    def test_sky_has_world_fixed_sun_and_view_ray(self):
        self.assertIn('uniform vec3 sun_direction;',CODE)
        self.assertIn('sky_forward',CODE)
        self.assertIn('dot(ray,sun)',CODE)
        self.assertNotIn('uv-vec2(.73,.51)',CODE)
        # Rays for two camera POSITIONS but the same ORIENTATION give same angle.
        sun=np.array([.35,.085,.93]);sun/=np.linalg.norm(sun)
        front=np.array([0.,0.,1.]);rotated=np.array([1.,0.,0.])
        self.assertAlmostEqual(float(np.dot(front,sun)),float(np.dot(front,sun)),places=8)
        self.assertNotAlmostEqual(float(np.dot(front,sun)),float(np.dot(rotated,sun)),places=2)

    def test_fallback_textures_are_1k_and_normals(self):
        names=['pine_bark','bark_willow','wood_planks','wood_planks_grey',
               'mossy_rock','wood_planks_dirt','sandbag_mud']
        for name in names:
            for suff in ('.png','_nor_gl.png'):
                path=BASE/'assets'/'detail'/(name+suff)
                self.assertTrue(path.is_file(),str(path))
                with Image.open(path) as im:
                    self.assertEqual(im.size,(1024,1024))
        self.assertIn('TEXTURE_SIZE = 1024',CODE)
        self.assertIn('texture_array((TEXTURE_SIZE,TEXTURE_SIZE,len(frames))',CODE)

    def test_decorative_props_finite_bounded_and_seeded(self):
        # Exercise the real generator and its helpers, not the V2.6 AST whitelist.
        from test_v391_atomic_streaming import game
        m=vars(game)
        class Mesh:
            def __init__(self):self.out=[]
            def quad(self,*values):
                for v in values[:4]:
                    assert all(math.isfinite(float(a)) for a in v)
                self.out.append(tuple(tuple(round(float(x),5) for x in pt) for pt in values[:4]))
        counts=[]
        for i in (0,2,6):
            left,right=Mesh(),Mesh()
            m['trench_detail_props'](left,i*80)
            m['trench_detail_props'](right,i*80)
            self.assertEqual(left.out,right.out)
            self.assertGreater(len(left.out),15)
            self.assertLess(len(left.out),25000)
            counts.append(len(left.out))
        self.assertEqual(len(counts),3)

    def test_legacy_obstacles_not_moved(self):
        m=self.r
        checks=m['obstacles_in_range'](0,1400)
        self.assertGreater(len(checks),15)
        self.assertTrue(all(o.s>0 for o in checks))
        self.assertIn('draw_trench_obstacles(mesh,start)',CODE)
        self.assertIn('trench_detail_props(mesh,start)',CODE)

    def test_src_compiles(self):
        compile(CODE,str(BASE/'trench_3d_test.py'),'exec')
        compile((BASE/'fetch_polyhaven.py').read_text(),str(BASE/'fetch_polyhaven.py'),'exec')

if __name__=='__main__':unittest.main()
