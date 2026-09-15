#!/usr/bin/env python3
"""Blades of Chaos keychain v2 — sculpted, flat-backed miniature.

Run: python model.py
All dimensions are mm. No GUI, image generation or downloaded meshes are used.
Dependencies: cadquery==2.6.1, numpy, scipy, shapely>=2, triangle.
CadQuery checks the parametric planar CAD blank; the detailed upper surface is
an analytic relief meshed over a constrained planar triangulation. The complete
relief is exported as STL, OBJ and 3MF (not a simplified STEP substitute).
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
STYLE = 'single'                  # Main ./output_model.stl: single or crossed.
SINGLE_LENGTH = 90.0              # Overall X length before display rotation.
CROSSED_LONG_SIDE = 90.0          # Longest dimension of the crossed emblem.
FOUNDATION = 2.40                 # Continuous flat-backed foundation.
BLADE_RISE = 1.50                 # Broad crowned blade above the foundation.
BEVEL_WIDTH = 2.00                # Width of the rounded, unsharpened shoulder.
GUARD_HEIGHT = 8.10               # Maximum nominal skull / brow relief.
GRIP_HEIGHT = 6.20                # Rounded grip crown.
ORNAMENT_WIDTH = 0.52             # Fine shallow inlay/groove width.
ORNAMENT_DEPTH = 0.36             # Fine decorative engraving depth.
FRACTURE_WIDTH = 0.58             # Main irregular weathering fissures.
FRACTURE_DEPTH = 0.52
WEAR_DEPTH = 0.06                 # Small physical pits and hammered relief.
FIT = 0.30                       # Per-side print clearance for the eyelet.
KEYRING_NOMINAL_D = 4.0
KEYRING_HOLE_D = KEYRING_NOMINAL_D + 2*FIT   # Actual opening = 4.6 mm.
KEYRING_WALL = 2.30               # Radial reinforcement, in physical mm.
CROSSED_ANGLE = 33.0              # Each blade's angle from the vertical.
OVERLAP_RISE = 1.0                # Front blade elevation at the crossing.
MESH_PITCH = 0.16                 # Surface sample spacing; 0.12 for resin.
EXPORT_BOTH = True
OUTPUT = Path('./output_model.stl')
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
            idx=np.where(inside)[0];win=hh>h[idx];h[idx[win]]=hh[win];mat[idx[win]]=2

        inside=shapely.distance(shapely.points(p),self.guard)<1e-7
        if np.any(inside):
            qq=q[inside];xx,yy=qq.T
            dist=shapely.distance(shapely.points(p[inside]),self.guard.boundary)
            taper=smooth(dist/(1.05*self.scale))
            hh=FOUNDATION+(GUARD_HEIGHT-FOUNDATION-1.6)*taper
            # The skull is in profile, with an elongated brow and swept cheek.
            ridges=[([(28.8,-13.8),(28.5,-8),(29.3,-2),(30.7,3),(34,6.1),(40.5,7.4),(45,6.5)],1.3,1.6),
                    ([(30,0),(32,3.2),(35,4.7),(39.8,4.6),(43,5.8)],.85,1.2),
                    ([(30.5,-6),(33,-2),(37,1.5),(40,2.8)],.7,.65),
                    ([(29,-11),(30.8,-14.6),(33,-16.4)],.85,.55)]
            for line,width,amount in ridges:
                dd=curve_distance(qq,line)
                hh+=amount*np.exp(-(dd/width)**2)*taper
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
            hh+=.04*np.sin(xx*4.2+yy*2.3)*np.sin(yy*3.4)*taper
            idx=np.where(inside)[0];win=hh>h[idx];h[idx[win]]=hh[win];mat[idx[win]]=3

        inside=shapely.distance(shapely.points(p),self.pommel)<1e-7
        if np.any(inside):
            pp=p[inside]-self.eye_center
            rad=np.linalg.norm(pp,axis=1);angle=np.arctan2(pp[:,1],pp[:,0])
            outer=KEYRING_HOLE_D/2+KEYRING_WALL
            crown=smooth((outer-rad)/.7)*smooth((rad-KEYRING_HOLE_D/2)/.45)
            hh=FOUNDATION+1.7*crown+.25*(np.cos(angle*3+rad*1.4)**2)*crown
            hh-=.25*np.exp(-(np.sin(angle*3+.6)/.17)**2)*crown
            idx=np.where(inside)[0];win=hh>h[idx];h[idx[win]]=hh[win];mat[idx[win]]=3
        # The eyelet is an actual through opening, removed in the planar domain.
        return np.maximum(h,FOUNDATION),mat


class Variant:
    def __init__(self,style):
        self.style=style
        self.sculpt=Sculpt(SINGLE_LENGTH/blade_polygon().bounds[2])
        self.maps=[]
        if style=='single':
            self.maps=[(np.eye(2),np.zeros(2),0)]
        else:
            pivot=np.array([32*self.sculpt.scale,0])
            for side in (-1,1):
                angle=np.radians(90+side*CROSSED_ANGLE)
                rotation=np.array([[cos(angle),-sin(angle)],[sin(angle),cos(angle)]])
                mirror=np.diag([1,side])
                matrix=rotation@mirror
                self.maps.append((matrix,-matrix@pivot,OVERLAP_RISE if side==1 else 0))
            d=self.make_domain();bb=d.bounds
            factor=CROSSED_LONG_SIDE/max(bb[2]-bb[0],bb[3]-bb[1])
            # Scale the motif before adding the fixed physical-size eyelet.
            self.sculpt=Sculpt(self.sculpt.scale*factor)
            pivot=np.array([32*self.sculpt.scale,0])
            self.maps=[(a,-a@pivot,rise) for a,offset,rise in self.maps]
        domain=self.make_domain();bb=domain.bounds
        self.shift=np.array([-bb[0],-bb[1]])
        self.maps=[(a,b+self.shift,rise) for a,b,rise in self.maps]
        self.domain=self.make_domain()
        require(self.domain.is_valid and self.domain.geom_type=='Polygon','Disconnected variant.')

    def make_domain(self):
        shapes=[]
        for a,b,r in self.maps:
            shapes.append(affine_transform(self.sculpt.domain,[a[0,0],a[0,1],a[1,0],a[1,1],b[0],b[1]]))
        return orient(unary_union(shapes),sign=1)

    def sample(self,p):
        height=np.full(len(p),FOUNDATION);material=np.ones(len(p),np.int32)
        for a,b,rise in self.maps:
            local=(p-b)@a
            inside=shapely.distance(shapely.points(local),self.sculpt.domain)<1e-7
            if not np.any(inside):continue
            values,mats=self.sculpt.sample(local[inside]);values+=rise
            idx=np.where(inside)[0];win=values>=height[idx]
            height[idx[win]]=values[win];material[idx[win]]=mats[win]
        return height,material


def planar_mesh(domain,pitch):
    loops=[np.array(domain.exterior.coords)[:-1]]+[np.array(r.coords)[:-1] for r in domain.interiors]
    # Densify all straight spans so the sculpt does not bridge across fine detail.
    dense=[]
    for loop in loops:
        points=[]
        for a,b in zip(loop,np.roll(loop,-1,axis=0)):
            count=max(1,int(np.ceil(np.linalg.norm(b-a)/pitch)))
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


def build(style,pitch=MESH_PITCH):
    variant=Variant(style)
    xy,top=planar_mesh(variant.domain,pitch)
    z,materials=variant.sample(xy)
    n=len(xy);vertices=np.vstack([np.column_stack([xy,z]),np.column_stack([xy,np.zeros(n)])])
    edges=np.concatenate([top[:,[0,1]],top[:,[1,2]],top[:,[2,0]]])
    keys=np.sort(edges,axis=1);_,first,counts=np.unique(keys,axis=0,return_index=True,return_counts=True)
    require(np.all((counts==1)|(counts==2)),'Invalid planar mesh topology.')
    boundary=edges[first[counts==1]]
    side=[]
    for a,b in boundary:side.extend([(a,a+n,b+n),(a,b+n,b)])
    faces=np.vstack([top,top[:,::-1]+n,np.array(side,np.int32)])
    side_material=np.repeat(materials[boundary[:,0]],2)
    face_material=np.r_[np.rint(materials[top].mean(axis=1)).astype(np.int32),
                        np.ones(len(top),np.int32),side_material]
    return variant,vertices,faces,face_material,len(top)


def validate(vertices,faces):
    t=vertices[faces]
    normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);length=np.linalg.norm(normals,axis=1)
    require(np.all(np.isfinite(vertices)) and np.all(length>1e-10),'Invalid or collapsed triangles.')
    edges=np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]])
    _,counts=np.unique(np.sort(edges,axis=1),axis=0,return_counts=True)
    require(np.all(counts==2),'Non-manifold or open edge.')
    require(len(np.unique(edges,axis=0))==len(edges),'Inconsistent triangle winding.')
    signed=np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()/6
    require(signed>0,'Inverted volume.')
    # One shell: a graph walk over the indexed surface vertices.
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    graph=coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(len(vertices),len(vertices))).tocsr()
    shells=connected_components(graph,directed=False,return_labels=False)
    require(shells==1,'Disconnected shells.')
    unsupported=(normals[:,2]/length<-(1/np.sqrt(2)+1e-6))&(t[:,:,2].max(axis=1)>1e-5)
    require(not unsupported.any(),'Unsupported underside exceeds 45 degrees.')
    return signed,normals/length[:,None]


def save_3mf(path,vertices,faces):
    v=''.join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x,y,z in vertices)
    f=''.join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in faces)
    doc=('<?xml version="1.0" encoding="UTF-8"?>'
         '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
         '<metadata name="Title">Blades of Chaos keychain v2</metadata><resources><object id="1" type="model">'
         f'<mesh><vertices>{v}</vertices><triangles>{f}</triangles></mesh></object></resources>'
         '<build><item objectid="1"/></build></model>')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as out:
        out.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        out.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        out.writestr('3D/3dmodel.model',doc)


def export(style,out,pitch=MESH_PITCH):
    print(f'Building {style} relief...',flush=True)
    variant,vertices,faces,mats,top_count=build(style,pitch)
    # Recheck using float32 positions actually written into the STL.
    vf=vertices.astype(np.float32)
    volume,normals=validate(vf.astype(float),faces)
    records=np.zeros(len(faces),dtype=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')]))
    records['n']=normals;records['v']=vf[faces]
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(b'Blades of Chaos v2; mm; sculpted CAD relief'.ljust(80,b' ')+struct.pack('<I',len(faces))+records.tobytes())
    save_3mf(out.with_suffix('.3mf'),vertices,faces)
    with out.with_suffix('.obj').open('w') as f:
        f.write('# Blades of Chaos v2, units: mm\n')
        for x,y,z in vertices:f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
        for a,b,c in faces:f.write(f'f {a+1} {b+1} {c+1}\n')
    # Verify a CadQuery solid of the continuous foundation independently.
    domain=variant.domain
    wire=cq.Workplane('XY').polyline(list(domain.exterior.coords)[:-1]).close()
    for ring in domain.interiors:wire=wire.polyline(list(ring.coords)[:-1]).close()
    foundation=wire.extrude(FOUNDATION).val()
    require(foundation.isValid() and len(foundation.Solids())==1,'Invalid parametric CAD foundation.')
    np.savez_compressed(out.with_suffix('.mesh.npz'),vertices=vertices,faces=faces,
                        material=mats,top_count=top_count)
    size=vertices.max(axis=0)-vertices.min(axis=0)
    report={'style':style,'version':2,'dimensions_mm':size.tolist(),'triangles':len(faces),
            'vertices':len(vertices),'volume_cm3':volume/1000,'keyring_hole_mm':KEYRING_HOLE_D,
            'mesh_pitch_mm':pitch,'minimum_foundation_mm':FOUNDATION,
            'geometry_checks':['one connected shell','watertight edge manifold',
              'consistent winding','finite nondegenerate STL facets','positive volume',
              'support-free underside','valid CadQuery foundation','exact planar-domain coverage'],
            'self_intersection_control':'Top is a single-valued positive height graph over a constrained, non-overlapping planar triangulation; bottom is Z=0; boundary walls are vertical.',
            'export_units':'millimeter','physical_print_tested':False}
    out.with_suffix('.validation.json').write_text(json.dumps(report,indent=2))
    print(f'{style}: {np.round(size,2)} mm; {len(faces):,} triangles; watertight, one shell.',flush=True)
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--style',choices=['single','crossed'])
    parser.add_argument('--pitch',type=float,default=MESH_PITCH);args=parser.parse_args()
    require(75<=SINGLE_LENGTH<=120,'SINGLE_LENGTH must be 75–120 mm.')
    require(75<=CROSSED_LONG_SIDE<=120,'CROSSED_LONG_SIDE must be 75–120 mm.')
    require(.10<=args.pitch<=.35,'Use mesh pitch 0.10–0.35 mm.')
    require(FOUNDATION>=2.2 and KEYRING_WALL>=2.2,'Foundation/eyelet wall too thin.')
    require(3.8<=KEYRING_HOLE_D<=5.5,'Unsupported keyring opening size.')
    require(STYLE in ('single','crossed'),'Invalid STYLE.')
    styles=[args.style] if args.style else (['single','crossed'] if EXPORT_BOTH else [STYLE])
    reports=[]
    for style in styles:
        path=OUTPUT.with_name('single_blade.stl' if style=='single' else 'crossed_blades.stl')
        reports.append(export(style,path,args.pitch))
        if style==(args.style or STYLE):
            for suffix in ('.stl','.3mf','.obj','.mesh.npz','.validation.json'):
                OUTPUT.with_suffix(suffix).write_bytes(path.with_suffix(suffix).read_bytes())
    OUTPUT.with_name('validation.json').write_text(json.dumps(reports,indent=2))


if __name__=='__main__':main()
