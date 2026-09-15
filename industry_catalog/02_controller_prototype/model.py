#!/usr/bin/env python3
"""ControlPod prototype housing. All dimensions in millimeters.
Run: python model.py
Writes ./output_model.stl, .3mf and assembled .step; no GUI.
Digital checks do not replace a physical fit/load trial.
"""

# ---------------- Exposed product parameters: mm ----------------
LENGTH=114.0
WIDTH=66.0
HEIGHT=25.0
WALL=2.4
FLOOR=2.6
CORNER_RADIUS=11.0
LID_THICKNESS=2.8
LIP_HEIGHT=3.0
LIP_WALL=1.6
FIT=0.25                   # Clearance on EACH locating-lip side.
SCREW_SPAN_X=92.0
SCREW_SPAN_Y=44.0
BOSS_RADIUS=4.6
SCREW_CLEARANCE=3.4
NUT_ACROSS_FLATS=5.8       # Nominal 5.5 mm M3 nut + 0.30 mm total clearance.
NUT_DEPTH=2.8
PCB_SPAN_X=54.0
PCB_SPAN_Y=30.0
PCB_STANDOFF=4.5
PCB_PILOT_DIAMETER=2.2
DISPLAY_LENGTH=42.0
DISPLAY_WIDTH=18.0
BUTTON_DIAMETER=10.5
PORT_WIDTH=14.0
PORT_HEIGHT=6.0

PRODUCT_ID='02_controller_prototype'
TITLE='ControlPod prototype housing'
CATEGORY='Functional prototypes'

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


def build():
    inner_l=LENGTH-2*WALL;inner_w=WIDTH-2*WALL
    require(min(inner_l,inner_w)>30 and LIP_HEIGHT<HEIGHT-FLOOR-2,'Housing is too small.')
    require(LIP_WALL>1 and FIT>=.20,'Use a printable lip wall and at least 0.20 mm side clearance.')
    outer=box(LENGTH,WIDTH,HEIGHT,CORNER_RADIUS)
    cavity=box(inner_l,inner_w,HEIGHT-FLOOR+EPS,CORNER_RADIUS-WALL,z=FLOOR)
    body=outer.cut(cavity)
    centers=[(x,y) for x in (-SCREW_SPAN_X/2,SCREW_SPAN_X/2) for y in (-SCREW_SPAN_Y/2,SCREW_SPAN_Y/2)]
    for x,y in centers:
        body=body.union(cyl(BOSS_RADIUS,HEIGHT-FLOOR+EPS,x=x,y=y,z=FLOOR-EPS))
        body=body.cut(cyl(SCREW_CLEARANCE/2,HEIGHT+2*EPS,x=x,y=y,z=-EPS))
        nut=cq.Workplane('XY',origin=(x,y,HEIGHT-NUT_DEPTH)).polygon(6,NUT_ACROSS_FLATS/(sqrt(3)/2)).extrude(NUT_DEPTH+EPS)
        body=body.cut(nut)
    for x in (-PCB_SPAN_X/2,PCB_SPAN_X/2):
        for y in (-PCB_SPAN_Y/2,PCB_SPAN_Y/2):
            post=cyl(3,PCB_STANDOFF,x=x,y=y,z=FLOOR-EPS)
            post=post.cut(cyl(PCB_PILOT_DIAMETER/2,PCB_STANDOFF+EPS,x=x,y=y,z=FLOOR-EPS))
            body=body.union(post)
    port=box(WALL+LIP_WALL+FIT+2,PORT_WIDTH,PORT_HEIGHT+EPS,
             x=LENGTH/2-WALL/2,z=HEIGHT-PORT_HEIGHT)
    body=body.cut(port)
    lid=box(LENGTH,WIDTH,LID_THICKNESS,CORNER_RADIUS)
    lip_l=inner_l-2*FIT;lip_w=inner_w-2*FIT
    lip=box(lip_l,lip_w,LIP_HEIGHT+EPS,CORNER_RADIUS-WALL-FIT,z=-LIP_HEIGHT)
    lip=lip.cut(box(lip_l-2*LIP_WALL,lip_w-2*LIP_WALL,LIP_HEIGHT+3*EPS,
                    CORNER_RADIUS-WALL-FIT-LIP_WALL,z=-LIP_HEIGHT-EPS))
    for x,y in centers:lip=lip.cut(cyl(BOSS_RADIUS+FIT,LIP_HEIGHT+3*EPS,x=x,y=y,z=-LIP_HEIGHT-EPS))
    lip=lip.cut(box(WALL+LIP_WALL+FIT+3,PORT_WIDTH+2*FIT,LIP_HEIGHT+3*EPS,
                    x=LENGTH/2-WALL/2,z=-LIP_HEIGHT-EPS))
    lid=lid.union(lip)
    lid=lid.cut(box(DISPLAY_LENGTH,DISPLAY_WIDTH,LID_THICKNESS+2*EPS,2,x=-18,z=-EPS))
    for y in (-12,12):lid=lid.cut(cyl(BUTTON_DIAMETER/2,LID_THICKNESS+2*EPS,x=30,y=y,z=-EPS))
    for x,y in centers:lid=lid.cut(cyl(SCREW_CLEARANCE/2,LID_THICKNESS+2*EPS,x=x,y=y,z=-EPS))
    body,lid=as_shape(body),as_shape(lid)
    assembled_lid=lid.translate((0,0,HEIGHT))
    print_lid=lid.rotate((0,0,0),(1,0,0),180)
    return [('body',body),('lid',print_lid)], [('Body',body),('Lid',assembled_lid)], [
        ('Body',body,'#297e97'),('Lid_exploded',lid.translate((0,0,HEIGHT+22)),'#73b5c4')],{
        'outer_envelope_mm':[LENGTH,WIDTH,HEIGHT+LID_THICKNESS],
        'lip_clearance_per_side_mm':FIT,'nut_pocket_across_flats_mm':NUT_ACROSS_FLATS,
        'PCB_standoff_pattern_mm':[PCB_SPAN_X,PCB_SPAN_Y],
        'hardware':'Four M3 bolts with nuts in the top-loaded hex pockets; screws for the selected PCB. Electronics, buttons and display are not included.',
        'use':'Fit/ergonomic prototype with display/button cutouts and an open-rim service port. No ingress rating. Retain nuts temporarily while closing the lid.'}

if __name__=='__main__':write_outputs(*build())
