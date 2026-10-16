"""Temporary manual results must never replace NORMAL pixel-ray semantics."""
import unittest
import types
from collections import deque
from unittest import mock
import pygame
from test_v391_atomic_streaming import game
from enemy_system import EnemyAgent,EnemySpec,EnemyDirector,FrozenEnemyFrame
from arcade_mode import ArcadeRun

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.t=game.Trench.__new__(game.Trench);t=self.t
        t.demo_mode=False;t.demo_pending=False;t.demo_targets=();t.demo_keys=set()
        t.demo_notice='';t.demo_results=deque(maxlen=32);t.demo_resume_frame=False
        t.paused=False;t.running=True;t.debug_jump_target=None;t.pose_lab_index=-1
        t.distance=0.;t.elapsed=12.;t.last_dt=.016;t.enemy_death_pause=0.
        t.last_world_shot_meshes=();t.last_shot_cover=None;t.battlefield=mock.Mock()
        t.arcade=ArcadeRun();t.enemies=EnemyDirector()
        t.enemies.active={0:EnemyAgent(EnemySpec(0,10.,0.,'unaware'))}
        t.player_can_shoot={0:True}
        vp=game.perspective(80.,800/600,.045,90)@game.view_from((0,1,0),(0,1,1))
        t.last_enemy_frame=FrozenEnemyFrame(800,600,tuple(map(tuple,vp)),0.,((0,'head',(0,1,10),.2),),((0,10.),))
        t._enemy_shot_occluded=mock.Mock(return_value=False)
        self.events=[]
        attrs={k:getattr(pygame,k) for k in dir(pygame) if k.startswith('K_') or k in ('QUIT','VIDEORESIZE','MOUSEBUTTONDOWN','KEYDOWN','KEYUP')}
        self.pg=types.SimpleNamespace(**attrs,event=types.SimpleNamespace(get=lambda:self.events))
        self.patch=mock.patch.object(game,'pygame',self.pg);self.patch.start();self.addCleanup(self.patch.stop)
    def key(self,k,up=False,repeat=False):return types.SimpleNamespace(type=pygame.KEYUP if up else pygame.KEYDOWN,key=k,repeat=repeat)
    def click(self,pos=(400,300)):return types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN,button=1,pos=pos)
    def send(self,*events):self.events=list(events);self.t.handle()
    def test_normal_actual_ray_hit_and_miss_with_exact_mouse_coordinates(self):
        original=self.t.submit_game_hit
        with mock.patch.object(self.t,'submit_game_hit',wraps=original) as shot:
            self.send(self.click((1,1)));self.assertEqual(self.t.arcade.kills,0)
            self.send(self.click((399.5,299.5)));self.assertEqual(self.t.arcade.kills,1)
            self.assertEqual(self.t.arcade.shots,2)
            self.assertEqual(shot.call_args.args,(399.5,299.5))
            self.assertFalse(self.t.demo_pending)
    def test_toggle_f9_is_not_reassigned_and_pause_freezes_all_simulation(self):
        self.send(self.key(pygame.K_b),self.key(pygame.K_b,True))
        self.assertTrue(self.t.demo_mode)
        self.t._manual_frame_presented()
        with mock.patch.object(self.t,'submit_game_hit',side_effect=AssertionError('raycast')):
            self.send(self.click((-999,9999)))
        agent=self.t.enemies.active[0];before=(agent.total_time,agent.state_time,self.t.elapsed,self.t.arcade.shots)
        for _ in range(50):self.t.update(100.)
        self.assertEqual(before,(agent.total_time,agent.state_time,self.t.elapsed,self.t.arcade.shots))
        self.send(self.key(pygame.K_b),self.key(pygame.K_F9))
        self.assertTrue(self.t.demo_mode);self.assertTrue(self.t.demo_pending)
    def test_hit_once_existing_death_event_and_no_queued_clicks(self):
        self.t.demo_mode=True
        self.send(self.click(),self.click(),self.key(pygame.K_SPACE),self.click(),self.key(pygame.K_SPACE,repeat=True))
        self.assertEqual((self.t.arcade.shots,self.t.arcade.kills),(1,1))
        self.assertEqual(self.t.enemies.active[0].state,'dead')
        self.assertFalse(self.t.demo_pending)
        self.send(self.key(pygame.K_SPACE,True),self.key(pygame.K_SPACE),self.key(pygame.K_m))
        self.assertFalse(self.t.paused);self.assertEqual(self.t.arcade.shots,1)
        self.assertEqual(set(self.t.demo_results[0]),{'source','verdict','target_id'})
    def test_ambiguous_hit_rejected_then_miss_resumes_and_normal_restored(self):
        self.t.demo_mode=True;self.t.begin_demo_shot();self.t.demo_targets=(0,1)
        self.assertFalse(self.t.decide_demo_shot(True));self.assertEqual(self.t.arcade.shots,0)
        self.assertTrue(self.t.decide_demo_shot(False));self.assertFalse(self.t.decide_demo_shot(False))
        self.t.update(999.);self.assertEqual(self.t.elapsed,12.)
        self.send(self.key(pygame.K_b),self.key(pygame.K_b,True))
        self.assertFalse(self.t.demo_mode)
        self.t._manual_frame_presented()
        self.send(self.click((399.5,299.5)));self.assertEqual(self.t.arcade.kills,1)
    def test_repeated_miss_cycles_do_not_consume_wait_time(self):
        self.t.demo_mode=True
        for _ in range(5):
            self.t._manual_frame_presented()
            self.send(self.click());self.t.update(600.)
            self.send(self.key(pygame.K_m),self.key(pygame.K_m,repeat=True),self.key(pygame.K_m,True))
            self.t.update(600.)
        self.assertEqual(self.t.arcade.shots,5);self.assertEqual(self.t.arcade.kills,0)
        self.assertEqual(self.t.elapsed,12.)

if __name__=='__main__':unittest.main()
