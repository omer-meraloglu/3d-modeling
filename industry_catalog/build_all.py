#!/usr/bin/env python3
"""Build all six standalone CAD models, or select IDs: --only 04 05.
Run from any directory. Existing source files are never regenerated/overwritten.
"""
from pathlib import Path
import argparse, subprocess, sys
ROOT=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only',nargs='+',help='Two-digit product IDs, e.g. 04 05')
    ap.add_argument('--previews',action='store_true',help='Also render actual CAD previews (requires clang++).')
    args=ap.parse_args();folders=sorted(p.parent for p in ROOT.glob('[0-9][0-9]_*/model.py'))
    if args.only:
        available={p.name[:2] for p in folders}
        if set(args.only)-available:ap.error('Unknown ID. Available: '+', '.join(sorted(available)))
        folders=[p for p in folders if p.name[:2] in args.only]
    for folder in folders:
        print('Building '+folder.name,flush=True)
        subprocess.run([sys.executable,'model.py'],cwd=folder,check=True)
    subprocess.run([sys.executable,str(ROOT/'verify_catalog.py'),*['--only',*[p.name[:2] for p in folders]]],check=True)
    if args.previews:subprocess.run([sys.executable,str(ROOT/'render_catalog.py'),*[p.name for p in folders]],check=True)

if __name__=='__main__':main()
