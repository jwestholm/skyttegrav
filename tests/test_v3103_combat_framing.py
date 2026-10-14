"""V3.10.3: physical framing, wall clearance and route-seed regression.

The projected position test is an offline pinhole model of intended 3D poses;
NOT an assertion that FPS, photorealism or physical accuracy improved.
"""
import ast
import math
from pathlib import Path
import unittest

from combat_tactics import encounter_lateral, tactical_cover_lane
from enemy_system import EnemySpec, EnemyDirector, encounter_spec

ROOT=Path(__file__).resolve().parents[1]


def functions_from_source(path, function_names, namespace):
    tree=ast.parse(path.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in function_names]
    assert len(nodes)==len(function_names), (len(nodes),function_names)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec'),namespace)
    return namespace


def geometry():
    return functions_from_source(ROOT/'trench_3d_test.py',
         {'noise','eased','turn_for_meter','route','sides','wall_width','cover_distance'},
         {'math':math,'SEED':1944,'WALL_HALF_WIDTH':1.12,'COVER_EYE_CLEARANCE':.49,
          '_ROUTE':[(0.,0.,0.)]})


class FramingRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo=geometry()

    def test_seeded_enemy_world_lanes_not_always_centered(self):
        samples=[encounter_spec(i) for i in range(4,104)]
        self.assertTrue(all(.25<=abs(s.lateral)<=.66 for s in samples))
        self.assertGreater(len({round(s.lateral,2) for s in samples}),30)
        self.assertGreater(sum(s.lateral>0 for s in samples),30)
        self.assertGreater(sum(s.lateral<0 for s in samples),30)
        self.assertEqual([encounter_spec(i) for i in range(104)],
                         [encounter_spec(i) for i in range(104)])
        self.assertEqual([encounter_spec(i).route_m for i in range(4)],
                         [32.,164.,258.,384.])
        self.assertEqual([encounter_spec(i).profile for i in range(4)],
                         ['unaware','ambush','cover','unaware'])

    def test_wall_lane_does_not_cross_bank_clearance(self):
        g=self.geo
        for s in (20.,150.,500.,800.,1100.,1600.):
            for lateral in (-.6,-.4,.4,.6):
                lane=tactical_cover_lane(lateral,s,g['wall_width'])
                side=1 if lane>=0 else -1
                self.assertLessEqual(abs(lane),g['cover_distance'](s,side)+1e-8)
                self.assertEqual(math.copysign(1,lane), -math.copysign(1,lateral))
        self.assertEqual(tactical_cover_lane(float('nan'),64,g['wall_width']),0.)

    def test_brain_lane_smooths_and_releases_without_teleport(self):
        source=ast.parse((ROOT/'trench_3d_test.py').read_text())
        cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='SoldierBrain')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef)
                 and n.name in {'update_contact_lane','_main_offset'}]
        ns={'math':math,'tactical_cover_lane':tactical_cover_lane,
            'wall_width':self.geo['wall_width'],'smooth':lambda a,b,t:a+(b-a)*t,
            'cover_distance':self.geo['cover_distance'],
            'obstacle_steering':lambda s:0.0,
            'near_junction':lambda s,radius=6.0:False,
            'BEND_FIRST':999999,'BEND_SPACING':34,
            'bend_marker':lambda i:999999+i*34,
            'bend_direction':lambda i:0.,
            'junction_marker':lambda i:999999+i*72}
        body=ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Brain',bases=[],keywords=[],
            body=methods,decorator_list=[])],type_ignores=[]))
        exec(compile(body,'<brain>','exec'),ns)
        b=ns['Brain']()
        for k,v in dict(state='main',blast_timer=0.,combat_offset=0.,
                        combat_lane_target=0.,combat_gaze=0.,fire_offset=0.,
                        branch_index=None,branch_side=0,visited=set()).items():setattr(b,k,v)
        b._close_to_junction=lambda s:(-1,-99999)
        seen=[]
        for _ in range(90):
            old=b.combat_offset
            b.update_contact_lane(1/60.,155.,.4)
            seen.append(b.combat_offset)
            self.assertLess(abs(b.combat_offset-old),.03)
        self.assertLess(b.combat_offset,-.16)
        self.assertLess(b.combat_gaze,-.1)
        self.assertLessEqual(abs(b._main_offset(155.)),self.geo['cover_distance'](155,-1)+1e-8)
        b.update_contact_lane(1/60.,155.,None)
        self.assertLess(abs(b.combat_offset),abs(seen[-1]))
        self.assertLess(abs(b.combat_gaze),.22)

    def test_bend_additions_are_smooth_and_leave_early_route_untouched(self):
        g=self.geo
        # All familiar start-area bend values must remain finite.
        for s in (0,32,64,164,258,384,430):
            self.assertTrue(math.isfinite(g['route'](s)[2]))
        before=g['turn_for_meter'](430.0)
        after=g['turn_for_meter'](430.01)
        self.assertLess(abs(before-after),.01)
        for s in (480,560,730,940,1040,1960,2010):
            p=g['route'](s);q=g['route'](s+.25)
            self.assertAlmostEqual(math.hypot(p[0]-q[0],p[1]-q[1]),.25,delta=.006)
            self.assertLess(abs(q[2]-p[2]),.12)

    def test_onscreen_spread_is_real_pinhole_geometry(self):
        # Frozen-world conceptual projection after contact lane converges;
        # static estimate is NOT substitute for live GPU screenshots.
        g=self.geo
        xs=[]
        for i in range(4,104):
            e=encounter_spec(i)
            player_s=e.route_m-8.
            lane=tactical_cover_lane(e.lateral,player_s,g['wall_width'])
            px,pz=g['sides'](player_s,lane)
            ex,ez=g['sides'](e.route_m,e.lateral)
            heading=g['route'](player_s)[2]+math.copysign(.22,lane)
            dx=(ex-px)*math.cos(heading)-(ez-pz)*math.sin(heading)
            dz=(ex-px)*math.sin(heading)+(ez-pz)*math.cos(heading)
            self.assertGreater(dz,0.)
            xs.append(.5+.5*dx/(dz*math.tan(math.radians(80)*.5)*(800/600)))
        self.assertTrue(all(.0<x<1. for x in xs))
        self.assertGreater(sum(x<1/3 for x in xs),10)
        self.assertGreater(sum(x>2/3 for x in xs),10)
        # Never assert physical-hit improvement based on this synthetic estimate.

    def test_first_four_off_center_encounters_keep_true_world_sight(self):
        from test_v391_atomic_streaming import game
        from combat_visibility import can_see_body, player_body
        geo=dict(route=game.route,sides=game.sides,wall_width=game.wall_width,
                 wall_height=game.wall_height,floor_y=game.floor_y,
                 obstacles_in_range=game.obstacles_in_range)
        for i in range(4):
            with self.subTest(enemy_id=i):
                e=encounter_spec(i)
                ss=e.route_m-8.
                lane=tactical_cover_lane(e.lateral,ss,game.wall_width)
                px,pz=game.sides(ss,lane)
                ex,ez=game.sides(e.route_m,e.lateral)
                body=player_body((px,game.floor_y(ss,lane)+1.55,pz),1.55)
                seen=can_see_body((ex,game.floor_y(e.route_m,e.lateral)+1.48,ez),
                                  body,e.route_m,ss,**geo)
                self.assertTrue(seen,'new flank would hide an existing first encounter')

    def test_bent_distant_chunk_is_real_finite_mesh(self):
        import numpy as np
        from test_v391_atomic_streaming import game
        mesh=game.make_chunk(960.)
        self.assertGreater(len(mesh),140000)
        self.assertEqual(mesh.shape[1],9)
        self.assertTrue(np.isfinite(mesh).all())

    def test_shot_frozen_3d_hit_uses_world_coordinate_not_fake_xy(self):
        director=EnemyDirector()
        e=encounter_spec(4)
        from enemy_system import EnemyAgent
        a=EnemyAgent(e)
        director.active[e.enemy_id]=a
        f=director.capture_frame(((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1)),
              800,600,e.route_m,lambda spec:(spec.lateral,0.,.25),lambda s:0.)
        self.assertTrue(f.hit_spheres)
        positions=[p for idx,part,p,r in f.hit_spheres]
        self.assertTrue(all(abs(x-e.lateral)<.8 for x,y,z in positions))
        self.assertEqual(f.actor_routes,((e.enemy_id,e.route_m),))


if __name__=='__main__':unittest.main()
