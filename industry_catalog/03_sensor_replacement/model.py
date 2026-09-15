#!/usr/bin/env python3
"""Gusseted sensor bracket. All dimensions in millimeters.
Run: python model.py
Writes ./output_model.stl, .3mf and assembled .step; no GUI.
Digital checks do not replace a physical fit/load trial.
"""

# ---------------- Exposed product parameters: mm ----------------
LENGTH=80.0
WIDTH=46.0
HEIGHT=46.0
BASE_THICKNESS=6.0
WALL_THICKNESS=8.0
GUSSET_THICKNESS=5.0
SENSOR_DIAMETER=18.0
SENSOR_CENTER_Z=29.0
FIT=0.25                   # Radial clearance around the sensor body.
MOUNT_X=10.0
MOUNT_Y=26.0
MOUNT_HOLE=5.5
SLOT_LENGTH=16.0

PRODUCT_ID='03_sensor_replacement'
TITLE='Gusseted sensor bracket'
CATEGORY='End-use replacement parts'

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
    require(SENSOR_DIAMETER+2*FIT<WIDTH-12,'Sensor opening leaves insufficient side ligaments.')
    require(MOUNT_Y/2+MOUNT_HOLE/2<=WIDTH/2-GUSSET_THICKNESS-1.5,'Mount slots must clear the gussets.')
    r=(SENSOR_DIAMETER+2*FIT)/2
    require(SENSOR_CENTER_Z-r>BASE_THICKNESS+3 and SENSOR_CENTER_Z+r*sqrt(2)<HEIGHT-2.5,'Insufficient web above/below the self-supporting sensor opening.')
    base=box(LENGTH,WIDTH,BASE_THICKNESS,1)
    wall=box(WALL_THICKNESS,WIDTH,HEIGHT-BASE_THICKNESS+EPS,1,
             x=-LENGTH/2+WALL_THICKNESS/2,z=BASE_THICKNESS-EPS)
    bracket=base.union(wall)
    for y in (-WIDTH/2+GUSSET_THICKNESS/2,WIDTH/2-GUSSET_THICKNESS/2):
        triangle=cq.Workplane('XZ',origin=(0,y+GUSSET_THICKNESS/2,0)).polyline([
            (-LENGTH/2+WALL_THICKNESS-EPS,BASE_THICKNESS-EPS),
            (LENGTH/2-10,BASE_THICKNESS-EPS),
            (-LENGTH/2+WALL_THICKNESS-EPS,HEIGHT-4)]).close().extrude(GUSSET_THICKNESS)
        bracket=bracket.union(triangle)
    start=-LENGTH/2-EPS
    bore=cq.Workplane('YZ',origin=(start,0,SENSOR_CENTER_Z)).circle(r).extrude(WALL_THICKNESS+2*EPS)
    roof=cq.Workplane('YZ',origin=(start,0,SENSOR_CENTER_Z)).polyline([
        (-r/sqrt(2),r/sqrt(2)),(r/sqrt(2),r/sqrt(2)),(0,r*sqrt(2))]).close().extrude(WALL_THICKNESS+2*EPS)
    bracket=bracket.cut(bore.union(roof))
    for y in (-MOUNT_Y/2,MOUNT_Y/2):
        slot=cq.Workplane('XY',origin=(MOUNT_X,y,-EPS)).slot2D(SLOT_LENGTH,MOUNT_HOLE,0).extrude(BASE_THICKNESS+2*EPS)
        bracket=bracket.cut(slot)
    p=as_shape(bracket)
    return [('sensor_bracket',p)],[('Sensor_bracket',p)],[('Sensor_bracket',p,'#d57e40')],{
        'sensor_body_nominal_mm':SENSOR_DIAMETER,'clearance_per_side_mm':FIT,
        'opening':'Circular seat with a 45-degree triangular roof; use the sensor mounting nuts and washers.',
        'hardware':'M18 sensor with its mounting nuts; two M5 bolts and washers.',
        'mount_slot_travel_mm':SLOT_LENGTH-MOUNT_HOLE,
        'use':'Example non-safety-critical replacement bracket. Confirm machine dimensions, temperature, vibration and tightening torque before service.'}

if __name__=='__main__':write_outputs(*build())
