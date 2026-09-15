#!/usr/bin/env python3
"""Venom: an original, all-sided fan-art display bust, built without a GUI.
CadQuery constructs the pedestal; a continuous implicit surface sculpts the
anatomy; Manifold fuses curved fangs, eye/emblem relief and the tongue.
Run: python model.py [--draft] [--height 180] [--pitch 0.28]
Exports ./output_model.stl and .3mf, plus a colored preview mesh and reports.
FDM supports are REQUIRED beneath the jaw, fangs, tongue and free tendrils.
"""
# ---------------- Exposed dimensions: millimeters ----------------
HEIGHT_MM=180.0                  # Uniform overall size; default desktop bust.
FINAL_PITCH_MM=0.28              # Implicit sculpt sampling; lower = more detail/RAM.
DRAFT_PITCH_MM=0.70              # Fast composition preview, not final delivery.
BASE_WIDTH_MM=128.0             # Canonical dimensions at the 180 mm design scale.
BASE_DEPTH_MM=82.0
BASE_HEIGHT_MM=9.0
EYE_RELIEF_MM=1.00
EMBLEM_RELIEF_MM=0.85
SKIN_TEXTURE_DEPTH_MM=0.085
VEIN_RELIEF_RADIUS_MM=0.68
FANG_TIP_RADIUS_MM=0.48          # Rounded fine tips, not mathematically sharp points.
UPPER_FANG_COUNT=20
LOWER_FANG_COUNT=18
INNER_FANG_COUNT=12
TONGUE_HALF_WIDTH_MM=5.3
TONGUE_HALF_THICKNESS_MM=2.0
RANDOM_SEED=37
OUTPUT='output_model.stl'
# Anatomy control points below are millimeters in a canonical 180 mm frame.
# HEIGHT_MM scales the whole sculpt after fusion; no separately assembled parts.
# -----------------------------------------------------------------
from pathlib import Path
import argparse,json,math,zipfile,gc,hashlib
import numpy as np
import cadquery as cq
import trimesh,manifold3d as md,triangle
from scipy.interpolate import CubicSpline
from scipy.ndimage import map_coordinates,gaussian_filter
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
from shapely.geometry import Polygon,Point,LineString
from shapely.affinity import scale as scale2
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parent
COLORS=np.array([[36,45,55],[226,230,223],[222,206,167],[96,35,42],
                 [155,45,65],[50,59,68],[211,218,212],[48,63,72]],np.uint8)

def require(ok,message):
    if not ok:raise ValueError(message)

def smoothmin(a,b,k):
    if k<=0:return np.minimum(a,b)
    h=np.maximum(k-np.abs(a-b),0)/k
    return np.minimum(a,b)-h*h*k*.25

def curve(points,step=.65):
    points=np.asarray(points,float)
    t=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
    require(np.all(np.diff(t)>0),'Repeated curve control point.')
    return CubicSpline(t,points,axis=0,bc_type='natural')(np.linspace(0,t[-1],max(8,int(t[-1]/step)+1)))

class Field:
    def __init__(self,pitch):
        self.pitch=pitch;self.lo=np.array([-84.,-62.,4.])
        self.axes=[np.arange(a,b+pitch,pitch,dtype=np.float32) for a,b in zip(self.lo,[84,42,184])]
        self.f=np.full(tuple(map(len,self.axes)),1000,np.float32)
        print('Sculpt grid:',self.f.shape,f'{self.f.nbytes/1e6:.0f} MB',flush=True)
    def region(self,lo,hi):
        a=np.maximum(np.floor((np.asarray(lo)-self.lo)/self.pitch).astype(int),0)
        b=np.minimum(np.ceil((np.asarray(hi)-self.lo)/self.pitch).astype(int)+1,self.f.shape)
        if np.any(b<=a):return None
        sl=tuple(slice(int(x),int(y)) for x,y in zip(a,b))
        x=self.axes[0][sl[0]][:,None,None];y=self.axes[1][sl[1]][None,:,None];z=self.axes[2][sl[2]][None,None,:]
        return sl,x,y,z
    def ellipsoid(self,c,r,blend=2.8,rotation=None,cut=False):
        c=np.array(c);r=np.array(r);rot=np.eye(3) if rotation is None else np.asarray(rotation)
        extent=np.abs(rot)@r+blend+1.5
        reg=self.region(c-extent,c+extent)
        if reg is None:return
        sl,x,y,z=reg;x=x-c[0];y=y-c[1];z=z-c[2]
        q=[(x*rot[0,i]+y*rot[1,i]+z*rot[2,i])/r[i] for i in range(3)]
        d=(np.sqrt(q[0]**2+q[1]**2+q[2]**2)-1)*min(r)
        if cut:self.f[sl]=np.maximum(self.f[sl],-d)
        else:self.f[sl]=smoothmin(self.f[sl],d,blend)
    def muscle(self,a,b,r1,r2,blend=3):
        a=np.array(a,float);b=np.array(b,float);v=b-a;length=np.linalg.norm(v);v/=length
        u=np.cross(v,[0,1,0]);u/=np.linalg.norm(u);w=np.cross(v,u)
        self.ellipsoid((a+b)/2,[r1,r2,length*.5],blend,np.stack([u,w,v],axis=1))
    def tube(self,points,radii,blend=.5,cut=False):
        p=np.asarray(points);r=np.broadcast_to(radii,(len(p),))
        for a,b,ra,rb in zip(p,p[1:],r,r[1:]):
            extent=max(ra,rb)+blend+1;reg=self.region(np.minimum(a,b)-extent,np.maximum(a,b)+extent)
            if reg is None:continue
            sl,x,y,z=reg;v=b-a;l2=np.dot(v,v)
            t=np.clip(((x-a[0])*v[0]+(y-a[1])*v[1]+(z-a[2])*v[2])/l2,0,1)
            d=np.sqrt((x-a[0]-t*v[0])**2+(y-a[1]-t*v[1])**2+(z-a[2]-t*v[2])**2)-(ra+(rb-ra)*t)
            if cut:self.f[sl]=np.maximum(self.f[sl],-d)
            else:self.f[sl]=smoothmin(self.f[sl],d,blend)
    def surface(self,x,z,back=False):
        x,z=np.broadcast_arrays(x,z);shape=x.shape;x=x.ravel();z=z.ravel()
        ix=(x-self.lo[0])/self.pitch;iz=(z-self.lo[2])/self.pitch
        iy=np.arange(len(self.axes[1]),dtype=float)
        samples=map_coordinates(self.f,[np.repeat(ix,len(iy)),np.tile(iy,len(ix)),np.repeat(iz,len(iy))],order=1,mode='constant',cval=1000).reshape(len(x),-1)
        inside=samples<0;require(np.all(inside.any(axis=1)),'Surface projection leaves the sculpt: '+str(np.c_[x,z][~inside.any(axis=1)][:4]))
        j=(len(iy)-1-np.argmax(inside[:,::-1],axis=1)) if back else np.argmax(inside,axis=1)
        k=j+1 if back else j-1;rows=np.arange(len(x));a=samples[rows,j];b=samples[rows,k]
        y=self.axes[1][j]+(self.axes[1][k]-self.axes[1][j])*(-a)/(b-a)
        return y.reshape(shape)
    def skin(self):
        # Seeded volumetric microtexture, with no repetitive image or UV pattern.
        noise_pitch=.78
        shape=tuple(int(np.ceil((axis[-1]-axis[0])/noise_pitch))+5 for axis in self.axes)
        noise=np.random.default_rng(RANDOM_SEED).standard_normal(shape,dtype=np.float32)
        noise=gaussian_filter(noise,.65);noise/=max(float(noise.std()),1e-6)
        for i in range(0,len(self.axes[0]),8):
            x=self.axes[0][i:i+8,None,None];y=self.axes[1][None,:,None];z=self.axes[2][None,None,:]
            slab=self.f[i:i+8];mask=np.abs(slab)<.55
            ix,iy,iz=np.broadcast_arrays((x-self.lo[0])/noise_pitch+2,(y-self.lo[1])/noise_pitch+2,(z-self.lo[2])/noise_pitch+2)
            q=map_coordinates(noise,[ix,iy,iz],order=1,prefilter=False)
            amplitude=np.clip((z-12)/25,0,1)*SKIN_TEXTURE_DEPTH_MM
            slab[mask]+=(np.tanh(q)*amplitude)[mask]
    def mesh(self):
        v,f,_,_=marching_cubes(self.f,0,spacing=(self.pitch,)*3,gradient_direction='ascent',allow_degenerate=False)
        m=trimesh.Trimesh(v+self.lo,f,process=True);m.fix_normals()
        require(m.is_watertight and m.is_volume,'Implicit anatomy mesh is not a closed solid.')
        return m

def upper(u):return np.c_[26*u,-22-8*(1-u*u),133+13*(1-u*u)]
def lower(u):return np.c_[25.5*u,-21-9*(1-u*u),133-23*(1-u*u)]

def build_anatomy(pitch):
    f=Field(pitch)
    # Pectoral, deltoid, trapezius, neck, scapular and abdominal masses blend.
    for c,r,k in [((0,3,44),(36,20,37),4),((0,5,67),(45,22,33),5),
                  ((0,7,101),(19,18,29),4),((0,1,143),(30,23,33),3),
                  ((0,3,154),(32,23,25),3),((0,-14,148),(26,17,13),3),
                  ((0,-13,112),(25,18,10),2.5)]:f.ellipsoid(c,r,k)
    for side in (-1,1):
        for c,r,k in [((side*43,2,77),(22,23,25),4),((side*23,-10,70),(25,20,20),3),
                      ((side*20,16,76),(23,14,25),3),((side*25,-2,131),(10.5,17,20),2.5),
                      ((side*25,-7,144),(11,17,13),2.5),((side*17,-5,40),(17,19,18),3)]:f.ellipsoid(c,r,k)
        f.muscle((side*44,7,89),(side*10,5,119),12,13,4)
        f.muscle((side*15,-5,93),(side*16,-8,126),5.6,8.0,3)
        f.muscle((side*6,20,96),(side*18,19,128),7,8,3)
        for z in (33,45,56):f.ellipsoid((side*9,-13,z),(9.5,10,8.5),2.2)
    # Deep blind maw. The rear throat wall remains thick, connecting the whole head.
    f.ellipsoid((0,-30,128),(27.5,30,17),0,cut=True)
    ug=upper(np.linspace(-1,1,130));lg=lower(np.linspace(-1,1,130))
    f.tube(ug,3.3,1.1);f.tube(lg,3.5,1.2)
    # Cheek ridges flow from grin corners into temples.
    for side in (-1,1):
        f.tube(curve([(side*25,-22,132),(side*30,-13,138),(side*30,-9,148),(side*25,-10,158)]),[2.5]*len(curve([(side*25,-22,132),(side*30,-13,138),(side*30,-9,148),(side*25,-10,158)])),.9)
    print('Anatomy and open jaw formed.',flush=True)
    # Veins project onto the actual muscle surface; both front and reverse are detailed.
    paths=[]
    for side in (-1,1):
        for j in range(4):
            paths.append(([(side*(16+j*5),40+j*4),(side*(29+j*5),53+j*3),(side*(38+j*4),69+j*3),(side*(37+j*3),84+j*2)],False))
        for j in range(5):
            paths.append(([(side*(7+j*7),37),(side*(14+j*6),56),(side*(20+j*5),76),(side*(12+j*5),96)],True))
        for j in range(3):
            paths.append(([(side*(6+j*4),91),(side*(10+j*3),105),(side*(8+j*5),122),(side*(11+j*4),145),(side*(6+j*4),166)],True))
        paths += [([(side*7,168),(side*15,173),(side*22,167),(side*27,158)],False)]
    for index,(xz,back) in enumerate(paths):
        p=curve(xz,.9);y=f.surface(p[:,0],p[:,1],back)
        pts=np.c_[p[:,0],y+(-.10 if back else .10),p[:,1]]
        radii=VEIN_RELIEF_RADIUS_MM*(.35+.65*np.sin(np.linspace(.05,math.pi-.05,len(p)))**.55)
        f.tube(pts,radii,.23)
        # A smaller branching vein leaves each long trunk.
        if index%3==0 and index<20:
            k=len(p)//2;end=p[min(len(p)-1,k+len(p)//4)].copy();end[0]+=(-1 if p[k,0]<0 else 1)*4
            branch=np.linspace(p[k],end,14)
            try:
                yy=f.surface(branch[:,0],branch[:,1],back);f.tube(np.c_[branch[:,0],yy,branch[:,1]],np.linspace(.55,.18,14),.18)
            except ValueError:pass
    # Embedded neck cords and four sweeping external symbiote tendrils.
    tendrils=[[(53,4,80),(69,1,95),(75,5,113),(66,10,126),(57,6,121)],
              [(-51,5,79),(-70,8,86),(-77,13,104),(-66,17,113),(-59,12,105)],
              [(27,20,75),(43,26,93),(46,24,112),(38,20,123)],
              [(-26,22,65),(-45,28,79),(-50,29,95),(-40,26,105)]]
    for i,path in enumerate(tendrils):
        p=curve(path,.55);r=np.linspace(4.0 if i<2 else 3.4,.7,len(p))**1.0;f.tube(p,r,.7)
        # Helical raised seam, attached along the cord surface.
        tangent=np.gradient(p,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None]
        a=np.cross(tangent,[0,1,0]);a/=np.maximum(np.linalg.norm(a,axis=1)[:,None],1e-8);b=np.cross(tangent,a)
        phase=np.linspace(0,7*math.pi,len(p));q=p+(a*np.cos(phase)[:,None]+b*np.sin(phase)[:,None])*(r*.87)[:,None]
        f.tube(q,np.linspace(.55,.18,len(p)),.18)
    f.skin();print('Veins, tendrils and fine skin relief formed.',flush=True)
    return f,ug,lg

def manifold(mesh,tag=0):
    require(mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0,'Component is not a valid closed mesh.')
    labels=np.broadcast_to(tag,(len(mesh.vertices),)).astype(int)
    props=np.c_[mesh.vertices,np.eye(8,dtype=float)[labels]]
    obj=md.Manifold(md.Mesh64(np.ascontiguousarray(props,np.float64),np.ascontiguousarray(mesh.faces,np.uint64)))
    require(obj.status()==md.Error.NoError,'Manifold rejected a component.')
    return obj

def tube_mesh(points,widths,depths=None,sides=24,flute=0,tongue=False):
    p=np.array(points,float);w=np.broadcast_to(widths,(len(p),));d=w if depths is None else np.broadcast_to(depths,(len(p),))
    tangent=np.gradient(p,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None]
    # Parallel transport keeps flattened tongue orientation continuous around the curl.
    a=np.cross(tangent[0],[0,1,0])
    if np.linalg.norm(a)<.01:a=np.cross(tangent[0],[1,0,0])
    a/=np.linalg.norm(a);frames=[]
    for t in tangent:
        a=a-t*np.dot(a,t);a/=np.linalg.norm(a);frames.append(a.copy())
    aa=np.array(frames);bb=np.cross(tangent,aa);theta=np.arange(sides)*2*np.pi/sides
    v=[]
    for i,(c,ax,bx) in enumerate(zip(p,aa,bb)):
        tt=i/(len(p)-1);rr=1+flute*np.cos(theta*7+tt*1.4)
        xx=w[i]*np.cos(theta)*rr;yy=d[i]*np.sin(theta)*rr
        if tongue:
            # Long median groove and small transverse folds are modeled in the surface.
            yy-=.36*np.exp(-(np.cos(theta)/.20)**2)*np.maximum(np.sin(theta),0)
            yy+=.12*np.sin(tt*2*np.pi*23+theta*.6)*np.sin(theta)**2
        v.extend(c+ax*xx[:,None]+bx*yy[:,None])
    v=np.array(v);faces=[]
    for i in range(len(p)-1):
        for j in range(sides):
            a0=i*sides+j;b0=i*sides+(j+1)%sides;c0=b0+sides;d0=a0+sides
            faces.extend([(a0,b0,c0),(a0,c0,d0)])
    v=np.vstack([v,p[0],p[-1]]);start=len(v)-2;end=len(v)-1
    for j in range(sides):faces.extend([(start,(j+1)%sides,j),(end,(len(p)-1)*sides+j,(len(p)-1)*sides+(j+1)%sides)])
    m=trimesh.Trimesh(v,faces,process=True);m.fix_normals();return m

def projected_relief(field,poly,relief,tag):
    require(poly.is_valid and poly.geom_type=='Polygon','Invalid eye/emblem outline.')
    rings=[np.asarray(poly.exterior.coords)[:-1]]+[np.asarray(r.coords)[:-1] for r in poly.interiors]
    verts=[];segments=[];holes=[]
    for i,ring in enumerate(rings):
        start=len(verts);verts.extend(ring);segments.extend((start+j,start+(j+1)%len(ring)) for j in range(len(ring)))
        if i:holes.append(np.asarray(Polygon(ring).representative_point().coords[0]))
    inputs={'vertices':np.array(verts),'segments':np.array(segments)}
    if holes:inputs['holes']=np.array(holes)
    data=triangle.triangulate(inputs,'pq26a.28');xz=data['vertices'];front=field.surface(xz[:,0],xz[:,1])
    # Closed shell embedded 2.8 mm into the true skin surface.
    n=len(xz);v=np.vstack([np.c_[xz[:,0],front-relief,xz[:,1]],np.c_[xz[:,0],front+2.8,xz[:,1]]])
    ff=data['triangles'];faces=np.vstack([ff,ff[:,::-1]+n]).tolist()
    for a,b in data['segments']:faces.extend([(a,b,b+n),(a,b+n,a+n)])
    m=trimesh.Trimesh(v,faces,process=True);m.fix_normals()
    return manifold(m,tag)

def add_details(field,body,ug,lg):
    # The dark red maw/gums are a preview finish on the same solid skin geometry.
    p=body.vertices;mouth=((p[:,0]/28)**2+((p[:,1]+30)/30)**2+((p[:,2]-128)/17)**2)
    lip_distance=np.minimum(cKDTree(ug).query(p)[0],cKDTree(lg).query(p)[0])
    tags=np.zeros(len(p));tags[((np.abs(mouth-1)<.10)&(p[:,1]<-5)&(p[:,2]>110)&(p[:,2]<147))|(lip_distance<3.7)]=3
    result=[manifold(body,tags)];del body
    eye=Polygon([(3.4, 151.5), (8, 157), (13, 160.5), (19, 164), (25, 166.5), (27.2, 166), (25.8, 162.3), (28.4, 163), (27, 157.5), (28, 158), (26, 153), (22.5, 149.2), (18, 147.5), (13, 148), (8, 150)])
    result.append(projected_relief(field,eye,EYE_RELIEF_MM,1))
    result.append(projected_relief(field,scale2(eye,xfact=-1,yfact=1,origin=(0,0)),EYE_RELIEF_MM,1))
    # A dimensional white spider emblem follows the pectoral surface.
    spider=[scale2(Point(0,72).buffer(1,32),4.1,7.2,origin=(0,72)),scale2(Point(0,59).buffer(1,32),5.3,8.5,origin=(0,59))]
    legs=[[(2,77),(14,84),(27,83),(38,89)],[(3,71),(17,77),(31,73),(42,79)],
          [(3,65),(18,67),(31,61),(40,64)],[(3,59),(16,55),(23,44),(33,40)]]
    for sign in (-1,1):
        for path in legs:
            p=curve([(sign*x,z) for x,z in path],.45);spider.append(LineString(p).buffer(1.35,quad_segs=6))
    emblem=unary_union(spider).buffer(.25).buffer(-.25)
    result.append(projected_relief(field,emblem,EMBLEM_RELIEF_MM,6))
    # Curved, fluted fangs: alternating lengths and staggered inner teeth.
    count=0
    for row,total in [('upper',UPPER_FANG_COUNT),('lower',LOWER_FANG_COUNT),('inner',INNER_FANG_COUNT)]:
        for i,u in enumerate(np.linspace(-.92,.92,total)):
            pos=(upper(np.array([u])) if row!='lower' else lower(np.array([u])))[0]
            if row=='inner':pos=pos+[0,3.4,1.5]
            direction=-1 if row!='lower' else 1
            length=(8.4+3.2*(1-abs(u))+(1.0 if i%2 else -.6))*(.68 if row=='inner' else 1)
            root=pos+[0,.25,-direction*.4]
            end=pos+[.7*np.sin(i*2.3),-2.8,direction*length]
            middle=(root+end)/2+[0,-1.0,0]
            path=curve([root,middle,end],.35)
            widths=(1-np.linspace(0,1,len(path)))**.85*((1.60 if row=='inner' else 1.95)-FANG_TIP_RADIUS_MM)+FANG_TIP_RADIUS_MM
            result.append(manifold(tube_mesh(path,widths,sides=28,flute=.055),2));count+=1
    tongue_path=curve([(0,-15,117),(0,-29,116),(3,-43,111),(14,-50,105),(29,-46,108),(37,-38,120),(33,-34,130)],.36)
    tt=np.linspace(0,1,len(tongue_path));w=TONGUE_HALF_WIDTH_MM*(1-.78*tt**1.45)
    d=TONGUE_HALF_THICKNESS_MM*(1-.58*tt)
    result.append(manifold(tube_mesh(tongue_path,w,d,sides=48,tongue=True),4))
    # Two saliva/symbiote filaments span the open grin; 1.5 mm minimum diameter.
    for path in [[(-18,-27,141),(-18.5,-31,132),(-17,-31,121)],[(19,-28,140),(20,-31,132),(20,-30,121)]]:
        p=curve(path,.5);result.append(manifold(tube_mesh(p,np.linspace(.95,.80,len(p)),sides=16),3))
    print(f'Added projected eyes/emblem, {count} individual fangs, grooved tongue and mouth filaments.',flush=True)
    return result,count

def pedestal():
    # Engineering foundation remains explicit CadQuery geometry.
    base=cq.Workplane('XY').ellipse(BASE_WIDTH_MM/2,BASE_DEPTH_MM/2).extrude(BASE_HEIGHT_MM)
    base=base.edges('>Z').chamfer(1.8).edges('<Z').chamfer(1.0)
    ring=cq.Workplane('XY',origin=(0,0,BASE_HEIGHT_MM-.5)).ellipse(BASE_WIDTH_MM/2-4,BASE_DEPTH_MM/2-4).extrude(1.8)
    base=base.union(ring)
    v,f=base.val().tessellate(.12,.10)
    m=trimesh.Trimesh([q.toTuple() for q in v],f,process=True);m.fix_normals()
    return manifold(m,5)

def save_3mf(mesh,path):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        with z.open('3D/3dmodel.model','w') as out:
            out.write(b'<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources><object id="1" type="model"><mesh><vertices>')
            for i in range(0,len(mesh.vertices),10000):out.write(''.join(f'<vertex x="{x:.8f}" y="{y:.8f}" z="{z:.8f}"/>' for x,y,z in mesh.vertices[i:i+10000]).encode())
            out.write(b'</vertices><triangles>')
            for i in range(0,len(mesh.faces),10000):out.write(''.join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in mesh.faces[i:i+10000]).encode())
            out.write(b'</triangles></mesh></object></resources><build><item objectid="1"/></build></model>')

def prepare_print_mesh(vertices,faces):
    """Weld only float32-scale seams; split collinear T-junctions explicitly.
    No large hole filling, surface remeshing or lost anatomical components.
    """
    raw=trimesh.Trimesh(np.asarray(vertices,np.float32),faces,process=False)
    for digits in (5,4,6,3):
        m=raw.copy();m.merge_vertices(digits_vertex=digits)
        m.update_faces(m.nondegenerate_faces(height=1e-10)&m.unique_faces());m.remove_unreferenced_vertices()
        repairs=0
        for attempt in range(30):
            if m.is_watertight:break
            edges,counts=np.unique(m.edges_sorted,axis=0,return_counts=True)
            if np.any(counts>2):break
            boundary=edges[counts==1];adj={}
            for a,b in boundary:adj.setdefault(int(a),set()).add(int(b));adj.setdefault(int(b),set()).add(int(a))
            start=next(iter(adj));group={start};todo=[start]
            while todo:
                for j in adj[todo.pop()]:
                    if j not in group:group.add(j);todo.append(j)
            if len(group)!=3:break
            local=np.array([e for e in boundary if int(e[0]) in group])
            lengths=np.linalg.norm(m.vertices[local[:,0]]-m.vertices[local[:,1]],axis=1)
            a,c=map(int,local[np.argmax(lengths)]);b=next(q for q in group if q not in (a,c))
            line=m.vertices[c]-m.vertices[a];length=np.linalg.norm(line)
            t=np.dot(m.vertices[b]-m.vertices[a],line)/(length*length)
            distance=np.linalg.norm(m.vertices[b]-(m.vertices[a]+t*line))
            if not (0<t<1 and distance<.0001):break
            match=np.flatnonzero(np.any(m.faces==a,axis=1)&np.any(m.faces==c,axis=1))
            if len(match)!=1:break
            index=int(match[0]);face=m.faces[index]
            for k in range(3):
                x,y,z=map(int,(face[k],face[(k+1)%3],face[(k+2)%3]))
                if {x,y}=={a,c}:break
            corrected=np.vstack([np.delete(m.faces,index,axis=0),[x,b,z],[b,y,z]])
            m=trimesh.Trimesh(m.vertices,corrected,process=False);repairs+=1
        if m.is_watertight and m.is_winding_consistent and m.is_volume and m.body_count==1:
            require(abs(m.volume-raw.volume)/raw.volume<1e-6,'Precision cleanup altered volume.')
            print(f'Print precision: {digits} decimal seam weld, {repairs} collinear seams split.',flush=True)
            return m,{'weld_decimal_places':digits,'collinear_seams_split':repairs,'volume_change_mm3':float(m.volume-raw.volume)}
    raise ValueError('Float32 print topology needs additional inspection; no final export approved.')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--draft',action='store_true');ap.add_argument('--height',type=float,default=HEIGHT_MM);ap.add_argument('--pitch',type=float);args=ap.parse_args()
    pitch=args.pitch or (DRAFT_PITCH_MM if args.draft else FINAL_PITCH_MM)
    require(150<=args.height<=220 and .18<=pitch<=.8,'Use height 150–220 mm and sampling 0.18–0.80 mm.')
    field,ug,lg=build_anatomy(pitch);body=field.mesh();print(f'Implicit anatomy: {len(body.faces):,} triangles.',flush=True)
    components,count=add_details(field,body,ug,lg);del field,body;gc.collect();components.append(pedestal())
    combined=md.Manifold.batch_boolean(components,md.OpType.Add)
    require(combined.status()==md.Error.NoError,'Boolean union failed.')
    pieces=combined.decompose()
    main_piece=max(pieces,key=lambda q:q.volume())
    dust=[q for q in pieces if q is not main_piece]
    require(all(abs(q.volume())<.5 for q in dust),'An anatomical detail is disconnected; fix its root.')
    # Remove sub-voxel grit and fill sealed sub-voxel bubbles, never whole details.
    discarded_volume=sum(abs(q.volume()) for q in dust)
    combined=main_piece.simplify(.012)
    print('Simplification:',combined.status(),'shells',len(combined.decompose()),flush=True)
    if combined.status()==md.Error.NoError:
        shell=combined.decompose();largest=max(shell,key=lambda q:q.volume())
        require(all(q is largest or abs(q.volume())<.5 for q in shell),'Simplification separated a detail.')
        combined=largest
    print('Sub-voxel shells cleaned:',len(dust),'volume mm3:',discarded_volume,flush=True)
    require(combined.status()==md.Error.NoError and len(combined.decompose())==1,'Final solid did not unify.')
    raw=combined.to_mesh64();props=raw.vert_properties;faces=np.asarray(raw.tri_verts,dtype=np.int64)
    v=props[:,:3].copy();v[:,2]-=v[:,2].min();factor=args.height/np.ptp(v[:,2]);v*=factor
    material=np.argmax(np.mean(props[faces,3:11],axis=1),axis=1).astype(np.uint8)
    cache='draft_preview.mesh.npz' if args.draft else 'sculpture_preview.mesh.npz'
    np.savez_compressed(cache,vertices=v.astype(np.float32),faces=faces.astype(np.int32),material=material)
    mesh,precision=prepare_print_mesh(v,faces)
    filename='draft_model.stl' if args.draft else OUTPUT
    mesh.export(filename)
    delivered=trimesh.load_mesh(filename,process=True)
    require(delivered.is_watertight and delivered.is_winding_consistent and delivered.is_volume and delivered.body_count==1,'Delivered float32 STL failed topology checks.')
    require(abs(delivered.volume-mesh.volume)/mesh.volume<1e-6,'STL volume mismatch.')
    over=(delivered.face_normals[:,2]<-1/np.sqrt(2))&(delivered.triangles[:,:,2].max(axis=1)>.001)
    report={'title':'Venom — symbiote bust','units':'millimeter','height_mm':args.height,'sampling_pitch_mm':pitch,'draft':args.draft,
            'triangles':len(delivered.faces),'vertices':len(delivered.vertices),'dimensions_mm':delivered.extents.tolist(),'volume_cm3':float(delivered.volume/1000),
            'watertight':True,'consistent_winding':True,'connected_solids':1,'pre_simplification_shells_cleaned':len(dust),'pre_simplification_removed_volume_mm3':discarded_volume,'post_simplification_shells_cleaned':len(shell)-1,'manifold_boolean_valid':True,
            'precision_cleanup':precision,'fang_count':count,'supports_required':True,'overhang_area_beyond_45_deg_mm2':float(delivered.area_faces[over].sum()),
            'physical_print_tested':False,'preview_colors':'Optional paint finish on the actual sculpture geometry.',
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if not args.draft:save_3mf(delivered,Path(OUTPUT).with_suffix('.3mf'))
    Path('draft_validation.json' if args.draft else 'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
