"""V3.9.5 filmic-motion regressions; no GPU context required for pose tests."""
import math
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from enemy_system import EnemyAgent,EnemySpec
from skeletal_pose import bone_matrices,_joints
from rig_renderer import SkeletalEnemyRenderer


def make_actor():
    return EnemyAgent(EnemySpec(2,32.,-.18,'unaware'))


class FilmicMotionRegression(unittest.TestCase):
    def test_walk_run_have_different_stride_lift_and_upper_body(self):
        actor=make_actor();actor.total_time=.19
        walking=_joints(actor,'walk');running=_joints(actor,'run')
        self.assertGreater(abs(running['feet'][0][2]-walking['feet'][0][2]), .10)
        self.assertGreater(abs(running['head'][2]-walking['head'][2]), .035)
        self.assertGreater(np.linalg.norm(running['hands'][0]-walking['hands'][0]), .06)
        self.assertFalse(np.allclose(bone_matrices(actor,'walk'),bone_matrices(actor,'run')))
        self.assertEqual(actor.route_m,32.)

    def test_standing_has_breath_sway_and_fixed_feet(self):
        actor=make_actor();actor.total_time=0.
        initial=_joints(actor,'stand');first=bone_matrices(actor,'stand')
        actor.total_time=.35
        moving=_joints(actor,'stand');second=bone_matrices(actor,'stand')
        self.assertTrue(np.allclose(initial['feet'],moving['feet']))
        self.assertGreater(abs(moving['head'][1]-initial['head'][1]),.003)
        self.assertFalse(np.array_equal(first[2],second[2]))
        self.assertEqual(actor.route_m,32.)

    def test_fire_lab_has_phased_recoil_and_recovers(self):
        actor=make_actor();actor.total_time=0.
        aim=_joints(actor,'aim')
        impulse=_joints(actor,'fire')
        self.assertGreater(aim['weapon_anchor'][2]-impulse['weapon_anchor'][2],.07)
        actor.total_time=.37
        recovered=_joints(actor,'fire')
        self.assertLess(np.linalg.norm(recovered['weapon_anchor']-aim['weapon_anchor']),.01)
        actor.total_time=1.05
        repeated=_joints(actor,'fire')
        self.assertGreater(aim['weapon_anchor'][2]-repeated['weapon_anchor'][2],.07)

    def test_real_firing_state_animates_without_extra_bullets(self):
        actor=make_actor();actor.pose_aim=1.
        actor.state='firing';actor.state_time=0.
        shot_count=actor.shots_fired
        at_shot=bone_matrices(actor)
        actor.state_time=.29
        after=bone_matrices(actor)
        self.assertGreater(np.linalg.norm(at_shot[15,:3,3]-after[15,:3,3]),.04)
        self.assertEqual(actor.shots_fired,shot_count)
        self.assertEqual(actor.route_m,32.)

    def test_muzzle_flash_in_demo_and_real_fire(self):
        source=Path(SkeletalEnemyRenderer.__module__.replace('.','/'))
        import inspect
        draw=inspect.getsource(SkeletalEnemyRenderer.draw)
        self.assertIn("current_pose=='fire'",draw)
        self.assertIn('actor.total_time%1.05<.095',draw)
        self.assertIn("actor.state=='firing'",draw)

    def test_visual_wetness_is_bounded_floor_only(self):
        import inspect
        from test_v393_gpu_skeleton import GPUSkeletonRegression
        GPUSkeletonRegression.setUpClass()
        game=GPUSkeletonRegression.game
        self.assertIn('if (v_layer==21)',game.FRAG)
        self.assertIn('wet_response=damp*.095*diffuse*sun_vis*spec;',game.FRAG)
        self.assertIn('uniform vec3 camera_position;',game.FRAG)


if __name__=='__main__':unittest.main()
