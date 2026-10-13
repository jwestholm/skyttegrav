"""Focused V3.8.4 regressions: actual dead-state clock, ModernGL fallback,
startup stages and visible confirmation. No hardware visual correctness claim.
"""
import ast
import unittest
from pathlib import Path
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
SOURCE=(BASE/'trench_3d_test.py').read_text()

from enemy_system import EnemyAgent, encounter_spec

class CrashAndDeathTests(unittest.TestCase):
    def test_elimination_advances_dead_animation_clock(self):
        a=EnemyAgent(encounter_spec(0))
        self.assertTrue(a.eliminate('pelvis'))
        self.assertEqual(a.state_time,0)
        for _ in range(25):a.update(.05)
        self.assertAlmostEqual(a.state_time,1.25,places=6)
        self.assertTrue(a.dead)

    def test_cannot_eliminate_dead_twice(self):
        a=EnemyAgent(encounter_spec(0))
        self.assertTrue(a.eliminate('pelvis'))
        a.update(1.2)
        self.assertFalse(a.eliminate('head'))

    def test_depthmask_legacy_attribute_is_not_unconditionally_accessed(self):
        src=(BASE/'battlefield_events.py').read_text()
        self.assertIn('gl.glDepthMask',src)
        self.assertIn('gl.glGetBooleanv',src)
        self.assertIn('depth_mask(previous.value)',src)
        self.assertNotIn('before_mask=self.ctx.depth_mask',src)

    def test_real_loading_stages_are_present(self):
        tree=ast.parse(SOURCE)
        self.assertTrue(any(isinstance(x,ast.ClassDef) and x.name=='StartupScreen' for x in tree.body))
        for label in ('Förbereder texturer','Laddar fiender','Genererar skyttegraven','Ritar kartan'):
            self.assertIn(label,SOURCE)
        self.assertIn('pygame.display.flip()',SOURCE)

    def test_death_hold_stops_auto_movement_and_resets(self):
        self.assertIn('self.enemy_death_pause=max(self.enemy_death_pause,1.25)',SOURCE)
        self.assertIn('or self.enemy_death_pause>0.0',SOURCE)
        self.assertIn('self.enemy_death_pause=0.0',SOURCE)

if __name__=='__main__':unittest.main()
