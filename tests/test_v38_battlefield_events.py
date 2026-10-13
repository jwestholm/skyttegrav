"""V3.8 battlefield VFX offline tests. These do NOT prove projected GPU visuals."""
import ast
import math
import sys
import types
import unittest
from unittest.mock import patch
import numpy as np
from pathlib import Path

from battlefield_events import (
    BattlefieldEventDirector, MAX_PARTICLES, MAX_PENDING, MAX_AIRCRAFT,
    PARTICLE_VERTEX, PARTICLE_FRAGMENT, PLANE_VERTEX, PLANE_FRAGMENT,
    BattlefieldEffectRenderer,
)

ROOT=Path(__file__).resolve().parents[1]


def ground(s,off):
    # Fake irregular outdoor ground. Deterministic; never mutated by director.
    return (off * .7, .12*math.sin(s*.05)+.04*math.cos(off*.2), s * .8)


class BattlefieldV38Tests(unittest.TestCase):
    def test_shell_particle_lifecycle_and_no_ground_mutation(self):
        d=BattlefieldEventDirector(seed=1944)
        before=[ground(s, o) for s,o in [(33.,42.),(105.,-31.),(1.,21.)]]
        d.trigger('shell',0.,ground)
        self.assertEqual(len(d.pending),1)
        self.assertEqual(d.impacts_spawned,0)
        d.update(.20,0.,ground)
        self.assertEqual(d.impacts_spawned,0)
        d.update(.15,0.,ground)
        self.assertEqual(d.impacts_spawned,1)
        self.assertTrue(any(p.kind==0 for p in d.particles))
        self.assertTrue(any(p.kind==1 for p in d.particles))
        self.assertLessEqual(len(d.particles),MAX_PARTICLES)
        # No infinite-duration smoke or stone particles.
        for _ in range(130):d.update(.1,0.,ground,allow_events=False)
        self.assertEqual(d.active_count,0)
        self.assertEqual(before,[ground(s,o) for s,o in [(33.,42.),(105.,-31.),(1.,21.)]])

    def test_artillery_short_staggered_grounded_salvo(self):
        d=BattlefieldEventDirector(seed=22)
        d.trigger('barrage',130.,ground)
        impacts=list(d.pending)
        self.assertGreaterEqual(len(impacts),2)
        self.assertLessEqual(len(impacts),4)
        times=[p.at for p in impacts]
        self.assertEqual(times,sorted(times))
        self.assertGreater(times[-1]-times[0],.3)
        self.assertTrue(all(p.origin=='artillery' for p in impacts))
        # Full list of future impacts uses the actual heightfield.
        for impact in impacts:
            x,y,z=impact.position
            ss=z/.8;off=x/.7
            self.assertAlmostEqual(y,ground(ss,off)[1],places=7)
        for _ in range(80):d.update(.1,130.,ground,allow_events=False)
        self.assertEqual(d.impacts_spawned,len(impacts))
        self.assertEqual(len(d.pending),0)

    def test_aircraft_crosses_horizon_without_touching_ground(self):
        d=BattlefieldEventDirector(seed=99)
        d.trigger('flyby',220.,ground)
        self.assertEqual(len(d.aircraft),1)
        p=d.aircraft[0]
        x0,z0=p.x,p.z
        self.assertGreater(p.y,25.)
        d.update(.2,220.,ground,allow_events=False)
        self.assertGreater(math.hypot(p.x-x0,p.z-z0),2.)
        self.assertAlmostEqual(math.hypot(p.dx,p.dz),1.,places=7)
        for _ in range(110):d.update(.1,220.,ground,allow_events=False)
        self.assertFalse(d.aircraft)
        self.assertFalse(d.pending)
        for _ in range(60):d.update(.1,220.,ground,allow_events=False)
        self.assertFalse(d.particles)

    def test_seed_reproducible_fixed_step(self):
        left=BattlefieldEventDirector(seed=500)
        right=BattlefieldEventDirector(seed=500)
        for d in (left,right):
            d.trigger('barrage',300.,ground)
            d.trigger('flyby',300.,ground)
            for _ in range(72):d.update(.05,300.,ground,allow_events=False)
        self.assertEqual(left.pending,right.pending)
        self.assertEqual(left.aircraft,right.aircraft)
        self.assertEqual(left.particles,right.particles)
        self.assertEqual(left.events_started,right.events_started)
        self.assertEqual(left.impacts_spawned,right.impacts_spawned)

    def test_long_running_world_memory_bounded(self):
        d=BattlefieldEventDirector(seed=1944)
        for tick in range(3500):
            d.update(.15,tick*.01,ground)
            self.assertLessEqual(d.active_count,MAX_PARTICLES)
            self.assertLessEqual(len(d.pending),MAX_PENDING)
            self.assertLessEqual(len(d.aircraft),MAX_AIRCRAFT)
        self.assertGreaterEqual(d.events_started,5)
        self.assertGreater(d.impacts_spawned,2)
        d.enabled=False
        for _ in range(90):d.update(.15,100.,ground,allow_events=False)
        self.assertFalse(d.particles)
        self.assertFalse(d.aircraft)
        self.assertFalse(d.pending)

    def test_cover_gates_new_random_events_but_expiration_continues(self):
        d=BattlefieldEventDirector(seed=3)
        d.trigger('shell',0.,ground)
        for _ in range(380):d.update(.1,100.,ground,allow_events=False)
        self.assertEqual(d.events_started,1)
        self.assertEqual(d.active_count,0)
        self.assertEqual(len(d.pending),0)

    def test_reset_and_invalid_event(self):
        d=BattlefieldEventDirector(seed=13)
        with self.assertRaises(ValueError):d.trigger('weapon_hit',0.,ground)
        d.trigger('shell',10.,ground)
        d.update(.2,10.,ground)
        d.update(.2,10.,ground)
        self.assertTrue(d.particles)
        d.reset()
        self.assertEqual(d.elapsed,0.)
        self.assertEqual(len(d.particles),0)
        self.assertFalse(d.pending)
        self.assertFalse(d.aircraft)
        self.assertEqual(d.events_started,0)

    def test_visual_only_contract_in_source(self):
        src=(ROOT/'battlefield_events.py').read_text()
        game=(ROOT/'trench_3d_test.py').read_text()
        for label in ('def _explode(', 'class BattlefieldEventDirector',
                      'class BattlefieldEffectRenderer'):
            self.assertIn(label,src)
        self.assertNotIn('from src.engine',src)
        self.assertNotIn('resolve_frozen_hit(',src)
        self.assertIn('self.battlefield.update(',game)
        self.assertIn('self.battlefield_renderer.draw(',game)
        for kind in ('shell','barrage','flyby'):
            self.assertIn("trigger('"+kind+"'",game)
        self.assertIn('self.battlefield.reset()',game)
        self.assertIn('self.battlefield_renderer.release()',game)

    def test_renderer_reuses_gpu_buffers_between_explosions(self):
        class Uniform:
            def write(self, data):
                self.payload=data
            @property
            def value(self):return getattr(self,'_v',None)
            @value.setter
            def value(self, value):self._v=value
        class Program:
            def __init__(self):self.uniforms={}
            def __getitem__(self, key):
                if key not in self.uniforms:self.uniforms[key]=Uniform()
                return self.uniforms[key]
            def release(self):pass
        class Buffer:
            def __init__(self,data=None,reserve=None):
                self.capacity=reserve if reserve is not None else len(data)
                self.writes=[]
            def write(self, value):
                assert len(value)<=self.capacity
                self.writes.append(len(value))
            def release(self):pass
        class Vao:
            def __init__(self):self.calls=[]
            def render(self, mode=None, vertices=None):
                self.calls.append((mode,vertices))
            def release(self):pass
        class Context:
            def __init__(self):
                self.buffers=[]
                self.vaos=[]
                self.depth_mask=True
            def program(self,**kwargs):return Program()
            def buffer(self,data=None,reserve=None,dynamic=False):
                b=Buffer(data,reserve);self.buffers.append(b);return b
            def vertex_array(self,*args):
                vao=Vao();self.vaos.append(vao);return vao
        context=Context()
        renderer=BattlefieldEffectRenderer(context)
        self.assertEqual(len(context.buffers),2)
        d=BattlefieldEventDirector(seed=2)
        d.trigger('shell',20.,ground)
        d.trigger('flyby',20.,ground)
        for _ in range(7):d.update(.1,20.,ground,allow_events=False)
        eye=(0.,2.,0.)
        mat=np.identity(4,dtype='f4')
        with patch.dict(sys.modules, {'moderngl': types.SimpleNamespace(TRIANGLES=4)}):
            for _ in range(8):
                renderer.draw(d,mat,eye,(1.,0.,0.),(0.,1.,0.))
                d.update(.1,20.,ground,allow_events=False)
        self.assertEqual(len(context.buffers),2)
        self.assertTrue(context.buffers[0].writes)
        self.assertTrue(context.depth_mask)
        self.assertTrue(all(v<=420*6*11*4 for v in context.buffers[0].writes))
        self.assertGreater(renderer.particles_drawn,0)
        renderer.release()

    def test_opengl_shaders_have_no_banned_legacy_versions(self):
        for shader in (PARTICLE_VERTEX,PARTICLE_FRAGMENT,PLANE_VERTEX,PLANE_FRAGMENT):
            self.assertTrue(shader.startswith('#version 330'))
        self.assertIn('camera_right',PARTICLE_VERTEX)
        self.assertIn('camera_up',PARTICLE_VERTEX)
        self.assertIn('tint.a',PARTICLE_FRAGMENT)


if __name__=='__main__':unittest.main()
