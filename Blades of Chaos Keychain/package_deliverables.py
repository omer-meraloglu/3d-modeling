#!/usr/bin/env python3
"""Package the three current blade revisions; uses only the Python standard library.

Run after generating and verifying the models. Documentation remains in the
single project-root README.md; version-specific drawing PDFs travel with kits.
"""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
KITS = (
    ('v5 - One-piece Print', 'polukal-blades-onepiece-fdm.zip', 'output_model.3mf'),
    ('v3 - Two-sided Assembly', 'polukal-blades-bonded-print-kit.zip', 'output_model.3mf'),
    ('v4 - Metal Production', 'polukal-blades-metal-supplier-kit.zip', 'metal_casting_master.stl'),
)
SUFFIXES = {'.py', '.txt', '.stl', '.3mf', '.step', '.dxf', '.pdf',
            '.json', '.png', '.cpp', '.npz'}


def main():
    for folder, archive_name, entry_point in KITS:
        source = ROOT / folder
        files = sorted(p for p in source.iterdir()
                       if p.is_file() and p.suffix.lower() in SUFFIXES
                       and not p.name.lower().startswith('readme')
                       and p.name != 'delivery-manifest.json')
        assert (source / entry_point).is_file(), entry_point
        entries = {
            p.name: {'bytes': p.stat().st_size,
                     'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in files
        }
        manifest = {
            'product': 'polukal Blades of Chaos miniature keychain',
            'revision': folder,
            'units': 'millimeter',
            'nominal_length_mm': 110.0,
            'start_file': entry_point,
            'physical_production_tested': False,
            'project_documentation': '3d-modeling/README.md',
            'files': entries,
        }
        if folder.startswith('v5'):
            manifest['slicer_supports_required'] = True
            manifest['supports_and_gcode_included'] = False
        manifest_path = source / 'delivery-manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        destination = ROOT / archive_name
        temporary = destination.with_suffix('.zip.tmp')
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in [*files, manifest_path]:
                z.write(p, p.name)
        with zipfile.ZipFile(temporary) as z:
            assert z.testzip() is None, 'Archive CRC error'
            assert not any(Path(n).name.lower().startswith('readme') for n in z.namelist())
            for name, details in entries.items():
                assert hashlib.sha256(z.read(name)).hexdigest() == details['sha256'], name
        temporary.replace(destination)
        print(f'{archive_name}: {len(files) + 1} files, '
              f'{destination.stat().st_size / 1_000_000:.1f} MB, CRC/SHA256 verified', flush=True)


if __name__ == '__main__':
    main()
