"""V3.10.6 genuine side-room threat uses rendered triangles for LOS.

Offline geometry/camera tests; not a live GTX 1070 nor physical target test.
"""
from dataclasses import replace
import math
import unittest
from enemy_system import (EnemySpec,EnemyAgent,EnemyDirector,FrozenEnemyFrame,
                          side_room_enemy_spec,actor_facing)
from combat_visibility import mesh_clear_body,enemy_shown_to_player_mesh
from shot_geometry import WorldShotMesh,trace_world
from test_v391_atomic_streaming import game


class TrueSideRoomSight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index=7
        cls.spec=side_room_enemy_spec(cls.index,game.junction_side(cls.index))
        cls.mesh=WorldShotMesh(game.make_chunk(560.))
        cls.trench=game.Trench.__new__(game.Trench)
        cls.trench.enemies=EnemyDirector()
        cls.agent=EnemyAgent(cls.spec)
        cls.trench.enemies.active[cls.spec.enemy_id]=cls.agent
        cls.pos=cls.trench.enemy_position(cls.spec)

    def player_eye(self,s):
        x,z=game.sides(s,0.0)
        return (x,game.floor_y(s,0.)+1.55,z)

    def visual_frame(self,s):
        eye=self.player_eye(s)
        dest=(self.pos[0],self.pos[1]+1.,self.pos[2])
        pv=game.perspective(80,800/600,.045,290.)@game.view_from(eye,dest)
        frame=self.trench.enemies.capture_frame(pv,800,600,s,
             self.trench.enemy_position,lambda ss:game.route(ss)[2])
        return replace(frame,world_shot_meshes=(self.mesh,))

    def test_spawn_sparse_and_side_is_actual_excavation(self):
        self.assertTrue(all(side_room_enemy_spec(i,game.junction_side(i)) is None
                            for i in range(7)))
        selected=[i for i in range(7,49)
                  if side_room_enemy_spec(i,game.junction_side(i)) is not None]
        self.assertEqual(selected,[7,15,23,31,39,47])
        s=self.spec
        self.assertEqual(s.branch_index,7)
        self.assertEqual(s.branch_side,game.junction_side(7))
        self.assertAlmostEqual(self.pos[0],game.branch_point(7,s.branch_side,2.8)[0])
        self.assertAlmostEqual(self.pos[2],game.branch_point(7,s.branch_side,2.8)[2])
        cx,cz=game.sides(s.route_m,0.)
        self.assertGreater(math.hypot(self.pos[0]-cx,self.pos[2]-cz),3.)
        self.assertEqual(self.agent.route_m,s.route_m)

    def test_banked_wall_blocks_visibility_but_real_doorway_opens(self):
        source=(self.pos[0],self.pos[1]+1.48,self.pos[2])
        def visible(s):
            x,y,z=self.player_eye(s)
            return bool(mesh_clear_body(source,((x,y-.12,z,.2),),(self.mesh,)))
        self.assertFalse(visible(563.))
        self.assertFalse(visible(565.))
        self.assertTrue(visible(567.))
        self.assertFalse(mesh_clear_body(source,((0.,1.,0.,.2),),()))

    def test_last_drawn_projection_not_fake_on_screen_through_wall(self):
        for offset,expected in ((-5.,False),(-3.,False),(-2.,True),(-1.,True)):
            s=self.spec.route_m+offset
            frame=self.visual_frame(s)
            self.assertEqual(enemy_shown_to_player_mesh(frame,self.spec.enemy_id,
                              self.player_eye(s)),expected)
            self.assertTrue(any(id_==self.spec.enemy_id for id_,*rest in frame.hit_spheres))
            self.assertEqual(frame.actor_routes,((self.spec.enemy_id,self.spec.route_m),))

    def test_actor_facing_portal_and_no_trunk_path_lock(self):
        self.assertAlmostEqual(actor_facing(self.agent,0.),-math.pi*.5,delta=.3)
        d=EnemyDirector();d.update(.02,566.,lambda _:True,
                                   branch_side_at=game.junction_side)
        spawned=d.active[self.spec.enemy_id]
        self.assertEqual(spawned.state,'turning')
        self.assertIsNone(spawned.investigation_goal)
        self.assertIsNone(d.current_threat(566.))
        self.assertTrue(d.clamp_advance(566.,1.0)>0.0)
        # No magic awareness: with no LOS, this sentry must not engage.
        d2=EnemyDirector();d2.update(.02,566.,lambda _:False,
                                    branch_side_at=game.junction_side)
        self.assertEqual(d2.active[self.spec.enemy_id].state,'idle')

    def test_static_world_blocks_projectile_even_if_actor_body_is_in_ray(self):
        source=self.player_eye(563.)
        centre=(self.pos[0],self.pos[1]+1.22,self.pos[2])
        delta=[centre[i]-source[i] for i in range(3)]
        length=math.sqrt(sum(x*x for x in delta))
        direction=tuple(x/length for x in delta)
        self.assertIsNotNone(trace_world(source,direction,length,(self.mesh,)))
        source=self.player_eye(567.)
        delta=[centre[i]-source[i] for i in range(3)]
        length=math.sqrt(sum(x*x for x in delta))
        direction=tuple(x/length for x in delta)
        self.assertIsNone(trace_world(source,direction,length,(self.mesh,)))


if __name__=='__main__':unittest.main()
