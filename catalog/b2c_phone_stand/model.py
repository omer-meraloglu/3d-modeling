#!/usr/bin/env python3
"""CablePass phone stand — all dimensions in millimeters.

Install: python -m pip install cadquery==2.6.1
Run from this folder: python model.py
Outputs: ./output_model.stl, ./output_model.step, ./preview_mesh.json
STL contains the printable parts arranged flat on the bed; import as mm.
STEP shows their assembly. Reference devices are excluded from both exports.
Nominal clearances are modeled explicitly. Qualify fit on your printer.
These are original functional designs; no load, ingress, or safety rating.

One-piece stand prints on its broad side. The charging passage has 45-degree
roofs in that orientation. SLOT_CLEARANCE is added to the nominal case thickness.
Test phone stability, charging-plug access, and contact padding before use.
"""
from collections import defaultdict
from math import isfinite, sqrt, tan, radians
from pathlib import Path
import json
import struct
import cadquery as cq
from OCP.BOPAlgo import BOPAlgo_ArgumentAnalyzer

# ---------------- CUSTOMIZABLE PARAMETERS: mm ----------------
BASE_DEPTH = 80.0
HEIGHT = 88.0
STAND_WIDTH = 58.0
VIEW_ANGLE_DEG = 63.0   # Phone backrest angle from horizontal.
FLOOR_THICKNESS = 4.4
FRAME_WALL = 4.4        # Normal wall thickness around the open frame.
SEAT_HEIGHT = 10.0
CASE_THICKNESS = 9.5
LIP_THICKNESS = 7.0
LIP_RISE = 10.0
BACK_RIB = 8.0
CHARGING_DIAGONAL = 18.0
SLOT_CLEARANCE = 0.5    # Total additional case clearance, independent of FIT.
FIT = 0.25                # Clearance PER SIDE, not total clearance.
BED_X = 220.0
BED_Y = 220.0
BED_MARGIN = 5.0
PART_GAP = 8.0
STL_TOLERANCE = 0.02      # Absolute chordal tolerance, mm.
STL_ANGLE = 0.10          # Radians.
OUTPUT = Path('./output_model.stl')
# ------------------------------------------------------------
EPS = 0.01               # Boolean overlap only; does not change fits.
ROOT2 = sqrt(2.0)
PRODUCT_ID = 'b2c_phone_stand'
PRODUCT_TITLE = 'CablePass phone stand'
PRODUCT_CATEGORY = 'B2C'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rounded_box(length, width, height, radius=0.0, z=0.0):
    require(min(length, width, height) > 0, 'Dimensions must be positive.')
    require(0 <= radius < min(length, width)/2, 'Corner radius is too large.')
    obj = cq.Workplane('XY', origin=(0, 0, z)).box(
        length, width, height, centered=(True, True, False))
    return obj.edges('|Z').fillet(radius) if radius else obj


def cylinder(x, y, z, radius, height):
    require(radius > 0 and height > 0, 'Cylinder dimensions must be positive.')
    return cq.Workplane('XY', origin=(x, y, z)).circle(radius).extrude(height)


def slot(x, y, z, length, diameter, height, angle=0):
    require(length >= diameter > 0 and height > 0, 'Invalid slot dimensions.')
    return (cq.Workplane('XY', origin=(x, y, z)).slot2D(length, diameter, angle)
            .extrude(height))


def solid(obj):
    return obj.clean().val() if isinstance(obj, cq.Workplane) else obj.clean()


def validate_part(name, part):
    require(part.isValid() and len(part.Solids()) == 1 and part.Volume() > 0,
            f'{name}: invalid, inverted or disconnected solid.')
    check = BOPAlgo_ArgumentAnalyzer()
    check.SetShape1(part.wrapped)
    check.SelfInterMode = True
    check.Perform()
    require(not check.HasFaulty(), f'{name}: self-intersecting CAD geometry.')


def no_collision(a, b, message):
    require(a.intersect(b).Volume() < 1e-5, message)


def mesh_data(name, part):
    vertices, faces = part.tessellate(0.25, 0.30)
    return {'name': name,
            'vertices': [[round(v.x, 3), round(v.y, 3), round(v.z, 3)] for v in vertices],
            'faces': [list(f) for f in faces]}


def write_outputs(parts, display, references=()):
    values = [v for k, v in globals().items() if k.isupper()
              and isinstance(v, (int, float)) and not isinstance(v, bool)]
    require(all(isfinite(v) for v in values), 'Parameters must be finite.')
    require(min(FIT, BED_X, BED_Y, PART_GAP, STL_TOLERANCE, STL_ANGLE) > 0
            and BED_MARGIN >= 0, 'Invalid fit, bed or export parameters.')
    positioned = []
    x = y = BED_MARGIN
    row = 0.0
    for name, shape in parts:
        validate_part(name, shape)
        bb = shape.BoundingBox()
        if x + bb.xlen > BED_X - BED_MARGIN:
            x, y, row = BED_MARGIN, y + row + PART_GAP, 0.0
        require(bb.xlen + 2*BED_MARGIN <= BED_X
                and y + bb.ylen <= BED_Y - BED_MARGIN,
                'Parts exceed BED_X/BED_Y; increase bed size or reduce dimensions.')
        positioned.append(shape.translate((x-bb.xmin, y-bb.ymin, -bb.zmin)))
        x += bb.xlen + PART_GAP
        row = max(row, bb.ylen)
    plate = cq.Compound.makeCompound(positioned)
    require(plate.isValid() and len(plate.Solids()) == len(parts), 'Invalid print layout.')
    for i, (_, a) in enumerate(display):
        for _, b in display[i+1:]:
            no_collision(a, b, 'Assembled printable parts intersect.')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix('.pending.stl')
    try:
        require(plate.exportStl(str(temp), tolerance=STL_TOLERANCE,
                               angularTolerance=STL_ANGLE, ascii=False, relative=False),
                'STL export failed.')
        triangles = verify_stl(temp, len(parts), plate.Volume())
        temp.replace(OUTPUT)
    finally:
        temp.unlink(missing_ok=True)
    assembly = cq.Assembly(name=PRODUCT_ID)
    for name, part in display:
        assembly.add(part, name=name)
    assembly.export(str(OUTPUT.with_suffix('.step')))
    bb = plate.BoundingBox()
    manifest = {'id': PRODUCT_ID, 'title': PRODUCT_TITLE, 'category': PRODUCT_CATEGORY,
                'volume_cm3': round(plate.Volume()/1000, 2), 'parts': len(parts),
                'triangles': triangles, 'footprint_mm': [round(bb.xlen, 1), round(bb.ylen, 1)],
                'clearance_per_side_mm': FIT,
                'checks': ['valid CAD solids', 'CAD self-intersection', 'assembly collision',
                           'watertight STL', 'facet normals', '45-degree overhang limit'],
                'meshes': [mesh_data(n, p) for n, p in display],
                'references': [mesh_data(n, p) for n, p in references]}
    OUTPUT.with_name('preview_mesh.json').write_text(json.dumps(manifest, separators=(',', ':')))
    print(f'{PRODUCT_ID}: {len(parts)} watertight part(s), {triangles:,} triangles, '
          f'{plate.Volume()/1000:.1f} cm³, footprint {bb.xlen:.1f} × {bb.ylen:.1f} mm', flush=True)

def verify_stl(path, expected_shells, expected_volume):
    """Check exported triangles, edge incidence, winding and positive shell volumes."""
    data = path.read_bytes()
    require(len(data) >= 84, "Truncated STL.")
    count = struct.unpack_from("<I", data, 80)[0]
    require(len(data) == 84 + 50 * count and count > 0, "Invalid binary STL size.")
    edges, neighbors, volumes = defaultdict(list), defaultdict(set), []
    for face in range(count):
        values = struct.unpack_from("<12fH", data, 84 + 50 * face)
        require(all(isfinite(v) for v in values[:12]), "Non-finite STL coordinates.")
        # Weld only at 1e-5 mm for topology checks; do not alter exported vertices.
        a, b, c = [tuple(round(v, 5) for v in values[j:j + 3]) for j in (3, 6, 9)]
        u, v = tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))
        cross = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2], u[0]*v[1] - u[1]*v[0])
        require(sum(t*t for t in cross) > 1e-16, "Degenerate STL triangle.")
        require(sum(cross[i] * values[i] for i in range(3)) > 0, "Flipped STL facet normal.")
        require(cross[2] >= -(1 / ROOT2 + 1e-4) * sqrt(sum(t*t for t in cross)) or
                max(a[2], b[2], c[2]) < 1e-4, "Unsupported overhang exceeds 45 degrees.")
        volumes.append(sum(a[i] * cross[i] for i in range(3)) / 6)
        for p, q in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((p, q)))].append((face, 1 if p < q else -1))
    for incident in edges.values():
        require(len(incident) == 2 and incident[0][1] + incident[1][1] == 0,
                "STL has an open/non-manifold edge or inconsistent winding.")
        i, j = incident[0][0], incident[1][0]
        neighbors[i].add(j)
        neighbors[j].add(i)
    remaining, shell_volumes = set(range(count)), []
    while remaining:
        stack, total = [remaining.pop()], 0.0
        while stack:
            face = stack.pop()
            total += volumes[face]
            for neighbor in neighbors[face]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        require(total > 0, "An STL shell is inverted or has zero volume.")
        shell_volumes.append(total)
    require(len(shell_volumes) == expected_shells, "Unexpected STL shell count.")
    require(abs(sum(shell_volumes) - expected_volume) / expected_volume < 0.005,
            "STL volume differs from CAD volume by more than 0.5%.")
    return count

def build():
    require(50 <= VIEW_ANGLE_DEG <= 72 and STAND_WIDTH >= 35, 'Invalid viewing angle or width.')
    require(min(FLOOR_THICKNESS,LIP_THICKNESS,BACK_RIB,FRAME_WALL) >= 4 and CASE_THICKNESS > 0
            and SLOT_CLEARANCE >= 0, 'Insufficient stand thickness.')
    require(HEIGHT > SEAT_HEIGHT+35 and LIP_RISE > 0, 'Invalid stand height.')
    seat_x = LIP_THICKNESS+CASE_THICKNESS+SLOT_CLEARANCE
    top_x = seat_x+(HEIGHT-SEAT_HEIGHT)/tan(radians(VIEW_ANGLE_DEG))
    require(top_x+BACK_RIB < BASE_DEPTH-4, 'Base is too short for this backrest angle.')
    require(0 < CHARGING_DIAGONAL < min(STAND_WIDTH-12,2*SEAT_HEIGHT),
            'Charging passage is too large.')
    outline = [(0,0),(BASE_DEPTH,0),(top_x+BACK_RIB,HEIGHT),(top_x,HEIGHT),
               (seat_x,SEAT_HEIGHT),(LIP_THICKNESS,SEAT_HEIGHT),
               (LIP_THICKNESS,SEAT_HEIGHT+LIP_RISE),(0,SEAT_HEIGHT+LIP_RISE)]
    frame = cq.Workplane('XY').polyline(outline).close().extrude(STAND_WIDTH)
    front_slope = 1/tan(radians(VIEW_ANGLE_DEG))
    rear_slope = (top_x+BACK_RIB-BASE_DEPTH)/HEIGHT
    front_intercept = seat_x-SEAT_HEIGHT*front_slope+FRAME_WALL*sqrt(1+front_slope**2)
    rear_intercept = BASE_DEPTH-FRAME_WALL*sqrt(1+rear_slope**2)
    intersection_z = (rear_intercept-front_intercept)/(front_slope-rear_slope)
    top_z = min(HEIGHT-FRAME_WALL, intersection_z-2)
    require(top_z > FLOOR_THICKNESS+15, 'Frame walls leave no usable opening.')
    window = [(front_intercept+front_slope*FLOOR_THICKNESS,FLOOR_THICKNESS),
              (rear_intercept+rear_slope*FLOOR_THICKNESS,FLOOR_THICKNESS),
              (rear_intercept+rear_slope*top_z,top_z),
              (front_intercept+front_slope*top_z,top_z)]
    cut = cq.Workplane('XY',origin=(0,0,-EPS)).polyline(window).close().extrude(STAND_WIDTH+2*EPS)
    frame = frame.cut(cut)
    d = CHARGING_DIAGONAL/2
    charging = (cq.Workplane('YZ',origin=(-EPS,SEAT_HEIGHT,STAND_WIDTH/2))
                .polyline([(-d,0),(0,d),(d,0),(0,-d)]).close().extrude(seat_x+2*EPS))
    frame = solid(frame.cut(charging))
    upright = frame.rotate((0,0,0),(1,0,0),90).translate((0,STAND_WIDTH/2,0))
    return [('Stand',frame)],[('Stand',upright)],[]


if __name__ == '__main__':
    write_outputs(*build())
