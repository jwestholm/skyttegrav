"""V3.10.0 regression: real triangles, skyl/skydd, and safe pre-portal checks.

No aim correction is used. Synthetic meshes are NOT physical validations.
"""
from __future__ import annotations

import math
import unittest
import numpy as np
from shot_geometry import WorldShotMesh, trace_world, cover_name
from enemy_system import EnemyAgent,EnemyDirector,EnemySpec,FrozenEnemyFrame
from test_v391_atomic_streaming import game


def plane(layer, left=-2.,right=2., z=5.):
    """One rendered 2-triangle front/back wall, same Nx9 as real MeshBuilder."""
    verts=[]
    positions=((left,0,z),(right,0,z),(right,2,z),
               (left,0,z),(right,2,z),(left,2,z))
    for x,y,zv in positions:
        verts.append((x,y,zv,0.,0.,1.,0.,0.,float(layer)))
    return np.asarray(verts, dtype='f4')


def built(*meshes):
    return WorldShotMesh(np.vstack(meshes))

O=(0.,1.,0.)
D=(0.,0.,1.)


class ExactWorldShotTests(unittest.TestCase):
    def test_real_earth_wall_stops_bullet(self):
        wall=built(plane(20))
        hit=trace_world(O,D,10.,(wall,))
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit.distance,5.,places=4)
        self.assertEqual(cover_name(hit.layer),'JORD')

    def test_actual_mesh_gap_passes_when_proxy_wall_would_not(self):
        # There is no rendered triangle between x=-0.35 .. +0.35.
        wall=built(plane(20,-2.,-.35),plane(20,.35,2.))
        self.assertIsNone(trace_world(O,D,9.,(wall,)))
        self.assertIsNotNone(trace_world((-.6,1.,0.),D,9.,(wall,)))
        self.assertIsNotNone(trace_world((+.6,1.,0.),D,9.,(wall,)))

    def test_leaf_cloth_puddles_and_flames_are_not_steel(self):
        for layer in (6,11,12,26):
            with self.subTest(layer=layer):
                self.assertIsNone(trace_world(O,D,9.,(built(plane(layer)),)))

    def test_canvas_texture_on_box_still_stops(self):
        # Canvas-colored solid crates are layer 9 and do NOT become phantom
        # penetrating cover merely because their texture name is canvas.
        self.assertIsNotNone(trace_world(O,D,9.,(built(plane(9)),)))
        self.assertEqual(cover_name(19),'SANDSÄCK')

    def test_first_solid_triangle_wins_over_later_wall(self):
        a=built(plane(26,z=2),plane(20,z=8))
        b=built(plane(17,z=4))
        result=trace_world(O,D,10.,(a,b))
        self.assertAlmostEqual(result.distance,4.,places=4)
        self.assertEqual(result.layer,17)

    def test_target_surface_is_not_automatically_cover(self):
        wall=built(plane(20,z=9.99))
        self.assertIsNone(trace_world(O,D,10.,(wall,)))
        self.assertIsNotNone(trace_world(O,D,11.,(wall,)))

    def test_no_hit_behind_ray_and_two_sided_geometry(self):
        mesh=built(plane(20))
        self.assertIsNone(trace_world(O,(0.,0.,-1.),10.,(mesh,)))
        self.assertIsNotNone(trace_world((0.,1.,9.),(0.,0.,-1.),10.,(mesh,)))

    def test_only_solid_mesh_blocks_frozen_enemy_without_aim_assist(self):
        # One head-sized point at the exact crosshair of the frozen camera.
        vp=game.perspective(80.,800./600.,.045,90.)@game.view_from(
            (0.,1.,0.),(0.,1.,1.))
        agent=EnemyAgent(EnemySpec(0,10.,0.,'unaware'))
        frame=FrozenEnemyFrame(800,600,tuple(tuple(float(v) for v in row) for row in vp),
            0.,((0,'head',(0.,1.,10.),.20),),((0,10.),))
        director=EnemyDirector();director.active={0:agent}
        gap=built(plane(20,-2.,-.40),plane(20,.40,2.),plane(26,z=4.))
        hit=director.resolve_frozen_hit(399.5,299.5,frame,
            lambda a,t,o,d:trace_world(o,d,t,(gap,)) is not None)
        self.assertEqual(hit,(0,'head'))
        self.assertTrue(agent.dead)
        # Same aim, different world surface (NOT a bigger hitbox): blocked.
        enemy2=EnemyAgent(EnemySpec(0,10.,0.,'unaware'))
        director.active={0:enemy2};director.eliminated.clear()
        solid=built(plane(20))
        blocked=director.resolve_frozen_hit(399.5,299.5,frame,
            lambda a,t,o,d:trace_world(o,d,t,(solid,)) is not None)
        self.assertIsNone(blocked)
        self.assertFalse(enemy2.dead)

    def test_actual_seeded_mesh_is_valid_and_has_excluded_foliage(self):
        data=game.make_chunk(0.)
        self.assertEqual(data.shape[1],9)
        soup=WorldShotMesh(data)
        self.assertGreater(len(soup.layers),25000)
        self.assertFalse(np.isin(soup.layers,[6,11,12,26]).any())
        self.assertTrue(np.all(np.isfinite(soup.bounds_min)))
        self.assertTrue(np.all(np.isfinite(soup.bounds_max)))

    def test_halt_earlier_still_looks_in_door_and_passes(self):
        from test_v399_stop_peek_watch import simulate
        for index in (0,1):
            with self.subTest(index=index):
                _, frames = simulate(index)
                stationary=[row for row in frames if row['state']=='observe_peek']
                self.assertTrue(stationary)
                marker=game.junction_marker(index)
                self.assertLessEqual(max(row['dist'] for row in stationary),
                                     marker - 2.40)
                self.assertGreater(max(abs(row['yaw']) for row in stationary),.90)
                self.assertGreater(frames[-1]['dist'], marker + 3.0)

    def test_frozen_frame_uses_its_own_world_mesh_not_later_stream(self):
        from test_v391_atomic_streaming import game
        game_obj=game.Trench.__new__(game.Trench)
        game_obj.distance=0.0
        game_obj.last_shot_cover=None
        # Current world has a new wall, but the rendered SHOT frame showed
        # a foliage screen. A delayed shot must use the old frame, not new.
        opaque=built(plane(20,z=5.))
        foliage=built(plane(6,z=5.))
        game_obj.last_world_shot_meshes=(opaque,)
        dummy=EnemyAgent(EnemySpec(0,10.,0.,'unaware'))
        old_clear=game_obj._enemy_shot_occluded(dummy,10.,O,D,
            route_at_shot=0.,enemy_route_at_shot=10.,meshes_at_shot=(foliage,))
        new_blocked=game_obj._enemy_shot_occluded(dummy,10.,O,D,
            route_at_shot=0.,enemy_route_at_shot=10.,meshes_at_shot=(opaque,))
        self.assertFalse(old_clear)
        self.assertTrue(new_blocked)

    def test_real_miss_spawns_impact_at_ray_triangle_not_fake_near_miss(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        vp=game.perspective(80.,800./600.,.045,90.)@game.view_from(
            (0.,1.,0.),(0.,1.,1.))
        wall=built(plane(20,z=5.))
        frame=FrozenEnemyFrame(800,600,tuple(tuple(float(v) for v in row) for row in vp),
            0.,(),(),(wall,))
        t=game.Trench.__new__(game.Trench)
        t.debug_jump_target=None
        t.pose_lab_index=-1
        t.last_enemy_frame=frame
        t.last_world_shot_meshes=(wall,)
        t.enemies=SimpleNamespace(resolve_frozen_hit=lambda *a,**k:None,
                                 hear_shot=lambda *a,**k:())
        t.arcade=SimpleNamespace(alive=True,player_shot=Mock())
        t.battlefield=SimpleNamespace(bullet_splash=Mock())
        t.distance=0.
        t.hit_notification='';t.hit_notification_until=0.
        self.assertIsNone(t.submit_game_hit(399.5,299.5,frame=frame))
        self.assertIn('JORD',t.hit_notification)
        args,kw=t.battlefield.bullet_splash.call_args
        self.assertAlmostEqual(args[0][2],5.,delta=.06)
        self.assertEqual(kw['material'],'earth')

    def test_photographic_asset_fallback_and_fog_does_not_change_geometry(self):
        source=game.FRAG
        self.assertIn('vec3(.295,.302,.297)',source)
        self.assertIn('terrain_pattern(v_world*vec3(3.6',source)
        self.assertIn('shadow_pcf(',source)
        self.assertIn('material_normals',source)


if __name__=='__main__':
    unittest.main()
