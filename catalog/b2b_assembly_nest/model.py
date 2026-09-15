#!/usr/bin/env python3
"""Custom assembly nest — all dimensions in millimeters.

Install: python -m pip install cadquery==2.6.1
Run from this folder: python model.py
Outputs: ./output_model.stl, ./output_model.step, ./preview_mesh.json
STL contains the printable parts arranged flat on the bed; import as mm.
STEP shows their assembly. Reference devices are excluded from both exports.
Nominal clearances are modeled explicitly. Qualify fit on your printer.
These are original functional designs; no load, ingress, or safety rating.

Locates a rounded rectangular workpiece with 0.25 mm side clearance.
Finger scallops and floor access holes assist removal. Intended for light assembly
and inspection; it is not a rated machining workholding fixture.
"""
from collections import defaultdict
from math import isfinite, sqrt, tan, radians
from pathlib import Path
import json
import struct
import cadquery as cq
from OCP.BOPAlgo import BOPAlgo_ArgumentAnalyzer

# ---------------- CUSTOMIZABLE PARAMETERS: mm ----------------
BASE_LENGTH = 108.0
BASE_WIDTH = 72.0
FLOOR = 4.0
BASE_CORNER_R = 6.0
PART_LENGTH = 64.0
PART_WIDTH = 32.0
PART_CORNER_R = 3.0
POCKET_DEPTH = 10.0
NEST_WALL = 4.0
FINGER_RADIUS = 7.0
SCALLOP_FLOOR = 2.0     # Wall height retained above the floor at each scallop.
MOUNT_MARGIN = 9.0
MOUNT_SCREW_D = 4.0
EJECT_HOLE_D = 8.0
ENTRY_CHAMFER = 0.5
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
PRODUCT_ID = 'b2b_assembly_nest'
PRODUCT_TITLE = 'Custom assembly nest'
PRODUCT_CATEGORY = 'B2B'


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
    il, iw = PART_LENGTH+2*FIT, PART_WIDTH+2*FIT
    ol, ow = il+2*NEST_WALL, iw+2*NEST_WALL
    require(FLOOR >= 3 and NEST_WALL >= 3 and ENTRY_CHAMFER < NEST_WALL/2,
            'Insufficient nest thickness.')
    require(0 < SCALLOP_FLOOR < POCKET_DEPTH and 0 < FINGER_RADIUS < PART_WIDTH/3,
            'Invalid finger access dimensions.')
    require(BASE_LENGTH > ol+12 and BASE_WIDTH > ow+12, 'Base must extend past the nest.')
    require(MOUNT_MARGIN > MOUNT_SCREW_D/2+FIT+2, 'Mounting edge distance too small.')
    require(BASE_WIDTH/2-MOUNT_MARGIN-(MOUNT_SCREW_D/2+FIT) > ow/2+2,
            'Mounting holes are too close to the nest.')
    require(0 < EJECT_HOLE_D < PART_WIDTH/2 and PART_LENGTH/4 > EJECT_HOLE_D+2,
            'Ejector holes overlap or weaken the floor.')
    base = rounded_box(BASE_LENGTH, BASE_WIDTH, FLOOR, BASE_CORNER_R)
    ring = rounded_box(ol, ow, POCKET_DEPTH+EPS, PART_CORNER_R+FIT+NEST_WALL, FLOOR-EPS)
    ring = ring.cut(rounded_box(il,iw,POCKET_DEPTH+3*EPS,PART_CORNER_R+FIT,FLOOR-2*EPS))
    ring = ring.faces('>Z').edges().chamfer(ENTRY_CHAMFER)
    base = base.union(ring)
    for x in (-ol/2, ol/2):
        base = base.cut(cylinder(x,0,FLOOR+SCALLOP_FLOOR,FINGER_RADIUS,
                                 POCKET_DEPTH-SCALLOP_FLOOR+EPS))
    for sx in (-1,1):
        for sy in (-1,1):
            base = base.cut(cylinder(sx*(BASE_LENGTH/2-MOUNT_MARGIN),
                                     sy*(BASE_WIDTH/2-MOUNT_MARGIN),-EPS,
                                     MOUNT_SCREW_D/2+FIT,FLOOR+2*EPS))
    for x in (-PART_LENGTH/4,0,PART_LENGTH/4):
        base = base.cut(cylinder(x,0,-EPS,EJECT_HOLE_D/2,FLOOR+2*EPS))
    base = solid(base)
    reference = solid(rounded_box(PART_LENGTH,PART_WIDTH,POCKET_DEPTH+7,PART_CORNER_R,FLOOR))
    no_collision(base,reference,'Workpiece reference interferes with the locating pocket.')
    return [('Nest',base)],[('Nest',base)],[('Workpiece_reference_only',reference)]


if __name__ == '__main__':
    write_outputs(*build())
