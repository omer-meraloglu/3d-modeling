#!/usr/bin/env python3
"""Blades of Chaos miniature keychain — self-contained CadQuery model.

All dimensions are millimeters. Install: pip install cadquery==2.6.1
Run: python model.py
Exports ./output_model.stl and .step, plus both individual design variants.
The STL is one fused watertight component, flat back on Z=0.
This is a stylized miniature fan-art interpretation, not game-extracted geometry.
"""
from collections import defaultdict
from math import atan2, degrees, hypot, isfinite, sqrt
from pathlib import Path
import json
import struct

import cadquery as cq
from OCP.BOPAlgo import BOPAlgo_ArgumentAnalyzer

# ---------------- Exposed parameters: millimeters ----------------
STYLE = 'crossed'              # 'single' or 'crossed'; main output selection.
LONG_SIDE_MM = 78.0            # Longest XY dimension, both variants.
BODY_THICKNESS = 3.6           # Solid foundation and blunt blade edge.
BLADE_BEVEL = 0.70             # 45-degree sweeping-edge bevel; blunt 2.9mm rim.
GUARD_RELIEF = 1.2             # Raised sculptural guard above the foundation.
GRIP_RELIEF = 0.60             # Raised diagonal wrap bands.
GROOVE_WIDTH = 0.85            # Minimum decorative stroke width.
GROOVE_DEPTH = 0.48            # Engraving depth, no through-holes in blade.
FIT = 0.30                    # Per-side print clearance on nominal opening.
KEYRING_NOMINAL_D = 4.0        # Nominal keyring opening before clearance.
KEYRING_HOLE_D = KEYRING_NOMINAL_D + 2*FIT  # Actual diameter: 4.6 mm.
KEYRING_WALL = 2.4             # Radial material around the keyring opening.
KEYRING_MOUTH_CHAMFER = 0.30   # Small upper lead-in on the eyelet.
CROSSED_ANGLE_DEG = 29.0        # Each blade's rotation from vertical.
CROSSED_LAYER_RISE = 0.8        # Front blade height difference; still flat-backed.
EXPORT_BOTH = True             # Also export named single/crossed STL + STEP.
STL_TOLERANCE = 0.018          # Absolute chordal error, mm.
STL_ANGLE = 0.10               # Angular tessellation tolerance, radians.
OUTPUT = Path('./output_model.stl')
# -----------------------------------------------------------------
EPS = 0.02


def require(condition, message):
    if not condition:
        raise ValueError(message)


def polygon(points, z, height):
    return (cq.Workplane('XY', origin=(0, 0, z)).polyline(points)
            .close().extrude(height).val())


def disc(x, y, radius, z, height):
    return cq.Solid.makeCylinder(radius, height, cq.Vector(x, y, z))


def stroke(points, width, z, height):
    """Rounded-ended engraving or relief path; analytic capsule segments."""
    pieces = []
    for a, b in zip(points, points[1:]):
        length = hypot(b[0]-a[0], b[1]-a[1])
        if length < 1e-8:
            continue
        pieces.append(cq.Workplane('XY', origin=((a[0]+b[0])/2,
                       (a[1]+b[1])/2, z))
                      .slot2D(length+width, width,
                              degrees(atan2(b[1]-a[1], b[0]-a[0])))
                      .extrude(height).val())
    require(bool(pieces), 'A decorative stroke has no length.')
    return pieces[0].fuse(*pieces[1:]).clean() if len(pieces)>1 else pieces[0]


def blade_wire():
    """Broad swept edge, hooked heel and three concave spine scallops."""
    return (cq.Workplane('XY')
        .moveTo(-5.0, 24.0).lineTo(-6.2, 28.0)
        .threePointArc((-13.0, 30.7), (-10.2, 35.7))
        .threePointArc((-14.0, 37.6), (-18.8, 33.5))
        .threePointArc((-20.1, 32.9), (-20.5, 34.1))
        .threePointArc((-23.0, 56.0), (-10.0, 76.5))
        .threePointArc((-4.1, 81.9), (0.8, 83.7))
        .threePointArc((1.5, 83.7), (1.55, 83.0))
        .threePointArc((0.9, 75.8), (3.8, 68.9))
        .lineTo(6.2, 67.2)
        .threePointArc((6.5, 66.7), (6.0, 66.4))
        .threePointArc((3.8, 61.8), (8.25, 57.7))
        .lineTo(10.6, 56.7)
        .threePointArc((11.0, 56.2), (10.5, 55.8))
        .threePointArc((7.7, 51.3), (11.0, 46.8))
        .lineTo(13.2, 45.0)
        .threePointArc((13.6, 44.4), (13.0, 44.0))
        .threePointArc((10.3, 39.7), (11.6, 35.4))
        .lineTo(9.3, 28.0).lineTo(5.0, 24.0).close())


def blank_unit(scale, extra_height=0.0):
    """Unscaled 2D motif; all visible Z dimensions retain their mm values."""
    thickness = BODY_THICKNESS + extra_height
    # Uniformly resize XY coordinates before building relief and hardware holes.
    # Scaling the planar wire is exact: arcs remain arcs.
    w = blade_wire().wire().val().scale(scale)
    blade = cq.Solid.extrudeLinear(w, [], cq.Vector(0,0,thickness))
    # Bevel only the long swept edge. Scallops retain their full blunt thickness;
    # this also avoids a pinched chamfer at their small rounded ornament tips.
    edge_list=[e for e in cq.Workplane(obj=blade).faces('>Z').edges().vals()
               if e.Length()>16*scale]
    require(len(edge_list)==1,'Unexpected swept-edge selection.')
    blade=blade.chamfer(BLADE_BEVEL,None,edge_list)

    def pts(values):return [(x*scale,y*scale) for x,y in values]
    # A wide continuous tang reaches inside the blade; decorative wraps sit on it.
    handle = polygon(pts([(-3.9,3),(-4.4,7),(-4.0,22),(-5.5,26),
                          (5.5,26),(4.0,22),(4.4,7),(3.9,3)]),0,thickness)
    handle = cq.Workplane(obj=handle).faces('>Z').edges().chamfer(min(.40,scale*.4)).val()
    eye_y = 3.8*scale
    eye_outer = KEYRING_HOLE_D/2 + KEYRING_WALL
    pommel = disc(0,eye_y,eye_outer,0,thickness+GRIP_RELIEF*.45)
    pommel = cq.Workplane(obj=pommel).faces('>Z').edges().chamfer(.25).val()
    body = blade.fuse(handle,pommel).clean()

    # Flaring horned guard and angular mask; all relief grows from the base.
    guard_points = pts([(-5.1,23.0),(-8.9,24.6),(-10.8,28.5),(-10.6,31.0),
                        (-8.8,30.2),(-6.5,27.7),(-4.0,29.3),(-2.7,32.0),
                        (0,30.7),(2.7,32.0),(4.0,29.3),(6.5,27.7),
                        (8.8,30.2),(10.6,31.0),(10.8,28.5),(8.9,24.6),
                        (5.1,23.0),(0,22.0)])
    # Relief is extruded from the bed: every ornamental horn has solid support.
    guard = polygon(guard_points,0,thickness+GUARD_RELIEF)
    guard = cq.Workplane(obj=guard).faces('>Z').edges().chamfer(.26).val()
    body = body.fuse(guard).clean()
    mask = polygon(pts([(-3.4,25.0),(-3.4,28.0),(-1.7,29.0),(0,28.4),
                        (1.7,29.0),(3.4,28.0),(3.4,25.0),(1.4,23.1),
                        (0,22.6),(-1.4,23.1)]),0,thickness+GUARD_RELIEF+.24)
    body = body.fuse(mask).clean()

    # Wrapped grip: diagonal raised bands clipped to the supporting tang.
    grip_clip = polygon(pts([(-3.8,8),(-3.8,22),(3.8,22),(3.8,8)]),
                        0,thickness+GRIP_RELIEF)
    for y in (8.8,12.3,15.8,19.3):
        band = stroke(pts([(-4.5,y-1.1),(4.5,y+1.1)]),max(.85,1.05*scale),
                      0,thickness+GRIP_RELIEF).intersect(grip_clip)
        body = body.fuse(band)

    # Branching engraved ornament, deliberately wider than a 0.4mm nozzle line.
    paths = [
        [(-2.8,33.0),(-5.1,40.0),(-7.0,47.0),(-7.0,54.0),(-5.2,62.0),(-2.2,71.0)],
        [(-5.1,40.0),(-10.5,42.0),(-14.1,40.8)],
        [(-7.0,47.0),(-13.4,47.8),(-17.0,45.5)],
        [(-7.0,54.0),(-13.6,56.0),(-16.4,59.0)],
        [(-5.2,62.0),(-10.3,64.5),(-11.0,68.4)],
        [(-5.1,40.0),(-.2,40.2),(3.5,43.3)],
        [(-7.0,47.0),(-1.2,48.3),(1.6,51.6)],
        [(-7.0,54.0),(-2.3,56.5),(-.2,60.1)],
        [(-5.2,62.0),(-.5,64.4)],
    ]
    cutters = [stroke(pts(path),GROOVE_WIDTH,thickness-GROOVE_DEPTH,
                      GROOVE_DEPTH+EPS) for path in paths]
    # Four angular runic ticks follow the broad cutting edge; decorative, not text.
    for x,y in [(-17.4,48.8),(-17.5,54.5),(-14.8,61.9),(-10.9,70.3)]:
        cutters.append(stroke(pts([(x-1,y-1.4),(x+1,y+1.4)]),GROOVE_WIDTH*.85,
                              thickness-GROOVE_DEPTH,GROOVE_DEPTH+EPS))
        cutters.append(stroke(pts([(x-1.1,y+.8),(x+1.0,y-.9)]),GROOVE_WIDTH*.85,
                              thickness-GROOVE_DEPTH,GROOVE_DEPTH+EPS))
    # Recessed eyes and mouth in the stylized guard mask.
    mask_top = thickness+GUARD_RELIEF+.24
    cutters += [polygon(pts([(-2.5,27.2),(-.65,26.7),(-1.0,25.8),(-2.3,26.0)]),
                        mask_top-GROOVE_DEPTH,GROOVE_DEPTH+EPS),
                polygon(pts([(2.5,27.2),(.65,26.7),(1.0,25.8),(2.3,26.0)]),
                        mask_top-GROOVE_DEPTH,GROOVE_DEPTH+EPS),
                stroke(pts([(-1.3,24.8),(0,24.2),(1.3,24.8)]),GROOVE_WIDTH,
                       mask_top-GROOVE_DEPTH,GROOVE_DEPTH+EPS)]
    body = body.cut(*cutters).clean()

    # Exact hardware opening is made after XY scaling. No assembly clearance guess.
    hole = disc(0,eye_y,KEYRING_HOLE_D/2,-EPS,thickness+GUARD_RELIEF+2)
    mouth_z = thickness+GRIP_RELIEF*.45-KEYRING_MOUTH_CHAMFER
    mouth = cq.Solid.makeCone(KEYRING_HOLE_D/2,KEYRING_HOLE_D/2+KEYRING_MOUTH_CHAMFER,
                             KEYRING_MOUTH_CHAMFER+EPS,cq.Vector(0,eye_y,mouth_z))
    return body.cut(hole,mouth).clean()


def make_variant(style):
    require(style in ('single','crossed'),'STYLE must be single or crossed.')
    # The eyelet keeps its requested physical size while the blade motif scales.
    # Estimate XY extent, then converge before final building expensive ornaments.
    raw = blade_wire().wire().val()
    def extent(scale):
        blade = cq.Solid.extrudeLinear(raw.scale(scale),[],cq.Vector(0,0,1))
        body = blade.fuse(polygon([(-4*scale,3.8*scale),(4*scale,3.8*scale),
                                  (5*scale,26*scale),(-5*scale,26*scale)],0,1),
                          disc(0,3.8*scale,KEYRING_HOLE_D/2+KEYRING_WALL,0,1))
        if style=='crossed':
            pivot=(0,29*scale,0)
            left=body.rotate(pivot,(0,29*scale,1),CROSSED_ANGLE_DEG)
            right=body.mirror('YZ').rotate(pivot,(0,29*scale,1),-CROSSED_ANGLE_DEG)
            body=left.fuse(right)
        bb=body.BoundingBox()
        return max(bb.xlen,bb.ylen)
    lo,hi=.4,2.0
    for _ in range(22):
        mid=(lo+hi)/2
        if extent(mid)<LONG_SIDE_MM:lo=mid
        else:hi=mid
    scale=(lo+hi)/2
    base=blank_unit(scale)
    if style=='crossed':
        pivot=(0,29*scale,0)
        left=base.rotate(pivot,(0,29*scale,1),CROSSED_ANGLE_DEG)
        front=blank_unit(scale,CROSSED_LAYER_RISE)
        right=front.mirror('YZ').rotate(pivot,(0,29*scale,1),-CROSSED_ANGLE_DEG)
        base=left.fuse(right).clean()
    bb=base.BoundingBox()
    return base.translate((-bb.xmin,-bb.ymin,-bb.zmin))


def verify_stl(path, volume):
    data=path.read_bytes()
    require(len(data)>=84,'Truncated STL.')
    count=struct.unpack_from('<I',data,80)[0]
    require(len(data)==84+50*count and count>0,'Invalid STL byte count.')
    edges=defaultdict(list);neighbors=defaultdict(set);signed_volume=0
    for i in range(count):
        vals=struct.unpack_from('<12fH',data,84+50*i)
        require(all(isfinite(x) for x in vals[:12]),'Non-finite STL coordinate.')
        a,b,c=[tuple(round(v,5) for v in vals[j:j+3]) for j in (3,6,9)]
        u=tuple(b[k]-a[k] for k in range(3));v=tuple(c[k]-a[k] for k in range(3))
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        norm=sqrt(sum(x*x for x in n))
        require(norm>1e-9,'Degenerate STL triangle.')
        require(sum(n[k]*vals[k] for k in range(3))>0,'Flipped facet normal.')
        require(n[2]>=-(1/sqrt(2)+.003)*norm or max(a[2],b[2],c[2])<1e-4,
                'An underside exceeds the 45-degree support-free limit.')
        signed_volume+=sum(a[k]*n[k] for k in range(3))/6
        for p,q in ((a,b),(b,c),(c,a)):
            edges[tuple(sorted((p,q)))].append((i,1 if p<q else -1))
    for faces in edges.values():
        require(len(faces)==2 and faces[0][1]+faces[1][1]==0,'Open or non-manifold STL edge.')
        a,b=faces[0][0],faces[1][0];neighbors[a].add(b);neighbors[b].add(a)
    seen=set();todo=[0]
    while todo:
        f=todo.pop()
        if f in seen:continue
        seen.add(f);todo.extend(neighbors[f]-seen)
    require(len(seen)==count,'STL has disconnected shells.')
    require(signed_volume>0 and abs(signed_volume-volume)/volume<.008,'STL volume disagrees with CAD.')
    return count


def export(shape, path, style):
    require(shape.isValid() and len(shape.Solids())==1 and shape.Volume()>0,
            f'{style}: CAD must be one valid solid.')
    check=BOPAlgo_ArgumentAnalyzer();check.SetShape1(shape.wrapped)
    check.SelfInterMode=True;check.Perform()
    require(not check.HasFaulty(),f'{style}: CAD self-intersection.')
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.pending.stl')
    try:
        require(shape.exportStl(str(temp),tolerance=STL_TOLERANCE,
                               angularTolerance=STL_ANGLE,ascii=False,relative=False),
                'STL export failed.')
        triangles=verify_stl(temp,shape.Volume())
        temp.replace(path)
    finally:temp.unlink(missing_ok=True)
    cq.exporters.export(shape,str(path.with_suffix('.step')))
    vertices,faces=shape.tessellate(.035,.12)
    bb=shape.BoundingBox()
    result={'style':style,'size_mm':[round(bb.xlen,3),round(bb.ylen,3),round(bb.zlen,3)],
            'volume_cm3':round(shape.Volume()/1000,3),'keyring_hole_mm':KEYRING_HOLE_D,
            'triangles':triangles,'single_solid':True,'watertight':True,
            'body_thickness_mm':BODY_THICKNESS,'guard_relief_mm':GUARD_RELIEF,
            'grip_relief_mm':GRIP_RELIEF,'groove_depth_mm':GROOVE_DEPTH,
            'crossed_layer_rise_mm':CROSSED_LAYER_RISE if style=='crossed' else 0,
            'checks':['CAD validity','CAD self-intersection','STL edge manifold',
                      'STL single shell','positive signed volume','facet normals',
                      '45-degree underside check'],
            'vertices':[[v.x,v.y,v.z] for v in vertices],'faces':[list(f) for f in faces]}
    path.with_suffix('.mesh.json').write_text(json.dumps(result,separators=(',',':')))
    print(f'{style}: {result["size_mm"]} mm; {triangles:,} triangles; '
          f'{result["volume_cm3"]} cm3; one watertight part.',flush=True)
    return result


def main():
    require(STYLE in ('single','crossed'),'STYLE must be single or crossed.')
    require(65<=LONG_SIDE_MM<=120,'Use LONG_SIDE_MM 65–120; smaller relief needs redesign.')
    require(BODY_THICKNESS>=3.0 and 0<BLADE_BEVEL<=.9,'Check thickness and bevel.')
    require(.6<=GUARD_RELIEF<=2 and .4<=GRIP_RELIEF<=1,'Check guard/grip relief height.')
    require(0<=FIT<=.5,'Use FIT between 0 and 0.5 mm per side.')
    require(0<GROOVE_DEPTH<BODY_THICKNESS/3 and GROOVE_WIDTH>=.65,'Check engraving dimensions.')
    require(3.6<=KEYRING_HOLE_D<=6 and KEYRING_WALL>=2.2,'Check keyring diameter and wall.')
    require(0<=CROSSED_LAYER_RISE<=1.5,'Use CROSSED_LAYER_RISE between 0 and 1.5 mm.')
    require(20<=CROSSED_ANGLE_DEG<=38,'Use a crossed angle between 20 and 38 degrees.')
    results=[]
    for style in (['single','crossed'] if EXPORT_BOTH else [STYLE]):
        shape=make_variant(style)
        path=OUTPUT.with_name(style+'_blade'+('s' if style=='crossed' else '')+'.stl') if EXPORT_BOTH else OUTPUT
        result=export(shape,path,style);results.append({k:v for k,v in result.items() if k not in ('vertices','faces')})
        if EXPORT_BOTH and style==STYLE:
            for suffix in ('.stl','.step','.mesh.json'):
                OUTPUT.with_suffix(suffix).write_bytes(path.with_suffix(suffix).read_bytes())
    OUTPUT.with_name('validation.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
