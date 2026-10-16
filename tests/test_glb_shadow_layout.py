"""Real GL regression: shadow shader optimizes away UV and normal attributes."""
import tempfile
from pathlib import Path
import unittest
import numpy as np
import moderngl
from test_v397_branch_and_glb import synthetic_glb
from gltf_actor import GLBSkinnedRenderer

class GLBShadowLayoutTests(unittest.TestCase):
    def test_real_shadow_vao_uses_only_active_attributes(self):
        try:ctx=moderngl.create_standalone_context(require=330,backend='egl')
        except Exception as exc:self.skipTest('EGL unavailable: '+str(exc))
        try:
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/'fixture.glb';synthetic_glb(p)
                r=GLBSkinnedRenderer(ctx,p,(0.,1.,0.),(0.,-1.,0.))
                f=ctx.simple_framebuffer((32,32));f.use();f.clear(depth=1.)
                pal,model=r.asset.matrices('Walk',.2)
                r.draw_skeletal_shadows(np.eye(4,dtype='f4'),[(model,pal,None)])
                self.assertEqual(ctx.error,'GL_NO_ERROR')
                r.release();f.release()
        finally:ctx.release()
if __name__=='__main__':unittest.main()
