"""V3.10.4: deterministic pairs, shared geometry cover, real moving bodies.

These are offline behavior/world-mesh regressions, NOT physical shooting or
live render/frame-rate validation.
"""
import math
import unittest
from enemy_system import (EnemyAgent, EnemyDirector, encounter_spec,
                          encounter_partner_spec, primary_for_partner)
from test_v391_atomic_streaming import game


class EnemyPairsAndCover(unittest.TestCase):
    def test_deterministic_bounded_pairs_keep_four_original_encounters(self):
        self.assertTrue(all(encounter_partner_spec(i) is None for i in range(4)))
        self.assertEqual([encounter_spec(i).route_m for i in range(4)],
                         [32.,164.,258.,384.])
        pairs=[encounter_partner_spec(i) for i in range(4,35)]
        spawned=[p for p in pairs if p is not None]
        self.assertEqual(len(spawned),7)
        for spec in spawned:
            original=encounter_spec(primary_for_partner(spec.enemy_id))
            self.assertNotEqual(spec.enemy_id,original.enemy_id)
            self.assertGreater(spec.route_m,original.route_m)
            self.assertNotEqual(math.copysign(1,spec.lateral),
                                math.copysign(1,original.lateral))

    def test_pair_is_independent_and_frozen_body_is_real(self):
        d=EnemyDirector()
        d.update(1/60,510.,can_see_player=lambda a:True)
        lead=d.active[4]
        buddy=d.active[encounter_partner_spec(4).enemy_id]
        self.assertIsNot(lead,buddy)
        self.assertEqual((lead.state,buddy.state),('scanning','scanning'))
        frame=d.capture_frame(((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)),
                              800,600,510.,lambda spec:game.world(spec.route_m,spec.lateral,0.),
                              lambda s:game.route(s)[2])
        ids={ident for ident,part,centre,radius in frame.hit_spheres}
        self.assertIn(4,ids)
        self.assertIn(buddy.spec.enemy_id,ids)
        self.assertTrue(lead.eliminate('torso'))
        self.assertFalse(buddy.dead)
        self.assertEqual(buddy.state,'scanning')

    def test_cover_is_one_seeded_object_for_visual_and_aim_geometry(self):
        ob=game.paired_cover_at(4)
        self.assertIsNotNone(ob)
        self.assertEqual(ob.kind,'crate')
        self.assertAlmostEqual(ob.height,.98)
        self.assertEqual([o.index for o in game.obstacles_in_range(ob.s-.1,ob.s+.1)],
                         [ob.index])
        self.assertEqual([o.index for o in game.obstacles_in_range(ob.s-2,ob.s+2)
                          if o.index==ob.index],[ob.index])
        # A cover prop sitting in a chunk must render into the same mesh
        # as the near-field player bullet occlusion data.
        self.assertGreater(len(game.make_chunk(480.)),140000)

    def test_player_shot_creates_continuous_cover_move_not_a_teleport(self):
        d=EnemyDirector()
        d.update(1/60,510.,can_see_player=lambda a:True)
        buddy=d.active[encounter_partner_spec(4).enemy_id]
        before_route=buddy.route_m
        before_lat=buddy.lateral_offset
        responded=d.react_to_player_fire(510.,game.obstacles_in_range)
        self.assertIn(buddy.spec.enemy_id,responded)
        self.assertEqual(buddy.state,'seeking_cover')
        target=buddy.cover_goal
        ob=game.paired_cover_at(4)
        self.assertEqual(target[2],ob.index)
        for _ in range(85):
            prev_route=buddy.route_m
            prev_lane=buddy.lateral_offset
            buddy.update(1/60.,visible=True,player_route=510.)
            self.assertLessEqual(abs(buddy.route_m-prev_route),2.1/60.+1e-7)
            self.assertLessEqual(abs(buddy.lateral_offset-prev_lane),1.15/60.+1e-7)
        self.assertNotAlmostEqual(buddy.route_m,before_route)
        self.assertAlmostEqual(buddy.route_m,target[0],delta=.12)
        self.assertAlmostEqual(buddy.lateral_offset,
                               target[1]-buddy.spec.lateral,delta=.12)
        self.assertEqual(buddy.state,'sheltered')
        d.update(1/60.,510.,can_see_player=lambda a:True)
        # Model + frozen hit targets follow the same moved route in renderer.
        moved=game.world(buddy.route_m,buddy.spec.lateral+buddy.lateral_offset,0.)
        original=game.world(before_route,buddy.spec.lateral+before_lat,0.)
        self.assertGreater(math.dist(moved,original),.5)

    def test_no_cover_is_suppression_not_invisible_bunker(self):
        a=EnemyAgent(encounter_spec(5))
        a.engage()
        self.assertTrue(a.react_to_fire(None))
        self.assertEqual(a.state,'suppressed')
        self.assertIsNone(a.cover_goal)
        for _ in range(90):a.update(1/60.,visible=True,player_route=a.route_m-8.)
        self.assertNotEqual(a.state,'suppressed')

    def test_partner_does_not_regenerate_after_elimination(self):
        d=EnemyDirector();d.update(.02,510.,lambda _:True)
        ident=encounter_partner_spec(4).enemy_id
        d.active[ident].eliminate('head')
        d.update(.02,510.,lambda _:True)
        self.assertIn(ident,d.eliminated)
        d.update(.02,800.,lambda _:True)
        d.update(.02,510.,lambda _:True)
        self.assertNotIn(ident,d.active)
        self.assertIn(4,d.active)


if __name__=='__main__':unittest.main()
