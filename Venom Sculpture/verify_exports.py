#!/usr/bin/env python3
"""Independently verify delivered STL and 3MF meshes, sizes and units."""
from pathlib import Path
import hashlib,json,zipfile,xml.etree.ElementTree as ET
import numpy as np
import trimesh,manifold3d as md
ROOT=Path(__file__).resolve().parent

def check(mesh):
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume
    assert mesh.body_count==1
    assert np.all(mesh.area_faces>1e-12)
    edges,counts=np.unique(mesh.edges_sorted,axis=0,return_counts=True)
    assert np.all(counts==2)
    assert abs(mesh.bounds[0,2])<1e-5
    assert mesh.extents[0]<210 and mesh.extents[1]<210 and mesh.extents[2]<=220.001
    return {'watertight':True,'consistent_winding':True,'positive_volume':True,
            'connected_shells':1,'every_edge_has_two_faces':True,
            'triangles':len(mesh.faces),'dimensions_mm':mesh.extents.tolist(),'volume_cm3':float(mesh.volume/1000)}

def main():
    meta=json.loads((ROOT/'validation.json').read_text());assert not meta['draft']
    stl=trimesh.load_mesh(ROOT/'output_model.stl',process=True);a=check(stl)
    v=[];f=[]
    with zipfile.ZipFile(ROOT/'output_model.3mf') as z:
        assert z.testzip() is None
        with z.open('3D/3dmodel.model') as raw:
            for event,el in ET.iterparse(raw,events=('start','end')):
                tag=el.tag.split('}')[-1]
                if event=='start' and tag=='model':assert el.attrib['unit']=='millimeter'
                if event=='end':
                    if tag=='vertex':v.append([float(el.attrib[k]) for k in ('x','y','z')])
                    if tag=='triangle':f.append([int(el.attrib[k]) for k in ('v1','v2','v3')])
                    el.clear()
    mf=trimesh.Trimesh(np.array(v),np.array(f),process=False);b=check(mf)
    assert len(stl.faces)==len(mf.faces) and np.allclose(stl.bounds,mf.bounds,atol=1e-6)
    assert abs(stl.volume-mf.volume)/stl.volume<1e-7
    obj=md.Manifold(md.Mesh64(np.ascontiguousarray(stl.vertices,np.float64),np.ascontiguousarray(stl.faces,np.uint64)))
    assert obj.status()==md.Error.NoError and len(obj.decompose())==1
    assert abs(stl.extents[2]-meta['height_mm'])<1e-3
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'model.py',ROOT/'output_model.stl',ROOT/'output_model.3mf']}
    report={'stl':a,'3mf':b,'stl_3mf_agree':True,'manifold_reload_valid':True,'supports_required':True,
            'physical_tested':False,'files_sha256':files}
    (ROOT/'export-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('STL and 3MF independently verified: one closed shell, millimeter units, matching geometry.',flush=True)
if __name__=='__main__':main()
