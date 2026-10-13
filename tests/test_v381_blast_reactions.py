"""V3.8.1 – transient battle events interrupt autonomous actors, not terrain.

These are offline behavioural tests. Render quality on GTX 1070 remains untested.
"""
import math
import unittest
from battlefield_events import BattlefieldEventDirector, blast_reaction_level
from enemy_system import EnemyAgent, EnemyDirector, EnemySpec
from test_v26_obstacles import runtime_geometry


def ground(s, off):
    return (float(off), .12*math.sin(float(s)*.07), float(s))


class BlastReactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()

    def test_reaction_distance_thresholds_and_weak_blasts(self):
        self.assertEqual(blast_reaction_level(125.,.8),0)
        self.assertEqual(blast_reaction_level(110.1,.8),0)
        self.assertEqual(blast_reaction_level(105.,.8),1)
        self.assertEqual(blast_reaction_level(90.,.8),2)
        self.assertEqual(blast_reaction_level(51.,.8),2)
        self.assertEqual(blast_reaction_level(31.,.8),3)
        self.assertEqual(blast_reaction_level(31.,.28),2)
        self.assertEqual(blast_reaction_level(20.,0.0),0)
        for invalid in (-1.0,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                blast_reaction_level(invalid,1.0)

    def test_notification_only_at_detonation_not_schedule(self):
        d=BattlefieldEventDirector(seed=1944)
        d.trigger('barrage',40.0,ground)
        self.assertEqual(d.last_detonations,())
        impacts=list(d.pending)
        self.assertGreaterEqual(len(impacts),2)
        self.assertFalse(d.update(.20,40.0,ground,allow_events=False))
        all_reported=[]
        for _ in range(70):
            all_reported.extend(d.update(.05,40.0,ground,allow_events=False))
        self.assertEqual(len(all_reported),len(impacts))
        self.assertEqual(all_reported,impacts)
        self.assertFalse(d.last_detonations)
        self.assertEqual(d.impacts_spawned,len(impacts))
        self.assertFalse(d.update(0.,40.0,ground,allow_events=False))

    def test_close_test_shell_stays_outside_trench(self):
        d=BattlefieldEventDirector(seed=1944)
        d.trigger('near_shell',80.,ground)
        self.assertEqual(len(d.pending),1)
        shot=d.pending[0]
        x,_,z=shot.position
        self.assertGreater(abs(x),9.)
        self.assertGreater(z-80.,6.)
        self.assertLess(math.hypot(x,z-80.),24.)
        self.assertEqual(shot.origin,'near_shell')
        self.assertFalse(d.update(.2,80.,ground,allow_events=False))
        self.assertEqual(d.update(.1,80.,ground,allow_events=False)[0],shot)
        self.assertTrue(d.particles)
        self.assertFalse(d.update(.1,80.,ground,allow_events=False))

    def test_brain_freezes_mid_corner_and_reassesses_with_state_intact(self):
        g=self.g
        brain=g['SoldierBrain']()
        brain.branch_index=1
        brain.branch_side=g['junction_side'](1)
        brain.state='turn_in'
        brain.phase='rundar hörnet i rörelse'
        brain.branch_progress=.9
        brain.corner_progress=.37
        brain.corner_length=1.8
        brain.visited={0,1}
        brain.checked_bends={0,1,2}
        original=(brain.state,brain.branch_index,brain.branch_progress,
                  brain.corner_progress,brain.visited.copy(),brain.checked_bends.copy())
        self.assertTrue(brain.interrupt_for_blast(3,19.))
        modes=[]
        for _ in range(23):
            modes.append(brain.choose(134.,.05))
            d,travel=brain.advance(134.,.18)
            self.assertEqual((d,travel),(134.,0.))
        self.assertTrue(all(v==2 for v in modes))
        self.assertEqual((brain.state,brain.branch_index,brain.branch_progress,
                          brain.corner_progress,brain.visited,brain.checked_bends),original)
        for _ in range(25):brain.choose(134.,.05)
        self.assertEqual(brain.blast_timer,0.)
        self.assertEqual(brain.state,'turn_in')
        self.assertEqual(brain.visited,{0,1})
        before=brain.corner_progress
        brain.advance(134.,.14)
        self.assertGreater(brain.corner_progress,before)

    def test_previously_peeked_corner_must_be_rechecked_after_blast(self):
        g=self.g
        for state,new_state in [('peek','edge'),('retract','edge'),
                                ('bend_peek','bend_settle'),('bend_assess','bend_settle')]:
            with self.subTest(state=state):
                brain=g['SoldierBrain']()
                brain.state=state
                brain.branch_index=1
                brain.branch_side=1
                brain.bend_index=2
                brain.bend_side=-1
                brain.visited={1}
                brain.checked_bends={0,1}
                brain.wait=.15
                self.assertTrue(brain.interrupt_for_blast(2,53.))
                for _ in range(30):
                    brain.choose(49.5,.05)
                    if brain.blast_timer<=0.0:break
                self.assertEqual(brain.state,new_state)
                self.assertGreater(brain.wait,0.0)
                self.assertEqual(brain.visited,{1})
                self.assertEqual(brain.checked_bends,{0,1})

    def test_reaction_does_not_reset_enemy_when_threat_alive(self):
        agent=EnemyAgent(EnemySpec(9,55.,0.,'cover'))
        agent.engage()
        original_shots=agent.shots_fired
        self.assertTrue(agent.react_to_blast(2))
        for _ in range(18):agent.update(.05)
        self.assertFalse(agent.dead)
        self.assertTrue(agent.threat)
        self.assertEqual(agent.shots_fired,original_shots)
        self.assertEqual(agent.state,'turning')
        for _ in range(90):agent.update(.05)
        self.assertTrue(agent.threat)
        self.assertGreater(agent.shots_fired,original_shots)

    def test_brain_salvo_escalation_while_kneeling(self):
        g=self.g
        brain=g['SoldierBrain']()
        brain.interrupt_for_blast(2,73.)
        self.assertEqual(brain.choose(10.,.016),1)
        for _ in range(13):brain.choose(10.,.04)
        brain.interrupt_for_blast(3,20.)
        self.assertEqual(brain.choose(10.,.016),2)
        self.assertAlmostEqual(brain.blast_distance,20.)
        self.assertGreater(brain.blast_timer,1.7)
        self.assertFalse(brain.interrupt_for_blast(0,200.))

    def test_enemy_ducks_without_dying_or_resolving_contact(self):
        agent=EnemyAgent(EnemySpec(7,30.,0.,'ambush'))
        agent.engage()
        for _ in range(30):agent.update(.05)
        shots=agent.shots_fired
        phase=agent.state
        self.assertTrue(agent.react_to_blast(3))
        for _ in range(15):agent.update(.05)
        self.assertGreater(agent.crouch_fraction(),.6)
        self.assertEqual(shots,agent.shots_fired)
        self.assertEqual(phase,agent.state)
        self.assertFalse(agent.dead)
        self.assertTrue(agent.threat)
        for _ in range(40):agent.update(.05)
        self.assertEqual(agent.blast_timer,0.)
        self.assertFalse(agent.dead)

    def test_enemy_director_world_distance_not_route_distance(self):
        director=EnemyDirector()
        near=EnemyAgent(EnemySpec(1,300.,0.,'cover'))
        far=EnemyAgent(EnemySpec(2,301.,0.,'cover'))
        dead=EnemyAgent(EnemySpec(3,302.,0.,'cover'))
        dead.eliminate('torso')
        director.active={1:near,2:far,3:dead}
        def position(spec):
            if spec.enemy_id==1:return (12.,0.,0.)
            if spec.enemy_id==2:return (130.,0.,0.)
            return (2.,0.,0.)
        n=director.react_to_blast((0.,0.,0.),.85,blast_reaction_level,position)
        self.assertEqual(n,1)
        self.assertEqual(near.blast_level,3)
        self.assertEqual(far.blast_level,0)
        self.assertTrue(dead.dead)
        self.assertEqual(dead.blast_level,0)

    def test_no_damage_and_no_nav_reset_across_repeated_impact(self):
        brain=self.g['SoldierBrain']()
        brain.visited={0,1,2,7}
        brain.checked_bends={1,9,17}
        d=BattlefieldEventDirector(seed=33)
        d.trigger('near_shell',0.,ground)
        for impact in d.update(.20,0.,ground,allow_events=False):
            self.fail('Impact happened before scheduled time')
        count=0
        for _ in range(8):
            for impact in d.update(.05,0.,ground,allow_events=False):
                x,_,z=impact.position
                lvl=blast_reaction_level(math.hypot(x,z),impact.strength)
                if lvl:brain.interrupt_for_blast(lvl,math.hypot(x,z))
                count+=1
        self.assertEqual(count,1)
        self.assertEqual(brain.visited,{0,1,2,7})
        self.assertEqual(brain.checked_bends,{1,9,17})


if __name__=='__main__':unittest.main()
