"""Reload the actual oriented FDM deliverables and check they remain one solid."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
import numpy as np,trimesh
import one_piece_model as m
p=Path(__file__).resolve().parent;result={}
ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
for name in ['one_piece_model','one_piece_FDM_oriented','output_model']:
    mesh=trimesh.load_mesh(p/(name+'.stl'),process=True)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume
    report,_=m.validate(mesh.vertices,mesh.faces,check_support=False)
    report['one_connected_solid']=True;report.pop('support_check_passed')
    with zipfile.ZipFile(p/(name+'.3mf')) as z:
        assert z.testzip() is None;root=ET.fromstring(z.read('3D/3dmodel.model'))
    assert root.attrib['unit']=='millimeter';assert len(root.findall('.//m:object',ns))==1
    v=np.array([[float(q.attrib[k]) for k in ('x','y','z')] for q in root.findall('.//m:vertex',ns)])
    f=np.array([[int(q.attrib[k]) for k in ('v1','v2','v3')] for q in root.findall('.//m:triangle',ns)])
    m.validate(v,f,check_support=False)
    assert len(f)==len(mesh.faces)
    report['3mf_one_object_mm']=True;result[name]=report
    print(name,'STL/3MF reload passed',flush=True)
assert (p/'output_model.stl').read_bytes()==(p/'one_piece_FDM_oriented.stl').read_bytes()
assert abs(result['one_piece_model']['volume_cm3']-result['output_model']['volume_cm3'])<1e-5
result['physical_print_tested']=False;result['slicer_supports_required']=True
(p/'one-piece-export-verification.json').write_text(json.dumps(result,indent=2))
