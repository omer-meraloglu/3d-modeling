#!/usr/bin/env python3
"""Reload delivered STL/3MF files and check the actual exported solids."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
import numpy as np
import trimesh
import model

ROOT=Path(__file__).resolve().parent
NS={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

def main():
    result={}
    expected_length=json.loads((ROOT/'validation.json').read_text())['nominal_length_mm']
    for name in ('one_piece_model','one_piece_FDM_oriented','output_model'):
        stl=trimesh.load_mesh(ROOT/(name+'.stl'),process=True)
        assert stl.is_watertight and stl.is_winding_consistent and stl.is_volume
        assert stl.body_count==1,'Disconnected pieces'
        assert stl.euler_number==-4,'Expected exactly three through openings'
        report,_=model.validate(stl.vertices,stl.faces,check_support=False)
        report.pop('support_check_passed')
        with zipfile.ZipFile(ROOT/(name+'.3mf')) as z:
            assert z.testzip() is None
            xml=ET.fromstring(z.read('3D/3dmodel.model'))
        assert xml.attrib['unit']=='millimeter'
        assert len(xml.findall('.//m:object',NS))==1
        vertices=np.array([[float(p.attrib[a]) for a in ('x','y','z')]
                           for p in xml.findall('.//m:vertex',NS)])
        faces=np.array([[int(p.attrib[a]) for a in ('v1','v2','v3')]
                        for p in xml.findall('.//m:triangle',NS)])
        model.validate(vertices,faces,check_support=False)
        assert len(faces)==len(stl.faces)
        assert np.allclose(np.ptp(vertices,axis=0),stl.extents,atol=2e-5)
        report.update({'3mf_units':'millimeter','3mf_objects':1,
                       'through_openings':3,'STL_3MF_match':True})
        result[name]=report
        print(name+': STL/3MF closed-solid reload passed',flush=True)
    assert (ROOT/'output_model.stl').read_bytes()==(ROOT/'one_piece_FDM_oriented.stl').read_bytes()
    assert abs(result['one_piece_model']['volume_cm3']-result['output_model']['volume_cm3'])<1e-5
    assert abs(result['one_piece_model']['dimensions_mm'][0]-expected_length)<1e-4
    result['physical_print_tested']=False
    result['supports_required']=True
    (ROOT/'export-verification.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
