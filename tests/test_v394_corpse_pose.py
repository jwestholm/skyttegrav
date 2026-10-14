"""V3.9.4: an eliminated soldier must NOT pose as a living prone rifleman.

The GPU rig and shadow pass both consume the same bone palette. These
regressions deliberately check only the visual rig, not physical hit truth.
"""
import unittest
import numpy as np
from enemy_system import EnemyAgent, EnemySpec
from skeletal_pose import _joints, bone_matrices, _bind_joints


class CorpsePoseRegression(unittest.TestCase):
    @staticmethod
    def agent(enemy_id):
        return EnemyAgent(EnemySpec(enemy_id, 32.0, -.18, 'unaware'))

    def test_eliminated_soldier_no_longer_aims_down_rifle(self):
        for enemy_id in range(3):
            with self.subTest(enemy_id=enemy_id):
                a=self.agent(enemy_id)
                prone=_joints(a,'prone')
                corpse=_joints(a,'dead')
                # Body and both hands genuinely differ from the prone marksman.
                self.assertGreater(np.linalg.norm(corpse['head']-prone['head']), .15)
                self.assertGreater(np.linalg.norm(corpse['hands'][0]-prone['hands'][0]), .17)
                self.assertGreater(np.linalg.norm(corpse['hands'][1]-prone['hands'][1]), .17)
                mid=(corpse['hands'][0]+corpse['hands'][1])*.5
                self.assertGreater(np.linalg.norm(corpse['weapon_anchor']-mid), .28)
                self.assertLess(corpse['weapon_anchor'][1],.25)

    def test_death_animation_releases_gun_and_turns_head(self):
        a=self.agent(1)
        standing=bone_matrices(a)
        a.eliminate('torso')
        self.assertTrue(np.allclose(bone_matrices(a), standing, atol=.02))
        a.update(.1)
        just_hit=bone_matrices(a)
        self.assertTrue(np.allclose(just_hit[15],standing[15],atol=.025))
        for _ in range(17):a.update(.1)
        fallen=bone_matrices(a)
        self.assertGreater(np.linalg.norm(fallen[15,:3,3]-standing[15,:3,3]),.40)
        self.assertGreater(abs(fallen[2,0,2]),.30)  # head no longer faces forward
        self.assertFalse(np.allclose(just_hit,fallen))
        self.assertTrue(np.array_equal(fallen,bone_matrices(a)))  # fixed body
        self.assertEqual(a.hit_regions((0.,0.,0.)),())

    def test_mirrored_dead_poses_remain_stable_and_bounded(self):
        a=self.agent(0);b=self.agent(1)
        for actor in (a,b):
            actor.eliminate('head')
            for _ in range(20):actor.update(.1)
        m0=bone_matrices(a);m1=bone_matrices(b)
        self.assertLess(m0[15,0,3]*m1[15,0,3],0.)
        self.assertTrue(np.isfinite(m0).all() and np.isfinite(m1).all())
        for model in (m0,m1):
            self.assertLess(abs(model[15,1,3]),2.)
            self.assertLess(np.max(np.abs(model[:,:3,3])),3.)


if __name__=='__main__':unittest.main()
