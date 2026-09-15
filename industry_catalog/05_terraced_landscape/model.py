#!/usr/bin/env python3
"""Terraced garden and pavilion: a headless, printable architectural presentation model.
Run: python model.py. Exports ./output_model.stl, .3mf and .step.
Fictional site, not construction documentation. All modeled dimensions are mm.
"""
# ----------------- Exposed parameters -----------------
SCALE_DENOMINATOR=200.0   # Nominal presentation scale; all geometry below is model mm.
SITE_LENGTH=180.0
SITE_WIDTH=140.0
BASE_THICKNESS=4.0
HILL_LEVELS=4
TERRACE_RISE=3.0
PAVILION_HEIGHT=15.0
POND_RX=27.0
POND_RY=17.0
POND_DEPTH=1.0

PRODUCT_ID='05_terraced_landscape'
TITLE='Terraced garden and pavilion'
CATEGORY="Architectural models and landscapes"

# Shared routines are embedded here so this model.py remains self-contained.
from pathlib import Path
from math import sqrt, isfinite
import json, zipfile
import cadquery as cq
import numpy as np
import trimesh
from OCP.BOPAlgo import BOPAlgo_ArgumentAnalyzer

EPS=0.02
OUTPUT=Path('./output_model.stl')
BED_X=220.0
BED_Y=220.0
PART_GAP=8.0
BED_MARGIN=5.0
STL_LINEAR_TOLERANCE=0.025
STL_ANGULAR_TOLERANCE=0.10


def require(test,message):
    if not test:raise ValueError(message)


def box(l,w,h,r=0,x=0,y=0,z=0):
    require(min(l,w,h)>0,'Box dimensions must be positive.')
    p=cq.Workplane('XY',origin=(x,y,z)).box(l,w,h,centered=(True,True,False))
    return p.edges('|Z').fillet(r) if r else p


def cyl(r,h,x=0,y=0,z=0):
    return cq.Workplane('XY',origin=(x,y,z)).circle(r).extrude(h)


def as_shape(p):
    return p.clean().val() if isinstance(p,cq.Workplane) else p.clean()


def mesh_record(name,p,color,reference=False):
    v,f=as_shape(p).tessellate(.10,.16)
    return {'name':name,'vertices':[[q.x,q.y,q.z] for q in v],
            'faces':[list(t) for t in f],'color':color,'reference':reference}


def check_mesh(mesh,expected_count,expected_volume):
    require(mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume,
            'Exported mesh is open, inverted or inconsistently wound.')
    require(mesh.body_count==expected_count,'Unexpected number of connected parts.')
    require(abs(mesh.volume-expected_volume)/expected_volume<.005,'Mesh and CAD volumes disagree.')
    below=(mesh.face_normals[:,2]<-1/sqrt(2)-.0003)&(mesh.triangles[:,:,2].max(axis=1)>1e-4)
    area=float(mesh.area_faces[below].sum())
    require(area<1e-6,f'Unsupported downward surfaces beyond 45 degrees: {area:.5f} mm2.')
    return {'watertight':True,'consistent_winding':True,'connected_parts':int(mesh.body_count),
            'triangles':len(mesh.faces),'volume_cm3':float(mesh.volume/1000),
            'dimensions_mm':mesh.extents.tolist(),'unsupported_area_beyond_45_deg_mm2':area}


def save_3mf(path,meshes,names):
    from xml.sax.saxutils import escape
    a=['<?xml version="1.0" encoding="UTF-8"?>',
       '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
       '<metadata name="Title">'+escape(TITLE)+'</metadata><resources>']
    for i,(m,n) in enumerate(zip(meshes,names),1):
        a.append(f'<object id="{i}" name="{escape(n)}" type="model"><mesh><vertices>')
        a.extend(f'<vertex x="{x:.8f}" y="{y:.8f}" z="{z:.8f}"/>' for x,y,z in m.vertices)
        a.append('</vertices><triangles>')
        a.extend(f'<triangle v1="{x}" v2="{y}" v3="{z}"/>' for x,y,z in m.faces)
        a.append('</triangles></mesh></object>')
    a.append('</resources><build>')
    a.extend(f'<item objectid="{i}"/>' for i in range(1,len(meshes)+1))
    a.append('</build></model>')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',''.join(a))


def write_outputs(parts,assembly,scene,details=None):
    require(all(isfinite(v) for k,v in globals().items() if k.isupper() and isinstance(v,(float,int))),
            'Dimensions must be finite.')
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    positions=[];meshes=[];reports={};x=y=BED_MARGIN;row=0.0
    for name,p in parts:
        p=as_shape(p)
        require(p.isValid() and len(p.Solids())==1 and p.Volume()>0,name+': invalid CAD solid.')
        analyzer=BOPAlgo_ArgumentAnalyzer();analyzer.SetShape1(p.wrapped)
        analyzer.SelfInterMode=True;analyzer.Perform()
        require(not analyzer.HasFaulty(),name+': self-intersecting CAD.')
        b=p.BoundingBox();p=p.translate((-b.xmin,-b.ymin,-b.zmin))
        if x+b.xlen>BED_X-BED_MARGIN:x,y,row=BED_MARGIN,y+row+PART_GAP,0
        require(x+b.xlen<=BED_X-BED_MARGIN and y+b.ylen<=BED_Y-BED_MARGIN,'Print plate exceeds the configured bed.')
        target=OUTPUT.with_name(name+'.stl')
        require(p.exportStl(str(target),tolerance=STL_LINEAR_TOLERANCE,
                           angularTolerance=STL_ANGULAR_TOLERANCE,ascii=False,relative=False),'STL export failed.')
        m=trimesh.load_mesh(target,process=True)
        reports[name]=check_mesh(m,1,p.Volume())
        m.apply_translation((x,y,0));meshes.append(m);positions.append(p.translate((x,y,0)))
        x+=b.xlen+PART_GAP;row=max(row,b.ylen)
    plate=cq.Compound.makeCompound(positions)
    require(plate.exportStl(str(OUTPUT),tolerance=STL_LINEAR_TOLERANCE,
                          angularTolerance=STL_ANGULAR_TOLERANCE,ascii=False,relative=False),'Plate STL export failed.')
    final=trimesh.load_mesh(OUTPUT,process=True)
    plate_report=check_mesh(final,len(parts),plate.Volume())
    save_3mf(OUTPUT.with_suffix('.3mf'),meshes,[n for n,p in parts])
    for i,(name,a) in enumerate(assembly):
        for name2,b in assembly[i+1:]:
            require(as_shape(a).intersect(as_shape(b)).Volume()<1e-5,'Assembled parts collide: '+name+' / '+name2)
    cad=cq.Assembly(name=PRODUCT_ID)
    for name,p in assembly:cad.add(as_shape(p),name=name)
    cad.export(str(OUTPUT.with_suffix('.step')))
    loaded=cq.importers.importStep(str(OUTPUT.with_suffix('.step'))).val()
    require(loaded.isValid() and len(loaded.Solids())==len(assembly),'STEP round-trip failed.')
    a_volume=sum(as_shape(p).Volume() for n,p in assembly)
    require(abs(loaded.Volume()-a_volume)/a_volume<1e-6,'STEP volume mismatch.')
    metadata={'id':PRODUCT_ID,'title':TITLE,'category':CATEGORY,'units':'millimeter',
              'parts':len(parts),'part_reports':reports,'print_plate':plate_report,
              'cad_self_intersection_checked':True,'assembly_collision_checked':True,
              'step_roundtrip_valid':True,'physical_tested':False,
              'support_free_in_exported_orientation':True,'details':details or {}}
    OUTPUT.with_name('validation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    display=[mesh_record(*item) for item in scene]
    OUTPUT.with_name('preview_mesh.json').write_text(json.dumps({'id':PRODUCT_ID,'title':TITLE,'meshes':display},separators=(',',':')))
    print(f'{TITLE}: {len(parts)} printable part(s), {len(final.faces):,} triangles, {plate.Volume()/1000:.1f} cm3; CAD/STL/STEP/45-degree checks passed.',flush=True)


def fuse_all(parts):
    return as_shape(parts[0]).fuse(*[as_shape(p) for p in parts[1:]]).clean()


def window_cut(axis,face,inward,along,z,width,height,depth=.65):
    # Blind facade recess: its top slopes slightly steeper than 45 degrees to the outside face.
    points=[(face-inward*EPS,z),(face+inward*depth,z),
            (face+inward*depth,z+height-depth*1.04),(face,z+height),
            (face-inward*EPS,z+height)]
    if axis=='y':return cq.Workplane('YZ',origin=(along-width/2,0,0)).polyline(points).close().extrude(width)
    return cq.Workplane('XZ',origin=(0,along+width/2,0)).polyline(points).close().extrude(width)


def detailed_block(x,y,l,w,floors,base,floor_height,parapet=True):
    height=floors*floor_height
    block=box(l,w,height,1.1,x=x,y=y,z=base)
    cuts=[]
    count_x=max(1,int((l-6)/7.8));count_y=max(1,int((w-6)/7.8))
    for level in range(floors):
        wz=base+level*floor_height+3.2
        wh=min(7.0,floor_height-5.0)
        for face,inside in ((y-w/2,1),(y+w/2,-1)):
            for xx in np.linspace(x-l/2+4.4,x+l/2-4.4,count_x):
                cuts.append(window_cut('y',face,inside,xx,wz,4.1,wh))
        for face,inside in ((x-l/2,1),(x+l/2,-1)):
            for yy in np.linspace(y-w/2+4.4,y+w/2-4.4,count_y):
                cuts.append(window_cut('x',face,inside,yy,wz,4.1,wh))
    for level in range(1,floors):
        for face,inside in ((y-w/2,1),(y+w/2,-1)):
            cuts.append(window_cut('y',face,inside,x,base+level*floor_height-.8,l-2.5,.7,.30))
        for face,inside in ((x-l/2,1),(x+l/2,-1)):
            cuts.append(window_cut('x',face,inside,y,base+level*floor_height-.8,w-2.5,.7,.30))
    if cuts:block=block.cut(cq.Compound.makeCompound([as_shape(c) for c in cuts]))
    if not parapet:return as_shape(block)
    # Roof parapets grow vertically from the solid roof, so no hidden bridges.
    parapet=box(l,w,1.4+EPS,1.1,x=x,y=y,z=base+height-EPS)
    parapet=parapet.cut(box(l-2.4,w-2.4,1.4+3*EPS,.25,x=x,y=y,z=base+height-2*EPS))
    return as_shape(block.union(parapet))


def tree(x,y,z,radius=3.6,height=12):
    trunk=cq.Solid.makeCylinder(.80,3.2,cq.Vector(x,y,z-EPS))
    canopy_z=z+2.9
    lower_h=radius-.80+0.20 # slightly steeper than 45 degrees
    lower=cq.Solid.makeCone(.80,radius,lower_h,cq.Vector(x,y,canopy_z))
    upper=cq.Solid.makeCone(radius,.35,max(2,height-2.9-lower_h),cq.Vector(x,y,canopy_z+lower_h))
    return trunk.fuse(lower,upper).clean()


def ellipse_pad(x,y,rx,ry,z,h):
    return cq.Workplane('XY',origin=(x,y,z)).ellipse(rx,ry).extrude(h)


def walkway(points,width,z,h):
    shapes=[cyl(width/2,h,x=x,y=y,z=z) for x,y in points]
    for (x0,y0),(x1,y1) in zip(points,points[1:]):
        length=float(np.hypot(x1-x0,y1-y0))
        strip=box(length,width,h,z=z).rotate((0,0,0),(0,0,1),float(np.degrees(np.arctan2(y1-y0,x1-x0))))
        shapes.append(strip.translate(((x0+x1)/2,(y0+y1)/2,0)))
    return fuse_all(shapes)


def build():
    require(SITE_LENGTH>=175 and SITE_WIDTH>=135,'The default landscape needs at least 175 x 135 mm.')
    require(2<=BASE_THICKNESS and .5<=POND_DEPTH<=BASE_THICKNESS-1.5,'Pond must retain at least 1.5 mm of solid floor.')
    require(18<=POND_RX<=30 and 12<=POND_RY<=19,'Keep the pond clear of paths and terrain.')
    require(2<=TERRACE_RISE<=4 and 12<=PAVILION_HEIGHT<=24,'Use the modeled landscape height ranges.')
    require(HILL_LEVELS==4,'This scene uses four coordinated terrace/entry levels.')
    site=box(SITE_LENGTH,SITE_WIDTH,BASE_THICKNESS,6)
    pond_outer=ellipse_pad(35,-27,POND_RX,POND_RY,BASE_THICKNESS-POND_DEPTH,POND_DEPTH+EPS)
    site=site.cut(pond_outer)
    water=ellipse_pad(35,-27,POND_RX-1.4,POND_RY-1.4,BASE_THICKNESS-POND_DEPTH-EPS,.08+EPS)
    curb=ellipse_pad(35,-27,POND_RX+2.5,POND_RY+2.5,BASE_THICKNESS-EPS,.55+EPS)
    curb=curb.cut(ellipse_pad(35,-27,POND_RX,POND_RY,BASE_THICKNESS-2*EPS,.55+4*EPS))
    hill=[]
    for level in range(HILL_LEVELS):
        hill.append(ellipse_pad(-30,22,43-level*5.3,31-level*4.0,
                                BASE_THICKNESS-EPS+level*TERRACE_RISE,TERRACE_RISE+EPS))
    top_z=BASE_THICKNESS+HILL_LEVELS*TERRACE_RISE
    pavilion=detailed_block(-30,22,29,20,1,top_z-EPS,PAVILION_HEIGHT)
    roofgarden=box(18,9,.65,1,x=-30,y=22,z=top_z+PAVILION_HEIGHT-2*EPS)
    east_lawn=ellipse_pad(49,32,26,20,BASE_THICKNESS-EPS,1.1)
    cottage=detailed_block(48,33,19,16,1,BASE_THICKNESS+1.1-EPS,10,parapet=False)
    # Gabled cottage roof grows inward from the supported roof footprint.
    roof=cq.Workplane('YZ',origin=(48-19/2,0,0)).polyline([
        (33-8,BASE_THICKNESS+1.1+10-2*EPS),
        (33+8,BASE_THICKNESS+1.1+10-2*EPS),
        (33,BASE_THICKNESS+1.1+17)]).close().extrude(19)
    roof=as_shape(roof).intersect(as_shape(box(19,16,8,1.1,x=48,y=33,z=BASE_THICKNESS+1.1+10-2*EPS)))
    cottage=as_shape(cottage).fuse(roof).clean()
    stairs=[]
    for i in range(8):
        front=-14+i*2.8;back=12.0
        stairs.append(box(12,back-front,(i+1)*TERRACE_RISE/2,.15,
                          x=-30,y=(front+back)/2,z=BASE_THICKNESS-EPS))
    paths=[walkway([(-74,-48),(-45,-48),(-30,-30),(-30,-14)],5,BASE_THICKNESS-EPS,.40),
           walkway([(-30,-30),(-8,-42),(8,-48),(31,-51),(57,-47),(72,-31),(74,-9),(63,6),(48,12)],4,BASE_THICKNESS-EPS,.40),
           walkway([(48,12),(48,27)],5,BASE_THICKNESS-EPS,1.3)]
    trees=[]
    for x,y,r,h in [(-73,28,3.5,12),(-70,51,4.0,14),(-53,57,3.8,13),
                    (-12,55,3.6,12),(10,53,4.2,14),(25,52,3.6,12),
                    (72,50,3.8,13),(77,20,3.4,11),(-70,-14,3.8,13),
                    (-60,-52,3.2,11),(-12,-56,3.1,10),(72,-56,3.4,12)]:
        # Trees outside the terrace footprint start at the site surface.
        trees.append(tree(x,y,BASE_THICKNESS-EPS,r,h))
    benches=[box(10,3,2,.5,x=x,y=y,z=BASE_THICKNESS-EPS) for x,y in [(4,-20),(65,-12),(-56,-30)]]
    bollards=[]
    for x,y in [(-43,-43),(-24,-33),(10,-49),(59,-42),(73,-6),(58,10)]:
        bollards.append(cyl(.85,4.5,x=x,y=y,z=BASE_THICKNESS-EPS))
    pieces=[site,water,curb,*hill,pavilion,roofgarden,east_lawn,cottage,*stairs,*paths,*trees,*benches,*bollards]
    complete=fuse_all(pieces)
    require(complete.BoundingBox().xlen<=SITE_LENGTH+.01 and complete.BoundingBox().ylen<=SITE_WIDTH+.01,'Features overrun the site.')
    scene=[('Site',site,'#c4c4b6'),('Pond_floor',water,'#5f9caf'),('Pond_curb',curb,'#d2c4a8'),
           ('Pavilion',pavilion,'#eadfcb'),('Pavilion_roof_garden',roofgarden,'#668f6c'),
           ('East_lawn',east_lawn,'#91a679'),('Cottage',cottage,'#d9cfbd')]
    scene += [(f'Terrace_{i}',p,['#b1b994','#a3b286','#94aa79','#86a16e'][i]) for i,p in enumerate(hill)]
    scene += [(f'Stair_{i}',p,'#c5b596') for i,p in enumerate(stairs)]
    scene += [(f'Walkway_{i}',p,'#d9c8aa') for i,p in enumerate(paths)]
    scene += [(f'Tree_{i}',p,'#397c62') for i,p in enumerate(trees)]
    scene += [(f'Bench_{i}',p,'#967957') for i,p in enumerate(benches)]
    scene += [(f'Bollard_{i}',p,'#667d79') for i,p in enumerate(bollards)]
    return [('terraced_garden',complete)],[('Terraced_garden',complete)],scene,{
        'architectural_scale':f'1:{SCALE_DENOMINATOR:g}',
        'site_mm':[SITE_LENGTH,SITE_WIDTH],'terrain_height_mm':HILL_LEVELS*TERRACE_RISE,
        'features':'Four landscape terraces, raised pavilion, gabled cottage, recessed pond, shoreline curb, linked paths, eight steps, twelve trees, benches and bollards.',
        'representation':'Fictional landscape concept with deliberately enlarged print details. Pond is a modeled recess, not a functional water container. Preview colors show an optional painted finish.',
        'print':'Single connected terrain/site model; flat base on bed, no slicer supports in the default pose.'}

if __name__=='__main__':write_outputs(*build())
