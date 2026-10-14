"""V3.9.6 pose-command transitions, shouldered rifle, and game invariants."""
import math
import unittest
import numpy as np
from enemy_system import EnemyAgent, EnemySpec
from skeletal_pose import (BONES, POSE_LAB, PoseTransition, _joints,
                           bone_matrices, interpolate_bone_matrices)


def actor():
    return EnemyAgent(EnemySpec(23, 32.0, -0.18, 'unaware'))


class PoseCommandTests(unittest.TestCase):
    def test_pose_order_and_no_unknown_commands(self):
        a=actor();c=PoseTransition()
        for pose in POSE_LAB:
            c.request(pose,a)
            self.assertEqual(c.pose,pose)
        with self.assertRaises(ValueError):c.request('teleport',a)

    def test_f1_transition_starts_at_previous_visible_frame(self):
        a=actor();c=PoseTransition()
        start=c.sample(a).copy()
        c.request('kneel',a)
        self.assertTrue(np.array_equal(c.sample(a),start))
        c.advance(.35)
        half=c.sample(a)
        goal=bone_matrices(a,'kneel')
        self.assertGreater(np.max(abs(half-start)),.02)
        self.assertGreater(np.max(abs(half-goal)),.02)
        c.advance(1.)
        self.assertTrue(np.array_equal(c.sample(a),goal))

    def test_interrupt_mid_transition_no_pop(self):
        a=actor();c=PoseTransition()
        c.request('kneel',a)
        c.advance(.29)
        frame=c.sample(a).copy()
        c.request('prone',a)
        self.assertTrue(np.array_equal(c.sample(a),frame))
        c.advance(1.)
        self.assertTrue(np.array_equal(c.sample(a),bone_matrices(a,'prone')))

    def test_quaternion_blending_preserves_orthonormal_bones(self):
        a=actor()
        src=bone_matrices(a,'stand');dst=bone_matrices(a,'prone')
        for fraction in (0.,.03,.23,.50,.79,.99,1.):
            mats=interpolate_bone_matrices(src,dst,fraction)
            self.assertTrue(np.isfinite(mats).all())
            self.assertEqual(mats.shape,(len(BONES),4,4))
            self.assertTrue(np.allclose(mats[:,3,:],(0,0,0,1),atol=1.e-5))
            rr=np.matmul(mats[:,:3,:3].transpose(0,2,1),mats[:,:3,:3])
            self.assertTrue(np.allclose(rr,np.eye(3),atol=1.e-5))
            self.assertTrue(np.all(np.linalg.det(mats[:,:3,:3])>.999))

    def test_invalid_blend_values_fail_closed(self):
        a=actor();m=bone_matrices(a,'stand')
        with self.assertRaises(ValueError):interpolate_bone_matrices(m,m,float('nan'))
        with self.assertRaises(ValueError):interpolate_bone_matrices(m,np.zeros((15,4,4)),.5)
        with self.assertRaises(ValueError):PoseTransition().advance(-.01)

    def test_rifle_shouldered_when_aiming(self):
        a=actor()
        idle=_joints(a,'stand');aim=_joints(a,'aim')
        self.assertGreater(aim['weapon_anchor'][1]-idle['weapon_anchor'][1],.38)
        self.assertLess(abs(aim['weapon_anchor'][1]-aim['shoulders'][1][1]),.16)
        self.assertGreater(aim['hands'][0][2]-aim['hands'][1][2],.20,
                           'left hand must support fore-end, right hand trigger')
        self.assertLess(abs(aim['hands'][1][1]-aim['shoulders'][1][1]),.13)

    def test_aim_and_fire_recoil_without_gameplay_bullets(self):
        a=actor();a.total_time=0.
        gun_aim=_joints(a,'aim')['weapon_anchor']
        gun_fire=_joints(a,'fire')['weapon_anchor']
        self.assertGreater(gun_aim[2]-gun_fire[2],.075)
        shots=a.shots_fired;before=(a.dead,a.route_m,a.state)
        for pose in POSE_LAB:bone_matrices(a,pose)
        self.assertEqual(a.shots_fired,shots)
        self.assertEqual((a.dead,a.route_m,a.state),before)

    def test_physical_hitboxes_stay_independent_of_preview(self):
        a=actor();regions=a.hit_regions((0.,0.,0.))
        a.pose_controller=PoseTransition()
        for command in ('aim','fire','kneel','prone','stand'):
            a.pose_controller.request(command,a)
            a.pose_controller.advance(.14)
            a.pose_controller.sample(a)
        self.assertEqual(regions,a.hit_regions((0.,0.,0.)))

    def test_no_root_motion_in_pose_command(self):
        a=actor();p=PoseTransition()
        before=(a.route_m,a.lateral_offset,a.gait_phase)
        for pose in POSE_LAB:
            p.request(pose,a)
            p.advance(.08)
            p.sample(a)
        self.assertEqual((a.route_m,a.lateral_offset,a.gait_phase),before)

    def test_intermediate_low_poses_do_not_sink_into_floor(self):
        # Vertex-level check against the SAME static skin mesh as production.
        from test_v393_gpu_skeleton import GPUSkeletonRegression
        GPUSkeletonRegression.setUpClass()
        raw=GPUSkeletonRegression.raw
        verts=np.column_stack((raw[:,:3],np.ones(len(raw))))
        owners=raw[:,9].astype(int)
        body=(raw[:,10]==0)
        a=actor()
        for command in ('kneel','prone','supine_sleep','fear_curl','dead'):
            ctl=PoseTransition()
            ctl.request(command,a)
            for f in (.0,.1,.3,.5,.7,.9,1.):
                ctl.elapsed=ctl.duration*f
                mats=ctl.sample(a)
                y=np.einsum('nij,nj->ni',mats[owners],verts)[:,1][body]
                with self.subTest(command=command,phase=f):
                    self.assertGreaterEqual(float(y.min()),-.025)
                    self.assertLess(float(y.max()),2.7)

    def test_controller_integrated_with_gpu_renderer_snapshot(self):
        import inspect
        from rig_renderer import SkeletalEnemyRenderer
        source=inspect.getsource(SkeletalEnemyRenderer.collect_instances)
        self.assertIn('pose_controller',source)
        self.assertIn('controller.sample(agent)',source)
        draw=inspect.getsource(SkeletalEnemyRenderer.draw_skeletal_shadows)
        self.assertIn('for variant,model,bones,actor in instances',draw)


if __name__=='__main__':unittest.main()
