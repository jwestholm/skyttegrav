"""V3.9.2: anatomically articulated enemy visuals without changing arcade truth."""
import math
import types
import unittest
from unittest.mock import patch

import numpy as np
from enemy_system import EnemyAgent,EnemySpec,actor_joints,enemy_parts


def enemy(kind='unaware'):
    return EnemyAgent(EnemySpec(0,32.,-.18,kind))


class CharacterMotionRegression(unittest.TestCase):
    def test_idle_stays_planted_no_fake_running_animation(self):
        actor=enemy()
        for i in range(130):actor.update(.05,visible=False,player_route=8.)
        self.assertEqual(actor.route_m,32.)
        self.assertEqual(actor.gait_phase,0.)
        self.assertEqual(actor.gait_strength,0.)
        a=actor_joints(actor)
        self.assertAlmostEqual(a['feet'][0][1],a['feet'][1][1])

    def test_realtime_gait_only_advances_if_actor_actually_moves(self):
        actor=enemy()
        actor.hear_shot(8.)
        first=actor.route_m
        for _ in range(18):actor.update(.05,visible=True,player_route=8.)
        self.assertLess(actor.route_m,first-1.)
        self.assertGreater(actor.gait_strength,.5)
        self.assertNotEqual(actor.gait_phase,0.)
        gait=actor.gait_phase
        actor._transition('alert')
        for _ in range(30):actor.update(.05,visible=True,player_route=8.)
        self.assertAlmostEqual(actor.gait_phase,gait)
        self.assertLess(actor.gait_strength,.01)

    def test_step_phase_tracks_metres_not_frame_count(self):
        def simulate(dt):
            a=enemy()
            a.hear_shot(8.)
            for i in range(round(.80/dt)):
                a.update(dt,visible=True,player_route=8.)
            return a
        fast=simulate(.02);slow=simulate(.05)
        self.assertAlmostEqual(fast.route_m,slow.route_m,places=4)
        self.assertAlmostEqual(fast.gait_phase,slow.gait_phase,places=4)

    def test_crouch_bends_knees_and_lowers_head(self):
        a=enemy();stood=actor_joints(a)
        a.pose_crouch=1.0
        crouched=actor_joints(a)
        self.assertLess(crouched['head'][1],stood['head'][1]-.2)
        self.assertGreater(crouched['knees'][0][2],stood['knees'][0][2]+.15)
        self.assertAlmostEqual(crouched['feet'][0][1],stood['feet'][0][1],places=4)

    def test_hit_centres_follow_rendered_joint_pose(self):
        a=enemy();a.hear_shot(10.)
        for _ in range(19):a.update(.05,visible=True,player_route=10.)
        j=actor_joints(a)
        regions=dict((name,point) for name,point,r in a.hit_regions((0.,0.,0.),0.0))
        self.assertEqual(regions['head'],j['head'])
        self.assertEqual(regions['torso'],j['torso'])
        self.assertEqual(regions['pelvis'],j['pelvis'])
        self.assertEqual(regions['left_leg'],j['knees'][0])
        self.assertEqual(regions['right_leg'],j['knees'][1])
        self.assertEqual(a.hit_regions((0.,0.,0.),0.0),a.hit_regions((0.,0.,0.),0.0))

    def test_local_hit_centres_rotate_with_world_yaw(self):
        a=enemy();j=actor_joints(a)
        regions=dict((name,p) for name,p,r in a.hit_regions((3.,2.,5.),math.pi/2))
        self.assertAlmostEqual(regions['head'][0],3.+j['head'][2])
        self.assertAlmostEqual(regions['head'][1],2.+j['head'][1])
        self.assertAlmostEqual(regions['head'][2],5.-j['head'][0])

    def test_new_sculpture_is_reused_and_not_per_frame_allocated(self):
        # Import the scene with OpenGL dependencies stubbed; run real
        # mesh generation against a fake GPU context (no driver required).
        import sys,importlib
        with patch.dict(sys.modules,{'moderngl':types.ModuleType('moderngl'),
                                     'pygame':types.ModuleType('pygame')}):
            game=importlib.import_module('trench_3d_test')
        class FakeBuffer:
            def __init__(self,raw):self.byte_count=len(raw)
            def release(self):pass
        class FakeProgram:
            def __setitem__(self,k,v):pass
            def __getitem__(self,k):return types.SimpleNamespace(value=None)
            def release(self):pass
        class FakeCtx:
            def program(self,**kw):return FakeProgram()
            def buffer(self,raw):return FakeBuffer(raw)
            def vertex_array(self,prg,bufs):return types.SimpleNamespace(release=lambda:None)
        renderer=game.EnemyRenderer(FakeCtx())
        try:
            parts=enemy_parts(enemy())
            self.assertLess(len(parts),80)
            self.assertEqual({(p[0],p[1]) for p in parts} - set(renderer.meshes),set())
            for shape in ('face','boot','limb'):
                self.assertTrue(any(p[0]==shape for p in parts))
            self.assertLess(sum(b.byte_count for b,v in renderer.meshes.values()),2_000_000)
            # Rigid part transform has real yaw, rather than just relocating
            # a head while its face stays pointing straight ahead.
            headpart=next(p for p in parts if p[0]=='face')
            turned=headpart[:4]+((0.,math.pi/2,0.),)
            m=game.EnemyRenderer.part_model((0.,0.,0.),0.,turned)
            self.assertAlmostEqual(m[0,2],1.,places=4)
            self.assertAlmostEqual(m[2,0],-1.,places=4)
            self.assertTrue(np.isfinite(m).all())
        finally:
            renderer.release()

    def test_death_pose_stays_finite_and_has_no_hittable_ghost(self):
        a=enemy()
        a.eliminate('torso')
        for _ in range(35):a.update(.05,visible=True,player_route=8.)
        self.assertEqual(a.hit_regions((0,0,0)),())
        dead=enemy_parts(a)
        for part in dead:
            vecs=part[2:4] if part[0] in ('cylinder','limb') else part[2:3]
            self.assertTrue(all(math.isfinite(x) for vec in vecs for x in vec))
        self.assertGreater(len(dead),45)
        self.assertLess(len(dead),80)

    def test_visual_change_does_not_change_AI_or_3d_ray(self):
        # New head poses remain cosmetic for decision-making; no LOS shortcut.
        a=enemy()
        a.head_look=.3
        a.pose_crouch=.55
        self.assertEqual(a.state,'idle')
        self.assertFalse(a.dead)
        self.assertEqual(len(a.hit_regions((0.,0.,0.))),5)


if __name__=='__main__':unittest.main()
