#!/usr/bin/env python3
"""Courtyard office campus: a headless, printable architectural presentation model.
Run: python model.py. Exports ./output_model.stl, .3mf and .step.
Fictional site, not construction documentation. All modeled dimensions are mm.
"""
# ----------------- Exposed parameters -----------------
SCALE_DENOMINATOR=200.0   # Building dimensions use this real-to-model ratio.
SITE_LENGTH=180.0         # Display-base dimensions in printed millimeters.
SITE_WIDTH=140.0
BASE_THICKNESS=4.0
FLOOR_HEIGHT_REAL=3000.0  # Real-world millimeters, divided by the scale.
REAR_FLOORS=3
LEFT_FLOORS=2
RIGHT_FLOORS=1
TREE_RADIUS=3.6
TREE_HEIGHT=12.0

PRODUCT_ID='04_courtyard_architecture'
TITLE='Courtyard office campus'
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
    require(150<=SITE_LENGTH<=200 and 120<=SITE_WIDTH<=190,'Keep the display site within the default print bed.')
    require(150<=SCALE_DENOMINATOR<=250,'Use a presentation scale between 1:150 and 1:250.')
    require(all(isinstance(f,int) and 1<=f<=5 for f in (REAR_FLOORS,LEFT_FLOORS,RIGHT_FLOORS)),'Use one to five integer floors per wing.')
    require(FLOOR_HEIGHT_REAL/SCALE_DENOMINATOR>=12,'Model floor height must be at least 12 mm.')
    require(2<=TREE_RADIUS<=5 and TREE_HEIGHT>=TREE_RADIUS+5,'Trees need a supported canopy and a visible trunk.')
    s=200.0/SCALE_DENOMINATOR
    # Site is a print/display size; building dimensions derive from real millimeters.
    floor=FLOOR_HEIGHT_REAL/SCALE_DENOMINATOR
    site=box(SITE_LENGTH,SITE_WIDTH,BASE_THICKNESS,5)
    podium=box(112*s,96*s,1.2,2,x=0,y=8*s,z=BASE_THICKNESS-EPS)
    z=BASE_THICKNESS+1.2-EPS
    rear=detailed_block(0,35*s,96*s,20*s,REAR_FLOORS,z,floor)
    left=detailed_block(-37*s,-2*s,22*s,74*s,LEFT_FLOORS,z,floor)
    right=detailed_block(37*s,-2*s,22*s,74*s,RIGHT_FLOORS,z,floor)
    building=fuse_all([rear,left,right])
    # Three roof gardens and two small plant-room volumes.
    roofs=[]
    for x,y,l,w,f in [(0,35*s,96*s,20*s,REAR_FLOORS),(-37*s,-2*s,22*s,74*s,LEFT_FLOORS),(37*s,-2*s,22*s,74*s,RIGHT_FLOORS)]:
        roof_z=z+f*floor
        roofs.append(box(l*.55,w*.43,.65,1,x=x,y=y,z=roof_z-EPS))
    plantroom=box(17*s,8*s,4*s,1,x=22*s,y=35*s,z=z+REAR_FLOORS*floor-EPS)
    greens=[];trees=[];pavers=[];benches=[];cars=[]
    for side in (-1,1):
        x=side*(SITE_LENGTH/2-15)
        greens.append(box(20,83,.65,3,x=x,y=12,z=BASE_THICKNESS-EPS))
        for yy in (-16,9,35):trees.append(tree(x,yy,BASE_THICKNESS+.65-EPS,TREE_RADIUS,TREE_HEIGHT))
    # Courtyard lawn and a pair of small planting beds.
    greens.append(box(43*s,32*s,.55,2,y=-3*s,z=z-EPS))
    trees.extend([tree(-12*s,-2*s,z+.55-EPS,3.2,11),tree(12*s,-2*s,z+.55-EPS,3.2,11)])
    for xx in np.arange(-54,55,9):
        for yy in (-58,-49):pavers.append(box(8,8,.30,.3,x=float(xx),y=yy,z=BASE_THICKNESS-EPS))
    for xx in (-22*s,22*s):benches.append(box(8,3,2,.5,x=xx,y=-25*s,z=z-EPS))
    for i in range(3):
        x=-52+i*14;y=-43
        car=fuse_all([box(10,4.5,1.8,.9,x=x,y=y,z=BASE_THICKNESS-EPS),
                      box(6.5,3.8,1.3,.5,x=x-.8,y=y,z=BASE_THICKNESS+1.8-2*EPS)])
        cars.append(car)
    # Broad shallow entrance steps are fully supported by the preceding level.
    stairs=[]
    for i in range(3):stairs.append(box(28,7-i*2,.4*(i+1),.2,y=-37.5+i,z=BASE_THICKNESS-EPS))
    pieces=[site,podium,building,plantroom,*roofs,*greens,*trees,*pavers,*benches,*cars,*stairs]
    complete=fuse_all(pieces)
    require(complete.BoundingBox().xlen<=SITE_LENGTH+.01 and complete.BoundingBox().ylen<=SITE_WIDTH+.01,'Landscape extends beyond the site.')
    scene=[('Site',site,'#b5b9b4'),('Podium',podium,'#c7c9c2'),('Buildings',building,'#e6e2d7'),
           ('Plant_room',plantroom,'#c6c9c6')]
    scene += [(f'Roof_garden_{i}',p,'#709174') for i,p in enumerate(roofs)]
    scene += [(f'Lawn_{i}',p,'#779e82') for i,p in enumerate(greens)]
    scene += [(f'Tree_{i}',p,'#397b66') for i,p in enumerate(trees)]
    scene += [(f'Paver_{i}',p,'#dedbd0') for i,p in enumerate(pavers)]
    scene += [(f'Bench_{i}',p,'#a48863') for i,p in enumerate(benches)]
    scene += [(f'Car_{i}',p,'#586d7b') for i,p in enumerate(cars)]
    scene += [(f'Step_{i}',p,'#d7d4c8') for i,p in enumerate(stairs)]
    return [('courtyard_site',complete)],[('Courtyard_site',complete)],scene,{
        'architectural_scale':f'1:{SCALE_DENOMINATOR:g}',
        'site_mm':[SITE_LENGTH,SITE_WIDTH],'floor_height_real_mm':FLOOR_HEIGHT_REAL,
        'floors':[REAR_FLOORS,LEFT_FLOORS,RIGHT_FLOORS],
        'features':'Three stepped building wings, recessed glazing, floor joints, roof gardens, parapets, plant room, courtyard, eight trees, paving, benches, entrance steps and cars.',
        'representation':'Fictional concept site; openings and landscape details use minimum printable feature sizes. Preview colors are optional paint/material suggestions.',
        'print':'Single connected model; flat site base on bed. 0.4 mm nozzle / 0.12-0.16 mm layers is a starting point; verify in slicer.'}

if __name__=='__main__':write_outputs(*build())
