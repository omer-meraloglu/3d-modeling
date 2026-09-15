#!/usr/bin/env python3
"""Create a local delivery ZIP; generated large files stay out of Git."""
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parent
NAMES=['model.py','requirements.txt','render_preview.py','rasterizer.cpp',
       'verify_exports.py','package_deliverables.py','output_model.stl','output_model.3mf',
       'validation.json','export-verification.json','preview.png','clay-preview.png','back-preview.png','head-detail.png']

def main():
    for name in NAMES:assert (ROOT/name).is_file(),name+' is missing.'
    checked=json.loads((ROOT/'export-verification.json').read_text())
    for name,digest in checked['files_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name+' changed after verification.'
    manifest={'title':'Venom — symbiote bust','units':'millimeter','supports_required':True,
              'physical_print_tested':False,'files':[{'path':n,'bytes':(ROOT/n).stat().st_size,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in NAMES]}
    p=ROOT/'delivery-manifest.json';p.write_text(json.dumps(manifest,indent=2)+'\n')
    target=ROOT/'venom-sculpture-print-kit.zip';temp=target.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in [*NAMES,p.name]:z.write(ROOT/name,arcname='Venom Sculpture/'+name)
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        for row in manifest['files']:assert hashlib.sha256(z.read('Venom Sculpture/'+row['path'])).hexdigest()==row['sha256']
    temp.replace(target)
    print(f'{target}: {target.stat().st_size/1024/1024:.1f} MiB, SHA-256 and CRC checked.')
if __name__=='__main__':main()
