"""Generate six independent, parameterized CadQuery product scripts."""
from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parent
original = (ROOT.parent / 'hero_enclosure.py').read_text()
tree = ast.parse(original)
mesh_check = next(ast.get_source_segment(original, n) for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == 'verify_stl')

HEADER = '''#!/usr/bin/env python3
"""{title} — all dimensions in millimeters.

Install: python -m pip install cadquery==2.6.1
Run from this folder: python model.py
Outputs: ./output_model.stl, ./output_model.step, ./preview_mesh.json
STL contains the printable parts arranged flat on the bed; import as mm.
STEP shows their assembly. Reference devices are excluded from both exports.
Nominal clearances are modeled explicitly. Qualify fit on your printer.
These are original functional designs; no load, ingress, or safety rating.

{notes}
"""
from collections import defaultdict
from math import isfinite, sqrt, tan, radians
from pathlib import Path
import json
import struct
import cadquery as cq
from OCP.BOPAlgo import BOPAlgo_ArgumentAnalyzer

# ---------------- CUSTOMIZABLE PARAMETERS: mm ----------------
{params}
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
PRODUCT_ID = {pid!r}
PRODUCT_TITLE = {title!r}
PRODUCT_CATEGORY = {category!r}

'''

COMMON = '''
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

'''

PRODUCTS = [
dict(pid='b2b_sensor_plate', title='Slotted sensor plate', category='B2B',
     use='Adjustable mounting for cylindrical sensors.',
     buyer='Machine builders and automation integrators',
     customize='Sensor diameter · slot travel · hole spacing',
     hardware='Two M5 bolts and washers; sensor mounting nuts',
     print_note='PETG or ASA · flat on bed · no supports',
     notes='Uses the sensor manufacturer\'s mounting nuts. Printed slot diameter includes\n0.25 mm radial clearance. Qualify clamp torque and environmental suitability.',
     params='''LENGTH = 90.0
WIDTH = 44.0
THICKNESS = 8.0
CORNER_R = 6.0
SENSOR_D = 18.0         # Nominal cylindrical sensor diameter.
COLLAR_D = 30.0         # Flat seat around the sensor aperture.
COLLAR_HEIGHT = 2.0
MOUNT_SCREW_D = 5.0
SLOT_LENGTH = 16.0      # Overall slot length, including rounded ends.
MOUNT_X = 32.0          # Two slot centers at +/- this X coordinate.
EDGE_CHAMFER = 0.4''',
     build='''def build():
    hole_r = SENSOR_D/2 + FIT
    require(THICKNESS >= 4 and COLLAR_HEIGHT > EDGE_CHAMFER > 0, 'Invalid plate thickness.')
    require(COLLAR_D/2-hole_r >= 3 and COLLAR_D+4 < WIDTH, 'Insufficient collar material.')
    require(MOUNT_X-(MOUNT_SCREW_D/2+FIT) > COLLAR_D/2+3, 'Slot collides with collar.')
    require(LENGTH/2-MOUNT_X-(MOUNT_SCREW_D/2+FIT) >= 3
            and WIDTH/2-SLOT_LENGTH/2 >= 3, 'Insufficient mounting-slot edge distance.')
    plate = rounded_box(LENGTH, WIDTH, THICKNESS, CORNER_R)
    plate = plate.faces('>Z').edges().chamfer(EDGE_CHAMFER)
    collar = cylinder(0, 0, THICKNESS-EPS, COLLAR_D/2, COLLAR_HEIGHT+EPS)
    collar = collar.faces('>Z').edges().chamfer(EDGE_CHAMFER)
    plate = plate.union(collar).cut(cylinder(0, 0, -EPS, hole_r,
                                           THICKNESS+COLLAR_HEIGHT+2*EPS))
    for x in (-MOUNT_X, MOUNT_X):
        plate = plate.cut(slot(x, 0, -EPS, SLOT_LENGTH, MOUNT_SCREW_D+2*FIT,
                              THICKNESS+2*EPS, 90))
    plate = solid(plate)
    sensor = solid(cylinder(0, 0, -8, SENSOR_D/2, THICKNESS+COLLAR_HEIGHT+24))
    no_collision(plate, sensor, 'Sensor reference interferes with its aperture.')
    return [('Plate', plate)], [('Plate', plate)], [('Sensor_reference_only', sensor)]
'''),
dict(pid='b2b_pcb_cradle', title='PCB inspection cradle', category='B2B',
     use='Holds a board upright for inspection and light bench work.',
     buyer='Electronics assembly and repair benches',
     customize='PCB thickness · edge engagement · base width',
     hardware='None; optional adhesive feet',
     print_note='PETG · two independent supports · no supports',
     notes='Prints two identical movable cradles. The board rests on its bottom edge.\nKeep components clear of the slotted edge. This is a passive holder, not a clamp.',
     params='''BASE_LENGTH = 48.0     # Width across the PCB plane, for stability.
BASE_WIDTH = 24.0       # Length along the PCB bottom edge.
BASE_THICKNESS = 4.0
HEIGHT = 28.0
TOWER_WIDTH = 14.0
PCB_THICKNESS = 1.6
EDGE_ENGAGEMENT = 8.0
BOARD_WIDTH = 90.0      # Reference board only; excluded from STL/STEP.
BOARD_HEIGHT = 60.0
SUPPORT_SPACING = 60.0  # Displayed center-to-center spacing; supports are movable.''',
     build='''def build():
    gap = PCB_THICKNESS+2*FIT
    require(BASE_LENGTH > TOWER_WIDTH+10 and BASE_WIDTH >= 15, 'Base is too small.')
    require(TOWER_WIDTH-gap >= 6 and EDGE_ENGAGEMENT > 0
            and HEIGHT-EDGE_ENGAGEMENT > BASE_THICKNESS+4, 'Insufficient slot material.')
    require(SUPPORT_SPACING > BASE_WIDTH
            and BOARD_WIDTH >= SUPPORT_SPACING+BASE_WIDTH, 'Invalid reference board spacing.')
    x, t = BASE_LENGTH/2, TOWER_WIDTH/2
    points = [(-x,0),(x,0),(x,BASE_THICKNESS),(t,HEIGHT-6),
              (t,HEIGHT),(-t,HEIGHT),(-t,HEIGHT-6),(-x,BASE_THICKNESS)]
    cradle = (cq.Workplane('XZ', origin=(0,BASE_WIDTH/2,0)).polyline(points)
              .close().extrude(BASE_WIDTH))
    cradle = cradle.cut(rounded_box(gap, BASE_WIDTH+2*EPS, EDGE_ENGAGEMENT+EPS,
                                   z=HEIGHT-EDGE_ENGAGEMENT))
    cradle = solid(cradle)
    display = [('Cradle_A', cradle.translate((0,-SUPPORT_SPACING/2,0))),
               ('Cradle_B', cradle.translate((0,SUPPORT_SPACING/2,0)))]
    board = solid(rounded_box(PCB_THICKNESS, BOARD_WIDTH, BOARD_HEIGHT,
                             z=HEIGHT-EDGE_ENGAGEMENT))
    for _, part in display:
        no_collision(part, board, 'PCB reference interferes with its slots.')
    return [('Cradle_A',cradle),('Cradle_B',cradle)], display, [('PCB_reference_only',board)]
'''),
dict(pid='b2b_assembly_nest', title='Custom assembly nest', category='B2B',
     use='Repeatable positioning for assembly, inspection, and labeling.',
     buyer='Small-batch manufacturers and quality teams',
     customize='Part envelope · corner radius · mounting pattern',
     hardware='Four M4 bolts and washers, if mounted',
     print_note='PETG · open pocket upwards · no supports',
     notes='Locates a rounded rectangular workpiece with 0.25 mm side clearance.\nFinger scallops and floor access holes assist removal. Intended for light assembly\nand inspection; it is not a rated machining workholding fixture.',
     params='''BASE_LENGTH = 108.0
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
ENTRY_CHAMFER = 0.5''',
     build='''def build():
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
'''),
dict(pid='b2c_cable_rail', title='Cable landing rail', category='B2C',
     use='Keeps charging leads at the desk edge with open-access cable slots.',
     buyer='Home offices, gaming desks, and shared workspaces',
     customize='Cable diameters · channel count · spacing',
     hardware='Adhesive tape or two M3 mounting screws',
     print_note='PLA or PETG · flat on bed · no supports',
     notes='Mount the rear flange on the desk with the slotted front projecting over\nthe edge. Cable slots remain open for lateral removal; they are not snap clamps.\nConnector bodies must be larger than the corresponding cable slot.',
     params='''CABLE_DIAMETERS = (3.0, 3.0, 4.0, 4.0, 5.0, 6.0)
PITCH = 18.0
END_MARGIN = 20.0
DEPTH = 44.0
HEIGHT = 8.0
CORNER_R = 5.0
SLOT_CENTER_Y = -10.0   # Front is negative Y; rear mounting flange is positive Y.
MOUNT_Y = 10.0
MOUNT_SCREW_D = 3.0
MOUNT_HOLES = True
TOP_CHAMFER = 0.4''',
     build='''def build():
    require(len(CABLE_DIAMETERS) >= 2 and all(isfinite(d) and d>0 for d in CABLE_DIAMETERS),
            'Provide at least two positive cable diameters.')
    require(PITCH > max(CABLE_DIAMETERS)+2*FIT+4 and HEIGHT >= 4, 'Cable lands are too thin.')
    require(-DEPTH/2 < SLOT_CENTER_Y < -max(CABLE_DIAMETERS)/2-2
            and END_MARGIN >= 12, 'Invalid slot placement or end margin.')
    require(MOUNT_Y > 3 and MOUNT_Y+MOUNT_SCREW_D/2+FIT+3 < DEPTH/2,
            'Mounting holes lack rear edge distance.')
    length = (len(CABLE_DIAMETERS)-1)*PITCH+2*END_MARGIN
    rail = rounded_box(length,DEPTH,HEIGHT,CORNER_R)
    for i,d in enumerate(CABLE_DIAMETERS):
        x = (i-(len(CABLE_DIAMETERS)-1)/2)*PITCH
        r = d/2+FIT
        tool = cylinder(x,SLOT_CENTER_Y,-EPS,r,HEIGHT+2*EPS)
        reach = SLOT_CENTER_Y+DEPTH/2+EPS
        opening = rounded_box(2*r,reach,HEIGHT+2*EPS,z=-EPS).translate(
            (x,(-DEPTH/2-EPS+SLOT_CENTER_Y)/2,0))
        rail = rail.cut(tool.union(opening))
    if MOUNT_HOLES:
        for x in (-length/2+10,length/2-10):
            rail = rail.cut(cylinder(x,MOUNT_Y,-EPS,MOUNT_SCREW_D/2+FIT,HEIGHT+2*EPS))
    require(0 < TOP_CHAMFER < HEIGHT/4, 'Invalid edge chamfer.')
    rail = solid(rail.faces('>Z').edges().chamfer(TOP_CHAMFER))
    return [('Rail',rail)],[('Rail',rail)],[]
'''),
dict(pid='b2c_divider_tray', title='Desk valet with divider', category='B2C',
     use='Separates daily carry, pens, and small tech accessories.',
     buyer='Desk setups, gift buyers, and branded office kits',
     customize='Tray size · divider position · compartment sizes',
     hardware='None; divider drops into open grooves',
     print_note='PLA or PETG · tray upright, divider flat · no supports',
     notes='The removable divider uses 0.25 mm clearance on each slot face and end.\nIt rests on the tray floor; no adhesive, snap flexure, or printed threads.',
     params='''LENGTH = 128.0
WIDTH = 84.0
HEIGHT = 20.0
WALL = 3.0
FLOOR = 2.4
CORNER_R = 8.0
DIVIDER_THICKNESS = 2.4
DIVIDER_X = 22.0        # Divider position along tray length.
GROOVE_DEPTH = 1.2      # Engagement cut into the side walls.
DIVIDER_TOP_GAP = 0.5
RIM_CHAMFER = 0.3''',
     build='''def build():
    il,iw = LENGTH-2*WALL,WIDTH-2*WALL
    require(FLOOR >= 2 and WALL >= 2.4 and HEIGHT > FLOOR+5, 'Invalid tray wall/floor.')
    require(CORNER_R > WALL and 0 < GROOVE_DEPTH < WALL-1.6, 'Invalid corner or groove depth.')
    require(FIT < GROOVE_DEPTH and DIVIDER_THICKNESS >= 1.6, 'Invalid divider fit.')
    require(abs(DIVIDER_X)+DIVIDER_THICKNESS/2+FIT < il/2-(CORNER_R-WALL)-2,
            'Divider grooves must remain on the straight side walls.')
    require(0 < RIM_CHAMFER < (WALL-GROOVE_DEPTH)/2 and DIVIDER_TOP_GAP > 0,
            'Invalid rim chamfer or divider headroom.')
    tray = rounded_box(LENGTH,WIDTH,HEIGHT,CORNER_R)
    tray = tray.cut(rounded_box(il,iw,HEIGHT-FLOOR+EPS,CORNER_R-WALL,FLOOR))
    tray = tray.faces('>Z').edges().chamfer(RIM_CHAMFER)
    groove = rounded_box(DIVIDER_THICKNESS+2*FIT,iw+2*GROOVE_DEPTH,
                          HEIGHT-FLOOR+EPS,z=FLOOR).translate((DIVIDER_X,0,0))
    tray = solid(tray.cut(groove))
    dh = HEIGHT-FLOOR-DIVIDER_TOP_GAP
    span = iw+2*(GROOVE_DEPTH-FIT)
    divider = solid(rounded_box(dh,span,DIVIDER_THICKNESS))
    assembled = divider.rotate((0,0,0),(0,1,0),90).translate(
        (DIVIDER_X-DIVIDER_THICKNESS/2,0,FLOOR+dh/2))
    no_collision(tray,assembled,'Divider interferes with its receiving grooves.')
    return [('Tray',tray),('Divider',divider)],[('Tray',tray),('Divider',assembled)],[]
'''),
dict(pid='b2c_phone_stand', title='CablePass phone stand', category='B2C',
     use='Supports a phone with an open frame and charging-cable passage.',
     buyer='Home desks, bedside setups, and reception counters',
     customize='Viewing angle · device width · case thickness',
     hardware='None; optional felt contact pads',
     print_note='PLA or PETG · print on its side as exported · no supports',
     notes='One-piece stand prints on its broad side. The charging passage has 45-degree\nroofs in that orientation. SLOT_CLEARANCE is added to the nominal case thickness.\nTest phone stability, charging-plug access, and contact padding before use.',
     params='''BASE_DEPTH = 80.0
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
SLOT_CLEARANCE = 0.5    # Total additional case clearance, independent of FIT.''',
     build='''def build():
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
'''),
]

for product in PRODUCTS:
    directory = ROOT / product['pid']
    directory.mkdir(exist_ok=True)
    script = HEADER.format(**product) + COMMON + mesh_check + '\n\n' + product['build']
    script += "\n\nif __name__ == '__main__':\n    write_outputs(*build())\n"
    (directory / 'model.py').write_text(script)
(ROOT / 'catalog.json').write_text(json.dumps([{k:v for k,v in p.items()
    if k not in ('params','build')} for p in PRODUCTS], indent=2))
print('Generated 6 self-contained CadQuery scripts.')
