"""V3.9.2 shader depth maps: matrix math and bounded GPU lifecycle.

Do not substitute fake GPU tests for the real Mesa shader compiler or the
user's GTX 1070 test. Fake context tests protect lifetime and integration.
"""
import math
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
from shadow_lighting import (SHADOW_GLSL,SHADOW_VERT,closest_shadow_lamp,
                             directional_matrix,lamp_matrix,look_at,ShadowRenderer)


class ShadowMatrixTests(unittest.TestCase):
    def test_sun_and_moon_are_different_stable_directions(self):
        sun=(.35,.085,.93);moon=(-.38,.40,-.69)
        a=directional_matrix((0,1.55,0),sun)
        b=directional_matrix((0,1.55,0),moon)
        self.assertTrue(np.isfinite(a).all())
        self.assertTrue(np.isfinite(b).all())
        self.assertFalse(np.allclose(a,b))
        # Camera movement smaller than a 0.5m snap leaves the light volume stable.
        self.assertTrue(np.allclose(a,directional_matrix((.12,1.55,.17),sun)))
        centre=np.array([0,1.4,0,1.])
        for mat in (a,b):
            p=mat@centre;p/=p[3]
            self.assertTrue(all(-1.<=v<=1. for v in p[:3]))

    def test_downward_lamp_projection_is_nondegenerate(self):
        mat=lamp_matrix((1,1.8,2))
        p=mat@np.array((1,0,2,1))
        p/=p[3]
        self.assertTrue(np.isfinite(p).all())
        self.assertTrue(all(-1.<v<1. for v in p[:3]))
        self.assertFalse(np.allclose(mat, np.eye(4)))

    def test_nearest_lamp_selection_is_bounded(self):
        lamps=[(2,1.8,0),(9,1.8,0),(-3,1.8,0)]
        self.assertEqual(closest_shadow_lamp(lamps,(1,1.5,0)),0)
        self.assertEqual(closest_shadow_lamp(lamps,(-2.8,1.5,0)),2)
        self.assertEqual(closest_shadow_lamp(lamps,(80,1.5,0)),-1)
        self.assertEqual(closest_shadow_lamp([], (0,0,0)),-1)

    def test_real_shadow_receiver_has_pcf_and_outside_light_boundary(self):
        self.assertIn('for(int x=-1;x<=1;x++)',SHADOW_GLSL)
        self.assertIn('projected.z>=1.0',SHADOW_GLSL)
        self.assertIn('projected.xy+vec2(x,y)*texel',SHADOW_GLSL)
        self.assertIn('light_mvp * world',SHADOW_VERT)


class FakeUniform:
    def __init__(self):self.value=None;self.data=None
    def write(self,data):self.data=bytes(data)


class FakeProgram:
    def __init__(self):self.uniforms={};self.released=False
    def __getitem__(self,k):return self.uniforms.setdefault(k,FakeUniform())
    def release(self):self.released=True


class FakeVAO:
    def __init__(self):self.calls=0;self.released=False
    def render(self,*a,**kw):self.calls+=1
    def release(self):self.released=True


class FakeBuffer:
    def __init__(self):self.released=False
    def release(self):self.released=True


class FakeTexture:
    def __init__(self):self.released=False;self.used=[]
    def use(self,location):self.used.append(location)
    def release(self):self.released=True


class FakeFramebuffer:
    def __init__(self):self.used=0;self.cleared=0;self.released=False
    def use(self):self.used+=1
    def clear(self,**kw):self.cleared+=1
    def release(self):self.released=True


class FakeCtx:
    def __init__(self):
        self.programs=[];self.textures=[];self.framebuffers=[];self.vaos=[]
        self.screen=FakeFramebuffer();self.viewport=(0,0,800,600);self.events=[]
    def program(self,**kw):
        p=FakeProgram();self.programs.append(p);return p
    def depth_texture(self,shape):
        t=FakeTexture();self.textures.append((shape,t));return t
    def framebuffer(self,**kw):
        f=FakeFramebuffer();self.framebuffers.append(f);return f
    def vertex_array(self,program,descriptions):
        # Both world and actor buffers must bind the 36-byte existing layout,
        # without copying another ~200K vertices to the GPU per chunk.
        self.vaos.append((program,descriptions,FakeVAO()))
        return self.vaos[-1][2]
    def disable(self,flag):self.events.append(('disable',flag))
    def enable(self,flag):self.events.append(('enable',flag))


class ShadowGPULifecycleTests(unittest.TestCase):
    def test_bounded_shadow_passes_reuse_vbo_without_breaking_streaming(self):
        fakegl=types.SimpleNamespace(DEPTH_TEST=1,BLEND=2,TRIANGLES=3,NEAREST=4)
        with patch.dict(sys.modules,{'moderngl':fakegl}):
            ctx=FakeCtx()
            shadows=ShadowRenderer(ctx,(.35,.085,.93),(-.38,.4,-.69))
            chunks={0:(FakeBuffer(),object(),100),1:(FakeBuffer(),object(),100),
                    8:(FakeBuffer(),object(),100)}
            actors=types.SimpleNamespace(meshes={('head',25):(FakeBuffer(),object())})
            instances=[(('head',25),np.eye(4,dtype='f4'))]
            program=FakeProgram()
            shadows.setup_material(program)
            try:
                shadows.draw_maps(chunks,actors,instances,(1,1.5,1),[(1,1.8,1)],
                                  (800,600),route_chunk=0,time_seconds=1.)
                self.assertEqual(ctx.screen.used,1)
                self.assertEqual(ctx.viewport,(0,0,800,600))
                self.assertEqual([f.cleared for f in ctx.framebuffers],[1,1,1])
                self.assertEqual(len(shadows.world_vaos),2)
                self.assertEqual(len(shadows.actor_vaos),1)
                self.assertTrue(all(t[1].released is False for t in ctx.textures))
                self.assertEqual(len(ctx.vaos),3)
                shadows.bind_material(program)
                self.assertEqual([program[k].value for k in
                    ('shadow_mode','shadow_lamp_index')],[1,0])
                self.assertTrue(all(t[1].used[-1]==i+2
                                    for i,t in enumerate(ctx.textures)))
                shadows.draw_maps(chunks,actors,instances,(1,1.5,1),[(1,1.8,1)],
                                  (800,600),0,2.)
                self.assertEqual(len(ctx.vaos),3)  # no repeated GL VAO allocation
                self.assertEqual(ctx.screen.used,2)
                old=shadows.world_vaos[0][1]
                chunks.pop(0)
                chunks[1]=(FakeBuffer(),object(),100) # reload same chunk index
                shadows.draw_maps(chunks,actors,instances,(10,1.5,1),[],(800,600),1,3.)
                self.assertTrue(old.released)
                self.assertEqual(shadows.lamp_index,-1)
                self.assertEqual(ctx.framebuffers[2].cleared,2) # lamp pass skipped
                shadows.enabled=False
                shadows.bind_material(program)
                self.assertEqual(program['shadow_mode'].value,0)
                self.assertEqual(program['shadow_lamp_index'].value,-1)
            finally:
                shadows.release()
            self.assertEqual(len(ctx.textures),3)
            self.assertTrue(all(t.released for size,t in ctx.textures))
            self.assertTrue(all(f.released for f in ctx.framebuffers))
            self.assertTrue(all(vao.released for key,desc,vao in ctx.vaos))
            self.assertFalse(any(vbo.released for vbo,_,count in chunks.values()))


if __name__=='__main__':unittest.main()
