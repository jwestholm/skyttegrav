"""Modern field compositions, real mesh clearance and unchanged gameplay AST."""
import ast
from pathlib import Path
import random
import unittest
import numpy as np
from test_v391_atomic_streaming import game as g
from shot_geometry import WorldShotMesh, NON_BALLISTIC_LAYERS

class First200Tests(unittest.TestCase):
    def test_props_determinism_dimensions_and_materials(self):
        state=random.getstate()
        for family in range(5,10):
            arrays=[]
            for _ in range(2):
                m=g.MeshBuilder();g.fieldwork_prop(m,lambda x,z,y:(x,y,z),family,37)
                arrays.append(m.as_array())
            a=arrays[0];np.testing.assert_array_equal(a,arrays[1])
            self.assertEqual(a.shape[1],9);self.assertTrue(np.isfinite(a).all())
            self.assertGreaterEqual(a[:,1].min(),0.)
            self.assertLessEqual(a[:,1].max(),.86)
            self.assertLessEqual(abs(a[:,2]).max(),.311 if family==9 else .15)
            self.assertLessEqual(abs(a[:,0]).max(),.48)
            self.assertFalse(set(a[:,8])&NON_BALLISTIC_LAYERS)
            self.assertEqual(len(WorldShotMesh(a).layers),len(a)//3)
            self.assertIn(27,a[:,8])
        self.assertEqual(state,random.getstate())

    def test_global_ownership_and_full_cluster_clearance(self):
        forward={s:list(g.modern_fieldwork_layout(s)) for s in (0,80,160,320)}
        reverse={s:list(g.modern_fieldwork_layout(s)) for s in (320,160,80,0)}
        self.assertEqual(forward,reverse)
        allprops=sum(forward.values(),[])
        self.assertGreaterEqual(len({p[2] for p in allprops if p[0]<200}),3)
        self.assertEqual(list(g.modern_fieldwork_layout(40)),[p for p in allprops if 40<=p[0]<120])
        for start,props in forward.items():
            for s,edge,family,index in props:
                self.assertTrue(start<=s<start+80)
                self.assertGreaterEqual(abs(edge)-.14,.68)
                self.assertFalse(g.near_junction(s+.35,6.6))
                self.assertFalse(g.obstacles_in_range(s-.55,s+1.15))
                side=1 if edge>0 else -1
                for t0 in (s-.5,s,s+.5,s+1.15):
                    self.assertLessEqual(abs(edge)+(.14 if family==7 else .12),g.lining_bank(t0,side)-.18)
                for t in (s-.5,s,s+.5,s+1.15):
                    for y in (0,.3,.6):
                        bank=g.wall_offset(t,side,g.floor_y(t,0)+y,g.wall_height(t,side))
                        self.assertLess(abs(edge)+.14,bank)
                m=g.MeshBuilder()
                spot=lambda x,z,y:g.world(s+x,edge+z,g.floor_y(s+x,edge+z)+y-.006)
                g.fieldwork_prop(m,spot,family,index)
                # Actual route projection: every vertex remains outside centre lane.
                route=np.array([g.world(t,0,0) for t in np.linspace(s-.6,s+.6,60)])[:,[0,2]]
                v=m.as_array()
                distance=np.linalg.norm(v[:,None,[0,2]]-route[None,:,:],axis=2).min()
                self.assertGreater(distance,.66)

    def test_rear_appliance_is_unique_and_beyond_inspection(self):
        from unittest.mock import patch
        records=[]
        real=g.fieldwork_prop
        def record(mesh,spot,family,seed):
            if family==9:records.append((seed,spot(0,0,0)))
            real(mesh,spot,family,seed)
        with patch.object(g,'fieldwork_prop',record):
            for i in range(2):
                for side in g.junction_sides(i):
                    g.dugout_furnishings(g.MeshBuilder(),i,side,g.branch_length(i))
        self.assertEqual(len(records),1)
        self.assertEqual(records[0][0],0)
        depth=g.SoldierBrain.__new__(g.SoldierBrain)._depth_to_check(0)
        self.assertGreater(g.branch_length(0)-1.15-.95-.3,depth+.7)
        self.assertEqual(records[0][1][1],g.floor_y(64,0))

    def test_only_authorized_graphics_functions_changed(self):
        root=Path(__file__).resolve().parents[1]
        before=ast.parse((root/'graphics_first200_validation/before_source.py').read_text())
        after=ast.parse((root/'trench_3d_test.py').read_text())
        def functions(tree):
            return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        a,b=functions(before),functions(after)
        changed={k for k in a if a[k]!=b[k]}
        self.assertEqual(changed,{'fieldwork_prop','trench_detail_props','dugout_furnishings','Trench'})
        old=next(n for n in before.body if isinstance(n,ast.ClassDef) and n.name=='Trench')
        new=next(n for n in after.body if isinstance(n,ast.ClassDef) and n.name=='Trench')
        self.assertEqual({k for k,v in functions(old).items() if functions(new)[k]!=v},{'load_textures'})

    def test_passage_rays_against_added_geometry(self):
        for start in (0,80,160):
            m=g.MeshBuilder();g.trench_detail_props(m,start)
            shots=WorldShotMesh(m.as_array())
            for s in np.arange(start+2,start+78,4):
                for lateral in (-.4,0,.4):
                    a=np.array(g.world(s,lateral,g.floor_y(s,lateral)+1.2))
                    b=np.array(g.world(s+2,lateral,g.floor_y(s+2,lateral)+1.2))
                    self.assertIsNone(shots.first_hit(a,b-a,float(np.linalg.norm(b-a))))

if __name__=='__main__':unittest.main()
