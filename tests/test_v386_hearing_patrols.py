"""V3.8.6: local gunshot hearing and route-following patrols.

Smoke tests are CPU-only and do NOT validate final audio attenuation, occlusion,
actual actor appearance or navigation in branched topology.
"""
import math
import unittest
import numpy as np
import importlib.util,sys,types
for optional in ('moderngl','pygame'):
    if optional not in sys.modules and importlib.util.find_spec(optional) is None:
        sys.modules[optional]=types.ModuleType(optional)

from enemy_system import EnemyDirector, EnemyAgent, encounter_spec, enemy_parts
import trench_3d_test as world


class HeardShotPatrolTests(unittest.TestCase):
    def test_first_four_stable_then_spacing_is_72m(self):
        baseline=(32.,164.,258.,384.)
        self.assertEqual(tuple(encounter_spec(i).route_m for i in range(4)),baseline)
        self.assertEqual(tuple(encounter_spec(i).route_m for i in range(4,9)),
                         (516.,588.,660.,732.,804.))
        for i in range(4,40):
            self.assertAlmostEqual(encounter_spec(i+1).route_m-encounter_spec(i).route_m,72.)

    def test_heard_shot_triggers_non_teleporting_investigation(self):
        d=EnemyDirector()
        d.update(.02,480.)
        self.assertIn(4,d.active)
        a=d.active[4]
        self.assertEqual(a.route_m,516.)
        self.assertEqual(a.state,'idle')
        self.assertEqual(d.hear_shot(480.),(4,))
        self.assertEqual(a.state,'investigating')
        self.assertFalse(d.hear_shot(480.))
        previous=a.route_m
        for i in range(45):
            d.update(.05,480.)
            self.assertLessEqual(a.route_m,previous)
            self.assertLessEqual(previous-a.route_m,.13)
            previous=a.route_m
        self.assertGreater(a.route_m,496.)
        self.assertLess(a.route_m,516.)
        self.assertFalse(a.dead)
        self.assertGreater(a.heard_shots,0)

    def test_halts_in_engagement_range_and_only_player_can_eliminate(self):
        d=EnemyDirector();d.update(.05,480.)
        d.hear_shot(480.)
        for _ in range(250):d.update(.05,480.)
        a=d.active[4]
        self.assertGreaterEqual(a.route_m,490.)
        self.assertLessEqual(a.route_m,496.2)
        self.assertIn(a.state,('turning','aiming','firing','cover'))
        fixed=a.route_m
        for _ in range(250):d.update(.05,480.)
        self.assertAlmostEqual(a.route_m,fixed,places=7)
        self.assertFalse(a.dead)
        self.assertTrue(d.current_threat(480.))
        self.assertEqual(d.clamp_advance(488.,2.),0.)

    def test_unheard_or_behind_enemy_does_not_run(self):
        a=EnemyAgent(encounter_spec(4))
        self.assertFalse(a.hear_shot(700.))
        self.assertFalse(a.hear_shot(0.))
        self.assertEqual(a.route_m,516.)
        self.assertEqual(a.state,'idle')

    def test_render_and_frozen_hit_geometry_use_moving_route(self):
        d=EnemyDirector();d.update(.05,480.)
        d.hear_shot(480.)
        world_object=object.__new__(world.Trench)
        world_object.enemies=d
        a=d.active[4]
        p0=np.array(world_object.enemy_position(a.spec))
        d.update(.05,480.)
        p1=np.array(world_object.enemy_position(a.spec))
        self.assertGreater(float(np.linalg.norm(p0-p1)),0.)
        # Render and capture both call the same position_at callback.
        eye=np.array(world.world(480.,0.,world.floor_y(480.)+1.55))
        pv=world.perspective(78.,800./600.,.045,220.)@world.view_from(eye,p1+np.array((0.,1.2,0.)))
        f=d.capture_frame(pv,800,600,480.,world_object.enemy_position,
                          lambda route_m: world.route(route_m)[2])
        head=next(h for h in f.hit_spheres if h[0]==4 and h[1]=='head')
        self.assertLess(abs(head[2][0]-p1[0]),.25)
        self.assertLess(abs(head[2][2]-p1[2]),.25)
        previous=f.hit_spheres
        for _ in range(5):d.update(.05,480.)
        self.assertEqual(f.hit_spheres,previous,'shot-time snapshot changed after world motion')
        next_frame=d.capture_frame(pv,800,600,480.,world_object.enemy_position,
                                   lambda route_m: world.route(route_m)[2])
        self.assertNotEqual(f.hit_spheres,next_frame.hit_spheres)
        leg_parts=[p for p in enemy_parts(a) if p[0]=='cylinder']
        self.assertGreater(len(leg_parts),8)

    def test_running_enemy_is_hit_at_its_frozen_visible_position(self):
        d=EnemyDirector();d.update(.02,480.)
        self.assertEqual(d.hear_shot(480.),(4,))
        for _ in range(90):d.update(.05,480.)
        obj=object.__new__(world.Trench)
        obj.enemies=d
        a=d.active[4]
        self.assertLess(a.route_m,a.spec.route_m)
        location=np.asarray(obj.enemy_position(a.spec))
        eye=location+np.asarray((0.,1.45,-8.0))
        # Camera points at the moved head, not the original encounter route.
        pv=world.perspective(72.,800./600.,.045,180.)@world.view_from(
            eye,location+np.asarray((0.,1.67,0.)))
        frame=d.capture_frame(pv,800,600,480.,obj.enemy_position,
                              lambda route_m:world.route(route_m)[2])
        _,_,head,_=next(v for v in frame.hit_spheres if v[0]==4 and v[1]=='head')
        clip=pv@np.array((*head,1.));clip/=clip[3]
        px=(clip[0]+1.)*400.-.5
        py=(1.-clip[1])*300.-.5
        self.assertEqual(d.resolve_frozen_hit(px,py,frame),(4,'head'))
        self.assertTrue(a.dead)
        self.assertIsNone(d.resolve_frozen_hit(px,py,frame))

    def test_visible_frame_freezes_occlusion_route_during_motion(self):
        d=EnemyDirector();d.update(.02,480.)
        d.hear_shot(480.)
        for _ in range(40):d.update(.05,480.)
        obj=object.__new__(world.Trench)
        obj.enemies=d
        obj.distance=480.0
        obj.enemy_death_pause=0.0
        position=obj.enemy_position(d.active[4].spec)
        eye=np.asarray(position)+np.asarray((0.,1.4,-9.))
        target=np.asarray(position)+np.asarray((0.,1.67,0.))
        pv=world.perspective(75.,800./600.,.045,180.)@world.view_from(eye,target)
        frame=d.capture_frame(pv,800,600,480.,obj.enemy_position,
                              lambda route_m: world.route(route_m)[2])
        frozen_m=dict(frame.actor_routes)[4]
        self.assertAlmostEqual(frozen_m,d.active[4].route_m)
        _,_,head,_=next(v for v in frame.hit_spheres if v[0]==4 and v[1]=='head')
        clip=pv@np.array((*head,1.));clip/=clip[3]
        px=(clip[0]+1.)*400.-.5
        py=(1.-clip[1])*300.-.5
        for _ in range(5):d.update(.05,480.)
        self.assertNotAlmostEqual(frozen_m,d.active[4].route_m)
        seen=[]
        def occlusion_probe(agent,t,origin,direction,route_at_shot=None,
                            enemy_route_at_shot=None):
            seen.append((route_at_shot,enemy_route_at_shot,agent.route_m))
            return False
        obj._enemy_shot_occluded=occlusion_probe
        self.assertEqual(obj.submit_game_hit(px,py,frame=frame),(4,'head'))
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0][0],480.)
        self.assertAlmostEqual(seen[0][1],frozen_m)
        self.assertNotAlmostEqual(seen[0][1],seen[0][2])

    def test_enemy_gunfire_alerts_next_patrol_without_cascade(self):
        d=EnemyDirector();d.update(.03,510.)
        self.assertIn(4,d.active)
        self.assertIn(5,d.active)
        b=d.active[5]
        self.assertEqual(b.state,'idle')
        for _ in range(120):d.update(.05,510.)
        self.assertGreater(d.active[4].shots_fired,0)
        self.assertGreater(b.heard_shots,0)
        self.assertIn(b.state,('investigating','alert','turning','aiming','firing','cover'))
        self.assertEqual(b.heard_shots,1)


if __name__=='__main__':unittest.main()
