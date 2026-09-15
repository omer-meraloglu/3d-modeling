#!/usr/bin/env python3
"""Package the six models locally, without network or Git actions.
Large exports stay local; the ZIP contains no additional README.
"""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'polukal-industry-catalog.zip'

def main():
    products=json.loads((ROOT/'catalog.json').read_text())['products']
    for p in products:
        for n in ['model.py','output_model.stl','output_model.3mf','output_model.step','preview.png','validation.json','export-verification.json']:
            assert (ROOT/p['id']/n).is_file(),p['id']+'/'+n+' missing; build/verify/render first.'
        report=json.loads((ROOT/p['id']/'export-verification.json').read_text())
        for name,wanted in report['files_sha256'].items():
            assert hashlib.sha256((ROOT/p['id']/name).read_bytes()).hexdigest()==wanted,'Changed since verification: '+p['id']+'/'+name
    allowed={'.py','.cpp','.txt','.json','.png','.stl','.3mf','.step','.html'}
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.suffix in allowed and '__pycache__' not in p.parts and p.name not in ['preview_mesh.json','delivery-manifest.json'] and not p.name.lower().startswith('readme'))
    manifest={'brand':'polukal','catalog':'Industry applications','contents':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    mp=ROOT/'delivery-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
    tmp=OUT.with_suffix('.zip.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in [*files,mp]:z.write(p,arcname='industry_catalog/'+str(p.relative_to(ROOT)))
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None
        for r in manifest['contents']:
            raw=z.read('industry_catalog/'+r['path']);assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
        assert not any(Path(n).name.lower().startswith('readme') for n in z.namelist())
    tmp.replace(OUT);print(f'{OUT}: {len(files)+1} files, {OUT.stat().st_size/1024/1024:.2f} MiB; CRC and SHA-256 checked.')
if __name__=='__main__':main()
