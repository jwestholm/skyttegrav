"""V3.8.7 grounded scenery / portal seam / honest frametime contracts.

Offline mesh+spatial tests. These cannot establish GTX 1070 frame pacing or
absence of every visible hole along infinite seed space.
"""
import ast
import math
import unittest
from pathlib import Path

import numpy as np
from test_v26_obstacles import runtime_geometry
from test_v31_no_surface_overlap import layers_at

SOURCE=Path(__file__).resolve().parents[1]/'trench_3d_test.py'
SRC=SOURCE.read_text(encoding='utf-8')


class PortalsAndProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()
        cls.mask=cls.g['world_excavation_masks'](240.)
        cls.segments=cls.g['_terrain_route_segments'](240.)

    def test_portal_mask_does_not_claim_unroofed_metres(self):
        g=self.g
        for s in (300.5,301.5,329.5,330.5):
            self.assertLess(g['tunnel_open'](s),.11)
            off=g['wall_width'](s,1)+.38
            x,z=g['sides'](s,off)
            self.assertFalse(g['soil_over_excavation'](x,z,self.mask),s)
        for s in (303.5,310.5,325.5,328.5):
            off=g['wall_width'](s,1)+.38
            x,z=g['sides'](s,off)
            self.assertTrue(g['soil_over_excavation'](x,z,self.mask),s)

    def test_exterior_props_reject_trench_roof_and_excavation(self):
        g=self.g
        for s in (303.5,310.5,325.5):
            off=g['wall_width'](s,1)+.38
            self.assertIsNone(g['exterior_prop_ground'](s,off,self.mask,self.segments))
        for s in (300.5,330.5):
            off=g['wall_width'](s,1)+1.80
            p=g['exterior_prop_ground'](s,off,self.mask,self.segments)
            self.assertIsNotNone(p)
            self.assertTrue(all(math.isfinite(v) for v in p))
            self.assertAlmostEqual(p[1],g['_exterior_y_world'](p[0],p[2],self.segments,{}),6)

    def test_scattered_rocks_have_actual_grid_ground_when_accepted(self):
        g=self.g
        n=0
        for s in np.arange(242.5,318.5,3.75):
            for off in (-22.,-15.,-8.,8.,15.,22.):
                pos=g['exterior_prop_ground'](float(s),float(off),self.mask,self.segments)
                if pos is None:continue
                n+=1
                self.assertAlmostEqual(pos[1],g['_exterior_y_world'](pos[0],pos[2],self.segments,{}),places=5)
        self.assertGreater(n,40)

    def test_covered_tunnel_side_join_reaches_grid_without_black_gap(self):
        g=self.g
        # Real emitted triangles: previously no layer at wall+1.0m.
        meshes=[g['make_chunk'](240.),g['make_chunk'](320.)]
        for s in (303.5,320.5,325.5,328.5):
            for side in (-1,1):
                for delta in (.45,.85,1.0,1.15,1.25):
                    x,z=g['sides'](s,side*(g['wall_width'](s,side)+delta))
                    earth=layers_at(meshes,x,z,[3,22])
                    self.assertTrue(earth,(s,side,delta))

    def test_dugout_mouth_soil_wings_never_cover_open_main_route(self):
        """Previously a soil wing at n=0 covered s=355.3, off=.35."""
        g=self.g
        meshes=[g['make_chunk'](240.),g['make_chunk'](320.)]
        for marker in (280.,352.):
            for s in np.arange(marker-9.3,marker+9.4,.7):
                if g['tunnel_open'](float(s))>.01:continue
                for off in (-.35,0.,.35):
                    x,z=g['sides'](float(s),off)
                    self.assertFalse(layers_at(meshes,x,z,[3,22]),
                                     (marker,float(s),off))

    def test_frozen_world_chunk_is_seed_repeatable(self):
        g=self.g
        a=g['make_chunk'](320.)
        b=g['make_chunk'](320.)
        self.assertTrue(np.array_equal(a,b))


class FrameTimeReporting(unittest.TestCase):
    def test_uncapped_frame_interval_is_reported_separately_from_safe_step(self):
        tree=ast.parse(SRC)
        trench=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Trench')
        run=next(n for n in trench.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        fragment=ast.get_source_segment(SRC,run)
        self.assertIn('raw_dt=max(0.00001,now-self.last)',fragment)
        self.assertIn('dt=min(.055,raw_dt)',fragment)
        self.assertIn('fps=1/max(.001,raw_dt)',fragment)
        self.assertIn('ms=raw_dt*1000',fragment)
        self.assertNotIn('fps=1/max(.001,dt)',fragment)

    def test_profile_f11_is_off_by_default_and_prints_phase_times(self):
        self.assertIn('self.profile_enabled=False',SRC)
        self.assertIn('pygame.K_F11',SRC)
        self.assertIn("labels=('events','update','chunks','draw','total')",SRC)


class GLDepthMaskCaching(unittest.TestCase):
    def test_particle_draw_reuses_libgl_lookup_between_frames(self):
        """The old Ubuntu fallback resolved libGL for EVERY smoke frame."""
        import ctypes
        import sys
        import types
        from unittest.mock import patch, Mock
        from battlefield_events import BattlefieldEffectRenderer, Particle

        class Uniform:
            value=None
            def write(self,*args):pass
        class Program:
            def __init__(self):self.fields={}
            def __getitem__(self,k):return self.fields.setdefault(k,Uniform())
        class Buffer:
            def write(self,*args):pass
        class VAO:
            def render(self,**kwargs):pass
        class Context:
            def program(self,**kwargs):return Program()
            def buffer(self,*args,**kwargs):return Buffer()
            def vertex_array(self,*args,**kwargs):return VAO()
        def get_boolean(which,pointer):
            ctypes.cast(pointer,ctypes.POINTER(ctypes.c_ubyte))[0]=1
        mock_get=Mock(side_effect=get_boolean)
        mock_mask=Mock()
        gl=types.SimpleNamespace(glGetBooleanv=mock_get,glDepthMask=mock_mask)
        particle=Particle(1.,1.,1.,0.,0.,0.,.03,1.5,.12,0,(.25,.25,.25),0.)
        director=types.SimpleNamespace(aircraft=[],particles=[particle])
        import numpy as np
        with patch('ctypes.util.find_library',return_value='libGL.so.1') as lookup, \
             patch('ctypes.CDLL',return_value=gl) as loader, \
             patch.dict(sys.modules,{'moderngl':types.SimpleNamespace(TRIANGLES=4)}):
            renderer=BattlefieldEffectRenderer(Context())
            for _ in range(3):
                renderer.draw(director,np.eye(4,dtype='f4'),(0.,1.,0.),
                              (1.,0.,0.),(0.,1.,0.))
        self.assertEqual(lookup.call_count,1)
        self.assertEqual(loader.call_count,1)
        self.assertEqual(mock_get.call_count,3)
        self.assertEqual(mock_mask.call_count,6)
        self.assertEqual(mock_mask.call_args.args[0],1)


if __name__=='__main__':
    unittest.main()
