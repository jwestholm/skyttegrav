"""V2.6 regression tests for seeded props and local SoldierBrain steering.

Uses the real pure geometry functions without Pygame or an OpenGL context.
It does NOT validate visible mesh appearance or 3-D prop collision.
"""
import ast
from dataclasses import dataclass
import math
from pathlib import Path
import random
import unittest
import numpy as np

SOURCE=Path(__file__).resolve().parents[1]/'trench_3d_test.py'


def runtime_geometry():
    tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
    function_names={
        'smooth','noise','eased','turn_for_meter','route','wall_height','sides','world',
        'junction_marker','nearest_junction','junction','junction_side',
        'junction_kind','junction_sides','branch_type','branch_half_width',
        'lantern_side','nearby_lanterns','branch_point',
        'branch_length','branch_center_shift','cover_distance','bend_marker',
        'bend_direction','near_junction','landscape_type','wall_width',
        'wall_offset','surface_material','hill_y','world_on_ground',
        'surface_normal','earth_surface_normal',
        'floor_y','tunnel_open','tunnel_drop','crater_height','is_branch_excavation',
        'oil_lantern','dugout_furnishings','battlefield_debris_chunk',
        'world_excavation_masks','soil_over_excavation',
        '_cutout_polygon_intersects_ground','_branch_footprint','_main_tunnel_footprint',
        '_main_route_footprint',
        'ground_patch_intersects_excavation','exterior_prop_ground',
        'obstacles_in_range','trench_obstacle','obstacle_steering',
        'draw_trench_obstacles','bar','blob','rock_fragment','sandbag_mesh',
        'ruined_wall_panel','ruined_outpost','hanging_fabric','torn_camouflage_net','vec_normal','box','local_box',
        'beam_world','scene_at','scenery_chunk','environment_chunk','trench_detail_props','make_chunk',
        'grass_tuft','rim_vegetation_chunk','trench_floor_litter','wood_crate',
        '_terrain_route_segments','_nearest_terrain_route','_exterior_y_world','build_exterior_terrain',
    }
    class_names={'MeshBuilder','TrenchObstacle','SoldierBrain'}
    selected=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))
              and node.name in function_names|class_names]
    env={
        'math':math,'random':random,'dataclass':dataclass,'np':np,
        'SEED':1944,'_ROUTE':[(0.,0.,0.)],
        'CHUNK_LEN':80.0,'SEGMENT':1.0,'WALL_HALF_WIDTH':1.12,
        'OBSTACLE_SPACING':13.0,
        'JUNCTION_FIRST':64,'JUNCTION_SPACING':72,
        'BEND_FIRST':11,'BEND_SPACING':34,
        'CORNER_DEPTH':1.50,'CORNER_MAIN_OFFSET':1.15,
        'COVER_EYE_CLEARANCE':.49,
        'SCENES':('fortified','exposed','ruined','marsh','forest','rocky'),
        'OUTDOOR_TILE_METRES':12.0,'OUTDOOR_CELL_METRES':3.0,
        'OUTDOOR_RADIUS_METRES':105.0,'OUTDOOR_MASK_SUBDIVISIONS':5,
    }
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(SOURCE),'exec'),env)
    return env


class ObstacleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=runtime_geometry()

    def test_stable_objects_across_chunk_boundaries(self):
        m=self.m
        whole=m['obstacles_in_range'](0,3200)
        split=[]
        for start in range(0,3200,80):
            split+=m['obstacles_in_range'](start,start+80-1e-6)
        self.assertEqual(whole,split)
        self.assertGreater(len(whole),35)
        self.assertGreaterEqual(len(set(ob.kind for ob in whole)),4)

    def test_walk_around_has_real_clearance(self):
        m=self.m
        detours=[ob for ob in m['obstacles_in_range'](0,5000) if ob.detour]
        self.assertGreater(len(detours),4)
        for ob in detours:
            s=ob.s
            side=1 if ob.detour>0 else -1
            # Obstruction is fully avoided while the detour is held constant.
            self.assertGreaterEqual(abs(ob.detour-ob.lateral),ob.width*.5+.24-1e-8)
            for d in (-1.0,-.5,0,.5,1):
                actual=m['obstacle_steering'](s+d)
                self.assertAlmostEqual(actual,ob.detour,places=7)
                self.assertLessEqual(abs(actual),m['cover_distance'](s+d,side)+1e-8)
            # Approaches are continuous and exactly zero at the end.
            self.assertAlmostEqual(m['obstacle_steering'](s-4.1),0.,places=8)
            self.assertAlmostEqual(m['obstacle_steering'](s+4.1),0.,places=8)
            points=[m['obstacle_steering'](s-4.1+i*.03) for i in range(275)]
            self.assertLess(max(abs(b-a) for a,b in zip(points,points[1:])),.05)

    def test_no_hard_obstacles_in_narrow_corridor(self):
        m=self.m
        for ob in m['obstacles_in_range'](0,5000):
            for i in range(100):
                d=ob.s + (i/99-.5)*2.0
                # Obstruction positions avoid the actual generated blind corners.
                self.assertFalse(m['near_junction'](d,3.5))
            if ob.kind in ('crate','rubble'):
                self.assertNotEqual(ob.detour,0.)

    def test_brain_resolves_prop_and_controls_speed(self):
        m=self.m
        for kind in ('crate','rubble','timber','sandbags','puddle'):
            ob=next((v for v in m['obstacles_in_range'](0,10000) if v.kind==kind),None)
            self.assertIsNotNone(ob,kind)
            brain=m['SoldierBrain']()
            # Isolate prop response from unrelated route corner checks.
            brain.visited.update(range(1000));brain.checked_bends.update(range(1000))
            mode=brain.choose(ob.s-.7,.016)
            self.assertIsNotNone(brain.obstacle_active,kind)
            self.assertEqual(brain.obstacle_active.index,ob.index)
            self.assertEqual(mode,5)
            self.assertLess(brain.speed_factor,1.0)
            self.assertEqual(kind in ('timber','sandbags'),brain.step_lift>0,kind)

    def test_long_autonomous_walk_has_continuous_camera_path(self):
        """One kilometre with real brain decisions and simulated camera turning.

        The main-route distance intentionally advances during rejoin; assert
        continuity in world-space camera coordinates instead of route metres.
        """
        m=self.m
        brain=m['SoldierBrain']()
        distance=0.0
        heading=None
        prior=None
        max_step=0.0
        dt=.05
        speeds=(0.0,0.0,0.0,.30,.68,1.15,1.65,2.30,3.35)
        for _ in range(28000):
            mode=brain.choose(distance,dt)
            distance,_=brain.advance(distance,speeds[mode]*brain.speed_factor*dt)
            x,z,desired=brain.camera_pose(distance)
            if heading is None:heading=desired
            delta=math.atan2(math.sin(desired-heading),math.cos(desired-heading))
            rate=1.15 if brain.state=='turn_back' else 1.75
            heading+=max(-rate*dt,min(rate*dt,delta))
            brain.heading_actual=heading
            if prior is not None:
                step=math.hypot(x-prior[0],z-prior[1])
                max_step=max(max_step,step)
            prior=(x,z)
            if distance>=1050.0:
                break
        self.assertGreaterEqual(distance,1050.0)
        self.assertGreaterEqual(len(brain.visited),10)
        self.assertLess(max_step,.23)

    def test_prop_mesh_is_finite(self):
        m=self.m
        seen=set()
        class RecordingMesh:
            def __init__(self):self.count=0
            def quad(self,*args):
                self.count+=1
                for vertex in args[:4]:
                    self.self_outer.assertTrue(all(math.isfinite(float(x)) for x in vertex))
        for chunk in range(0,13):
            mesh=RecordingMesh();mesh.self_outer=self
            m['draw_trench_obstacles'](mesh,chunk*80)
            if m['obstacles_in_range'](chunk*80,(chunk+1)*80):
                self.assertGreater(mesh.count,0)
            for ob in m['obstacles_in_range'](chunk*80,(chunk+1)*80):seen.add(ob.kind)
        self.assertGreaterEqual(len(seen),4)


if __name__=='__main__':unittest.main()
