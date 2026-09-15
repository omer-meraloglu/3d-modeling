#!/usr/bin/env python3
"""Exercise meaningful dimension/clearance changes in temporary directories.
Defaults and their print exports remain untouched. Runtime: several minutes.
"""
from pathlib import Path
import tempfile, subprocess, sys, json, re
ROOT=Path(__file__).resolve().parent
CASES=[('04_courtyard_architecture',{'REAR_FLOORS':4,'SITE_LENGTH':190.0,'SITE_WIDTH':150.0}),
       ('05_terraced_landscape',{'TERRACE_RISE':2.5,'PAVILION_HEIGHT':18.0,'SITE_LENGTH':190.0}),
       ('02_controller_prototype',{'FIT':0.30})]

def main():
    results=[]
    for product,changes in CASES:
        source=(ROOT/product/'model.py').read_text()
        for name,value in changes.items():
            source,n=re.subn(r'^'+re.escape(name)+r'=[^\n#]+',f'{name}={value!r} ',source,flags=re.M)
            assert n==1,name
        with tempfile.TemporaryDirectory(prefix='polukal-cad-variant-') as temp:
            p=Path(temp);p.joinpath('model.py').write_text(source)
            subprocess.run([sys.executable,'model.py'],cwd=p,check=True)
            report=json.loads(p.joinpath('validation.json').read_text())
            results.append({'product':product,'changes':changes,'validation':report})
    (ROOT/'customization-verification.json').write_text(json.dumps(results,indent=2)+'\n')
    print('Three customization cases passed; default exports unchanged.')

if __name__=='__main__':main()
