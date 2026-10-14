"""V3.8.9 replaces V3.8.8 timer death with shots + LOS."""
import unittest
from arcade_mode import ArcadeRun
from combat_visibility import player_body, line_clear, can_see_body, enemy_faces_player
from enemy_system import EnemyAgent, EnemySpec, EnemyDirector


def straight_route(s):return (0.,float(s),0.)
def straight_sides(s,side):return (float(side),float(s))
def trench_width(s,side):return 1.15
def trench_height(s,side):return 2.1
def ground(s,lateral=0):return 0.0
def no_obstacles(a,b):return ()
GEO=dict(route=straight_route,sides=straight_sides,wall_width=trench_width,
         wall_height=trench_height,floor_y=ground,obstacles_in_range=no_obstacles)

class ArcadeRegression(unittest.TestCase):
    def test_no_timer_death(self):
        run=ArcadeRun()
        for i in range(200):run.step(.06,8+i*.01)
        self.assertTrue(run.alive)
        self.assertEqual(run.shots,0)

    def test_occluded_fire_cannot_kill(self):
        run=ArcadeRun()
        for _ in range(100):
            self.assertFalse(run.enemy_shot(2,clear_sight=False,distance_metres=8))
        self.assertTrue(run.alive)
        self.assertEqual(run.incoming_shots,0)

    def test_clear_fire_eventually_kills_but_can_miss(self):
        run=ArcadeRun()
        self.assertFalse(run.enemy_shot(2,clear_sight=True,distance_metres=8,exposure=0.0))
        misses=0
        for _ in range(60):
            if run.enemy_shot(2,clear_sight=True,distance_metres=8):break
            misses+=1
        self.assertFalse(run.alive)
        self.assertEqual(run.deaths,1)
        self.assertLess(run.incoming_shots,61)
        self.assertEqual(run.killed_by,2)

    def test_score_and_reset(self):
        run=ArcadeRun()
        run.step(.1,123.9)
        run.player_shot(None)
        run.player_shot((1,'torso'))
        self.assertEqual((run.score_metres,run.kills,run.shots,run.score),(123,1,2,223))
        run.reset()
        self.assertEqual((run.score_metres,run.kills,run.shots,run.score),(0,0,0,0))
        self.assertTrue(run.alive)

    def test_posture_changes_target_height(self):
        standing=player_body((0,1.55,0),1.55)
        crouched=player_body((0,1.0,0),1.0)
        prone=player_body((0,.43,0),.43)
        self.assertGreater(max(pt[1] for pt in standing),max(pt[1] for pt in crouched))
        self.assertGreater(max(pt[1] for pt in crouched),max(pt[1] for pt in prone))
        self.assertTrue(all(abs(p[0])<1e-10 for p in standing))

    def test_bank_blocks_line_but_open_corridor_passes(self):
        self.assertTrue(line_clear((0,1.5,10),(0,1.2,0),10,0,**GEO))
        self.assertFalse(line_clear((0,1.5,10),(3,1.2,0),10,0,**GEO))

    def test_occluded_body_is_unseen(self):
        body=player_body((3,1.55,0),1.55)
        self.assertFalse(can_see_body((0,1.4,10),body,10,0,**GEO))
        visible=can_see_body((0,1.4,10),player_body((0,1.55,0),1.55),10,0,**GEO)
        self.assertGreater(len(visible),0)

    def test_enemy_only_engages_when_visible(self):
        director=EnemyDirector()
        director.update(.05,20,can_see_player=lambda a:False)
        self.assertEqual(director.active[0].state,'idle')
        self.assertEqual(director.gunshots_this_frame,())
        for i in range(80):director.update(.05,20,can_see_player=lambda a:False)
        self.assertEqual(director.active[0].shots_fired,0)
        director.update(.05,20,can_see_player=lambda a:True)
        self.assertEqual(director.active[0].state,'scanning')
        for i in range(280):director.update(.05,20,can_see_player=lambda a:True)
        self.assertGreater(director.active[0].shots_fired,0)

    def test_unaware_enemy_needs_facing_or_sound(self):
        p=(0.0,0.0,10.0)
        eye=(0.0,1.55,0.0)
        self.assertFalse(enemy_faces_player(p,eye,0.0))
        self.assertTrue(enemy_faces_player(p,eye,3.141592653589793))
        self.assertTrue(enemy_faces_player(p,(0.0,1.55,6.0),0.0))

    def test_enemy_loses_sight_and_stops_firing(self):
        agent=EnemyAgent(EnemySpec(3,32,0,'ambush'))
        agent.engage()
        for i in range(70):agent.update(.05,visible=False)
        self.assertEqual(agent.shots_fired,0)
        self.assertEqual(agent.state,'searching')
        agent.update(.05,visible=True)
        self.assertEqual(agent.state,'turning')

    def test_body_keeps_virtual_camera_xz(self):
        for posture in (1.55,1.0,.43):
            body=player_body((6.7,posture+2.0,-9.4),posture)
            self.assertTrue(all(abs(x-6.7)<1e-8 and abs(z+9.4)<1e-8 for x,y,z,r in body))

if __name__=='__main__':unittest.main()
