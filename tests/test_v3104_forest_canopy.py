"""V3.10.4: procedural forest upgrade, texture/shadow/shot consistency.

GPU shader compilation is separately exercised by check_glsl_v397_egl.py.
"""
from __future__ import annotations
import pathlib
import random
import unittest

import numpy as np
from PIL import Image

from test_v391_atomic_streaming import game
from shot_geometry import WorldShotMesh, NON_BALLISTIC_LAYERS
from world_lod import NEAR,MID,FAR

ROOT=pathlib.Path(__file__).resolve().parents[1]

class CinematicForestTests(unittest.TestCase):
    def test_bundled_rgba_foliage_is_cutout_not_rectangular(self):
        path=ROOT/'assets'/'trees'/'foliage_cards.png'
        with Image.open(path) as a:
            self.assertEqual(a.size,(1024,1024))
            self.assertEqual(a.mode,'RGBA')
            alpha=np.asarray(a.getchannel('A'))
        self.assertGreater((alpha==0).sum(),60000)
        self.assertGreater((alpha>220).sum(),30000)

    def test_new_bark_maps_have_matching_size_and_open_gl_normals(self):
        for species in ('pine_bark','willow_bark'):
            with Image.open(ROOT/'assets'/'trees'/(species+'.png')) as diffuse, \
                 Image.open(ROOT/'assets'/'trees'/(species+'_nor_gl.png')) as normal:
                self.assertEqual(diffuse.size,(1024,1024))
                self.assertEqual(normal.size,(1024,1024))
                self.assertEqual(normal.mode,'RGB')

    def test_conifer_broadleaf_use_nonsolid_alpha_cards(self):
        for func,args in (
            (game.conifer_canopy,((0.,0.,0.),7.0,1.6)),
            (game.broadleaf_canopy,((0.,7.,0.),1.1)),
        ):
            mesh=game.MeshBuilder()
            func(mesh,*args,random.Random(33),NEAR)
            arr=mesh.as_array()
            self.assertTrue(np.isfinite(arr).all())
            self.assertGreater(np.count_nonzero(arr[:,8]==27),100)
            self.assertEqual(len(arr)%3,0)
            self.assertGreater(len(arr),120)

    def test_broadleaf_lod_budget_produces_fewer_cards_at_distance(self):
        samples=[]
        for quality in (NEAR,MID,FAR):
            m=game.MeshBuilder()
            game.broadleaf_canopy(m,(0.,7.,0.),1.0,random.Random(22),quality)
            samples.append(len(m.as_array()))
        self.assertGreater(samples[0],samples[1])
        self.assertGreater(samples[1],samples[2])

    def test_tree_trunk_tapers_and_normals_are_finite(self):
        m=game.MeshBuilder()
        game.tree_trunk(m,(0.,0.,0.),(.2,9.,.3),.25,13,NEAR)
        verts=m.as_array()
        self.assertEqual(set(verts[:,8]),{13.})
        low=verts[verts[:,1]<.1,:]
        high=verts[verts[:,1]>8.8,:]
        self.assertGreater(np.max(np.linalg.norm(low[:,[0,2]],axis=1)),
                           np.max(np.linalg.norm(high[:,[0,2]]-np.array([.2,.3]),axis=1))*1.7)
        self.assertTrue(np.isfinite(verts).all())

    def test_leaf_sprites_do_not_become_bulletproof(self):
        m=game.MeshBuilder()
        game.leaf_spray(m,(0.,1.,4.),2.0,1.,.5,tile=2,views=3)
        shot=WorldShotMesh(m.as_array())
        self.assertEqual(len(shot.layers),0)
        self.assertIn(27,NON_BALLISTIC_LAYERS)

    def test_shadow_cutout_matches_main_shader(self):
        from shadow_lighting import SHADOW_VERT,SHADOW_FRAG
        self.assertIn('v_layer==27',SHADOW_FRAG)
        self.assertIn('texture(foliage_cards,v_uv).a < .53',SHADOW_FRAG)
        self.assertIn('if (spray.a < .53) discard;',game.FRAG)
        self.assertIn('soil_color(v_world,n',game.FRAG)
        self.assertIn('self.foliage_texture.use(location=5)',ROOT.joinpath('trench_3d_test.py').read_text())

    def test_world_seed_and_triangles_are_reproducible(self):
        a=game.MeshBuilder();b=game.MeshBuilder()
        game.scenery_chunk(a,0.);game.scenery_chunk(b,0.)
        self.assertTrue(np.array_equal(a.as_array(),b.as_array()))
        self.assertTrue(np.isfinite(a.as_array()).all())

if __name__=='__main__':unittest.main()
