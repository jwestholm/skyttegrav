import unittest
from pathlib import Path
import numpy as np
from enemy_system import EnemyAgent,EnemySpec
from rig_renderer import SkeletalEnemyRenderer
from gltf_actor import TacticalEnemyRenderer,GLBCharacter
from skeletal_pose import bone_matrices

class TacticalLiveTests(unittest.TestCase):
    def test_asset_bounds_weights_and_no_extra_headset(self):
        path=Path(__file__).resolve().parents[1]/'assets/characters/tactical/soldier.glb'
        a=GLBCharacter(path)
        self.assertEqual(a.joint_count,16);self.assertEqual(len(a.primitives),7)
        allv=np.concatenate([p.vertices for p in a.primitives])
        self.assertTrue(np.isfinite(allv).all())
        np.testing.assert_allclose(allv[:,12:16].sum(1),1,atol=1e-5)
        self.assertLess(allv[:,1].min(),.01);self.assertGreater(allv[:,1].min(),-.01)
        self.assertLess(allv[:,1].max(),1.9)
        self.assertTrue((allv[:,8:12]>=0).all());self.assertTrue((allv[:,8:12]<16).all())
    def test_live_preserves_root_and_actor_without_mutation(self):
        native=SkeletalEnemyRenderer.__new__(SkeletalEnemyRenderer)
        tactical=TacticalEnemyRenderer.__new__(TacticalEnemyRenderer)
        tactical.asset=GLBCharacter(Path(__file__).resolve().parents[1]/'assets/characters/tactical/soldier.glb')
        for state in ('idle','aiming','firing','rushing','dead'):
            a=EnemyAgent(EnemySpec(4,20.,0.,'unaware'));a.state=state;a.dead=state=='dead'
            a.state_time=.7;a.total_time=3.;a.gait_strength=.7;a.gait_phase=1.2
            before=dict(a.__dict__)
            n=native.collect_instances([a],lambda s:(1.,2.,3.),lambda s:.3)[0]
            t=tactical.collect_instances([a],lambda s:(1.,2.,3.),lambda s:.3)[0]
            np.testing.assert_array_equal(n[1],t[0])
            self.assertTrue(np.isfinite(t[1]).all())
            self.assertEqual(before,a.__dict__)
if __name__=='__main__':unittest.main()
