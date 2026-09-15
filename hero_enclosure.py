#!/usr/bin/env python3
"""B2B configurable PCB/sensor enclosure; millimeters throughout.

Install: python -m pip install cadquery==2.6.1
Run:     python hero_enclosure.py

output_model.stl contains TWO separate, watertight parts on one print plate:
base upright, lid exterior-face down. No supports or printed threads required.
STL carries no units: import it as millimeters. STEP uses millimeters.
Assembly: flip the lid 180 degrees about X; seat its locating tongue in the base.

Hardware for the default configuration:
  8 x M3 heat-set inserts, 5.0 mm long, requiring a 4.2 mm installation bore;
  4 x M3x8 button-head lid screws; 4 x M3x6 PCB screws;
  optional 4 x M4 mounting screws with washers, length to suit the substrate.
Use the insert supplier's bore specification; insert dimensions are NOT universal.
PCB: 90 x 50 x 1.6, four M3 clearance holes on an 82 x 42 pattern.

Starting print settings: PETG, 0.4 mm nozzle, 0.2 mm layers, 5 perimeters,
6 top/bottom layers, 30% infill; solid infill around mounting tabs and inserts.
Qualify physical fit and load capacity on your printer before batch production.
Geometry/export checks passed with CadQuery 2.6.1 for the default configuration
and a 100 x 74 mm variant without tabs/vents and with 0.30 mm tongue clearance.
"""

from collections import defaultdict
from math import isfinite, sqrt
from pathlib import Path
import struct

import cadquery as cq
from OCP.BOPAlgo import BOPAlgo_ArgumentAnalyzer


# ---------------------- PRODUCT PARAMETERS: mm ----------------------
LENGTH = 120.0                  # Base exterior X, excluding mounting tabs.
WIDTH = 84.0                    # Base exterior Y.
HEIGHT = 34.0                   # Base height; assembled height = HEIGHT + LID.
WALL = 2.4
FLOOR = 2.8
LID = 3.0
OUTER_CORNER = 4.0              # Leg length of the exterior 45-degree corners.
INNER_CORNER = 14.0             # Larger cavity corners leave solid screw lands.
BED_EDGE_CHAMFER = 0.3          # 45-degree relief against elephant-foot binding.

FIT = 0.25                     # Clearance PER SIDE, including diagonal tongue faces.
TONGUE_WALL = 1.6
TONGUE_HEIGHT = 2.6
TONGUE_CHAMFER = 0.4            # 45-degree lead-in at both tongue-tip edges.

SCREW_D = 3.0
LID_SCREW_MARGIN = 6.0          # Hole-center offset from both exterior edges.
INSERT_BORE_D = 4.2             # Tune to the selected heat-set insert datasheet.
INSERT_LENGTH = 5.0
INSERT_POCKET_DEPTH = 5.6       # Blind; includes space beneath the insert.
INSERT_LEAD_IN = 0.3            # Equal radial/axial 45-degree entry chamfer.
MIN_LIGAMENT = 1.6              # Minimum material around screw/insert features.

PCB_LENGTH = 90.0
PCB_WIDTH = 50.0
PCB_THICKNESS = 1.6
PCB_HOLE_EDGE_X = 4.0           # Four symmetric holes, measured from board edges.
PCB_HOLE_EDGE_Y = 4.0
PCB_OFFSET_X = 0.0
PCB_OFFSET_Y = 0.0
PCB_STANDOFF_HEIGHT = 8.0       # Floor's upper face to PCB's lower face.
PCB_STANDOFF_D = 9.0
PCB_ROOT_FLARE = 2.0            # Radius increase AND height: 45-degree root.
PCB_COMPONENT_HEIGHT = 16.0     # Component envelope above the board.
PCB_CLEARANCE = 1.0

ENABLE_MOUNT_TABS = True
TAB_PROJECTION = 16.0           # Distance extending beyond either X end wall.
TAB_WIDTH = 16.0
TAB_THICKNESS = 4.0
TAB_Y_MARGIN = 18.0             # Tab-center distance from either Y exterior edge.
TAB_CORNER = 2.0
MOUNT_SCREW_D = 4.0             # Printed clearance diameter = this + 2*FIT.
MOUNT_WASHER_D = 9.0

ENABLE_VENTS = True             # Vents open to ambient; no ingress rating claimed.
VENT_COUNT = 7                  # Per long wall; one row on each of +/-Y walls.
VENT_DIAGONAL = 6.0             # Equal horizontal/vertical diagonals: 45-degree roof.
VENT_PITCH = 10.0
VENT_Z = 19.0                   # Center height measured from the print bed.

PRINT_GAP = 8.0
BED_X = 220.0
BED_Y = 220.0
BED_MARGIN = 5.0
STL_TOLERANCE = 0.02            # Absolute chordal tolerance, mm.
STL_ANGLE = 0.1                 # Angular tessellation tolerance, radians.
EXPORT_STEP = True              # Also exports the assembled solid CAD model.
OUTPUT = Path("./output_model.stl")
# ------------------------------------------------------------------

EPS = 0.01                     # Boolean-tool overlap; never added to fit dimensions.
ROOT2 = sqrt(2.0)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def octagon(length, width, corner, height, z=0.0):
    """Extruded rectangle with planar, vertical 45-degree corners."""
    require(0 < corner < min(length, width) / 2, "Invalid octagon corner size.")
    x, y = length / 2, width / 2
    points = [(-x + corner, -y), (x - corner, -y), (x, -y + corner),
              (x, y - corner), (x - corner, y), (-x + corner, y),
              (-x, y - corner), (-x, -y + corner)]
    return cq.Workplane("XY", origin=(0, 0, z)).polyline(points).close().extrude(height)


def cylinder(x, y, z, radius, height):
    return cq.Workplane("XY", origin=(x, y, z)).circle(radius).extrude(height)


def cone(x, y, z, r1, r2, height):
    solid = cq.Solid.makeCone(r1, r2, height, cq.Vector(x, y, z))
    return cq.Workplane("XY").newObject([solid])


def insert_pocket(part, x, y, top):
    radius = INSERT_BORE_D / 2
    part = part.cut(cylinder(x, y, top - INSERT_POCKET_DEPTH, radius,
                             INSERT_POCKET_DEPTH + EPS))
    return part.cut(cone(x, y, top - INSERT_LEAD_IN, radius,
                         radius + INSERT_LEAD_IN + EPS, INSERT_LEAD_IN + EPS))


def dimensions_and_checks():
    numbers = [v for k, v in globals().items()
               if k.isupper() and isinstance(v, (int, float)) and not isinstance(v, bool)]
    require(all(isfinite(v) for v in numbers), "All parameters must be finite.")
    require(min(LENGTH, WIDTH, HEIGHT, WALL, FLOOR, LID, FIT, MIN_LIGAMENT) > 0,
            "Envelope dimensions, thicknesses and fit clearance must be positive.")
    require(min(WALL, FLOOR, LID, TONGUE_WALL) >= MIN_LIGAMENT,
            "A principal wall is thinner than MIN_LIGAMENT.")
    require(0 <= BED_EDGE_CHAMFER < min(FLOOR, LID, WALL) / 2,
            "Bed-edge chamfer is too large.")
    require(0 < TONGUE_CHAMFER < TONGUE_WALL / 2 and
            TONGUE_HEIGHT > TONGUE_CHAMFER, "Invalid tongue dimensions.")
    require(0 < INSERT_LEAD_IN < INSERT_LENGTH <= INSERT_POCKET_DEPTH,
            "Invalid insert pocket dimensions.")
    require(0 < SCREW_D < INSERT_BORE_D and
            INSERT_POCKET_DEPTH + MIN_LIGAMENT < HEIGHT - FLOOR,
            "Insert pockets require more depth or a suitable bore diameter.")
    inner_l, inner_w = LENGTH - 2 * WALL, WIDTH - 2 * WALL
    a, b = inner_l / 2, inner_w / 2
    require(0 < OUTER_CORNER < min(LENGTH, WIDTH) / 2 and
            0 < INNER_CORNER < min(a, b), "Invalid corner dimensions.")
    require(INNER_CORNER >= OUTER_CORNER - (2 - ROOT2) * WALL,
            "Cavity corner would thin the diagonal exterior wall.")
    offset = FIT + TONGUE_WALL
    require(0 < INNER_CORNER - (2 - ROOT2) * offset < min(a, b) - offset,
            "The locating tongue cannot fit inside this cavity.")

    screws = [(sx * (LENGTH / 2 - LID_SCREW_MARGIN),
               sy * (WIDTH / 2 - LID_SCREW_MARGIN)) for sx in (-1, 1) for sy in (-1, 1)]
    r = max(INSERT_BORE_D / 2 + INSERT_LEAD_IN, SCREW_D / 2 + FIT)
    require(0 < LID_SCREW_MARGIN < min(LENGTH, WIDTH) / 2, "Invalid screw margin.")
    for x, y in screws:
        exterior = min(LENGTH / 2 - abs(x), WIDTH / 2 - abs(y),
                       (LENGTH / 2 + WIDTH / 2 - OUTER_CORNER - abs(x) - abs(y)) / ROOT2)
        cavity_land = (abs(x) + abs(y) - (a + b - INNER_CORNER)) / ROOT2
        require(min(exterior, cavity_land) >= r + MIN_LIGAMENT,
                "A lid screw pocket lacks material; increase INNER_CORNER or change margin.")

    require(0 < PCB_HOLE_EDGE_X < PCB_LENGTH / 2 and
            0 < PCB_HOLE_EDGE_Y < PCB_WIDTH / 2 and PCB_THICKNESS > 0 and
            PCB_COMPONENT_HEIGHT >= 0 and PCB_CLEARANCE > 0, "Invalid PCB parameters.")
    require(0 < PCB_ROOT_FLARE < PCB_STANDOFF_HEIGHT and
            PCB_STANDOFF_HEIGHT - INSERT_POCKET_DEPTH >= MIN_LIGAMENT and
            PCB_STANDOFF_D / 2 >= INSERT_BORE_D / 2 + INSERT_LEAD_IN + MIN_LIGAMENT,
            "PCB standoffs are too short or thin for the inserts.")
    px, py = abs(PCB_OFFSET_X) + PCB_LENGTH / 2, abs(PCB_OFFSET_Y) + PCB_WIDTH / 2
    require(min(a - px, b - py, (a + b - INNER_CORNER - px - py) / ROOT2) >= PCB_CLEARANCE,
            "The PCB envelope collides with the walls or corner screw lands.")
    require(FLOOR + PCB_STANDOFF_HEIGHT + PCB_THICKNESS + PCB_COMPONENT_HEIGHT +
            PCB_CLEARANCE <= HEIGHT - TONGUE_HEIGHT, "Insufficient component headroom.")
    mounts = [(PCB_OFFSET_X + sx * (PCB_LENGTH / 2 - PCB_HOLE_EDGE_X),
               PCB_OFFSET_Y + sy * (PCB_WIDTH / 2 - PCB_HOLE_EDGE_Y))
              for sx in (-1, 1) for sy in (-1, 1)]
    root = PCB_STANDOFF_D / 2 + PCB_ROOT_FLARE
    for x, y in mounts:
        require(min(a - abs(x), b - abs(y),
                    (a + b - INNER_CORNER - abs(x) - abs(y)) / ROOT2) >= root + EPS,
                "A standoff root intersects the enclosure wall.")
    require(min(PCB_LENGTH - 2 * PCB_HOLE_EDGE_X, PCB_WIDTH - 2 * PCB_HOLE_EDGE_Y) > 2 * root,
            "PCB standoff roots overlap.")

    if ENABLE_MOUNT_TABS:
        require(TAB_THICKNESS >= FLOOR and TAB_PROJECTION > 0 and MOUNT_SCREW_D > 0,
                "Invalid mounting tab dimensions.")
        require(MOUNT_WASHER_D >= MOUNT_SCREW_D + 2 * FIT and
                min(TAB_PROJECTION, TAB_WIDTH) / 2 >= MOUNT_WASHER_D / 2 + MIN_LIGAMENT,
                "Insufficient washer clearance on mounting tabs.")
        require(0 < TAB_CORNER < min(TAB_WIDTH, TAB_PROJECTION) / 2 and
                TAB_Y_MARGIN - TAB_WIDTH / 2 > OUTER_CORNER and
                WIDTH - 2 * TAB_Y_MARGIN > TAB_WIDTH,
                "Mounting tabs overlap or lie beyond the straight end walls.")

    if ENABLE_VENTS:
        require(isinstance(VENT_COUNT, int) and VENT_COUNT > 0 and VENT_DIAGONAL > 0,
                "Vent count must be a positive integer; size must be positive.")
        require(VENT_PITCH >= VENT_DIAGONAL + MIN_LIGAMENT and
                (VENT_COUNT - 1) * VENT_PITCH / 2 + VENT_DIAGONAL / 2 + MIN_LIGAMENT < a - INNER_CORNER,
                "Vents overlap or intersect corner screw lands.")
        require(FLOOR + MIN_LIGAMENT < VENT_Z - VENT_DIAGONAL / 2 and
                VENT_Z + VENT_DIAGONAL / 2 + MIN_LIGAMENT < HEIGHT - TONGUE_HEIGHT,
                "Vents are too close to the floor or locating tongue.")
    require(PRINT_GAP > 0 and BED_MARGIN >= 0 and min(BED_X, BED_Y, STL_TOLERANCE, STL_ANGLE) > 0,
            "Invalid print layout or tessellation parameters.")
    return inner_l, inner_w, screws, mounts


def build():
    inner_l, inner_w, screws, mounts = dimensions_and_checks()
    base = octagon(LENGTH, WIDTH, OUTER_CORNER, HEIGHT)
    if BED_EDGE_CHAMFER:
        base = base.faces("<Z").edges().chamfer(BED_EDGE_CHAMFER)
    base = base.cut(octagon(inner_l, inner_w, INNER_CORNER, HEIGHT - FLOOR + EPS, FLOOR))

    if ENABLE_MOUNT_TABS:
        overlap = WALL / 2
        for sx in (-1, 1):
            for sy in (-1, 1):
                x = sx * (LENGTH / 2 + (TAB_PROJECTION - overlap) / 2)
                y = sy * (WIDTH / 2 - TAB_Y_MARGIN)
                tab = octagon(TAB_PROJECTION + overlap, TAB_WIDTH, TAB_CORNER,
                              TAB_THICKNESS).translate((x, y, 0))
                base = base.union(tab)
                hx = sx * (LENGTH / 2 + TAB_PROJECTION / 2)
                base = base.cut(cylinder(hx, y, -EPS, MOUNT_SCREW_D / 2 + FIT,
                                         TAB_THICKNESS + 2 * EPS))

    for x, y in mounts:
        r = PCB_STANDOFF_D / 2
        foot = cone(x, y, FLOOR - EPS, r + PCB_ROOT_FLARE, r, PCB_ROOT_FLARE)
        post = cylinder(x, y, FLOOR + PCB_ROOT_FLARE - 2 * EPS, r,
                        PCB_STANDOFF_HEIGHT - PCB_ROOT_FLARE + 2 * EPS)
        base = base.union(foot).union(post)
        base = insert_pocket(base, x, y, FLOOR + PCB_STANDOFF_HEIGHT)
    for x, y in screws:
        base = insert_pocket(base, x, y, HEIGHT)

    if ENABLE_VENTS:
        d = VENT_DIAGONAL / 2
        for i in range(VENT_COUNT):
            x = (i - (VENT_COUNT - 1) / 2) * VENT_PITCH
            for sy in (-1, 1):
                # XZ's normal points toward -Y; signed extrusion enters either wall.
                cutter = (cq.Workplane("XZ", origin=(x, sy * (WIDTH / 2 + EPS), VENT_Z))
                          .polyline([(-d, 0), (0, d), (d, 0), (0, -d)]).close()
                          .extrude(sy * (WALL + 2 * EPS)))
                base = base.cut(cutter)

    lid = octagon(LENGTH, WIDTH, OUTER_CORNER, LID)
    if BED_EDGE_CHAMFER:
        lid = lid.faces("<Z").edges().chamfer(BED_EDGE_CHAMFER)

    def inset_profile(offset, height, z):
        # Parallel offset: the diagonal faces retain the same PER-SIDE clearance.
        return octagon(inner_l - 2 * offset, inner_w - 2 * offset,
                       INNER_CORNER - (2 - ROOT2) * offset, height, z)

    tongue = inset_profile(FIT, TONGUE_HEIGHT + EPS, LID - EPS)
    tongue = tongue.cut(inset_profile(FIT + TONGUE_WALL, TONGUE_HEIGHT + 3 * EPS, LID - 2 * EPS))
    tongue = tongue.faces(">Z").edges().chamfer(TONGUE_CHAMFER)
    lid = lid.union(tongue)
    for x, y in screws:
        lid = lid.cut(cylinder(x, y, -EPS, SCREW_D / 2 + FIT, LID + 2 * EPS))

    base, lid = base.clean().val(), lid.clean().val()
    for name, part in (("base", base), ("lid", lid)):
        require(part.isValid() and len(part.Solids()) == 1 and part.Volume() > 0,
                f"{name}: invalid or disconnected CAD solid.")
        checker = BOPAlgo_ArgumentAnalyzer()
        checker.SetShape1(part.wrapped)
        checker.SelfInterMode = True
        checker.Perform()
        require(not checker.HasFaulty(), f"{name}: CAD self-intersection detected.")
    assembled_lid = lid.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, HEIGHT + LID))
    require(base.intersect(assembled_lid).Volume() < 1e-5, "Lid/base assembly collision.")
    return base, lid, assembled_lid


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


def main():
    base, lid, assembled_lid = build()
    plate = cq.Compound.makeCompound([base, lid.translate((0, WIDTH + PRINT_GAP, 0))])
    bounds = plate.BoundingBox()
    require(bounds.xlen + 2 * BED_MARGIN <= BED_X and bounds.ylen + 2 * BED_MARGIN <= BED_Y,
            "Both parts do not fit the configured bed; enlarge BED_X/BED_Y or reduce dimensions.")
    plate = plate.translate((BED_MARGIN - bounds.xmin, BED_MARGIN - bounds.ymin, -bounds.zmin))
    require(plate.isValid() and len(plate.Solids()) == 2, "Invalid print-plate compound.")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".pending.stl")
    try:
        require(plate.exportStl(str(temporary), tolerance=STL_TOLERANCE,
                                angularTolerance=STL_ANGLE, ascii=False, relative=False),
                "STL export failed.")
        triangles = verify_stl(temporary, 2, plate.Volume())
        temporary.replace(OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    if EXPORT_STEP:
        assembly = cq.Assembly(name="Parametric_PCB_Enclosure")
        assembly.add(base, name="Base", color=cq.Color(0.16, 0.20, 0.25))
        assembly.add(assembled_lid, name="Lid", color=cq.Color(0.75, 0.78, 0.81))
        assembly.export(str(OUTPUT.with_suffix(".step")))
    print(f"Exported {OUTPUT.resolve()}: 2 watertight shells, {triangles:,} triangles; "
          f"material volume {plate.Volume()/1000:.1f} cm^3; "
          f"footprint {bounds.xlen:.1f} x {bounds.ylen:.1f} mm.")


if __name__ == "__main__":
    main()
