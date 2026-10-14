"""Exterior world patrol geometry and awareness, fully offline."""
from dataclasses import replace
import math
import unittest
from enemy_system import (EnemyDirector,EnemyAgent,exterior_patrol_spec,
                          off_trunk,actor_facing)
from shot_geometry import WorldShotMesh,trace_world
from combat_visibility import mesh_clear_body,enemy_shown_to_player_mesh
from test_v391_atomic_streaming import game


class ExteriorPatrolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=exterior_patrol_spec(7)
        cls.trench=game.Trench.__new__(game.Trench)
        cls.director=EnemyDirector()
        cls.trench.enemies=cls.director
        cls.agent=EnemyAgent(cls.spec)
        cls.director.active[cls.spec.enemy_id]=cls.agent
        cls.mesh=WorldShotMesh(game.make_chunk(720.0))

    def test_sparse_seeded_above_bank_not_fake_mainline(self):
        self.assertTrue(all(exterior_patrol_spec(i) is None for i in range(7)))
        selected=[i for i in range(7,49) if exterior_patrol_spec(i) is not None]
        self.assertEqual(selected,[7,15,23,31,39,47])
        self.assertEqual(self.spec.route_m,732.0)
        self.assertEqual(self.spec.exterior_side,-1)
        self.assertTrue(off_trunk(self.spec))
        s=self.agent.route_m
        x,y,z=self.trench.enemy_position(self.spec)
        cx,cz=game.sides(s,0)
        self.assertGreater(math.hypot(cx-x,cz-z),game.wall_width(s,-1)+.9)
        self.assertGreater(y,game.floor_y(s,0)+.9)

    def test_exterior_actor_moves_continuously_and_shared_pose(self):
        a=EnemyAgent(self.spec)
        d=EnemyDirector();d.active[self.spec.enemy_id]=a
        trench=game.Trench.__new__(game.Trench);trench.enemies=d
        positions=[]
        for _ in range(110):
            old=a.route_m
            a.update(1/60,visible=False)
            positions.append(a.route_m)
            self.assertLess(abs(old-a.route_m),.035)
            pt=trench.enemy_position(self.spec)
            expected=game.world_on_ground(a.route_m,
                    -game.wall_width(a.route_m,-1)-self.spec.exterior_clearance)
            for v,e in zip(pt,expected):self.assertAlmostEqual(v,e)
        self.assertGreater(max(positions)-min(positions),.2)
        self.assertGreater(a.gait_phase,.01)
        self.assertEqual(a.state,'idle')
        a.engage();old=a.route_m
        a.update(.05,visible=True)
        self.assertAlmostEqual(a.route_m,old)  # no patrol through the bank during firefight

    def test_ground_position_matches_world_triangle_height(self):
        a=self.agent
        for s in (730.,732.,734.):
            a.route_m=s
            x,y,z=self.trench.enemy_position(self.spec)
            hit=trace_world((x,y+5.,z),(0.,-1.,0.),10.,(self.mesh,))
            self.assertIsNotNone(hit)
            self.assertLess(abs(hit.distance-5.),.09)

    def test_enemies_cannot_detect_or_shoot_through_soil(self):
        pos=self.trench.enemy_position(self.spec)
        origin=(pos[0],pos[1]+1.48,pos[2])
        s=740.
        x,z=game.sides(s,0)
        # Low crouched silhouette is protected by the ACTUAL hillside.
        ground=game.floor_y(s,0)
        crouched=((x,ground+.44,z,.12),)
        upright=((x,ground+1.55,z,.12),)
        self.assertFalse(mesh_clear_body(origin,crouched,(self.mesh,)))
        self.assertTrue(mesh_clear_body(origin,upright,(self.mesh,)))
        # No mesh is NOT permission to attack through an unknown surface.
        self.assertFalse(mesh_clear_body(origin,upright,()))

    def test_patroller_not_mainline_threat_and_no_magic_knowledge(self):
        d=EnemyDirector()
        d.update(.02,724.,lambda _:False)
        a=d.active[self.spec.enemy_id]
        self.assertEqual(a.state,'idle')
        d.active={self.spec.enemy_id:a}  # another real mainline encounter is 8m ahead
        self.assertIsNone(d.current_threat(724.))
        self.assertAlmostEqual(d.clamp_advance(724.,1.25),1.25)
        self.assertFalse(a.hear_shot(724.))  # does not chase through a trench wall
        d.update(.02,724.,lambda _:True)
        self.assertEqual(a.state,'turning')
        d.active={self.spec.enemy_id:a}
        self.assertIsNone(d.current_threat(724.))

    def test_same_presented_pose_can_be_targeted_without_aim_assist(self):
        d=EnemyDirector();a=EnemyAgent(self.spec);d.active[self.spec.enemy_id]=a
        trench=game.Trench.__new__(game.Trench);trench.enemies=d
        p=trench.enemy_position(self.spec)
        route_m=728.
        x,z=game.sides(route_m,0.)
        eye=(x,game.floor_y(route_m,0.)+1.55,z)
        target=(p[0],p[1]+1.25,p[2])
        pv=game.perspective(80.,800./600.,.045,290.)@game.view_from(eye,target)
        frame=d.capture_frame(pv,800,600,route_m,trench.enemy_position,
                              lambda s:game.route(s)[2])
        frame=replace(frame,world_shot_meshes=(self.mesh,))
        self.assertEqual(len(frame.actor_routes),1)
        self.assertTrue(enemy_shown_to_player_mesh(frame,self.spec.enemy_id,eye))
        self.assertFalse(enemy_shown_to_player_mesh(
            replace(frame,world_shot_meshes=()),self.spec.enemy_id,eye))


if __name__=='__main__':unittest.main()
