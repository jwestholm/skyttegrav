"""Real deterministic route geometry: curved navigation stays in passage footprint.

This validates the 2D plan view; it is NOT GPU, raycast or physical collision validation.
"""
import ast
import math
from pathlib import Path
import unittest


def real_brain():
    path=Path(__file__).resolve().parents[1]/'trench_3d_test.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    names={'SoldierBrain','noise','eased','turn_for_meter','route',
           'wall_width','branch_center_shift','junction_marker','junction_side',
           'branch_length','cover_distance','bend_marker','bend_direction'}
    body=[node for node in tree.body
          if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names]
    env={'math':math, 'SEED':1944, '_ROUTE':[(0.,0.,0.)],
         'WALL_HALF_WIDTH':1.12,'JUNCTION_FIRST':64,'JUNCTION_SPACING':72,
         'CORNER_DEPTH':1.5,'CORNER_MAIN_OFFSET':1.15,
         'BEND_FIRST':11,'BEND_SPACING':34,'COVER_EYE_CLEARANCE':.49,
         'smooth':lambda a,b,alpha:a+(b-a)*alpha}
    exec(compile(ast.Module(body=body,type_ignores=[]),str(path),'exec'),env)
    return env


class RealCornerClearanceTests(unittest.TestCase):
    def test_curves_stay_in_corridor_footprint(self):
        m=real_brain()
        for i in range(100):
            b=m['SoldierBrain']()
            b.branch_index=i
            b.branch_side=m['junction_side'](i)
            marker=m['junction_marker'](i)
            cx,cz,heading=m['route'](marker)
            near=max(m['wall_width'](marker,b.branch_side),
                     m['wall_width'](marker-2,b.branch_side),
                     m['wall_width'](marker+2,b.branch_side))-.18
            for outward in (True,False):
                b._start_corner(outward)
                for k in range(101):
                    x,z=b._bezier(b.corner_points,k/100.)
                    lateral=(x-cx)*math.cos(heading)-(z-cz)*math.sin(heading)
                    forward=(x-cx)*math.sin(heading)+(z-cz)*math.cos(heading)
                    side=1 if lateral>=0 else -1
                    inside_main=(abs(lateral)<=m['wall_width'](marker,side)-.025
                                 and abs(forward)<=2.0)
                    inside_branch=(lateral*b.branch_side>=near-.20
                                   and abs(forward)<=1.85)
                    self.assertTrue(inside_main or inside_branch,
                        f'branch {i}, outward={outward}, t={k/100}, '
                        f'lat={lateral:.3f}, longitudinal={forward:.3f}')

if __name__=='__main__':unittest.main()
