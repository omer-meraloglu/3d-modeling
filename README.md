# 3d-modeling

Parametric CAD models, printable products and production assets for polukal.
All dimensions are millimeters. Modeling and rendering run without GUI control.
This is the project's only README; product-specific PDFs remain in their folders.

## Git repository and local exports

Git tracks the parametric source, requirements, documentation, validation reports
and preview images. Generated CAD exports (STL, STEP, 3MF, OBJ and DXF), mesh
caches, delivery ZIPs, compiled renderers and generated video/audio are ignored
to keep pushes and clones small. Existing exports remain on the local Desktop.

Links below to model exports, archives and videos refer to local generated files;
those files are not included in a Git clone. Use each product's documented build
command to generate its exports, then run the preview or packaging scripts as
needed. Source files, preview images and PDF guides are available in the repository.

## Current Blades of Chaos deliverables

| Route | What you make | Start file |
|---|---|---|
| One-piece FDM, v5 | One fully sculpted 110 mm blade in a single print; slicer supports required | [Oriented 3MF](<Blades of Chaos Keychain/v5 - One-piece Print/output_model.3mf>) |
| Bonded halves, v3 | One A + one mirrored B + 3 keys per blade; four halves make a pair | [One blade kit](<Blades of Chaos Keychain/v3 - Two-sided Assembly/output_model.3mf>) · [Two-blade kit](<Blades of Chaos Keychain/v3 - Two-sided Assembly/two_blades_print_plate.3mf>) |
| One-piece metal, v4 | Solid casting master for a foundry | [Master STL](<Blades of Chaos Keychain/v4 - Metal Production/metal_casting_master.stl>) · [Turkish supplier brief](<Blades of Chaos Keychain/v4 - Metal Production/Metal_Sanayi_Uretim_Paketi_TR.pdf>) |

[Assembly drawings](<Blades of Chaos Keychain/v3 - Two-sided Assembly/Printing_and_Assembly.pdf>) explain the mirrored halves and concealed conical keys.

Complete delivery archives:

- [One-piece FDM kit](<Blades of Chaos Keychain/polukal-blades-onepiece-fdm.zip>): oriented and neutral STL/3MF, parametric source, mesh previews and validation.
- [Bonded print kit](<Blades of Chaos Keychain/polukal-blades-bonded-print-kit.zip>): mirrored halves, alignment keys, one/two-blade plates and assembly drawings.
- [Metal supplier kit](<Blades of Chaos Keychain/polukal-blades-metal-supplier-kit.zip>): casting STL/3MF, faceted STEP, reference DXF and Turkish handoff PDF.

Each kit contains a SHA-256 delivery manifest. The archives contain no additional
README files. Rebuild current archives with
`python "Blades of Chaos Keychain/package_deliverables.py"` from the project root.

The original `hero_enclosure.py`, root enclosure exports, six-product `catalog/`,
and earlier blade revisions are preserved. Root `output_model.stl` is the original
enclosure, so use the linked blade-version folders for blade prints.

## One-piece FDM printing - v5

**Folder:** `Blades of Chaos Keychain/v5 - One-piece Print/`

The blade is a single closed solid, detailed on both front and back with rounded
handle, skull guard, pommel, chased border and fine ornament. It has no joining
seam or alignment pockets. The finished envelope is approximately
110 × 38.27 × 11.85 mm, with a 4.60 mm eyelet. Print two copies for a pair of blades.

- `output_model.stl` / `.3mf`: default FDM pose, long axis tilted 65° from the bed,
  rolled 12°. Each file contains one part. The posed mesh is 47.85 × 37.81 × 101.98 mm before supports/brim. This pose is a starting point.
- `one_piece_FDM_oriented.stl` / `.3mf`: named copies of the FDM pose.
- `one_piece_model.stl` / `.3mf`: the same full geometry in its neutral pose.
- `one_piece_model.py`: complete self-contained parametric source.
- `one-piece-validation.json`: manifold and orientation/overhang measurements.
- `one-piece-export-verification.json`: independent STL/3MF reload checks.

**Supports are required.** Enable tree/organic supports in your slicer and inspect
contact beneath the guard hook, pommel and blade curves. Start with automatic
support placement, then add or adjust supports where the layer preview shows
unsupported islands. Prefer accessible underside/edge contact where possible;
expect some cleanup and local support marks. No machine-specific supports or
G-code are embedded in these model-only STL/3MF files.

For a calibrated FDM printer, start with a 0.4 mm nozzle at 0.12 mm layers, 4 walls
and 25–35% infill. A 0.25 mm nozzle can preserve more of the fine engraving. Use
a brim for stability in the tall tilted pose and tune support interfaces to your
material/printer profile. Slicer estimates are required for time and material use.
A first supported print is still required to qualify detail, support release and
keyring fit. The v3 halves provide the flatter, support-free printing alternative.

```sh
cd "Blades of Chaos Keychain/v5 - One-piece Print"
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python one_piece_model.py --length 110 --pitch 0.12
```

The generator automatically writes `./output_model.stl`. Dimensions, relief,
eyelet, edge rounding, mesh pitch, tilt and roll are exposed in the source.
The models pass digital geometry checks; no physical print or casting trial is
claimed. Preview colors illustrate possible painted or patinated finishes.

Support reference: [Prusa organic-support guidance](https://help.prusa3d.com/article/organic-supports_480131). Use your own slicer and material profile; the support layout needs a layer-preview check.

## Documentation map

- Bonded printing and fit details: below, `BONDED DOCS` section.
- Metal files, process notes and supplier handoff: `METAL DOCS` section.
- Six B2B/B2C products: `CATALOG DOCS` section.
- Existing social-media renders: `ADVERTISEMENTS DOCS` section.
- Earlier v2/v1 geometry and parameters: historical sections at the end.

<!-- BEGIN BONDED DOCS -->
## Bonded printing: A + mirrored B

**Working folder:** `Blades of Chaos Keychain/v3 - Two-sided Assembly/`

Print **one A front + one mirrored B back + three alignment keys** for each
finished blade. A pair of complete blades uses four halves and six keys.

### Start here

- `output_model.3mf` / `output_model.stl`: one blade kit, with two spare keys.
- `two_blades_print_plate.3mf`: two complete blade kits, with two spare keys.
- `blade_A_front.stl` and `blade_B_back_mirrored.stl`: separate halves.
- `alignment_key.stl`: one registration key.
- `Printing_and_Assembly.pdf`: drawings, section view and assembly instructions.
- `assembled_REFERENCE_ONLY.3mf`: posed assembly for inspection.

The 3MF files use millimeters and keep each part as a named object. STL imports
must use mm. The one-blade plate is 110 × 89.75 mm; each half is 5.92 mm high.
The finished model is 110 × 38.28 × 11.93 mm with the illustrated 0.08 mm glue line.
No spacer enforces that gap; a flush joint is about 11.85 mm thick.

The outer faces include chased blade borders, interlaced ornament, fine ticks,
bone plates and rivets on the skull, wrap stitching, ferrules and a rounded
pommel. Both faces are sculpted; B is mirrored so the asymmetric outline fits.

### Fit and printing

Three conical sockets are hidden in each mating face: Ø2.90 mm at the mouth,
1.566 mm deep, with 47.2° roofs. Keys are Ø2.40 mm at their widest point and
1.40 mm long, with Ø1.00 mm tip flats. Nominal radial clearance is 0.25 mm.
The exported geometry retains at least 1.06 mm of material above the sockets.

Print flat bonding faces down, relief up, supports off. Start with a calibrated
0.25 mm nozzle and 0.10 mm layers for detail, 4 walls, 5 bottom layers, 6 top
layers, and 30% infill. A 0.4 mm nozzle softens the finer detail. A small brim
can help the tiny keys; remove it completely before fitting.

Dry-fit A, three keys, and B flipped over so the flat faces meet and the blade
outline and keyring opening coincide. Bond the flat lands with an adhesive
compatible with the polymer, clamp through the adhesive's full cure, and finish
the seam. For plastic welding, use matching polymers and trial the process on
a coupon. The parts are designed for a flush joint; the visualization gap is
optional. The metal production version is in the separate v4 folder.

### Rebuild without a GUI

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python model.py
python verify_assembly.py
python render_preview.py
```

`model.py` is self-contained and automatically exports `./output_model.stl`.
All geometry, detail, fit and spacing parameters are documented at the top.
Use `python model.py --length 110 --pitch 0.12`; supported length is 95–130 mm.
Custom configurations are checked for minimum socket skin and printable roofs.

The preview renderer uses the actual exported meshes, NumPy/Pillow and a C++17
compiler (`clang++`); macOS Command Line Tools provide that compiler. Linux font
fallback needs matplotlib. Preview colors represent an optional painted finish.

`validation.json` and `assembly-verification.json` record manifold/winding,
connected volumes, support-angle, mirror-registration, pocket-skin, key-clearance
and STL/3MF reload checks. The upper surface is a non-overlapping constrained
heightfield, closed to a planar mating face and exact conical socket roofs.
Physical printing, bonding and welding trials have not yet been performed.
<!-- END BONDED DOCS -->

<!-- BEGIN METAL DOCS -->
## Metal production handoff

**Working folder:** `Blades of Chaos Keychain/v4 - Metal Production/`

Give the foundry `metal_casting_master.stl` and `Metal_Sanayi_Uretim_Paketi_TR.pdf`.
The PDF contains a Turkish manufacturing brief, dimensions, tolerance targets,
and a ready-to-send quotation request. No supplier has been contacted.

The model is one solid with sculpted faces on both sides, rounded XY tips and
corners, a through eyelet, and no glue seam or alignment sockets. Nominal finished
size is **110.00 × 38.27 × 11.85 mm**, with a **4.60 mm** eyelet. The thinnest edge
is 1.80 mm. Nominal volume is 8.741 cm³: approximately 74 g in brass at an assumed
8.5 g/cm³, or 24 g in aluminium at 2.7 g/cm³, before alloy/finish variation.

### Files and authority

| File | Use |
|---|---|
| `metal_casting_master.stl` | Authoritative high-detail finished geometry; import as mm |
| `metal_casting_master.3mf` | Same geometry, explicit mm units |
| `metal_CAD_interchange.step` | Valid single-solid faceted B-rep CAD reference |
| `metal_outline_REFERENCE_ONLY.dxf` | 2D plan contour for inspection/quotation, mm |
| `Metal_Sanayi_Uretim_Paketi_TR.pdf` | Turkish drawing and manufacturing brief |
| `metal_model.py` | Complete self-contained parametric generator |
| `metal-validation.json` | Mesh, CAD and STEP round-trip verification |

The STEP contains 65,000 planar faces and is about 163 MB before ZIP compression.
It preserves the sculpt as a faceted CAD approximation. The maximum sampled
bidirectional surface difference from the detailed master was 0.0464 mm over
30,000 samples; this is not a proven global error bound. It is not a smooth
feature-tree CAD model. Use the high-resolution STL for the fine casting master.

### Proposed manufacturing route

Start with a foundry or jewelry/accessory workshop offering **hassas döküm / kayıp
mum döküm**. The recommended route is an appropriate wax/castable resin pattern
followed by investment casting and finishing. Antique brass/bronze appearance is
the proposed finish; confirm the cast alloy, patina/plating and weight with the
producer. The supplied DXF is a silhouette reference; the full relief comes from
the 3D master.

The files are **finished nominal geometry at 1:1**. Shrinkage compensation,
sprues/gates, vents, pattern supports, polishing and coating allowances belong
to the selected foundry process. No universal shrinkage percentage or untested
sprue tree is embedded. Inspect an initial sample for detail retention, eyelet,
dimensions, finish and weight before committing to a batch.

Drawing targets: length, width and overall thickness ±0.30 mm; finished eyelet
Ø4.60 +0.20/0 mm. These are proposed acceptance targets for the supplier to
confirm, not claims about a shop's capability. Casting and physical finish trials
have not yet been performed.

### Regenerate headlessly

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python metal_model.py
```

The script exports `./output_model.stl` as the one-piece metal master, plus the
named STL, 3MF, DXF and STEP. Use `--skip-step` for a faster master-only rebuild.
Length, sculpt detail, edge rounding and CAD exchange resolution are exposed in
the source. CAD validity and sampled deviation are checked before STEP export.

Process sources: [Formlabs casting guide](https://formlabs.com/support/Introduction-to-casting-with-Formlabs-resins/)
and [pattern production workflow](https://formlabs.com/global/industries/jewelry/).
The process choice is an engineering recommendation based on these workflows
and the sculpt's small details.
<!-- END METAL DOCS -->

<!-- BEGIN CATALOG DOCS -->
## Hero product catalog

**Working folder:** `catalog/`

Six original CadQuery designs, split evenly between B2B and B2C. Each product folder contains an independent `model.py`, printable STL, assembled STEP, preview PNG, and mesh data.

![Six product previews](<catalog/hero-products-preview.png>)

### Run or customize

Install Python and CadQuery once: `python -m pip install cadquery==2.6.1`. Change into a product folder, edit the exposed parameters at the top of `model.py`, then run `python model.py`. Outputs are relative to your current working directory. Import STL as millimeters.

Each script is self-contained; `build_catalog.py` and `render_previews.py` are optional catalog maintenance tools. Rerunning `build_catalog.py` restores the catalog defaults and overwrites product scripts.

### Products

#### Slotted sensor plate — B2B

Adjustable mounting for cylindrical sensors.

- Customer: Machine builders and automation integrators
- Customize: Sensor diameter · slot travel · hole spacing
- Hardware: Two M5 bolts and washers; sensor mounting nuts
- Printing: PETG or ASA · flat on bed · no supports
- Output: 1 printable part(s); 90.0 × 44.0 mm print footprint.
- Files: [Python](<catalog/b2b_sensor_plate/model.py>) · [STL](<catalog/b2b_sensor_plate/output_model.stl>) · [STEP](<catalog/b2b_sensor_plate/output_model.step>) · [Preview](<catalog/b2b_sensor_plate/preview.png>)

#### PCB inspection cradle — B2B

Holds a board upright for inspection and light bench work.

- Customer: Electronics assembly and repair benches
- Customize: PCB thickness · edge engagement · base width
- Hardware: None; optional adhesive feet
- Printing: PETG · two independent supports · no supports
- Output: 2 printable part(s); 104.0 × 24.0 mm print footprint.
- Files: [Python](<catalog/b2b_pcb_cradle/model.py>) · [STL](<catalog/b2b_pcb_cradle/output_model.stl>) · [STEP](<catalog/b2b_pcb_cradle/output_model.step>) · [Preview](<catalog/b2b_pcb_cradle/preview.png>)

#### Custom assembly nest — B2B

Repeatable positioning for assembly, inspection, and labeling.

- Customer: Small-batch manufacturers and quality teams
- Customize: Part envelope · corner radius · mounting pattern
- Hardware: Four M4 bolts and washers, if mounted
- Printing: PETG · open pocket upwards · no supports
- Output: 1 printable part(s); 108.0 × 72.0 mm print footprint.
- Files: [Python](<catalog/b2b_assembly_nest/model.py>) · [STL](<catalog/b2b_assembly_nest/output_model.stl>) · [STEP](<catalog/b2b_assembly_nest/output_model.step>) · [Preview](<catalog/b2b_assembly_nest/preview.png>)

#### Cable landing rail — B2C

Keeps charging leads at the desk edge with open-access cable slots.

- Customer: Home offices, gaming desks, and shared workspaces
- Customize: Cable diameters · channel count · spacing
- Hardware: Adhesive tape or two M3 mounting screws
- Printing: PLA or PETG · flat on bed · no supports
- Output: 1 printable part(s); 130.0 × 44.0 mm print footprint.
- Files: [Python](<catalog/b2c_cable_rail/model.py>) · [STL](<catalog/b2c_cable_rail/output_model.stl>) · [STEP](<catalog/b2c_cable_rail/output_model.step>) · [Preview](<catalog/b2c_cable_rail/preview.png>)

#### Desk valet with divider — B2C

Separates daily carry, pens, and small tech accessories.

- Customer: Desk setups, gift buyers, and branded office kits
- Customize: Tray size · divider position · compartment sizes
- Hardware: None; divider drops into open grooves
- Printing: PLA or PETG · tray upright, divider flat · no supports
- Output: 2 printable part(s); 153.1 × 84.0 mm print footprint.
- Files: [Python](<catalog/b2c_divider_tray/model.py>) · [STL](<catalog/b2c_divider_tray/output_model.stl>) · [STEP](<catalog/b2c_divider_tray/output_model.step>) · [Preview](<catalog/b2c_divider_tray/preview.png>)

#### CablePass phone stand — B2C

Supports a phone with an open frame and charging-cable passage.

- Customer: Home desks, bedside setups, and reception counters
- Customize: Viewing angle · device width · case thickness
- Hardware: None; optional felt contact pads
- Printing: PLA or PETG · print on its side as exported · no supports
- Output: 1 printable part(s); 80.0 × 88.0 mm print footprint.
- Files: [Python](<catalog/b2c_phone_stand/model.py>) · [STL](<catalog/b2c_phone_stand/output_model.stl>) · [STEP](<catalog/b2c_phone_stand/output_model.step>) · [Preview](<catalog/b2c_phone_stand/preview.png>)

### Validation and manufacturing

Defaults and one dimensionally customized variant of each product executed using Python 3.12 and CadQuery 2.6.1; variants used 0.30 mm per-side clearance. Each printable component passed valid-solid and CAD self-intersection checks. Assembled printable components were checked for collisions. Exported STL files passed edge-manifold, winding, facet-normal, shell-count, positive-volume, CAD-volume agreement, and support-free 45-degree overhang checks. The six default jobs contain eight printable components in total.

Nominal mating clearances are 0.25 mm per side. These checks validate digital geometry; they do not establish print accuracy, load ratings, environmental performance, or sales demand. Calibrate your printer and selected material, then qualify first articles. Slicer estimates are required for actual mass and print time. Gray reference devices are omitted from STL and STEP files.

### Category references

These sources establish commercial product categories, not sales estimates or endorsements of these designs:
- [Phoenix Contact: electronics housings](https://www.phoenixcontact.com/en-us/products/electronics-housings)
- [Carr Lane: modular fixturing](https://www.carrlane.com/engineering-resources/technical-information/manual-workholding/modular-fixturing)
- [IKEA: SIGNUM cable management](https://www.ikea.com/gb/en/p/signum-cable-trunking-horizontal-silver-colour-30200253/)
- [Twelve South: BookArc Flex](https://www.twelvesouth.com/products/bookarc-flex)
<!-- END CATALOG DOCS -->

<!-- BEGIN ADVERTISEMENTS DOCS -->
## Product advertisement videos

**Working folder:** `catalog/advertisements/`

Six original advertisements based on the catalog's actual product geometry.

**Format:** 1080 × 1920, vertical 9:16, 24 fps, 12 seconds each. BT.709 H.264 video with stereo AAC audio in MP4 containers. On-screen captions carry the message without sound; every ad also includes an original synthesized instrumental track.

### Individual videos

| Product | Advertisement | Poster |
| --- | --- | --- |
| Slotted sensor plate | [Play MP4](<catalog/advertisements/videos/b2b_sensor_plate.mp4>) | [JPG](<catalog/advertisements/posters/b2b_sensor_plate.jpg>) |
| PCB inspection cradle | [Play MP4](<catalog/advertisements/videos/b2b_pcb_cradle.mp4>) | [JPG](<catalog/advertisements/posters/b2b_pcb_cradle.jpg>) |
| Custom assembly nest | [Play MP4](<catalog/advertisements/videos/b2b_assembly_nest.mp4>) | [JPG](<catalog/advertisements/posters/b2b_assembly_nest.jpg>) |
| Cable landing rail | [Play MP4](<catalog/advertisements/videos/b2c_cable_rail.mp4>) | [JPG](<catalog/advertisements/posters/b2c_cable_rail.jpg>) |
| Desk valet with divider | [Play MP4](<catalog/advertisements/videos/b2c_divider_tray.mp4>) | [JPG](<catalog/advertisements/posters/b2c_divider_tray.jpg>) |
| CablePass phone stand | [Play MP4](<catalog/advertisements/videos/b2c_phone_stand.mp4>) | [JPG](<catalog/advertisements/posters/b2c_phone_stand.jpg>) |

[Watch the complete collection](<catalog/advertisements/all-six-product-ads.mp4>)

### Creative structure

Each ad has three four-second sections: a benefit-led opening, an animated demonstration, and a customization call to action. B2B ads use a dark teal studio palette; B2C ads use a warm neutral palette.

The sensor, PCB, workpiece, cables, phone, pens, and key are illustrative reference props. They demonstrate use and are not included in the printable product files. Product geometry is unchanged. These are rendered product advertisements, not footage of physical prototypes or evidence of tested performance.

No brand, URL, price, rating, or unverified performance statistic was added. Calls to action are generic and can be updated before publication.

### Editable sources

- `make_ads.py`: copy, typography, colors, camera motion, product demonstrations, soundtrack synthesis, and video encoding.
- `rasterizer.cpp`: accelerated CPU renderer with a depth buffer and smooth shading.
- `original-sound-bed.wav`: original synthesized stereo instrumental; no third-party recordings were used.
- `storyboards/b2b.jpg` and `storyboards/b2c.jpg`: opening, demonstration, and closing frames for review.
- `video-manifest.json`: the individual exports and format information.

The generator reads `../catalog_preview_data.json` in the existing project. The ZIP package includes this data under `source-data/`, which the generator uses automatically when run separately. It does not open a browser or control the desktop.

To regenerate on macOS with Python 3.12 and command line developer tools:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install cadquery==2.6.1 numpy Pillow imageio-ffmpeg==0.6.0 matplotlib
.venv/bin/python make_ads.py --previews
.venv/bin/python make_ads.py --render --workers 2
```

Run from this advertisements folder. Regeneration overwrites the corresponding exports. For one product, add `--product b2c_phone_stand` or the matching catalog folder name. Captions and calls to action are in the `CREATIVE` dictionary; the final footer is controlled by `FOOTER`. macOS uses Avenir Next when available, with a DejaVu Sans fallback.
<!-- END ADVERTISEMENTS DOCS -->

<!-- BEGIN V2 DOCS -->
## Earlier v2 flat-back blade

**Working folder:** `Blades of Chaos Keychain/`

A rebuilt, game-inspired miniature with a swept blade, asymmetrical skull guard,
rounded wrapped grip, reinforced pommel eyelet, shallow knot engraving and fine
surface wear. The detail is part of the exported mesh. The back is flat for
printing. This is an original reconstruction adapted to keychain scale.

The earlier stylized version is preserved separately in `v1-stylized/`.

### Ready-to-slice files

| Design | STL | 3MF | Overall size, mm |
|---|---|---|---|
| Single blade — main design | `output_model.stl` / `single_blade.stl` | `output_model.3mf` / `single_blade.3mf` | 90.00 × 31.32 × 9.30 |
| Crossed blades — fused emblem | `crossed_blades.stl` | `crossed_blades.3mf` | 90.00 × 74.22 × 10.30 |

Each design is one connected, closed solid. The crossed emblem has two eyelets;
it contains no moving or separate interlocking components. The 3MF files contain
the model only, with explicit millimeter units. STL is unitless: import as mm.
OBJ versions are also included.

The full sculpt is supplied in mesh formats. `model.py` checks the continuous
foundation using CadQuery and constructs its detailed upper surface with a
constrained triangulation. A simplified STEP has not been substituted for the
full model.

### Generate and customize without a GUI

Use Python 3.11 or 3.12 in a virtual environment:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python model.py
```

Run from the folder where you want the output files. The script automatically
creates `./output_model.stl`, 3MF and OBJ equivalents, and both named variants.
All geometry and ornament definitions are inside `model.py`; no reference image,
downloaded mesh, online service or GUI is needed.

The documented parameters at the top include:

| Parameter | Default | Meaning |
|---|---:|---|
| `STYLE` | `single` | Variant copied to `output_model.*` |
| `SINGLE_LENGTH` | 90.0 mm | Exact single blade length; supported range 75–120 mm |
| `CROSSED_LONG_SIDE` | 90.0 mm | Crossed emblem's long dimension |
| `FOUNDATION` | 2.40 mm | Minimum continuous thickness |
| `BLADE_RISE` | 1.50 mm | Broad blade crown above foundation |
| `BEVEL_WIDTH` | 2.00 mm | Rounded perimeter shoulder width |
| `GUARD_HEIGHT` | 8.10 mm | Nominal guard height before local bony ridges |
| `GRIP_HEIGHT` | 6.20 mm | Nominal grip crown |
| `ORNAMENT_WIDTH` | 0.52 mm | Main engraving width |
| `ORNAMENT_DEPTH` | 0.36 mm | Main engraving depth |
| `WEAR_DEPTH` | 0.06 mm | Subtle physical surface wear |
| `FIT` | 0.30 mm/side | Eyelet clearance around nominal opening |
| `KEYRING_HOLE_D` | 4.60 mm | Actual eyelet opening, including clearance |
| `KEYRING_WALL` | 2.30 mm | Radial reinforcement around eyelet |
| `CROSSED_ANGLE` | 33° | Blade angle from vertical |
| `MESH_PITCH` | 0.16 mm | Surface sampling interval |

The guard's superimposed ridges make its final peak taller than its nominal
height. Exact generated dimensions are recorded in `validation.json`.
Changing the length scales the sculpt's XY proportions; foundation thickness,
eyelet opening and keyring wall remain physical millimeter values.

Generate just one variant, or increase mesh resolution:

```sh
python model.py --style single
python model.py --style crossed
python model.py --style single --pitch 0.12
```

A `--style` selection also determines `output_model.*` for that invocation.

### Printing

- Place the supplied flat back at Z=0 on the bed; supports off.
- For the small engraved details, a 0.25 mm nozzle and 0.10 mm layers are a useful
  starting point. A 0.4 mm nozzle at 0.12 mm layers retains the main sculpt but
  may soften the fine grooves and wear. Fine resin printing preserves more detail.
- For FDM, start with 4 walls, 5 bottom layers, 6 top layers and 25–35% infill.
  Use a calibrated profile for your chosen PLA or PETG and inspect the sliced
  toolpaths, especially at the pointed silhouette and small engraving.
- Add a metal split ring through the pommel eyelet after printing.
- The upper relief has no undercuts. All downward-facing model area lies on the
  build plate; external sides and eyelet walls are vertical.

The previews show the actual mesh under software lighting. The colored view
illustrates an optional steel, bronze and brown painted finish; the print files
contain single-material geometry. The gray view shows the same unpainted model.

### Verification and previews

```sh
python verify_exports.py
python render_preview.py
```

The preview renderer also needs a C++17 compiler (`clang++`); on macOS this is
provided by Command Line Tools. Rendering uses no application windows. Pillow
and NumPy create the previews; the C++ renderer calculates lighting and shadows
from the mesh. Linux font fallback additionally needs matplotlib.

`validation.json` records manifold edges, consistent outward winding, positive
volume, one connected shell, nondegenerate float32 STL facets, valid CadQuery
foundation, constrained planar coverage and support-free undersides. The top is
a single-valued positive height over a non-overlapping planar triangulation,
closed by a Z=0 bottom and vertical boundary walls; this construction prevents
self-intersections.

`export-verification.json` records independent STL/3MF/OBJ reload checks and
custom-size checks at 80 and 110 mm. Mesh validation has passed; a physical print
and keyring fit test have not yet been performed.

### Visual references

- [Santa Monica Studio's Blades of Chaos concept sheet](https://x.com/SonySantaMonica/status/1693654368220823856)
- [Sanket Tonde — God of War Blades of Chaos sculpt](https://sanktond.artstation.com/projects/NG9a3N)

The model uses newly authored geometry, with a flat back and reinforced eyelet
added for the keychain. It is not an extracted game asset or an exact replica.
<!-- END V2 DOCS -->

<!-- BEGIN V1 DOCS -->
## Earlier v1 stylized blade

**Working folder:** `Blades of Chaos Keychain/v1-stylized/`

A stylized miniature of Kratos's Blades of Chaos, with a swept blade, hooked heel, scalloped spine, engraved ornament, raised horned guard, wrapped grip and reinforced pommel eyelet. Two designs are included. Each is a single fused printable part.

![Actual CAD preview](<Blades of Chaos Keychain/v1-stylized/preview.png>)

| Design | Size, mm | Printable STL | Editable CAD |
| --- | --- | --- | --- |
| Crossed blades — default | 72.1 × 78.0 × 5.85 | [output_model.stl](<Blades of Chaos Keychain/v1-stylized/output_model.stl>) | [STEP](<Blades of Chaos Keychain/v1-stylized/output_model.step>) |
| Single blade | 34.2 × 78.0 × 5.05 | [single_blade.stl](<Blades of Chaos Keychain/v1-stylized/single_blade.stl>) | [STEP](<Blades of Chaos Keychain/v1-stylized/single_blade.step>) |

`crossed_blades.stl` and `crossed_blades.step` are named copies of the default design. The crossed design has a 0.8 mm difference in blade height so the overlap remains visible. Both backs remain flat at Z=0; no separate parts or glue are required. The crossed version has an eyelet on each pommel; use either one.

### Print

- Import the STL in **millimeters**, in its exported orientation: flat back on the bed, engraved face upward.
- Start with a 0.4 mm nozzle, 0.16–0.20 mm layers, four walls and 100% infill for these small parts.
- Supports: **off**. The geometry passes the 45-degree underside check in this orientation.
- PETG is a useful starting material for a daily keychain; PLA is suitable for an initial detail/fit print.
- Fit a small metal split ring through the 4.6 mm opening. Its surrounding radial wall is 2.4 mm before the small upper chamfer.
- The long blade bevel leaves a thick blunt perimeter. Fine engraving is recessed 0.48 mm, using 0.85 mm main strokes.

The preview's steel, bronze and red are an optional painted finish. STL files contain single-material geometry; those colors are not separate printable components. A first print is still needed to confirm your printer's detail quality and hardware fit.

### Customize and regenerate

All modeling code is in [model.py](<Blades of Chaos Keychain/v1-stylized/model.py>), with exposed parameters at the top. No GUI, downloaded mesh, account, or network is used by the script.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install cadquery==2.6.1
.venv/bin/python model.py
```

Run from this folder. By default, the script exports both variants, writes the selected design to `./output_model.stl` and `./output_model.step`, and writes mesh/validation JSON alongside them.

Useful settings:

- `STYLE`: `single` or `crossed` for the main output file.
- `LONG_SIDE_MM`: longest XY dimension, default 78 mm. Supported design range 65–120 mm; thickness and hole diameter remain independent.
- `BODY_THICKNESS`, `GUARD_RELIEF`, `GRIP_RELIEF`: physical thickness and surface detail.
- `KEYRING_NOMINAL_D` and `FIT`: opening diameter plus print clearance. The default is 4.0 + 2 × 0.30 = 4.6 mm. `KEYRING_HOLE_D` may also be edited directly.
- `KEYRING_WALL`: radial reinforcement around the opening.
- `GROOVE_WIDTH` and `GROOVE_DEPTH`: decorative detail dimensions.
- `CROSSED_ANGLE_DEG` and `CROSSED_LAYER_RISE`: spacing and overlap relief.

Optional preview regeneration uses `render_preview.py`, NumPy, Pillow and a C++ compiler. It renders the saved CAD meshes without a window or display server. `rasterizer.cpp` is included; its native library is compiled automatically. The macOS system font is used when present, with a Matplotlib DejaVu fallback.

### Geometry checks

Both defaults were executed with CadQuery 2.6.1. The export routine checks valid positive-volume CAD, one solid, CAD self-intersection, STL edge manifoldness, connected shell count, facet winding, signed volume agreement and underside angles. Results are saved in [validation.json](<Blades of Chaos Keychain/v1-stylized/validation.json>). These are digital geometry checks, not physical load tests.

An additional crossed variant at 85 mm, with a 4.0 mm foundation, 5.0 mm ring openings and 1.0 mm ornament strokes, was also verified. The default files retain their original dimensions.

### Design reference

This is an original, simplified fan-art CAD interpretation. The silhouette and ornament were informed by a [Blades of Chaos replica reference](https://www.barbabos.ubuy.com/product/FOI5688FI-god-of-war-kratos-blades-of-chaos-real-full-metal-21inch-stainless-steel-1-1-replica-from-the-game-weapon-prop); the [official God of War page](https://www.playstation.com/en-us/god-of-war/) provides the character/weapon context. No game mesh or third-party printable model is included.
<!-- END V1 DOCS -->
