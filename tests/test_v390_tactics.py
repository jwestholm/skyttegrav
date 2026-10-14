"""V3.9.0: deterministic AI, onscreen fairness, cover response, progression."""
import ast
import math
from pathlib import Path
import unittest

from arcade_mode import ArcadeRun
from combat_tactics import difficulty_at, MATERIALS, projected_visible
from combat_visibility import enemy_shown_to_player
from enemy_system import EnemyAgent, EnemySpec, EnemyDirector, FrozenEnemyFrame
from battlefield_events import BattlefieldEventDirector, MAX_PARTICLES


def straight_route(s):return (0.,float(s),0.)
def straight_sides(s,side):return (float(side),float(s))
def trench_width(s,side):return 1.15
def trench_height(s,side):return 2.1
def ground(s,lateral=0):return 0.0
def no_obstacles(a,b):return ()
GEO=dict(route=straight_route,sides=straight_sides,wall_width=trench_width,
         wall_height=trench_height,floor_y=ground,obstacles_in_range=no_obstacles)


class CombatAIRegression(unittest.TestCase):
    def test_progression_is_monotonic_and_keeps_fairness(self):
        steps=[difficulty_at(d) for d in (0,180,450,850)]
        self.assertEqual([x.level for x in steps],[0,1,2,3])
        self.assertTrue(all(a.accuracy_scale < b.accuracy_scale for a,b in zip(steps,steps[1:])))
        self.assertTrue(all(a.reaction_grace > b.reaction_grace for a,b in zip(steps,steps[1:])))
        self.assertTrue(all(x.warning_shots>=1 for x in steps))
        self.assertEqual(difficulty_at(-500),steps[0])

    def test_explicit_material_policies(self):
        self.assertTrue(MATERIALS['canvas'].hides)
        self.assertLess(MATERIALS['canvas'].bullet_stopping,.1)
        self.assertEqual(MATERIALS['earth'].bullet_stopping,1)
        self.assertEqual(MATERIALS['rock'].bullet_stopping,1)
        self.assertLess(MATERIALS['crate'].bullet_stopping,MATERIALS['sandbags'].bullet_stopping)

    def test_initial_enemy_peeks_twice_then_moves_and_shoots(self):
        enemy=EnemyAgent(EnemySpec(0,32.0,-.18,'unaware'))
        self.assertTrue(enemy.begin_tactical_encounter())
        self.assertEqual(enemy.state,'scanning')
        phases=[enemy.state]
        last=enemy.route_m
        movement_seen=False
        offset_seen=False
        for k in range(340):
            enemy.update(.05,visible=True,player_route=14.0)
            if enemy.state!=phases[-1]:phases.append(enemy.state)
            self.assertLessEqual(abs(enemy.route_m-last),.12)
            movement_seen|=enemy.route_m<32-1.0
            offset_seen|=abs(enemy.lateral_offset)>.025
            last=enemy.route_m
            if enemy.shots_fired:break
        self.assertGreaterEqual(enemy.peek_count,2)
        self.assertTrue(movement_seen)
        self.assertTrue(offset_seen)
        for stage in ('scanning','peeking','hiding','rushing','locating','turning','aiming','firing'):
            self.assertIn(stage,phases,phases)
        self.assertEqual(enemy.shots_fired,1)
        self.assertGreater(enemy.route_m,14.0+6.7)

    def test_patrol_cannot_engage_through_occluded_corner(self):
        director=EnemyDirector()
        for _ in range(400):director.update(.05,8,can_see_player=lambda a:False)
        self.assertEqual(director.active[0].state,'idle')
        self.assertEqual(director.gunshots_this_frame,())
        self.assertEqual(director.active[0].route_m,32.0)

    def test_lost_contact_triggers_reposition_not_through_wall_fire(self):
        enemy=EnemyAgent(EnemySpec(1,32.0,.15,'ambush'))
        enemy.begin_tactical_encounter()
        for _ in range(260):enemy.update(.05,visible=True,player_route=16)
        shots=enemy.shots_fired
        for _ in range(26):enemy.update(.05,visible=False,player_route=16)
        self.assertEqual(enemy.shots_fired,shots)
        self.assertIn(enemy.state,('searching','repositioning','locating'))

    def test_damage_can_be_gated_by_onscreen_fairness(self):
        run=ArcadeRun()
        for _ in range(100):
            self.assertFalse(run.enemy_shot(0,clear_sight=True,
                distance_metres=9,allow_damage=False))
        self.assertTrue(run.alive)
        self.assertEqual(run.incoming_shots,100)
        self.assertEqual(run.last_incoming_event,'warning')

    def test_visible_opportunity_requires_viewport_and_world_LOS(self):
        mat=((1.,0.,0.,0.),(0.,1.,0.,0.),(0.,0.,1.,0.),(0.,0.,0.,1.))
        frame=FrozenEnemyFrame(800,600,mat,0.,((0,'torso',(0.,.5,.5),.25),),((0,0.),))
        self.assertTrue(enemy_shown_to_player(frame,0,(0.,.5,-.5),geometry=GEO))
        self.assertFalse(enemy_shown_to_player(frame,1,(0.,.5,-.5),geometry=GEO))
        behind=FrozenEnemyFrame(800,600,mat,0.,((0,'torso',(0.,.5,2.0),.25),),((0,0.),))
        self.assertFalse(enemy_shown_to_player(behind,0,(0.,.5,-.5),geometry=GEO))
        wall=FrozenEnemyFrame(800,600,mat,0.,((0,'torso',(2.0,.5,.5),.25),),((0,0.),))
        self.assertFalse(enemy_shown_to_player(wall,0,(0.,.5,-.5),geometry=GEO))

    def test_splashes_are_bounded_and_do_not_modify_world(self):
        fx=BattlefieldEventDirector(seed=9)
        before=fx.events_started
        for _ in range(60):fx.bullet_splash((0.,1.,0.),material='wood')
        self.assertLessEqual(fx.active_count,MAX_PARTICLES)
        self.assertEqual(fx.events_started,before)
        self.assertEqual(len(fx.pending),0)
        self.assertGreater(len(fx.particles),0)
        with self.assertRaises(ValueError):fx.bullet_splash((0,0,0),material='cotton')

    def test_soldier_cover_overlay_decides_without_new_navigation(self):
        # Extract real pure SoldierBrain class without importing OpenGL/GPU.
        root=Path(__file__).resolve().parent.parent
        tree=ast.parse((root/'trench_3d_test.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SoldierBrain')
        names={'receive_fire','update_fire_cover','combat_posture'}
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
        code=compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='B',bases=[],keywords=[],
                          body=methods,decorator_list=[])],type_ignores=[])),'<brain>','exec')
        ns={'math':math,'smooth':lambda a,b,t:a+(b-a)*t,
            'cover_distance':lambda s,side:.48}
        exec(code,ns)
        brain=ns['B']()
        for k,v in dict(fire_timer=0.,fire_recent=0.,fire_count=0,
                        fire_offset=0.,fire_side=1,fire_urgency=0,
                        phase='',state='main',blast_timer=0.).items():setattr(brain,k,v)
        self.assertIsNone(brain.combat_posture(True))
        brain.receive_fire(from_side=-1)
        self.assertEqual(brain.combat_posture(True),1)
        brain.update_fire_cover(.1,20,True)
        self.assertLess(brain.fire_offset,0.0)
        brain.receive_fire(from_side=-1)
        brain.receive_fire(from_side=-1)
        self.assertEqual(brain.combat_posture(True),2)
        self.assertEqual(brain.combat_posture(False),4)
        brain.update_fire_cover(4.,20,False)
        self.assertEqual(brain.fire_timer,0.0)
        self.assertIsNone(brain.combat_posture(True))

if __name__=='__main__':unittest.main()

class WorldGeometryRegression(unittest.TestCase):
    def test_first_enemy_really_hidden_before_bend_and_visible_after(self):
        """Actual deterministic first trench bend, not invented straight corridor."""
        import sys
        import types
        import importlib
        from unittest import mock
        with mock.patch.dict(sys.modules,{'moderngl':types.ModuleType('moderngl'),
                                           'pygame':types.ModuleType('pygame')}):
            game=importlib.import_module('trench_3d_test')
        from combat_visibility import player_body,can_see_body
        geo=dict(route=game.route,sides=game.sides,wall_width=game.wall_width,
                 wall_height=game.wall_height,floor_y=game.floor_y,
                 obstacles_in_range=game.obstacles_in_range)
        x,z=game.sides(32,0.)
        origin=(x,game.floor_y(32)+1.48,z)
        for dist in (8.,12.):
            px,pz=game.sides(dist,0.)
            eye=(px,game.floor_y(dist)+1.55,pz)
            self.assertEqual(can_see_body(origin,player_body(eye,1.55),32.,dist,**geo),())
        px,pz=game.sides(16.,0.)
        eye=(px,game.floor_y(16.)+1.55,pz)
        self.assertTrue(can_see_body(origin,player_body(eye,1.55),32.,16.,**geo))

    def test_first_contact_no_invisible_shots_at_eight_metres(self):
        """Regression for real V3.8.9 video: shooting from behind first bank."""
        import sys, types, importlib
        from unittest import mock
        with mock.patch.dict(sys.modules,{'moderngl':types.ModuleType('moderngl'),
                                          'pygame':types.ModuleType('pygame')}):
            game=importlib.import_module('trench_3d_test')
        from combat_visibility import player_body,can_see_body,enemy_faces_player
        from enemy_system import actor_facing
        director=EnemyDirector()
        route_m=8.0
        x,z=game.sides(route_m,0.0)
        eye=(x,game.floor_y(route_m)+1.55,z)
        body=player_body(eye,1.55)
        geo=dict(route=game.route,sides=game.sides,wall_width=game.wall_width,
                 wall_height=game.wall_height,floor_y=game.floor_y,
                 obstacles_in_range=game.obstacles_in_range)
        def visibility(agent):
            ex,ez=game.sides(agent.route_m,agent.spec.lateral)
            origin=(ex,game.floor_y(agent.route_m,agent.spec.lateral)+1.48,ez)
            visible=can_see_body(origin,body,agent.route_m,route_m,**geo)
            if not visible:return False
            heading=actor_facing(agent,game.route(agent.route_m)[2])
            return enemy_faces_player(origin,eye,heading)
        for _ in range(160):
            # 8m -> 32m is outside the SHORT footstep hearing range.
            self.assertEqual(director.hear_shot(route_m,max_range=12.0),())
            director.update(.05,route_m,can_see_player=visibility)
            self.assertEqual(director.gunshots_this_frame,())
        self.assertEqual(director.active[0].state,'idle')
        self.assertEqual(director.active[0].shots_fired,0)
        self.assertAlmostEqual(director.active[0].route_m,32.0)

    def test_unaware_sentry_actually_sweeps_not_permanently_blind(self):
        from enemy_system import actor_facing
        agent=EnemyAgent(EnemySpec(0,32.0,-.18,'unaware'))
        headings=[]
        for i in range(60):
            agent.total_time=i*.17
            headings.append(actor_facing(agent,0.))
        self.assertGreater(max(headings)-min(headings),2.5)
        self.assertTrue(any(abs(h-math.pi)<.15 for h in headings))
