"""V3.4 visual-prototype regressions: joint death pose, foot contact, draw reuse.

The same shared material IDs and hit-event contract remain unchanged.
No claim of physically simulated ragdolls or animated GLB assets.
"""
import math
import unittest
import numpy as np
from pathlib import Path
import sys
import types
import importlib.util
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
for optional in ('pygame','moderngl'):
    if optional not in sys.modules and importlib.util.find_spec(optional) is None:
        sys.modules[optional]=types.ModuleType(optional)
from enemy_system import EnemyAgent, EnemyDirector, encounter_spec, enemy_parts
import enemy_system as rig
import trench_3d_test as world


class EnemyVisualV34Tests(unittest.TestCase):
    def new_actor(self,profile='unaware'):
        spec=encounter_spec(0)
        spec=type(spec)(spec.enemy_id,spec.route_m,spec.lateral,profile)
        return EnemyAgent(spec)

    def test_humanoid_materials_sculpted_jacket_helmet_and_face(self):
        actor=self.new_actor()
        parts=enemy_parts(actor)
        self.assertGreaterEqual(len(parts),55)
        self.assertIn(('jacket',23),{(p[0],p[1]) for p in parts})
        self.assertIn(('helmet',24),{(p[0],p[1]) for p in parts})
        self.assertIn(('oval',25),{(p[0],p[1]) for p in parts})
        self.assertIn(('cylinder',10),{(p[0],p[1]) for p in parts})
        self.assertTrue(all(p[1] in (10,11,13,23,24,25) for p in parts))

    def test_fall_rotates_meshes_as_well_as_part_centres(self):
        actor=self.new_actor();actor.engage()
        before=enemy_parts(actor)
        actor.eliminate('head');actor.state_time=1.5
        after=enemy_parts(actor)
        for kind in ('jacket','helmet','oval','cube'):
            piece=next(p for p in after if p[0]==kind)
            self.assertEqual(len(piece),5,kind)
            self.assertAlmostEqual(piece[4],1.52,places=6)
            model=world.EnemyRenderer.part_model((0,0,0),0.,piece)
            # A vertical local Y vector must be predominantly horizontal Z.
            y_axis=model[:3,:3]@np.array((0.,1.,0.))
            self.assertGreater(abs(y_axis[2]),abs(y_axis[1])*6,kind)
            self.assertTrue(np.isfinite(model).all())
        self.assertTrue(all(len(p)==4 if p[0] in ('oval','cube','jacket','helmet') else len(p)==5
                            for p in before))

    def test_corpse_floor_contact_through_entire_animation(self):
        actor=self.new_actor();actor.engage();actor.eliminate('torso')
        for step in range(111):
            actor.state_time=step*.02
            parts=enemy_parts(actor)
            angle=1.52*rig._smoothstep01(actor.state_time/1.10)
            low=[rig._rotated_support_bottom(p,angle) for p in parts
                 if p[1] in (10,23,24,25) and
                 # Ignore dropped rifle, but include the first 47 body pieces.
                 p in parts[:47]]
            self.assertGreaterEqual(min(low),-.014,step)
            self.assertTrue(all(math.isfinite(v) for p in parts
                                for v in (p[2] if isinstance(p[2],tuple) else (p[2],))))
        self.assertLessEqual(min(low),.027,'The body must REST on the floor')

    def test_head_faces_ground_backpack_above_body_weapon_rests_next_to_actor(self):
        actor=self.new_actor();actor.engage();actor.eliminate('torso')
        actor.state_time=2.
        parts=enemy_parts(actor)
        helmet=next(p for p in parts if p[0]=='helmet')
        jacket=next(p for p in parts if p[0]=='jacket')
        head=next(p for p in parts if p[0]=='oval' and p[1]==25 and p[2][2]>1.)
        self.assertLess(head[2][1],.55)
        self.assertGreater(head[2][2],jacket[2][2]+.36)
        self.assertLess(jacket[2][1],.55)
        self.assertGreater(helmet[2][2],jacket[2][2]+.3)
        rifle=[p for p in parts if p[0]=='cylinder' and p[1]==10 and
               p[2][0]>.25 and p[3][0]>.25]
        self.assertGreaterEqual(len(rifle),3)
        for p in rifle:
            self.assertGreaterEqual(min(p[2][1],p[3][1])-p[4],.0)
            self.assertLess(max(p[2][1],p[3][1]),.35)

    def test_elimination_remains_permanent_and_frozen_shot_regions_stay_unmoved(self):
        d=EnemyDirector();d.update(.05,27.)
        pv=np.eye(4,dtype='f4')
        frozen=d.capture_frame(pv,800,600,27.,lambda spec:(0,0,10),lambda s:0.)
        d.active[0].eliminate('head')
        d.active[0].state_time=1.5
        self.assertTrue(d.active[0].dead)
        self.assertEqual(frozen.hit_spheres,dummy:=tuple(frozen.hit_spheres))
        now=d.capture_frame(pv,800,600,27.,lambda spec:(0,0,10),lambda s:0.)
        self.assertFalse(any(s[0]==0 for s in now.hit_spheres))
        for _ in range(300):d.update(.1,27.)
        self.assertFalse(d.current_threat(27.))
        self.assertFalse(d.active[0].state=='firing')

    def test_sculpted_mesh_geometry_finite_and_no_bad_normals(self):
        for shape,mat in (('jacket',23),('helmet',24)):
            mesh=world.MeshBuilder()
            world.build_enemy_sculpture(mesh,shape,mat)
            arr=mesh.as_array()
            self.assertGreater(len(arr),250)
            self.assertEqual(arr.shape[1],9)
            self.assertTrue(np.isfinite(arr).all())
            self.assertGreater(float(np.max(arr[:,1])-np.min(arr[:,1])),.22)
            self.assertGreater(float(np.max(arr[:,0])-np.min(arr[:,0])),.35)
            self.assertGreater(float(np.max(arr[:,2])-np.min(arr[:,2])),.22)
            normals=arr[:,3:6]
            self.assertGreater((np.linalg.norm(normals,axis=1)>.95).mean(),.92)


if __name__=='__main__':
    unittest.main()
