"""V3.1: surface-level, triangle-intersection regressions for underground spaces.

The former tests only checked mesh centroids. A single large *triangle* may
cross an entire roofed passage even though its centre is outside the cave.
These checks intersect triangles with points in the playable X/Z corridor,
compare actual surface heights, and verify there is NO terrain below the roof.
"""
import math
import unittest
import numpy as np
from test_v26_obstacles import runtime_geometry


def layers_at(meshes, x, z, allowed_layers=None):
    """Return all triangle/barycentric Y hits at an exact world X/Z point."""
    hits=[]
    for mesh in meshes:
        triangles=mesh.reshape(-1,3,9)
        if allowed_layers is not None:
            triangles=triangles[np.isin(triangles[:,0,8].astype(int),allowed_layers)]
        v=triangles[:,:,:3]
        lo=v[:,:,[0,2]].min(axis=1)
        hi=v[:,:,[0,2]].max(axis=1)
        active=(lo[:,0]<=x+1.e-5)&(hi[:,0]>=x-1.e-5)&(lo[:,1]<=z+1.e-5)&(hi[:,1]>=z-1.e-5)
        for vertices,layer in zip(v[active],triangles[active,0,8].astype(int)):
            p=vertices[:,[0,2]].astype(float)
            d=p[1:]-p[0]
            det=d[0,0]*d[1,1]-d[0,1]*d[1,0]
            if abs(det)<1.e-9:continue
            tx,tz=x-p[0,0],z-p[0,1]
            u=(tx*d[1,1]-tz*d[1,0])/det
            w=(d[0,0]*tz-d[0,1]*tx)/det
            if min(u,w,1.-u-w)>-1.e-4:
                y=vertices[0,1]*(1-u-w)+vertices[1,1]*u+vertices[2,1]*w
                hits.append((float(y),int(layer)))
    return hits


class SurfaceIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g=runtime_geometry()
        # Main test scene has a covered tunnel around 301-331 and dugout at
        # 352. Sample BOTH sides of the 320m chunk boundary.
        cls.mesh={k:cls.g['make_chunk'](k) for k in (240.,320.,400.)}

    def test_ground_cutout_intersection_catches_straddling_polygon(self):
        g=self.g
        footprint=((-.20,-2.0),(.20,-2.0),(.20,2.0),(-.20,2.0))
        huge_quad=((-2.,-.25),(2.,-.25),(2.,.25),(-2.,.25))
        self.assertTrue(g['_cutout_polygon_intersects_ground'](huge_quad,footprint))
        self.assertFalse(g['_cutout_polygon_intersects_ground'](
            ((3.,0.),(5.,0.),(5.,2.),(3.,2.)),footprint))

    def test_main_tunnel_has_floor_roof_and_no_midair_soil(self):
        g=self.g
        meshes=(self.mesh[240.],self.mesh[320.])
        # Many offset samples, including points where the old material-3
        # ground band crossed the roof below the inner vaulted ceiling.
        inspected=0
        for s in np.arange(302.15,330.0,.85):
            if g['tunnel_open'](s)<.70:continue
            for offset in (-.24,0.,.24):
                x,z=g['sides'](float(s),offset)
                ys=layers_at(meshes,x,z,[3,20,21])
                floor=g['floor_y'](float(s),offset)
                roofs=[h for h,layer in ys if layer==20 and h>floor+1.1]
                self.assertTrue(roofs,(s,offset,ys))
                roof=min(roofs)
                self.assertGreater(roof-floor,1.90,(s,offset,roof,floor))
                soil=[h for h,layer in ys if layer==3]
                self.assertFalse([h for h in soil if floor+.10<h<roof+.10],
                                 (s,offset,floor,roof,ys))
                inspected+=1
        self.assertGreater(inspected,75)

    def test_dugout_no_soil_between_floor_and_cave_roof(self):
        g=self.g
        # Junction index 4 => 352m, often side cut crossing nearby terrain.
        meshes=(self.mesh[240.],self.mesh[320.],self.mesh[400.])
        tested=0
        for i in range(2,6):
            marker=g['junction_marker'](i)
            if not (240<=marker<=420 and g['branch_type'](i)=='dugout'):
                continue
            for side in g['junction_sides'](i):
                for along in (2.8,4.5,6.3,8.1):
                    if along>=g['branch_length'](i)-.8:continue
                    for lateral in (-.25,0.,.25):
                        x,_,z=g['branch_point'](i,side,along,lateral,0.)
                        ys=layers_at(meshes,x,z,[3,20,21])
                        roof=[y for y,layer in ys if layer==20 and y>1.1]
                        self.assertTrue(roof,(i,side,along,lateral,ys))
                        ceiling=min(roof)
                        self.assertGreater(ceiling-g['floor_y'](marker,0.),2.12,
                                           (i,side,along,lateral,ys))
                        bad=[y for y,layer in ys if layer==3 and
                             g['floor_y'](marker,0.)+.12<y<ceiling+.09]
                        self.assertFalse(bad,(i,side,along,lateral,ys))
                        tested+=1
        self.assertGreater(tested,0)

    def test_open_trench_has_no_outdoor_field_over_walkway(self):
        """Older V3.0 generated extra earth levels in all 228 sample points.

        This catches ground strips folded back over an OPEN passage, not just
        a covered tunnel. The entire main route is an excavation cutout.
        """
        g=self.g
        meshes=(self.mesh[240.],self.mesh[320.],self.mesh[400.])
        count=0
        for s in np.arange(242.3,392.0,6.3):
            if g['tunnel_open'](s)>.01 or g['near_junction'](s,4.0):
                continue
            for across in (-.23,0.,.23):
                x,z=g['sides'](float(s),across)
                earth=layers_at(meshes,x,z,[3])
                self.assertFalse(earth,(s,across,earth))
                count+=1
        self.assertGreater(count,30)

    def test_floor_mesh_does_not_extend_through_narrow_banks(self):
        """Regression: V3.0 floor was a hardcoded 3.84m wide everywhere."""
        g=self.g
        meshes=(self.mesh[240.],self.mesh[320.],self.mesh[400.])
        samples=0
        for s in (246.4,262.3,306.5,319.2,331.5,408.1):
            if g['near_junction'](s,3.5): continue
            for side in (-1,1):
                inside=side*max(.1,g['wall_width'](s,side)-.18)
                outside=side*(g['wall_width'](s,side)+.17)
                ix,iz=g['sides'](s,inside)
                ox,oz=g['sides'](s,outside)
                inner=layers_at(meshes,ix,iz,[21])
                outer=layers_at(meshes,ox,oz,[21])
                self.assertTrue(inner,(s,side,inside,inner))
                self.assertFalse(outer,(s,side,outside,outer))
                samples+=1
        self.assertGreater(samples,7)

    def test_chunk_seam_floor_continuity(self):
        g=self.g
        for s in (80.,160.,240.,320.,400.,480.):
            for offset in (-.50,0.,.50):
                self.assertAlmostEqual(g['floor_y'](s-1.e-4,offset),
                                       g['floor_y'](s+1.e-4,offset),delta=.003)


if __name__=='__main__': unittest.main()
