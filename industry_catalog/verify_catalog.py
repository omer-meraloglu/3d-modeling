#!/usr/bin/env python3
"""Independently reload print files; verify topology, units, bounds and volumes.
Each model.py also checks exact CAD validity, CAD self-intersection, assembly
clearance and STEP import. Those checks run again whenever a model is rebuilt.
"""
from pathlib import Path
import argparse, json, zipfile, xml.etree.ElementTree as ET, hashlib
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parent
NS={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--only',nargs='+');args=ap.parse_args()
    reports={}
    for folder in sorted(ROOT.glob('[0-9][0-9]_*')):
        if not folder.is_dir() or args.only and folder.name[:2] not in args.only:continue
        meta=json.loads((folder/'validation.json').read_text())
        plate=trimesh.load_mesh(folder/'output_model.stl',process=True)
        assert plate.is_watertight and plate.is_winding_consistent and plate.is_volume
        assert plate.body_count==meta['parts']
        with zipfile.ZipFile(folder/'output_model.3mf') as z:
            assert z.testzip() is None
            xml=ET.fromstring(z.read('3D/3dmodel.model'))
        assert xml.attrib['unit']=='millimeter'
        meshes=[];ids=[]
        for ob in xml.findall('m:resources/m:object',NS):
            v=np.array([[float(q.attrib[k]) for k in ['x','y','z']] for q in ob.findall('m:mesh/m:vertices/m:vertex',NS)])
            f=np.array([[int(q.attrib[k]) for k in ['v1','v2','v3']] for q in ob.findall('m:mesh/m:triangles/m:triangle',NS)])
            m=trimesh.Trimesh(v,f,process=False)
            assert m.is_watertight and m.is_winding_consistent and m.is_volume and m.body_count==1
            assert np.min(m.area_faces)>1e-10 and len(m.faces)==len(m.unique_faces().nonzero()[0])
            assert abs(m.bounds[0,2])<1e-6 and np.all(m.bounds[0,:2]>=0) and np.all(m.bounds[1,:2]<=220)
            bad=(m.face_normals[:,2]<-1/np.sqrt(2)-.0003)&(m.triangles[:,:,2].max(axis=1)>1e-4)
            assert m.area_faces[bad].sum()<1e-6
            ids.append(ob.attrib['id']);meshes.append(m)
        build=[i.attrib['objectid'] for i in xml.findall('m:build/m:item',NS)]
        assert ids==build and len(meshes)==meta['parts']
        combined=trimesh.util.concatenate(meshes)
        assert abs(combined.volume-plate.volume)/plate.volume<1e-6
        assert np.allclose(combined.bounds,plate.bounds,atol=1e-5)
        assert len(combined.faces)==len(plate.faces)
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.suffix in ('.stl','.step','.3mf','.py')}
        report={'files_sha256':files,'reloaded_3mf_objects':len(meshes),'units':'millimeter','watertight':True,
                'consistent_winding':True,'positive_volume':True,'no_degenerate_or_duplicate_facets':True,
                'stl_3mf_agree':True,'fits_220_mm_bed':True,'unsupported_area_beyond_45_deg_mm2':0.0,
                'dimensions_mm':plate.extents.tolist(),'triangles':len(plate.faces),'physical_tested':False}
        (folder/'export-verification.json').write_text(json.dumps(report,indent=2)+'\n')
        reports[folder.name]=report
        print(folder.name+': independent STL/3MF verification passed.',flush=True)
    if not args.only:(ROOT/'catalog-verification.json').write_text(json.dumps(reports,indent=2)+'\n')

if __name__=='__main__':main()
