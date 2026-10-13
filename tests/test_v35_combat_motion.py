"""V3.5 enemy animation contracts without a GPU or physical hit claims."""
import math
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enemy_system import EnemyAgent, EnemySpec, EnemyDirector, enemy_parts, actor_facing


def agent(kind='cover', identity=2):
    return EnemyAgent(EnemySpec(identity, 32.0, 0.0, kind))


def until(a, state, steps=400):
    for _ in range(steps):
        a.update(.025)
        if a.state==state:
            return
    raise AssertionError('never entered '+state)


class CombatMotionTests(unittest.TestCase):
    def test_aim_does_not_teleport_at_state_boundaries(self):
        a=agent('unaware', 0);a.engage()
        until(a,'aiming')
        for _ in range(10):a.update(.025)
        before=a.aim_fraction()
        until(a,'firing')
        entering=a.aim_fraction()
        self.assertLess(abs(entering-before),.75)
        self.assertGreater(entering,.85)
        self.assertEqual(a.shots_fired,1)
        until(a,'aiming')
        self.assertGreater(a.aim_fraction(),.90,'gun should remain shouldered between shots')
        self.assertTrue(all(0<=p<=1 for p in (a.aim_fraction(),a.crouch_fraction())))

    def test_cover_crouch_and_stand_are_continuous(self):
        a=agent('cover');a.engage()
        for _ in range(1500):
            previous=a.crouch_fraction()
            previous_aim=a.aim_fraction()
            a.update(.025)
            self.assertLess(abs(a.crouch_fraction()-previous),.10)
            self.assertLess(abs(a.aim_fraction()-previous_aim),.12)
            if a.state=='cover' and a.crouch_fraction()>.85:break
        else: self.fail('cover stance never appeared')
        self.assertGreater(a.crouch_fraction(),.85)
        self.assertGreater(a.shots_fired,0)
        until(a,'aiming')
        self.assertGreater(a.crouch_fraction(),.05,'should not snap back to standing')
        for _ in range(65):a.update(.025)
        self.assertLess(a.crouch_fraction(),.025)

    def test_flash_matches_counted_shot(self):
        a=agent('unaware',0);a.engage()
        until(a,'firing')
        self.assertEqual(a.shots_fired,1)
        self.assertTrue(any(part[1]==11 for part in enemy_parts(a)),
                        'bright muzzle flash should be present when shot is counted')
        for _ in range(7):a.update(.025)
        self.assertFalse(any(part[1]==11 for part in enemy_parts(a)),
                         'flash must vanish before the firing cycle ends')
        until(a,'aiming')
        self.assertEqual(a.shots_fired,1,'do not count the same flash twice')

    def test_ambush_no_instant_turn_on_alert(self):
        a=agent('ambush',1)
        before=actor_facing(a,1.0)
        a.engage()
        self.assertAlmostEqual(actor_facing(a,1.0),before,delta=1e-9)
        seq=[]
        for _ in range(60):
            a.update(.01)
            seq.append(actor_facing(a,1.0))
        self.assertTrue(all(0<=q-p<.04 for p,q in zip(seq,seq[1:])))
        self.assertAlmostEqual(seq[-1],1.+math.pi,delta=.005)

    def test_equipment_variants_bounded_repeatable_and_not_new_mesh_types(self):
        available={('oval',10),('oval',11),('oval',23),('oval',24),('oval',25),
            ('cube',10),('cube',24),('jacket',23),('helmet',24),
            ('cylinder',10),('cylinder',13),('cylinder',23),('cylinder',24),('cylinder',25)}
        shapes=[]
        for i in range(9):
            a=agent('unaware',i)
            parts=enemy_parts(a)
            self.assertEqual(parts,enemy_parts(a))
            self.assertLess(len(parts),65,'draw calls must stay bounded per actor')
            self.assertTrue(all((p[0],p[1]) in available for p in parts))
            shapes.append(tuple((p[0],p[1]) for p in parts))
        self.assertEqual(len(set(shapes)),3)
        self.assertEqual(shapes[0],shapes[3])
        self.assertEqual(shapes[1],shapes[4])
        self.assertEqual(shapes[2],shapes[5])

    def test_death_remains_grounded_in_each_equipment_variant(self):
        import enemy_system as rig
        for i in range(6):
            a=agent('unaware',i);a.engage();a.eliminate('torso')
            for stamp in (0,.15,.25,.5,.8,1.1,1.6):
                a.state_time=stamp
                parts=enemy_parts(a)
                angle=1.52*rig._smoothstep01(stamp/1.10)
                # Don't include the detached rifle in body support calculation.
                rifle_at_end = 8 # body parts come before a fixed weapon group
                lows=[rig._rotated_support_bottom(p,angle) for p in parts[:-rifle_at_end]
                      if p[1] in (10,23,24,25)]
                self.assertGreaterEqual(min(lows),-.014,(i,stamp))

    def test_frozen_frame_is_not_changed_by_pose_smoothing(self):
        import numpy as np
        director=EnemyDirector();director.update(.025,27.)
        before=director.capture_frame(np.eye(4),800,600,27.,
                                      lambda spec:(0.,0.,10.),lambda s:0.)
        director.active[0].engage()
        for _ in range(85):director.active[0].update(.025)
        after=director.capture_frame(np.eye(4),800,600,27.,
                                     lambda spec:(0.,0.,10.),lambda s:0.)
        self.assertNotEqual(before.hit_spheres,after.hit_spheres)
        self.assertEqual(before.hit_spheres,
                         tuple(before.hit_spheres), 'frozen evidence must be immutable')


if __name__=='__main__':unittest.main()
