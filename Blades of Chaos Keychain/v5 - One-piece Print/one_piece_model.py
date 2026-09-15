#!/usr/bin/env python3
"""Blades of Chaos v5 — one-piece, fully sculpted 3D-print model.

Run: python one_piece_model.py
All dimensions are mm. No GUI, image generation or downloaded meshes are used.
Dependencies: cadquery==2.6.1, numpy, scipy, shapely>=2, triangle.
Both faces are analytic relief surfaces on a constrained planar triangulation.
The single closed solid is exported as STL and 3MF. Add supports in your slicer.
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
from shapely.affinity import affine_transform
from scipy.spatial import cKDTree

# --------------------- Customizable parameters: mm ---------------------
SINGLE_LENGTH = 110.0             # Finished blade length; all dimensions in mm.
FOUNDATION = 0.90                 # Half of the minimum 1.80 mm blunt edge thickness.
BLADE_RISE = 1.55                 # Blade crown rise on each side of the center plane.
BEVEL_WIDTH = 2.80                # Broad shoulder on each outer face.
GUARD_HEIGHT = 5.80               # Nominal half guard height, plus small ridges.
GRIP_HEIGHT = 4.10                # Half grip crown; finished grip about 8.2 mm.
POMMEL_HEIGHT = 2.50              # Half eyelet crown.
ORNAMENT_WIDTH = 0.52             # Main shallow inlay/groove width.
ORNAMENT_DEPTH = 0.28             # Fine decorative engraving depth.
FRACTURE_WIDTH = 0.58             # Main irregular weathering fissures.
FRACTURE_DEPTH = 0.32
WEAR_DEPTH = 0.06                 # Small physical pits and hammered relief.
FIT = 0.30                       # Per-side print clearance for the eyelet.
KEYRING_NOMINAL_D = 4.0
KEYRING_HOLE_D = KEYRING_NOMINAL_D + 2*FIT   # Actual opening = 4.6 mm.
KEYRING_WALL = 2.30               # Radial reinforcement, in physical mm.
MESH_PITCH = 0.12                 # High-detail surface sampling interval.
OUTPUT = Path('./output_model.stl')
CORNER_RADIUS = .30              # XY tip/spike rounding for handling/finishing.
MODEL_SCALE = 1.000               # Uniform scale; 1.000 retains nominal dimensions.
FDM_TILT_DEG = 65.0               # Long axis elevation above the bed.
FDM_ROLL_DEG = 12.0               # Slight roll changes the support contact pattern.
RESIN_TILT_DEG = 45.0             # Optional resin pose; still requires supports.
RESIN_ROLL_DEG = 20.0
DEFAULT_PRINT_ORIENTATION = 'fdm' # ./output_model.stl orientation.
# ----------------------------------------------------------------------


def require(value,message):
    if not value:raise ValueError(message)


def smooth(t):
    t=np.clip(t,0,1);return t*t*(3-2*t)


def path(start,segments):
    """Sample connected cubic Beziers at sub-print resolution."""
    points=[np.array(start,dtype=float)]
    for segment in segments:
        if len(segment)==2:
            end=np.array(segment);length=np.linalg.norm(end-points[-1])
            p=points[-1].copy()
            points.extend(p+(end-p)*u for u in np.linspace(0,1,max(2,int(length/.14)))[1:])
        else:
            a=points[-1].copy();b,c,d=np.array(segment).reshape(3,2)
            length=sum(np.linalg.norm(q-p) for p,q in zip((a,b,c),(b,c,d)))
            for u in np.linspace(0,1,max(3,int(length/.14)))[1:]:
                points.append((1-u)**3*a+3*(1-u)**2*u*b+3*(1-u)*u*u*c+u**3*d)
    return np.array(points)


def blade_polygon():
    # Profile based on the studio's Norse-era concept silhouette: long neck,
    # small back scallops, rising point and a broad swept belly near the tip.
    outline=path((31.5,3.8),[
        (42,4.0),(53,4.0),(59,4.7),
        (60,3.0,63,2.9,65,5.3),(65.5,6.8),
        (67,4.4,70,3.6,73,6.4),(73.8,8.0),
        (77,5.0,80,5.7,83,8.7),(83.5,10.3),
        (90,7.5,95,10.2,99.2,14.9),
        (99.7,15.6,100.2,15.3,100.0,14.4),
        (98.2,0.1,91.8,-11.8,78.7,-19.3),
        (78.1,-19.7,77.4,-19.6,77.7,-18.8),
        (79.2,-14.6,75.7,-11.8,71.8,-13.8),(70.7,-14.7),
        (71.0,-10.8,67.0,-9.0,63.3,-10.8),(62.5,-11.6),
        (61.3,-7.9,57.9,-7.5,54.8,-8.7),
        (44,-8.6),(35,-9.8),(31.5,3.8)])
    return Polygon(outline).buffer(.10,join_style='round').buffer(-.10,join_style='round')


def guard_polygon():
    return Polygon(path((27.5,-3),[
        (27,1,28,5,31.5,7.8),
        (34.5,10.0,38.0,9.8,42.0,8.1),
        (45.0,7.2,47.3,7.0,48.0,6.1),
        (44.1,5.6,42.0,4.4,40.1,2.4),
        (37.7,1.0,35.1,-1.0,33.6,-4.6),
        (31.8,-8.6,31.0,-12.5,34.2,-16.6),
        (34.6,-17.7,33.7,-18.2,32.6,-17.4),
        (27.8,-16.0,26.3,-12.3,27.2,-8.1),
        (28.0,-5.6,28.0,-4.8,27.5,-3)]))


def curve_distance(points,control,curved=False):
    """Vector distance to a polyline; used for continuous sculpted ridges."""
    if curved:
        from scipy.interpolate import CubicSpline
        knots=np.array(control,dtype=float)
        t=np.r_[0,np.cumsum(np.linalg.norm(np.diff(knots,axis=0),axis=1))]
        control=CubicSpline(t,knots,bc_type='natural')(np.linspace(0,t[-1],max(12,int(t[-1]/.5))))
    best=np.full(len(points),1e9)
    for a,b in zip(np.array(control[:-1]),np.array(control[1:])):
        d=b-a;t=np.clip(((points-a)@d)/max(d@d,1e-12),0,1)
        best=np.minimum(best,np.linalg.norm(points-(a+t[:,None]*d),axis=1))
    return best


def oval(points,center,axes,angle=0):
    x,y=(points-np.array(center)).T;a=np.radians(angle)
    xx=x*cos(a)+y*sin(a);yy=-x*sin(a)+y*cos(a)
    return (xx/axes[0])**2+(yy/axes[1])**2


class Sculpt:
    def __init__(self,scale):
        self.scale=scale
        self.blade=affine_transform(blade_polygon(),[scale,0,0,scale,0,0])
        self.guard=affine_transform(guard_polygon(),[scale,0,0,scale,0,0])
        self.grip=Polygon(np.array([(7,-3.35),(10,-3.5),(26,-3.15),(30,-3.8),
                                    (30,3.8),(26,3.15),(10,3.5),(7,3.35)])*scale)
        self.eye_center=np.array([KEYRING_HOLE_D/2+KEYRING_WALL,0.0])
        r=KEYRING_HOLE_D/2+KEYRING_WALL
        self.pommel=Point(*self.eye_center).buffer(r,quad_segs=96)
        self.hole=Point(*self.eye_center).buffer(KEYRING_HOLE_D/2,quad_segs=96)
        self.domain=orient(unary_union([self.blade,self.guard,self.grip,self.pommel])
                           .difference(self.hole),sign=1)
        require(self.domain.is_valid and self.domain.geom_type=='Polygon','Invalid connected profile.')

    def sample(self,p):
        h=np.full(len(p),-1.0);mat=np.zeros(len(p),np.int32)
        q=p/self.scale;x,y=q.T
        in_blade=shapely.contains_xy(self.blade,p[:,0],p[:,1])
        # Include boundary samples, whose exact height is still well-defined.
        in_blade |= shapely.distance(shapely.points(p),self.blade)<1e-7
        if np.any(in_blade):
            pts=p[in_blade];qq=q[in_blade];xx,yy=qq.T
            distance=shapely.distance(shapely.points(pts),self.blade.boundary)
            edge=smooth(distance/BEVEL_WIDTH)
            hh=FOUNDATION+BLADE_RISE*edge
            hh+=.22*np.exp(-((yy+1.2)/6.0)**2)*edge
            # Two restrained channels and intersecting curvilinear knot cuts.
            lines=[
                [(39,-.9),(48,-.6),(57,-1.1),(64,-.4),(72,-1.1),(80,.8),(88,4.4)],
                [(42,-4.8),(51,-4.3),(60,-5.3),(68,-5.0),(77,-6.0),(85,-1.9),(91,5.5)],
                [(45,-1),(48,1),(52,1.2),(55,-1),(58,-4.2),(62,-5.0),(66,-3.0),(68,-.4)],
                [(49,-4.5),(52,-6.4),(56,-6.0),(59,-3.3),(62,-.5),(66,.8),(70,.7),(73,-1)],
                [(71,-1),(75,1.4),(79,2),(82,.2),(84,-2.6),(87,-1.5)],
            ]
            for line in lines:
                dd=curve_distance(qq,line,curved=True)*self.scale
                hh-=ORNAMENT_DEPTH*np.exp(-(dd/(ORNAMENT_WIDTH*.56))**4)*edge
            # Small diamond hubs replace the oversize repeated X marks of v1.
            for cx,cy in [(57,-1.1),(72,-1.1),(80,.8)]:
                line=[(cx-1.0,cy),(cx,cy+1.0),(cx+1.0,cy),(cx,cy-1.0),(cx-1.0,cy)]
                dd=curve_distance(qq,line)*self.scale
                hh-=.26*np.exp(-(dd/.22)**4)*edge
            # Chased border and additional double-line loops are actual relief.
            rim=np.abs(distance-(BEVEL_WIDTH+.45))
            hh-=.16*np.exp(-(rim/.22)**4)*edge
            for line in [
                [(40,-2.6),(43,.4),(48,.7),(52,-2.6),(49,-5.2),(44,-5.5),(40,-2.6)],
                [(47,-2.5),(51,.5),(56,.8),(61,-2.5),(57,-5.6),(52,-5.2),(47,-2.5)],
                [(53,-2.7),(57,.2),(62,-.3),(66,-3.0),(62,-5.3),(57,-5.4),(53,-2.7)]]:
                dd=curve_distance(qq,line,curved=True)*self.scale
                hh+=.15*np.exp(-(dd/.28)**4)*edge
                hh-=.10*np.exp(-((dd-.48)/.17)**4)*edge
            # Fine transverse rune-like ticks along the two terminating rails.
            for cx,cy in [(74,-1.0),(77,-.5),(81,1.2),(85,3.0),(83,-3.2)]:
                for off in (-.55,.55):
                    dd=curve_distance(qq,[(cx+off,cy-.65),(cx+off,cy+.65)])*self.scale
                    hh-=.20*np.exp(-(dd/.20)**4)*edge
            fissures=[[(39,2.0),(44,1.4),(46,2.2),(51,1.7)],
                      [(60,3.2),(61,.8),(59.8,-.3),(61.2,-1.8),(60.6,-3.0)],
                      [(68,-8),(70,-6.5),(69.4,-4.5),(71,-3.5)],
                      [(79,6),(80.4,3.5),(79.5,1.8),(81,-.3),(80.6,-3.0)],
                      [(87,-6),(85,-4.5),(86,-2.3),(84.8,-1.5)],
                      [(94,8),(92,7.1),(92.3,5.5),(90.5,4.2)]]
            for line in fissures:
                dd=curve_distance(qq,line)*self.scale
                hh-=FRACTURE_DEPTH*np.exp(-(dd/(FRACTURE_WIDTH*.48))**2)*edge
            # Real mesh displacement: restrained forging and wear, not a texture.
            hh+=WEAR_DEPTH*.38*(np.sin(xx*1.9+yy*.8)*np.sin(yy*2.7-xx*.6))*edge
            rng=np.random.default_rng(19)
            for px,py,rad in zip(rng.uniform(40,95,32),rng.uniform(-13,9,32),rng.uniform(.25,.75,32)):
                rr=((xx-px)**2+(yy-py)**2)/(rad*rad)
                hh-=WEAR_DEPTH*np.exp(-rr*1.7)*edge
            h[in_blade]=np.maximum(FOUNDATION,hh);mat[in_blade]=1

        inside=shapely.distance(shapely.points(p),self.grip)<1e-7
        if np.any(inside):
            xx,yy=q[inside].T
            dome=np.sqrt(np.clip(1-(yy/3.65)**2,0,1))
            end=np.minimum(smooth((xx-7)/2.5),smooth((30.5-xx)/2.6))
            hh=FOUNDATION+(GRIP_HEIGHT-FOUNDATION)*dome*end
            seams=np.sin(pi*(xx+.73*yy)/3.15)
            hh-=.48*np.exp(-(seams/.20)**2)*dome*end
            hh+=.03*np.sin(xx*5.8+yy*3.2)*dome*end
            # A subtly raised second binding crosses the leather at the neck.
            rr=curve_distance(q[inside],[(22,-3),(24,-1),(25,2),(27,3)])*self.scale
            hh+=.34*np.exp(-(rr/.55)**4)*end
            for cx in (12.5,15.65,18.8,21.95):
                for cy in (-1.65,1.65):
                    knot=oval(q[inside],(cx-.73*cy,cy),(.43,.20),48)
                    hh+=.15*np.exp(-knot**2)*dome*end
            # End ferrules and small embossed fastening studs.
            collar=(np.exp(-((xx-9.7)/.60)**4)+np.exp(-((xx-26.6)/.60)**4))*dome*end
            hh+=.36*collar
            idx=np.where(inside)[0];win=hh>h[idx];h[idx[win]]=hh[win];mat[idx[win]]=2
            metallic=win&(collar>.12);mat[idx[metallic]]=3

        inside=shapely.distance(shapely.points(p),self.guard)<1e-7
        if np.any(inside):
            qq=q[inside];xx,yy=qq.T
            dist=shapely.distance(shapely.points(p[inside]),self.guard.boundary)
            taper=smooth(dist/(1.05*self.scale))
            hh=FOUNDATION+(GUARD_HEIGHT-FOUNDATION-1.9)*taper
            # The skull is in profile, with an elongated brow and swept cheek.
            ridges=[([(28.8,-13.8),(28.5,-8),(29.3,-2),(30.7,3),(34,6.1),(40.5,7.4),(45,6.5)],1.3,1.6),
                    ([(30,0),(32,3.2),(35,4.7),(39.8,4.6),(43,5.8)],.85,1.2),
                    ([(30.5,-6),(33,-2),(37,1.5),(40,2.8)],.7,.65),
                    ([(29,-11),(30.8,-14.6),(33,-16.4)],.85,.55)]
            for line,width,amount in ridges:
                dd=curve_distance(qq,line)
                hh+=.68*amount*np.exp(-(dd/width)**2)*taper
            # Recessed, asymmetric orbital cavity with a modeled raised rim.
            eye=oval(qq,(34.1,2.0),(2.75,1.40),34)
            hh-=2.5*np.exp(-(eye/.82)**2)*taper
            hh+=.48*np.exp(-((eye-1.3)/.5)**2)*taper
            nose=oval(qq,(39.8,5.7),(1.5,.63),13)
            hh-=1.1*np.exp(-(nose/.8)**2)*taper
            cheek=oval(qq,(31.2,-5.5),(1.0,2.8),-15)
            hh-=1.2*np.exp(-(cheek/.95)**2)*taper
            # Carved flutes give the skull bony layers instead of a face badge.
            grooves=[[(32,7.2),(33.5,5.6),(36.6,5.5),(41,7.2)],
                     [(35,8.2),(36.7,6.6),(41.1,6.5),(45.0,6.2)],
                     [(29.8,5.3),(28.4,2.3),(29.2,-1.6),(28.2,-5.0)],
                     [(33.2,-1.0),(31.9,-3.8),(32.0,-7.2),(30.0,-10.5)],
                     [(29,-10.5),(30,-13),(32,-15.5)]]
            for line in grooves:
                dd=curve_distance(qq,line)*self.scale
                hh-=.53*np.exp(-(dd/.25)**2)*taper
            for k in range(7):
                dd=curve_distance(qq,[(31+k*1.4,6.1),(32+k*1.4,7.3)])*self.scale
                hh-=.20*np.exp(-(dd/.19)**2)*taper
            # Swept cheek/brow plates, each with a raised ridge and chased edge.
            plates=[[(29.0,-10.4),(29.1,-6.0),(31.0,-2.7),(35.7,.6),(39.0,3.1)],
                    [(29.5,-8.2),(30.3,-4.3),(32.5,-1.6),(36.8,1.1),(40.5,3.8)],
                    [(29.6,2.5),(30.4,5.8),(34.5,8.1),(39.2,8.0),(44.0,6.4)],
                    [(31.3,4.7),(34.6,6.3),(39.0,6.1),(43.1,6.0)]]
            for line in plates:
                dd=curve_distance(qq,line,curved=True)*self.scale
                hh+=.28*np.exp(-(dd/.38)**2)*taper
                hh-=.15*np.exp(-((dd-.57)/.19)**4)*taper
            # Small rivets and irregular bone cracks distinguish the planes.
            for cx,cy in [(29.6,0.3),(31.0,6.3),(36.7,7.9)]:
                rr=((xx-cx)*self.scale)**2+((yy-cy)*self.scale)**2
                hh+=.23*np.exp(-(rr/.18)**2)*taper
            for line in [[(30,-12),(29.4,-11.4),(30.1,-10.7)],
                         [(35.3,8.6),(35.6,7.3),(34.8,6.8)],
                         [(40.5,7.7),(40,6.9),(40.7,6.4)]]:
                dd=curve_distance(qq,line)*self.scale
                hh-=.18*np.exp(-(dd/.20)**2)*taper
            hh+=.04*np.sin(xx*4.2+yy*2.3)*np.sin(yy*3.4)*taper
            idx=np.where(inside)[0];win=hh>h[idx];h[idx[win]]=hh[win];mat[idx[win]]=3

        inside=shapely.distance(shapely.points(p),self.pommel)<1e-7
        if np.any(inside):
            pp=p[inside]-self.eye_center
            rad=np.linalg.norm(pp,axis=1);angle=np.arctan2(pp[:,1],pp[:,0])
            outer=KEYRING_HOLE_D/2+KEYRING_WALL
            crown=smooth((outer-rad)/.7)*smooth((rad-KEYRING_HOLE_D/2)/.45)
            section=np.sin(pi*np.clip((rad-KEYRING_HOLE_D/2)/KEYRING_WALL,0,1))**.70
            hh=FOUNDATION+(POMMEL_HEIGHT-FOUNDATION)*section+.10*(np.cos(angle*3+rad*1.4)**2)*crown
            hh-=.25*np.exp(-(np.sin(angle*3+.6)/.17)**2)*crown
            idx=np.where(inside)[0];win=hh>h[idx];h[idx[win]]=hh[win];mat[idx[win]]=3
        # The eyelet is an actual through opening, removed in the planar domain.
        return np.maximum(h,FOUNDATION),mat


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
    chunks=['<?xml version="1.0" encoding="UTF-8"?>','<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">','<metadata name="Title">Blades of Chaos v5 - one-piece FDM</metadata><resources>']
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
        path.write_bytes(b'Blades of Chaos v5; mm; one-piece FDM; add slicer supports'.ljust(80,b' ')+struct.pack('<I',len(f))+rows.tobytes())
    np.savez_compressed(path.with_suffix('.mesh.npz'),vertices=item['vertices'],faces=item['faces'],material=item['material'],top_count=item['top_count'],top_vertices=item['top_vertices'])


def one_piece_mesh(pitch):
    factor=SINGLE_LENGTH/blade_polygon().bounds[2]
    for _ in range(5):
        s=Sculpt(factor)
        s.blade=s.blade.buffer(-CORNER_RADIUS).buffer(CORNER_RADIUS)
        s.guard=s.guard.buffer(-CORNER_RADIUS).buffer(CORNER_RADIUS)
        s.domain=orient(unary_union([s.blade,s.guard,s.grip,s.pommel]).difference(s.hole),sign=1)
        factor*=SINGLE_LENGTH/s.domain.bounds[2]
    xy,top=planar_mesh(s.domain,pitch);h,mat=s.sample(xy);n=len(xy)
    vertices=np.vstack([np.c_[xy,h],np.c_[xy,-h]])
    faces=[top,top[:,::-1]+n];side=[];edges=edge_list(top)
    for a,b in edges:side.extend([(a,a+n,b+n),(a,b+n,b)])
    faces.append(np.array(side,np.int32));faces=np.vstack(faces)
    mats=np.r_[np.rint(mat[top].mean(axis=1)).astype(int),np.rint(mat[top].mean(axis=1)).astype(int),np.repeat(mat[edges[:,0]],2)]
    vertices[:,1]-=vertices[:,1].min();vertices[:,2]-=vertices[:,2].min()
    vertices*=MODEL_SCALE
    report,_=validate(vertices,faces,check_support=False)
    report['slicer_supports_required']=not report.pop('support_check_passed')
    return {'vertices':vertices,'faces':faces,'material':mats,'top_count':len(top),'top_vertices':n,'report':report},s


def oriented(item,tilt,roll):
    t,r=np.radians([tilt,roll])
    rx=np.array([[1,0,0],[0,np.cos(r),-np.sin(r)],[0,np.sin(r),np.cos(r)]])
    ry=np.array([[np.cos(t),0,-np.sin(t)],[0,1,0],[np.sin(t),0,np.cos(t)]])
    v=item['vertices']@(ry@rx).T;v-=v.min(axis=0)
    out={**item,'vertices':v}
    check,normals=validate(v,item['faces'],check_support=False)
    tri=v[item['faces']];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    need=(normals[:,2]<-1/np.sqrt(2))&(tri[:,:,2].max(axis=1)>1e-5)
    check['downward_area_beyond_45_deg_mm2']=float(area[need].sum())
    check['supports_required']=True
    out['report']=check
    return out


def main():
    global SINGLE_LENGTH
    p=argparse.ArgumentParser();p.add_argument('--length',type=float,default=SINGLE_LENGTH);p.add_argument('--pitch',type=float,default=MESH_PITCH)
    p.add_argument('--orientation',choices=['fdm','resin'],default=DEFAULT_PRINT_ORIENTATION);args=p.parse_args();SINGLE_LENGTH=args.length
    require(95<=SINGLE_LENGTH<=130,'Use 95-130 mm length.')
    print('Generating fully sculpted one-piece blade...',flush=True)
    model,s=one_piece_mesh(args.pitch)
    fdm=oriented(model,FDM_TILT_DEG,FDM_ROLL_DEG);resin=oriented(model,RESIN_TILT_DEG,RESIN_ROLL_DEG)
    for name,item in [('one_piece_model',model),('one_piece_FDM_oriented',fdm),*([('one_piece_resin_oriented',resin)] if args.orientation=='resin' else [])]:
        save_mesh(Path(name+'.stl'),item);save_3mf(Path(name+'.3mf'),[item],[name+'; supports must be added in slicer'])
    selected=fdm if args.orientation=='fdm' else resin
    save_mesh(Path('output_model.stl'),selected);save_3mf(Path('output_model.3mf'),[selected],['One complete blade; add supports in slicer'])
    r={'version':5,'nominal_length_mm':SINGLE_LENGTH,'one_piece':True,'assembly_required':False,
       'model':model['report'],'fdm_orientation':fdm['report'],'resin_orientation':resin['report'],
       'fdm_tilt_deg':FDM_TILT_DEG,'fdm_roll_deg':FDM_ROLL_DEG,'resin_tilt_deg':RESIN_TILT_DEG,'resin_roll_deg':RESIN_ROLL_DEG,
       'default_output_orientation':args.orientation,'slicer_supports_included':False,'physical_print_tested':False}
    Path('one-piece-validation.json').write_text(json.dumps(r,indent=2))
    print(json.dumps(r,indent=2),flush=True)

if __name__=='__main__':main()
