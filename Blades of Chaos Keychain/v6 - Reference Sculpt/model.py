#!/usr/bin/env python3
"""Reference-sculpted 110 mm Blades of Chaos miniature, headless CAD/mesh export.

Run: python model.py
The reference is interpreted as geometry, not projected as an image texture.
Both faces are sculpted. A continuous helical wrap runs around the grip.
STL/3MF contain one closed solid; add FDM supports in the slicer.
"""
from pathlib import Path
from math import pi, sin, cos
import argparse, json, struct, zipfile
import numpy as np
import cadquery as cq
import triangle
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union, orient
from shapely.affinity import affine_transform, scale as scale_shape, rotate
from scipy.spatial import cKDTree

# ------------------------ Parameters in millimeters ------------------------
LENGTH = 110.0                    # Overall length. Supported range: 100-150 mm.
EDGE_HALF_THICKNESS = 0.90        # Blunt perimeter thickness = 1.80 mm total.
BLADE_CROWN_RISE = 1.65           # Crown rise above each face's perimeter.
BEVEL_WIDTH = 3.30                # Broad bright bevel, measured inward in XY.
ENGRAVING_WIDTH = 0.60            # Main branching sigils; width at half depth.
ENGRAVING_DEPTH = 0.34
RUNE_WIDTH = 0.48                 # Smaller edge symbols, mm at half depth.
RUNE_DEPTH = 0.24
BONE_TEXTURE_DEPTH = 0.16         # Secondary scales; primary forms are larger.
BONE_TEXTURE_SPACING = 0.86
GRIP_HALF_HEIGHT = 3.85
WRAP_PITCH = 5.00                 # Axial pitch of the continuous helical band.
WRAP_GROOVE_DEPTH = 0.55
KEYRING_HOLE_DIAMETER = 4.60       # Nominal 4 mm ring wire + 0.30 mm per side.
KEYRING_MIN_WALL = 1.40           # Checked against the finished planar domain.
POMMEL_SECOND_HOLE_DIAMETER = 2.00
TIP_RADIUS = 0.28                 # Rounds the silhouette; never a sharpened edge.
MESH_PITCH = 0.08                 # Fine sculpt sampling; does not change nozzle resolution.
FDM_TILT_DEG = 65.0               # Long axis above bed; supports REQUIRED.
FDM_ROLL_DEG = 12.0
OUTPUT = Path('./output_model.stl')
# All decorative control points below use a canonical 110 mm coordinate frame.
# In-plane forms scale with LENGTH; thickness, groove widths and hole sizes do not.
# --------------------------------------------------------------------------


def require(test, message):
    if not test:
        raise ValueError(message)


def smooth(t):
    t = np.clip(t, 0, 1)
    return t*t*(3-2*t)


def path(start, segments):
    points = [np.asarray(start, float)]
    for segment in segments:
        a = points[-1].copy()
        if len(segment) == 2:
            b = np.asarray(segment, float)
            count = max(2, int(np.linalg.norm(b-a)/.075)+1)
            points.extend(a+(b-a)*u for u in np.linspace(0, 1, count)[1:])
        else:
            b,c,d = np.asarray(segment, float).reshape(3,2)
            length = sum(np.linalg.norm(q-p) for p,q in ((a,b),(b,c),(c,d)))
            count = max(3, int(length/.075)+1)
            points.extend((1-u)**3*a+3*(1-u)**2*u*b+3*(1-u)*u*u*c+u**3*d
                          for u in np.linspace(0,1,count)[1:])
    return np.asarray(points)


def ellipse(center, axes, angle=0):
    p = scale_shape(Point(*center).buffer(1, quad_segs=96), *axes, origin=center)
    return rotate(p, angle, origin=center)


def stroke_distance(points, control, curved=False):
    """Dense continuous polyline distance, <=0.04 mm sample spacing."""
    knots = np.asarray(control, float)
    steps = np.r_[0, np.cumsum(np.linalg.norm(np.diff(knots,axis=0),axis=1))]
    require(np.all(np.diff(steps)>0), 'Duplicate stroke control points.')
    samples = np.linspace(0, steps[-1], max(3, int(steps[-1]/.04)+1))
    if curved and len(knots)>2:
        from scipy.interpolate import CubicSpline
        curve = CubicSpline(steps, knots, bc_type='natural')(samples)
    else:
        curve = np.c_[np.interp(samples,steps,knots[:,0]),
                      np.interp(samples,steps,knots[:,1])]
    return cKDTree(curve).query(points)[0]


def oval(points, center, axes, angle=0):
    x,y = (points-np.asarray(center)).T
    a = np.radians(angle)
    return ((x*cos(a)+y*sin(a))/axes[0])**2+((-x*sin(a)+y*cos(a))/axes[1])**2


def blade_profile():
    # Broad curved belly, swept tip, two deep notches, scalloped dorsal shoulder.
    return Polygon(path((37.5, 3.7), [
        (47,4.4,56,3.9,63,5.0),
        (64.5,5.1,66,6.0,68,7.2),
        (68,4.3,71,4.8,74.5,8.5),
        (75.0,6.2,77,7.2,80.4,10.4),
        (81.0,8.0,84,9.9,86.2,12.0),
        (96,15.2,104,20.7,110,23.4),
        (106.6,12.8,101,3.0,91,-6.7),
        (88,-9.8,83,-13.3,78.5,-15.9),
        (83.4,-8.5,77.6,-6.0,72.2,-10.5),
        (73.7,-5.5,69.0,-4.6,64.4,-8.2),
        (61,-7.0,57.2,-6.3,53,-7.0),
        (46,-7.7,42,-8.5,37.5,-7.9), (37.5,3.7)
    ])).buffer(-TIP_RADIUS).buffer(TIP_RADIUS)


def skull_profile():
    body = Polygon(path((29.2,-4.0),[
        (27.0,0,28.6,6.5,32,8.8),
        (34.6,11.0,39.3,9.1,42.7,6.1),
        (45.6,5.0,48.8,5.1,52.2,3.0),
        (50.2,1.1,46.3,1.2,45.0,-1.8),
        (42.3,-4.4,39.5,-5.6,38.7,-9.5),
        (35.2,-10.6,31.1,-7.6,29.2,-4.0)
    ]))
    ring = ellipse((32.6,-10.1),(7.6,7.0),-14)
    # Rounded thorn roots overlap the ring; no disconnected ornament.
    spines=[]
    for i,theta in enumerate(np.linspace(192,275,5)):
        a=np.radians(theta)
        c=np.array([32.6+7.4*np.cos(a),-10.1+6.7*np.sin(a)])
        outward=np.array([np.cos(a),np.sin(a)])
        tangent=np.array([-outward[1],outward[0]])
        spines.append(Polygon([c-tangent*.72-outward*.45,
                               c+tangent*.72-outward*.45,
                               c+outward*(1.05+.28*np.sin(i)) + tangent*.30]).buffer(.20))
    tail=Polygon(path((34,-15),[(36,-16,39,-16.8,42,-15.2),
        (40.8,-17.6,38.9,-19.7,37.6,-18.7),(35,-17.4,33.9,-16.1,34,-15)])).buffer(.15)
    return unary_union([body,ring,tail,*spines]).buffer(-.12).buffer(.12)


def pommel_profile():
    # A pierced heraldic crown, replacing the previous plain circular eyelet.
    return Polygon(path((.0,3.7),[
        (1.7,3.1,2.4,4.5,2.2,6.2),
        (4.3,5.8,5.6,6.8,6.8,6.7),
        (6.6,4.6,8.1,4.2,9.9,5.2),
        (10.1,3.6,10.8,2.7,12.5,2.7),
        (13.3,1.3,13.1,-2.0,12.0,-3.0),
        (11.3,-3.1,11.7,-4.1,12.4,-5.1),
        (10.2,-4.5,9.3,-5.3,9.1,-6.6),
        (7.0,-5.3,5.2,-5.0,3.7,-6.1),
        (3.9,-3.7,2.2,-3.4,0.8,-3.9),
        (1.0,-1.6,0.1,1.5,0.0,3.7)
    ])).buffer(-.17).buffer(.17)


def tooth_profile(i):
    a=np.array([38.4+i*2.0, -0.3-i*.52])
    b=a+np.array([3.8, -2.2-i*.12])
    c=a+np.array([5.5+i*.32, -5.8-i*.25])
    line=path(a,[(*b,*b,*c)])
    tangent=np.gradient(line,axis=0)
    normal=np.c_[-tangent[:,1],tangent[:,0]]
    normal/=np.linalg.norm(normal,axis=1)[:,None]
    width=np.linspace(.9,.27,len(line))
    return Polygon(np.vstack([line+normal*width[:,None],
                              (line-normal*width[:,None])[::-1]])).buffer(.12)


def sigil_strokes():
    strokes=[]
    # Sparse branching trees and square joints follow the photographed engraving.
    for hub, branches in [
        ((57.2,-1.0), [[(54.3,1.0),(50.8,1.8)],[(54.8,-3.5),(51.3,-4.6)],
                      [(58.5,2.2),(61.2,3.2)],[(59.5,-3.4),(61.8,-4.2)]]),
        ((74.0,-.6), [[(70.3,1.5),(68.4,3.7)],[(69.5,-2.3),(67.0,-4.5)],
                      [(76.7,3.0),(79.8,6.4)],[(76.5,-3.6),(78.8,-6.5)]]),
        ((91.5,5.2), [[(85.7,5.6),(84.0,8.6)],[(86.6,1.1),(83.0,-1.5)],
                      [(96.6,8.5),(100.3,13.8)],[(94.4,2.3),(97.0,2.2)]])
    ]:
        cx,cy=hub
        strokes.append(([(cx-.75,cy-.65),(cx+.75,cy-.65),(cx+.75,cy+.65),
                         (cx-.75,cy+.65),(cx-.75,cy-.65)],False))
        for control in branches:
            direction=np.asarray(control[0])-hub
            start=np.asarray(hub)+direction/np.linalg.norm(direction)*.95
            strokes.append(([start,*control],True))
            x,y=control[-1]
            # Terminal fork and diamond: readable geometry at miniature scale.
            strokes.append(([(x-.65,y-.45),(x,y),(x-.65,y+.45)],False))
            strokes.append(([(x+.15,y-.62),(x+.62,y),(x+.15,y+.62)],False))
    strokes.extend([
        ([(48.8,-1.3),(51.2,-1.0),(54.5,-1.0)],True),
        ([(58.1,-1),(62.4,-.8),(65.0,-.1)],True),
        ([(65.0,-.1),(66.4,1.0),(67.7,-.1),(66.4,-1.2),(65.0,-.1)],False),
        ([(67.7,-.1),(70.0,-.3),(73.2,-.6)],True),
        ([(74.8,-.3),(81,1.4),(85.5,3.1),(90.7,5.0)],True),
    ])
    return strokes


class Sculpt:
    def __init__(self):
        canonical={
            'blade':blade_profile(), 'guard':skull_profile(),
            'grip':Polygon([(10,-1.2),(34,-1.2),(34,1.2),(10,1.2)]),
            'pommel':pommel_profile(),
            'collar':ellipse((31.0,0),(2.2,4.8)),
        }
        self.teeth=[tooth_profile(i) for i in range(4)]
        for i,tooth in enumerate(self.teeth):canonical[f'tooth{i}']=tooth
        whole=unary_union(list(canonical.values()))
        self.origin=np.asarray(whole.bounds[:2])
        self.scale=LENGTH/(whole.bounds[2]-whole.bounds[0])
        self.parts={name:affine_transform(part,[self.scale,0,0,self.scale,
                    -self.origin[0]*self.scale,-self.origin[1]*self.scale])
                    for name,part in canonical.items()}
        self.key_center=self.world([4.8,.45])
        self.holes=[Point(*self.key_center).buffer(KEYRING_HOLE_DIAMETER/2,quad_segs=96),
                    Point(*self.world([9.4,-3.1])).buffer(POMMEL_SECOND_HOLE_DIAMETER/2,quad_segs=64),
                    affine_transform(ellipse((32.4,-10.2),(4.65,3.8),-14),
                        [self.scale,0,0,self.scale,-self.origin[0]*self.scale,-self.origin[1]*self.scale])]
        self.domain=orient(unary_union(list(self.parts.values())).difference(unary_union(self.holes)),sign=1)
        require(self.domain.is_valid and self.domain.geom_type=='Polygon','Profile must form one connected polygon.')
        require(len(self.domain.interiors)==3,'Expected two pommel apertures and one open guard loop.')
        self.key_wall=float(self.holes[0].distance(self.domain.exterior))
        self.key_wall=min(self.key_wall,*(self.holes[0].distance(h) for h in self.holes[1:]))
        require(self.key_wall>=KEYRING_MIN_WALL,f'Keyring ligament too narrow: {self.key_wall:.3f} mm.')
        self.sigils=sigil_strokes()

    def world(self,q):
        return (np.asarray(q)-self.origin)*self.scale

    def sample(self,p,back=False):
        q=p/self.scale+self.origin
        x,y=q.T
        h=np.full(len(p),EDGE_HALF_THICKNESS)
        mat=np.ones(len(p),np.int32)
        pts=shapely.points(p)
        for name,shape in self.parts.items():
            mask=shapely.distance(pts,shape)<1e-7
            if not mask.any():continue
            qq=q[mask];xx,yy=qq.T;pp=p[mask]
            dist=shapely.distance(pts[mask],shape.boundary)
            taper=smooth(dist/.65)
            material=np.full(len(qq),3,np.int32)
            if name=='blade':
                edge=smooth(dist/BEVEL_WIDTH)
                hh=EDGE_HALF_THICKNESS+BLADE_CROWN_RISE*edge
                hh+=.20*np.exp(-((yy+.2)/8.0)**2)*edge
                material[:]=1;material[dist<BEVEL_WIDTH*.90]=5
                all_grooves=np.zeros(len(qq))
                for line,curved in self.sigils:
                    dd=stroke_distance(qq,line,curved)*self.scale
                    all_grooves=np.maximum(all_grooves,np.exp(-(dd/(ENGRAVING_WIDTH/.912))**4*16))
                hh-=ENGRAVING_DEPTH*all_grooves*smooth((dist-BEVEL_WIDTH*.65)/.7)
                material[(all_grooves>.60)&(dist>BEVEL_WIDTH*.85)]=4
                # Rune-like edge marks, following the large swept outer bevel.
                for i,(cx,cy,angle) in enumerate([(86,-6.0,32),(90,-2.2,40),(94,2.2,45),
                        (97.5,6.4,49),(100.7,10.7,53),(103.2,14.7,58)]):
                    glyphs=[[[(-.5,-.7),(.5,.7)],[(-.5,.7),(.5,-.7)]],
                            [[(-.5,-.7),(-.5,.7),(.5,.15),(-.5,-.15)]],
                            [[(0,-.8),(0,.8)],[(0,.0),(.65,.65)],[(-.6,0),(0,.55)]],
                            [[(-.55,0),(0,.7),(.55,0),(0,-.7),(-.55,0)]]]
                    a=np.radians(angle);rot=np.array([[cos(a),-sin(a)],[sin(a),cos(a)]])
                    for line in glyphs[i%len(glyphs)]:
                        dd=stroke_distance(qq,np.asarray(line)@rot.T+[cx,cy])*self.scale
                        g=np.exp(-(dd/(RUNE_WIDTH/.912))**4*16)
                        hh-=RUNE_DEPTH*g*smooth(dist/.60)
                        material[(g>.60)&(dist>.60)]=6
                hh+=.027*np.sin(xx*3.5+yy*.3)*np.sin(yy*6.1)*edge
            elif name=='grip':
                hh=np.full(len(qq),EDGE_HALF_THICKNESS)
                material[:]=2
            elif name=='collar':
                dome=np.sqrt(np.clip(1-(yy/4.8)**2,0,1))
                hh=EDGE_HALF_THICKNESS+3.8*dome*smooth(dist/.35)
                hh+=.20*np.cos(xx*9)*dome*taper
                hh-=.23*np.exp(-((xx-31)/.24)**4)*dome*taper
            elif name=='guard':
                dh=shapely.distance(pts[mask],self.holes[2].boundary)
                local_edge=np.minimum(dist,dh)
                taper=smooth(local_edge/.75)
                rounded=np.sqrt(np.clip(local_edge/2.6,0,1))
                hh=EDGE_HALF_THICKNESS+1.25*rounded
                hh+=2.20*np.exp(-oval(qq,(34.8,4.8),(4.9,3.2),-12))*taper
                hh+=1.50*np.exp(-oval(qq,(40.1,.0),(3.3,2.6),-28))*taper
                ring_profile=np.sin(pi*np.clip(dist/np.maximum(dist+dh,1e-8),0,1))**.70
                hook=smooth((-yy-2.5)/3.5)
                ring_height=EDGE_HALF_THICKNESS+1.65*ring_profile
                hh=hh*(1-hook)+ring_height*hook
                # Scale-shaped chased pits are real mesh displacement, not shading.
                row=np.round(yy*self.scale/(BONE_TEXTURE_SPACING*.82))
                dx=(xx*self.scale/BONE_TEXTURE_SPACING+.5*(row%2))
                dx=(dx-np.round(dx))*BONE_TEXTURE_SPACING
                dy=yy*self.scale-row*BONE_TEXTURE_SPACING*.82
                cell=(dx/(BONE_TEXTURE_SPACING*.36))**2+(dy/(BONE_TEXTURE_SPACING*.27))**2
                texture=smooth((-yy-2.0)/3.0)
                hh-=BONE_TEXTURE_DEPTH*np.exp(-(cell/.80)**2)*taper*texture
                hh+=.055*np.exp(-((cell-1.2)/.34)**2)*taper*texture
                hh+=.075*np.sin(xx*4.6+np.sin(yy*3))*np.sin(yy*5.7+np.sin(xx))*taper*(1-texture)
                for k in range(6):
                    line=[(36.5+k*.55,1.8-k*.55),(39.2+k*.7,.7-k*.43),(42.3+k*.50,.75-k*.57)]
                    dd=stroke_distance(qq,line,True)*self.scale
                    hh-=.25*np.exp(-(dd/.24)**4)*taper
                    hh+=.16*np.exp(-((dd-.40)/.20)**2)*taper
                ridges=[([(29.0,2),(30.8,6.0),(34.6,8.4),(38.8,7.0),(43.5,4.5)],.63,.78),
                        ([(31.1,2.9),(33.0,5.8),(36.3,6.3),(40.2,4.0)],.55,.95),
                        ([(37.0,1.1),(40.6,2.0),(45.0,2.2),(49.8,2.7)],.48,.76),
                        ([(31.8,-.5),(33.5,-2.4),(37.2,-3.5),(41.0,-2.8)],.60,.65)]
                for line,width,height in ridges:
                    dd=stroke_distance(qq,line,True)*self.scale
                    hh+=height*np.exp(-(dd/width)**2)*taper
                    hh-=.16*np.exp(-((dd-width*.95)/.20)**4)*taper
                eye=oval(qq,(35.4,3.65),(2.75,1.4),-18)
                hh-=2.65*np.exp(-(eye/.80)**3)*taper
                hh+=.38*np.exp(-((eye-1.1)/.31)**2)*taper
                nose=oval(qq,(45.2,3.15),(1.50,.57),-11)
                hh-=1.08*np.exp(-(nose/.85)**3)*taper
                material[eye<.65]=6;material[nose<.58]=6
                # Raised lips on the actual open hook, with a second chased rail.
                dh=shapely.distance(pts[mask],self.holes[2].boundary)
                hh+=.43*np.exp(-((dh-.52)/.24)**2)*taper
                hh-=.20*np.exp(-((dh-.98)/.19)**2)*taper
                for line in [ [(31,-1),(31.5,-3),(33.0,-4.2)],
                              [(38.5,5.8),(41.0,5.1),(43.7,4.6)],
                              [(33,8.0),(32,7.1),(32.6,6.4)],
                              [(37.6,8.2),(37.0,7.2),(38.0,6.6)]]:
                    dd=stroke_distance(qq,line)*self.scale
                    hh-=.24*np.exp(-(dd/.24)**4)*taper
            elif name.startswith('tooth'):
                hh=EDGE_HALF_THICKNESS+3.1*np.sqrt(np.clip(dist/.88,0,1))
                hh-=.17*np.exp(-((dist-.36)/.15)**4)*smooth(dist/.4)
            else: # pierced pommel, contour moulding and small diamond bosses
                dh=shapely.distance(pts[mask],unary_union(self.holes[:2]).boundary)
                crown=smooth(dist/.70)*smooth(dh/.55)
                hh=EDGE_HALF_THICKNESS+1.75*crown
                hh+=.26*np.exp(-((dist-.45)/.20)**2)*smooth(dh/.5)
                hh-=.20*np.exp(-((dist-.95)/.18)**4)*smooth(dh/.5)
                for cx,cy in [(7.5,1.2),(7.6,-1.0),(5.4,-3.5),(9.7,.8)]:
                    diamond=(np.abs(xx-cx)+np.abs(yy-cy))/.75
                    hh+=.30*np.exp(-diamond**4)*crown
                hh+=.05*np.sin(xx*8)*np.cos(yy*8)*crown
            idx=np.flatnonzero(mask)
            # Layered overlapping forms are fused by their upper envelope.
            win=hh>h[idx]
            h[idx[win]]=hh[win]
            mat[idx[win]]=material[win]
        # A vertical 1.8 mm blunt perimeter remains even beneath the fine relief.
        return np.maximum(h,EDGE_HALF_THICKNESS),mat


def planar_mesh(domain,pitch,boundary_pitch=None):
    boundary_pitch=boundary_pitch or pitch
    loops=[np.array(domain.exterior.coords)[:-1]]+[np.array(r.coords)[:-1] for r in domain.interiors]
    # Densify all straight spans so the sculpt does not bridge across fine detail.
    dense=[]
    for loop in loops:
        points=[]
        for a,b in zip(loop,np.roll(loop,-1,axis=0)):
            count=max(1,int(np.ceil(np.linalg.norm(b-a)/boundary_pitch)))
            points.extend(a+(b-a)*u/count for u in range(count))
        dense.append(np.array(points))
    boundary=np.concatenate(dense)
    segments=[];offset=0
    for loop in dense:
        segments.extend((offset+i,offset+(i+1)%len(loop)) for i in range(len(loop)));offset+=len(loop)
    x0,y0,x1,y1=domain.bounds
    xx,yy=np.meshgrid(np.arange(x0+pitch*.31,x1,pitch),np.arange(y0+pitch*.27,y1,pitch))
    grid=np.column_stack([xx.ravel(),yy.ravel()])
    grid=grid[shapely.contains_xy(domain,grid[:,0],grid[:,1])]
    grid=grid[cKDTree(boundary).query(grid)[0]>pitch*.45]
    vertices=np.vstack([boundary,grid])
    args={'vertices':vertices,'segments':np.array(segments,np.int32)}
    if domain.interiors:
        args['holes']=np.array([list(Polygon(r).representative_point().coords)[0] for r in domain.interiors])
    result=triangle.triangulate(args,'pQ')
    xy=np.array(result['vertices']);faces=np.array(result['triangles'],np.int32)
    t=xy[faces];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0];area=a[:,0]*b[:,1]-a[:,1]*b[:,0]
    faces[area<0]=faces[area<0][:,::-1];area=np.abs(area)/2
    require(np.all(area>1e-12),'Degenerate planar facet.')
    require(abs(area.sum()-domain.area)<1e-5,'Planar triangulation does not match the profile.')
    centers=xy[faces].mean(axis=1)
    require(np.all(shapely.covers(domain,shapely.points(centers))),'Planar triangles leave the domain.')
    return xy,faces


def edge_list(faces):
    e=np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]])
    _,first,count=np.unique(np.sort(e,axis=1),axis=0,return_index=True,return_counts=True)
    require(np.all((count==1)|(count==2)),'Invalid planar topology.')
    return e[first[count==1]]


def validate(vertices,faces,shells=1,check_support=True):
    v=np.asarray(vertices,dtype=np.float32).astype(float);t=v[faces]
    normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);area2=np.linalg.norm(normals,axis=1)
    require(np.all(np.isfinite(v)) and np.all(area2>1e-10),'Degenerate export triangle.')
    e=np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]])
    _,count=np.unique(np.sort(e,axis=1),axis=0,return_counts=True)
    require(np.all(count==2),'Open or non-manifold edge.')
    require(len(np.unique(e,axis=0))==len(e),'Inconsistent winding.')
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    graph=coo_matrix((np.ones(len(e)),(e[:,0],e[:,1])),shape=(len(v),len(v))).tocsr()
    count=connected_components(graph,directed=False,return_labels=False)
    require(count==shells,f'Expected {shells} shells; got {count}.')
    volume=np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()/6
    require(volume>0,'Inverted solid.')
    unit=normals/area2[:,None]
    bad=(unit[:,2]<-(1/np.sqrt(2)+.0002))&(t[:,:,2].max(axis=1)>1e-5)
    if check_support:require(not bad.any(),f'{int(bad.sum())} unsupported facets above bed.')
    return {'watertight':True,'consistent_winding':True,'closed_shells':int(count),
            'volume_cm3':float(volume/1000),'dimensions_mm':np.ptp(v,axis=0).tolist(),
            'triangles':len(faces),'support_check_passed':bool(not bad.any())},unit


def save_3mf(path,parts,names):
    from xml.sax.saxutils import escape
    chunks=['<?xml version="1.0" encoding="UTF-8"?>','<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">','<metadata name="Title">Blades of Chaos v6 - reference sculpt</metadata><resources>']
    for i,(p,name) in enumerate(zip(parts,names),1):
        chunks.append(f'<object id="{i}" name="{escape(name)}" type="model"><mesh><vertices>')
        chunks.extend(f'<vertex x="{x:.8f}" y="{y:.8f}" z="{z:.8f}"/>' for x,y,z in p['vertices']);chunks.append('</vertices><triangles>')
        chunks.extend(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in p['faces']);chunks.append('</triangles></mesh></object>')
    chunks.append('</resources><build>');chunks.extend(f'<item objectid="{i}"/>' for i in range(1,len(parts)+1));chunks.append('</build></model>')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as out:
        out.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        out.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        out.writestr('3D/3dmodel.model',''.join(chunks))


def save_mesh(path,item,stl=True):
    if stl:
        v=item['vertices'].astype(np.float32);f=item['faces'];t=v[f].astype(float)
        nn=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);nn/=np.linalg.norm(nn,axis=1)[:,None]
        rows=np.zeros(len(f),dtype=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]))
        rows['n']=nn;rows['v']=v[f]
        path.write_bytes(b'Blades of Chaos v6; mm; reference sculpt; FDM supports required'.ljust(80,b' ')+struct.pack('<I',len(f))+rows.tobytes())
    np.savez_compressed(path.with_suffix('.mesh.npz'),vertices=item['vertices'],faces=item['faces'],material=item['material'],top_count=item['top_count'],top_vertices=item['top_vertices'])


def fuse_round_grip(vertices, faces, material, sculpt, pitch):
    """Fuse a genuine radial helical wrap, including the narrow side faces."""
    import manifold3d as manifold
    count=max(144,int(np.ceil(2*pi*GRIP_HALF_HEIGHT/pitch)))
    axis=np.linspace(10.9,33.0,max(100,int(np.ceil(22.1*sculpt.scale/pitch))))
    theta=np.arange(count)*2*pi/count
    xx,aa=np.meshgrid(axis,theta,indexing='ij')
    phase=2*pi*((xx-10.8)*sculpt.scale/WRAP_PITCH)-aa
    seam=np.exp(-(np.sin(phase/2)/.24)**4)
    lip=np.exp(-(np.sin((phase-.62)/2)/.20)**4)
    radius_y=3.33+.20*np.sin(np.clip((xx-10)/23,0,1)*pi)
    end=.86+.14*smooth((xx-10.9)/1.25)*smooth((33-xx)/1.25)
    delta=-WRAP_GROOVE_DEPTH*seam+.22*lip
    braid=smooth((xx-10.9)/1.1)*smooth((17.5-xx)/2)
    delta+=.18*np.exp(-(np.sin(3*aa+(xx-11)*.95)/.30)**4)*braid
    delta+=.025*np.sin(phase*9+np.sin(aa*6))
    yy=(radius_y*sculpt.scale+delta)*end*np.sin(aa)
    zz=(GRIP_HALF_HEIGHT+delta)*end*np.cos(aa)
    gx=(xx-sculpt.origin[0])*sculpt.scale
    gy=yy-sculpt.origin[1]*sculpt.scale
    gv=np.c_[gx.ravel(),gy.ravel(),zz.ravel()]
    gm=np.full(xx.shape,3,np.int32);gm[seam>.24]=2;gm[lip>.60]=5
    gf=[]
    for i in range(len(axis)-1):
        for j in range(count):
            a=i*count+j;b=i*count+(j+1)%count;c=(i+1)*count+j;d=(i+1)*count+(j+1)%count
            gf.extend([(a,c,d),(a,d,b)])
    cap=len(gv)
    gv=np.vstack([gv,[gx[0,0],-sculpt.origin[1]*sculpt.scale,0],
                     [gx[-1,0],-sculpt.origin[1]*sculpt.scale,0]])
    for j in range(count):
        k=(j+1)%count
        gf.extend([(cap,j,k),(cap+1,(len(axis)-1)*count+k,(len(axis)-1)*count+j)])
    gf=np.asarray(gf,np.int32)
    gm=np.r_[gm.ravel(),3,3]
    a,b,c=gm[gf].T
    gmat=np.where((a==b)|(a==c),a,np.where(b==c,b,a))
    # Orient the capped radial mesh outwards.
    tri=gv[gf]
    if np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()<0:
        gf=gf[:,::-1].copy()
    validate(gv,gf,check_support=False)
    tag_map={}
    def solid(v,f,m):
        order=np.argsort(m,kind='stable');m=m[order];f=f[order]
        runs=np.r_[0,np.flatnonzero(np.diff(m))+1,len(m)]
        first=manifold.Manifold.reserve_ids(len(runs)-1)
        ids=np.arange(first,first+len(runs)-1,dtype=np.uint32)
        tag_map.update({int(tag):int(m[runs[i]]) for i,tag in enumerate(ids)})
        mesh=manifold.Mesh(np.asarray(v,np.float32,order='C'),
             np.asarray(f,np.uint32,order='C'),run_index=np.asarray(runs*3,np.uint32),
             run_original_id=ids)
        obj=manifold.Manifold(mesh)
        require(obj.status()==manifold.Error.NoError,'Mesh boolean input rejected.')
        return obj
    fused=solid(vertices,faces,material)+solid(gv,gf,gmat)
    require(fused.status()==manifold.Error.NoError,'Round grip fusion failed.')
    mesh=fused.to_mesh()
    vf=np.asarray(mesh.vert_properties)[:,:3].astype(float)
    ff=np.asarray(mesh.tri_verts,dtype=np.int32)
    mm=np.empty(len(ff),np.int32)
    for i,tag in enumerate(mesh.run_original_id):
        mm[mesh.run_index[i]//3:mesh.run_index[i+1]//3]=tag_map[int(tag)]
    return vf,ff,mm


def build_model(pitch):
    sculpt=Sculpt()
    sculpt.domain=orient(sculpt.domain.simplify(.001, preserve_topology=True),sign=1)
    print('Meshing planar domain with three true openings...',flush=True)
    xy,top=planar_mesh(sculpt.domain,pitch)
    print(f'Sculpting both faces at {len(xy):,} surface samples...',flush=True)
    front,front_mat=sculpt.sample(xy)
    back,back_mat=sculpt.sample(xy,back=True)
    n=len(xy)
    vertices=np.vstack([np.c_[xy,front],np.c_[xy,-back]])
    edges=edge_list(top)
    sides=np.array([t for a,b in edges for t in ((a,a+n,b+n),(a,b+n,b))],np.int32)
    faces=np.vstack([top,top[:,::-1]+n,sides])
    def face_material(values):
        a,b,c=values[top].T
        return np.where((a==b)|(a==c),a,np.where(b==c,b,a))
    material=np.r_[face_material(front_mat),face_material(back_mat),
                   np.repeat(front_mat[edges[:,0]],2)]
    # A complete mirrored height graph bounds a non-overlapping solid domain.
    require(np.all(front>=EDGE_HALF_THICKNESS) and np.all(back>=EDGE_HALF_THICKNESS),
            'Upper and lower surfaces must remain strictly separated.')
    print('Fusing the fully rounded helical grip...',flush=True)
    vertices,faces,material=fuse_round_grip(vertices,faces,material,sculpt,pitch)
    vertices[:,2]-=vertices[:,2].min()
    report,_=validate(vertices,faces,check_support=False)
    report.pop('support_check_passed')
    report.update({'one_connected_solid':True,'self_intersections_excluded_by_construction':True,
                   'blunt_blade_edge_thickness_mm':2*EDGE_HALF_THICKNESS,
                   'keyring_hole_diameter_mm':KEYRING_HOLE_DIAMETER,
                   'minimum_keyring_ligament_mm':sculpt.key_wall,
                   'true_through_openings':len(sculpt.domain.interiors),
                   'continuous_helical_grip':True,
                   'main_engraving_width_mm':ENGRAVING_WIDTH,
                   'main_engraving_depth_mm':ENGRAVING_DEPTH})
    # CadQuery verifies a simplified engineering envelope of the silhouette.
    outline=sculpt.domain.simplify(.045, preserve_topology=True)
    cad=cq.Workplane('XY').polyline(list(outline.exterior.coords)[:-1]).close()
    for ring in outline.interiors:
        cad=cad.polyline(list(ring.coords)[:-1]).close()
    envelope=cad.extrude(2*EDGE_HALF_THICKNESS).val()
    require(envelope.isValid() and len(envelope.Solids())==1,'Invalid CAD envelope.')
    report['cad_envelope_valid']=True
    return {'vertices':vertices,'faces':faces,'material':material,
            'top_count':len(faces)//2,'top_vertices':len(vertices),'report':report}


def orient_fdm(item):
    t,r=np.radians([FDM_TILT_DEG,FDM_ROLL_DEG])
    rx=np.array([[1,0,0],[0,np.cos(r),-np.sin(r)],[0,np.sin(r),np.cos(r)]])
    ry=np.array([[np.cos(t),0,-np.sin(t)],[0,1,0],[np.sin(t),0,np.cos(t)]])
    v=item['vertices']@(ry@rx).T
    v-=v.min(axis=0)
    out={**item,'vertices':v}
    report,normals=validate(v,item['faces'],check_support=False)
    report.pop('support_check_passed')
    tri=v[item['faces']]
    area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    needs=(normals[:,2]<-1/np.sqrt(2))&(tri[:,:,2].max(axis=1)>1e-5)
    report.update({'slicer_supports_required':True,
                   'downward_area_beyond_45_deg_mm2':float(area[needs].sum()),
                   'tilt_from_bed_deg':FDM_TILT_DEG,'roll_deg':FDM_ROLL_DEG})
    out['report']=report
    return out


def main():
    global LENGTH
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--length',type=float,default=LENGTH)
    parser.add_argument('--pitch',type=float,default=MESH_PITCH)
    args=parser.parse_args();LENGTH=args.length
    require(100<=LENGTH<=150,'Use 100-150 mm length for these miniature features.')
    require(.06<=args.pitch<=.30,'Use 0.06-0.30 mm mesh pitch.')
    print('Building v6 reference sculpt, all dimensions in mm...',flush=True)
    model=build_model(args.pitch)
    fdm=orient_fdm(model)
    for name,item in [('one_piece_model',model),('one_piece_FDM_oriented',fdm)]:
        save_mesh(Path(name+'.stl'),item)
        save_3mf(Path(name+'.3mf'),[item],[name+'; add slicer supports'])
    save_mesh(OUTPUT,fdm)
    save_3mf(OUTPUT.with_suffix('.3mf'),[fdm],[f'{LENGTH:g} mm reference-sculpted miniature; supports required'])
    result={'version':6,'reference':'reference.png supplied by user',
            'nominal_length_mm':LENGTH,'mesh_pitch_mm':args.pitch,
            'model':model['report'],'fdm_orientation':fdm['report'],
            'supports_or_gcode_included':False,'physical_print_tested':False,
            'chain':'Attach separate hardware through the pommel; chain not modeled.',
            'fine_surface_texture_may_not_resolve_with_0_4_mm_nozzle':True}
    Path('validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
