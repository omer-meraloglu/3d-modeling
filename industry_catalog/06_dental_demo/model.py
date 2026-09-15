#!/usr/bin/env python3
"""Generic dental training arch. NON-CLINICAL demonstration geometry only.
Run: python model.py. Exports ./output_model.stl, .3mf and .step.
No patient scan or anatomical fitting. Not for intraoral use or treatment.
"""
# ----------------- Exposed parameters: millimeters -----------------
BASE_LENGTH=84.0
BASE_WIDTH=70.0
BASE_THICKNESS=3.2
GUM_HEIGHT=4.2
ARCH_RX=31.5           # Centerline radii of the illustrative tooth row.
ARCH_RY=27.5
GUM_OUTER_RX=38.0
GUM_OUTER_RY=34.0
GUM_INNER_RX=25.0
GUM_INNER_RY=21.0
CROWN_HEIGHT=6.5       # Root-to-occlusal platform, before rounded cusps.
END_ANGLE_DEG=10.0
TOOTH_GAP=0.6          # Minimum nominal spacing allowance along the row.
LABEL_DEPTH=0.6       # Permanent recessed DEMO mark.
PRODUCT_ID='06_dental_demo'
TITLE='Dental training arch'
CATEGORY='Medical and dental: non-clinical demonstration'

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


def load_print_mesh(path):
    # OCC sphere poles can emit zero-area STL triangles with repeated vertices.
    # Remove only degenerates/duplicate facets; do not fill holes or move vertices.
    mesh=trimesh.load_mesh(path,process=True)
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-10)&mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    mesh.export(path,file_type='stl')
    # Reload the delivered bytes, rather than validating only the in-memory mesh.
    return trimesh.load_mesh(path,process=True)


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
        m=load_print_mesh(target)
        reports[name]=check_mesh(m,1,p.Volume())
        m.apply_translation((x,y,0));meshes.append(m);positions.append(p.translate((x,y,0)))
        x+=b.xlen+PART_GAP;row=max(row,b.ylen)
    plate=cq.Compound.makeCompound(positions)
    require(plate.exportStl(str(OUTPUT),tolerance=STL_LINEAR_TOLERANCE,
                          angularTolerance=STL_ANGULAR_TOLERANCE,ascii=False,relative=False),'Plate STL export failed.')
    final=load_print_mesh(OUTPUT)
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




def ellipse(rx,ry,z,h):
    return cq.Workplane('XY',origin=(0,0,z)).ellipse(rx,ry).extrude(h)


def crown(width,depth,kind):
    root_z=BASE_THICKNESS+GUM_HEIGHT-EPS
    p=(cq.Workplane('XY',origin=(0,0,root_z)).ellipse(width*.39,depth*.38)
       .workplane(offset=3.0).ellipse(width*.50,depth*.50)
       .workplane(offset=CROWN_HEIGHT-3.0).ellipse(width*.46,depth*.44).loft(ruled=True))
    top=root_z+CROWN_HEIGHT
    if kind=='molar':cusps=[(x,y,.85) for x in (-1.15,1.15) for y in (-1.25,1.25)]
    elif kind=='premolar':cusps=[(0,y,1.0) for y in (-1.2,1.2)]
    elif kind=='canine':cusps=[(0,0,1.5)]
    else:return as_shape(p.union(box(width*.72,1.4,.6,.6,z=top-EPS)))
    for x,y,r in cusps:
        cap=cq.Solid.makeSphere(r,cq.Vector(x,y,top-EPS),angleDegrees1=0,angleDegrees2=90)
        p=p.union(cap)
    return as_shape(p)


def build():
    require(BASE_LENGTH>2*GUM_OUTER_RX+5 and BASE_WIDTH>GUM_OUTER_RY+25,'Base must contain the arch and permanent DEMO label.')
    require(5.5<=CROWN_HEIGHT<=9 and 8<=END_ANGLE_DEG<=18,'Use the demonstrated crown-height and row-angle ranges.')
    base=box(BASE_LENGTH,BASE_WIDTH,BASE_THICKNESS,4,y=12)
    # Polygon lettering avoids platform font dependencies and fragile font splines.
    outlines=[[(0,0),(3,0),(4.5,1.5),(4.5,5.5),(3,7),(0,7)],
              [(0,0),(4.5,0),(4.5,1.2),(1.2,1.2),(1.2,2.9),(3.7,2.9),(3.7,4.1),(1.2,4.1),(1.2,5.8),(4.5,5.8),(4.5,7),(0,7)],
              [(0,0),(1.1,0),(1.1,5),(2.25,3.4),(3.4,5),(3.4,0),(4.5,0),(4.5,7),(3.4,7),(2.25,5.2),(1.1,7),(0,7)],
              [(1,0),(3.5,0),(4.5,1),(4.5,6),(3.5,7),(1,7),(0,6),(0,1)]]
    inners={0:[(1.2,1.2),(2.5,1.2),(3.3,2),(3.3,5),(2.5,5.8),(1.2,5.8)],
            3:[(1.5,1.2),(3,1.2),(3.3,1.5),(3.3,5.5),(3,5.8),(1.5,5.8),(1.2,5.5),(1.2,1.5)]}
    for i,outline in enumerate(outlines):
        origin=(-10.95+i*5.8,-15.5,BASE_THICKNESS-LABEL_DEPTH)
        mark=cq.Workplane('XY',origin=origin).polyline(outline).close().extrude(LABEL_DEPTH+EPS)
        if i in inners:
            core=cq.Workplane('XY',origin=(origin[0],origin[1],origin[2]-EPS)).polyline(inners[i]).close().extrude(LABEL_DEPTH+3*EPS)
            mark=mark.cut(core)
        base=base.cut(mark)
    gum=ellipse(GUM_OUTER_RX,GUM_OUTER_RY,BASE_THICKNESS-EPS,GUM_HEIGHT+EPS)
    gum=gum.cut(ellipse(GUM_INNER_RX,GUM_INNER_RY,BASE_THICKNESS-2*EPS,GUM_HEIGHT+4*EPS))
    gum=gum.intersect(box(2*GUM_OUTER_RX+2,GUM_OUTER_RY+1,GUM_HEIGHT+4*EPS,y=(GUM_OUTER_RY+1)/2,z=BASE_THICKNESS-2*EPS))
    half=[('molar',6.6,8.0),('molar',6.6,8.0),('premolar',5.6,7.0),('premolar',5.6,7.0),('canine',4.8,6.5),('incisor',4.0,6.0),('incisor',4.0,6.0)]
    specs=half+list(reversed(half))
    angles=np.linspace(np.radians(END_ANGLE_DEG),np.radians(180-END_ANGLE_DEG),3001)
    xy=np.stack([ARCH_RX*np.cos(angles),ARCH_RY*np.sin(angles)],axis=1)
    cumulative=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
    widths=np.array([s[1] for s in specs]);need=float(widths.sum()+TOOTH_GAP*(len(specs)-1))
    require(need<cumulative[-1],'Crowns do not fit along this arch. Increase arch radii or reduce widths.')
    gaps=(cumulative[-1]-widths.sum())/(len(specs)-1)
    stations=np.cumsum(widths)-widths/2+gaps*np.arange(len(specs))
    stations=(stations-stations[0])/(stations[-1]-stations[0])*cumulative[-1]
    teeth=[]
    for station,(kind,w,d) in zip(stations,specs):
        a=float(np.interp(station,cumulative,angles))
        x=ARCH_RX*np.cos(a);y=ARCH_RY*np.sin(a)
        tangent=np.degrees(np.arctan2(ARCH_RY*np.cos(a),-ARCH_RX*np.sin(a)))
        teeth.append(crown(w,d,kind).rotate((0,0,0),(0,0,1),float(tangent)).translate((float(x),float(y),0)))
    for i,t in enumerate(teeth):
        for t2 in teeth[i+1:]:require(t.intersect(t2).Volume()<1e-6,'Adjacent demonstration crowns overlap.')
    complete=as_shape(base).fuse(as_shape(gum),*teeth).clean()
    scene=[('Labeled_base',base,'#bbc9c4'),('Illustrative_gum',gum,'#b9857b')]
    scene += [(f'Generic_crown_{i+1:02}',t,'#e6ddc5') for i,t in enumerate(teeth)]
    return [('dental_demo',complete)],[('Dental_demo',complete)],scene,{
        'intended_use':'Generic dental education and display prop only. Fourteen illustrative crowns; not anatomically validated.',
        'clinical_use':False,'patient_specific':False,
        'restriction':'Do not use intraorally, for aligner manufacture, surgical guidance, diagnosis, treatment or fitting prostheses.',
        'print':'Base flat on bed. Ordinary filament is suitable only for handling/display of this non-clinical prop.',
        'identification':'Permanent recessed DEMO mark on the base.','crown_count':14}

if __name__=='__main__':write_outputs(*build())
