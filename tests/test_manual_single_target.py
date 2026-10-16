"""Presentation admission and atomic manual triggers; no GL required."""
import ast
import concurrent.futures
import hashlib
import json
from pathlib import Path
import threading
import types
import unittest
import numpy as np
import enemy_system as es
from test_demo_mode import DemoTests, game
from test_demo_polish import SeedTests

class AdmissionTests(unittest.TestCase):
    def test_normal_unchanged_five_seeds_and_manual_streaming(self):
        ns=vars(es).copy()
        tree=ast.parse(Path('manual_validation/before_enemies.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='EnemyDirector')
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'baseline','exec'),ns)
        rows=[]
        for seed in (1944,98765,44123,44223,20261016):
            old=ns['EnemyDirector'](seed);normal=es.EnemyDirector(seed);manual=es.EnemyDirector(seed)
            manual.set_manual_presentation(True,0)
            signature=[];max_active=0
            for s in range(0,1001,5):
                for d in (old,normal,manual):d.update(.01,s,lambda a:False)
                def sig(d):return [(i,repr(a.spec),a.route_m,a.state,a.total_time) for i,a in sorted(d.active.items())]
                self.assertEqual(sig(old),sig(normal));signature.append(sig(normal))
                living=[a for a in manual.active.values() if not a.dead]
                max_active=max(max_active,len(living));self.assertLessEqual(len(living),1)
                frame=manual.capture_frame(np.eye(4),800,600,s,lambda spec:(0,0,spec.route_m),lambda s:0)
                self.assertLessEqual(len(set(x[0] for x in frame.hit_spheres)),1)
                if living and 0<living[0].route_m-s<15:
                    living[0].eliminate('test')
                self.assertFalse(set(manual.active)&set(manual.manual_waiting))
            rows.append(dict(seed=seed,normal_matches_before=True,normal_signature=hashlib.sha256(repr(signature).encode()).hexdigest(),manual_max_living=max_active))
        Path('manual_validation/seeds.json').write_text(json.dumps(rows,indent=2))
    def test_toggle_retains_objects_handoff_reload_reset(self):
        d=es.EnemyDirector(1944);d.update(0,45,lambda a:False)
        original=dict(d.active);self.assertGreater(len(original),1)
        d.set_manual_presentation(True,45,preferred=(1,))
        self.assertEqual(list(d.active),[1]);self.assertEqual(len(d.active)+len(d.manual_waiting),len(original))
        waiting_times={i:a.total_time for i,a in d.manual_waiting.items()}
        d.update(.1,45,lambda a:False)
        for i,tm in waiting_times.items():self.assertEqual(d.manual_waiting[i].total_time,tm)
        d.set_manual_presentation(False,45)
        for i,a in original.items():self.assertIs(d.active[i],a)
        d.set_manual_presentation(True,45);dead=d.manual_target;d.active[dead].eliminate('test')
        d.update(0,45,lambda a:False);self.assertNotEqual(d.manual_target,dead)
        d.update(0,1000,lambda a:False);d.update(0,45,lambda a:False)
        self.assertNotIn(dead,d.manual_waiting);self.assertNotIn(dead,d.active)
        d.reset();self.assertFalse(d.active or d.manual_waiting or d.eliminated)
        d.update(0,45,lambda a:False);self.assertIn(dead,set(d.active)|set(d.manual_waiting))
    def test_normal_ray_body_unchanged(self):
        def fn(path):
            tree=ast.parse(Path(path).read_text())
            return next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==('_submit_game_hit' if path=='trench_3d_test.py' else 'submit_game_hit'))
        old=fn('manual_validation/before_game.py');new=fn('trench_3d_test.py')
        new.body=new.body[2:];new.name=old.name
        self.assertEqual(ast.dump(old),ast.dump(new))

class TriggerTests(DemoTests):
    def test_reproduce_old_ambiguity_and_callback_bypass(self):
        from arcade_mode import ArcadeRun
        tree=ast.parse(Path('manual_validation/before_game.py').read_text());ns=vars(game).copy()
        for name in ('begin_demo_shot','decide_demo_shot','submit_game_hit'):
            node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'baseline','exec'),ns)
        t=self.t;t.demo_mode=True
        t.enemies.active[1]=es.EnemyAgent(es.EnemySpec(1,10.,.4,'unaware'))
        t.player_can_shoot[1]=True
        from dataclasses import replace
        t.last_enemy_frame=replace(t.last_enemy_frame,actor_routes=((0,10.),(1,10.)))
        self.assertTrue(ns['begin_demo_shot'](t));self.assertEqual(t.demo_targets,(0,1))
        self.assertFalse(ns['decide_demo_shot'](t,True))
        for _ in range(5):ns['submit_game_hit'](t,0,0)
        self.assertEqual(t.arcade.shots,5)
        before=dict(active=2,eligible_targets=2,hit_rejected=True,extra_callback_results=t.arcade.shots)
        t.arcade=ArcadeRun()
        for _ in range(5):t.submit_game_hit(0,0)
        self.assertEqual(t.arcade.shots,0)
        Path('manual_validation/before_after.json').write_text(json.dumps(dict(before=before,after_extra_callback_results=0),indent=2))

    def test_concurrent_callbacks_and_no_replay(self):
        t=self.t;t.demo_mode=True
        barrier=threading.Barrier(6)
        def trigger():barrier.wait();return t.begin_demo_shot()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(lambda _:trigger(),range(6)))
        self.assertEqual(results.count(True),1);self.assertEqual(t.arcade.shots,0)
        frame=t.last_enemy_frame
        for _ in range(5):
            t.submit_game_hit(400,300)
            t.submit_verified_hit_event(types.SimpleNamespace(game_x=400,game_y=300),frame)
        self.assertEqual(t.arcade.shots,0);self.assertEqual(len(t.demo_results),0)
        t.update(1000);self.assertEqual(t.elapsed,12.)
        self.assertTrue(t.decide_demo_shot(False));self.assertFalse(t.decide_demo_shot(True))
        t.submit_game_hit(400,300);self.assertFalse(t.demo_pending)
        t.update(1000);self.assertEqual(t.elapsed,12.)
        t._manual_frame_presented();self.assertEqual(t.arcade.shots,1);self.assertFalse(t.demo_pending)
    def test_public_callbacks_concurrent_single_pending(self):
        t=self.t;t.demo_mode=True
        barrier=threading.Barrier(6)
        def shot(_):barrier.wait();t.submit_game_hit(400,300)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(shot,range(6)))
        self.assertTrue(t.demo_pending);self.assertEqual(t.demo_targets,(0,));self.assertEqual(t.arcade.shots,0)
        self.assertTrue(t.decide_demo_shot(True));self.assertEqual(t.arcade.shots,1)
        self.assertFalse(t.decide_demo_shot(True))

    def test_zero_missing_or_replaced_target(self):
        t=self.t;t.demo_mode=True
        t.player_can_shoot={};self.assertTrue(t.begin_demo_shot())
        self.assertFalse(t.decide_demo_shot(True));self.assertTrue(t.decide_demo_shot(False))
        t._manual_frame_presented();t.player_can_shoot={0:True};t.begin_demo_shot()
        original=t.enemies.active.pop(0)
        self.assertFalse(t.decide_demo_shot(True))
        t.enemies.active[0]=es.EnemyAgent(original.spec)
        self.assertFalse(t.decide_demo_shot(True));self.assertTrue(t.decide_demo_shot(False))
        self.assertEqual(t.arcade.kills,0)
    def test_r_s_from_alive_dead_and_pending(self):
        from unittest import mock
        t=self.t
        for alive in (True,False):
            t.arcade.alive=alive
            with mock.patch.object(t,'restart_world') as reset:
                self.send(self.key(self.pg.K_r),self.key(self.pg.K_r,True))
                reset.assert_called_once_with(None)
                self.send(self.key(self.pg.K_s),self.key(self.pg.K_s,True))
                self.assertEqual(reset.call_count,2)
                self.assertNotEqual(reset.call_args.args[0],game.SEED)
                t.demo_pending=True
                self.send(self.key(self.pg.K_s),self.key(self.pg.K_s,True),self.key(self.pg.K_r),self.key(self.pg.K_r,True))
                self.assertEqual(reset.call_count,2)
                t.demo_pending=False
    def test_death_cancels_mark_without_scoring(self):
        t=self.t;t.demo_mode=True;t.begin_demo_shot();t.arcade.alive=False;t.death_age=0
        t.update(.01)
        self.assertFalse(t.demo_pending);self.assertEqual(t.arcade.shots,0)

    def test_exit_cancels_without_result(self):
        t=self.t;t.demo_mode=True;t.begin_demo_shot()
        self.send(self.key(self.pg.K_ESCAPE),self.click())
        self.assertFalse(t.running or t.demo_pending);self.assertEqual(t.arcade.shots,0)
        self.assertFalse(t.begin_demo_shot())
    def test_reset_pending_guard_and_waiting_lifecycle(self):
        from unittest import mock
        t=SeedTests().world();t.enemies=es.EnemyDirector(1944)
        t.enemies.update(0,45,lambda a:False);t.enemies.set_manual_presentation(True,45)
        self.assertTrue(t.enemies.manual_waiting)
        t.demo_pending=True;self.assertFalse(t.restart_world(98765));self.assertTrue(t.enemies.manual_waiting)
        t.demo_pending=False
        with mock.patch.object(game.moderngl,'DEPTH_TEST',2,create=True),mock.patch.object(game,'StartupScreen'),mock.patch.object(game,'make_chunk',return_value=np.zeros((6,9),dtype='f4')):
            self.assertTrue(t.restart_world(98765))
        self.assertFalse(t.enemies.manual_waiting or t.enemies.active);self.assertEqual(t.enemies.world_seed,98765)
        t.enemies.update(0,45,lambda a:False);plan=[repr(a.spec) for a in list(t.enemies.active.values())+list(t.enemies.manual_waiting.values())]
        t.restart_world();t.enemies.update(0,45,lambda a:False)
        self.assertEqual(plan,[repr(a.spec) for a in list(t.enemies.active.values())+list(t.enemies.manual_waiting.values())])
        game.set_world_seed(1944)

if __name__=='__main__':unittest.main()
