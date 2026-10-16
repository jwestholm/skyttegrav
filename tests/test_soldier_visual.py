"""Render-only geometry contracts; no replacement hit regions or AI."""
import unittest
import numpy as np
from test_v391_atomic_streaming import game
from enemy_system import EnemyAgent,EnemySpec,enemy_parts
from rig_renderer import to_bind_mesh,bone_for_part

class SoldierVisualTests(unittest.TestCase):
    def test_curved_templates_keep_authored_positions_uv_material(self):
        for shape,mat in (('jacket',23),('helmet',24),('face',25),('limb',23)):
            m=game.MeshBuilder();game.build_enemy_sculpture(m,shape,mat)
            original=m.as_array();new=game._rig_shape_template(shape,mat)
            np.testing.assert_array_equal(new[:,:3],original[:,:3])
            np.testing.assert_array_equal(new[:,6:],original[:,6:])
            self.assertTrue(np.isfinite(new).all())
            np.testing.assert_allclose(np.linalg.norm(new[:,3:6],axis=1),1,atol=1e-5)
            self.assertFalse(np.array_equal(new[:,3:6],original[:,3:6]))
    def test_bevel_within_original_box_and_outward_normals(self):
        for mat in (10,24):
            data=game._rig_shape_template('cube',mat)
            self.assertEqual(data.shape,(324,9))
            self.assertLessEqual(float(np.abs(data[:,:3]).max()),1.)
            self.assertTrue((np.sum(data[:,:3]*data[:,3:6],axis=1)>0).all())
            np.testing.assert_allclose(np.linalg.norm(data[:,3:6],axis=1),1,atol=1e-5)
            self.assertTrue((data[:,8]==mat).all())
    def test_rifle_uses_equipment_surface_on_original_weapon_bone(self):
        for variant in range(3):
            a=EnemyAgent(EnemySpec(variant,5.,0.,'unaware'))
            parts=enemy_parts(a)
            keys={p[:2] for p in parts}|{('cylinder',13),('cube',10),('oval',11)}
            shapes={k:game._rig_shape_template(*k) for k in keys}
            data=to_bind_mesh(parts,shapes,game.EnemyRenderer.part_model)
            rifle=data[data[:,10]==1]
            self.assertTrue((rifle[:,9]==15).all())
            self.assertFalse((rifle[:,8]==13).any())
            self.assertTrue(np.isfinite(data).all())
            self.assertEqual(a.state,'idle');self.assertFalse(a.dead)

if __name__=='__main__':unittest.main()
