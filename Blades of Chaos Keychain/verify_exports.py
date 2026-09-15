#!/usr/bin/env python3
"""Reload and validate deliverables; no GUI required. Requires trimesh too."""
from pathlib import Path
import hashlib,json,struct,zipfile,xml.etree.ElementTree as ET
import numpy as np
import trimesh
import model

ROOT=Path(__file__).resolve().parent

def verify():
    results=[]
    for name in ('single_blade','crossed_blades'):
        stl=ROOT/(name+'.stl')
        mesh=trimesh.load_mesh(stl,process=True)
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume
        assert len(mesh.split(only_watertight=False))==1
        volume,_=model.validate(mesh.vertices,mesh.faces)
        with zipfile.ZipFile(ROOT/(name+'.3mf')) as z:
            assert z.testzip() is None
            root=ET.fromstring(z.read('3D/3dmodel.model'))
        ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
        assert root.attrib['unit']=='millimeter'
        verts=np.array([[float(v.attrib[k]) for k in ('x','y','z')] for v in root.findall('.//m:vertex',ns)])
        faces=np.array([[int(f.attrib[k]) for k in ('v1','v2','v3')] for f in root.findall('.//m:triangle',ns)])
        model.validate(verts,faces)
        npz=np.load(ROOT/(name+'.mesh.npz'))
        assert np.array_equal(faces,npz['faces'])
        assert np.max(np.abs(verts-npz['vertices']))<=.00000051
        raw=stl.read_bytes();n=struct.unpack('<I',raw[80:84])[0]
        dtype=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')])
        facets=np.frombuffer(raw,offset=84,count=n,dtype=dtype)
        assert np.array_equal(facets['v'],npz['vertices'].astype(np.float32)[faces])
        obj=trimesh.load_mesh(ROOT/(name+'.obj'),process=True)
        assert obj.is_watertight and obj.is_winding_consistent
        assert len(obj.faces)==len(mesh.faces)==len(faces)
        results.append({'file':name,'stl_3mf_obj_reload':'pass','closed_connected_volume':True,
                        'triangles':len(faces),'euler_characteristic':mesh.euler_number,
                        'volume_cm3':volume/1000,'sha256':hashlib.sha256(raw).hexdigest()})
        print(name+': STL, 3MF and OBJ reload verified.',flush=True)
    main_style=json.loads((ROOT/'output_model.validation.json').read_text())['style']
    main_name='single_blade' if main_style=='single' else 'crossed_blades'
    assert (ROOT/'output_model.stl').read_bytes()==(ROOT/(main_name+'.stl')).read_bytes()
    for length,hole in [(80.0,5.0),(110.0,4.2)]:
        model.SINGLE_LENGTH=length;model.KEYRING_HOLE_D=hole
        variant,verts,faces,_,_=model.build('single',pitch=.28)
        volume,_=model.validate(verts.astype(np.float32).astype(float),faces)
        assert abs(np.ptp(verts[:,0])-length)<1e-5
        assert len(variant.domain.interiors)==1
        results.append({'custom_length_mm':length,'custom_eyelet_mm':hole,
                        'watertight_one_shell':True,'triangles':len(faces),'mesh_pitch_mm':.28})
        print(f'Custom {length} mm / {hole} mm eyelet: pass.',flush=True)
    (ROOT/'export-verification.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':verify()
