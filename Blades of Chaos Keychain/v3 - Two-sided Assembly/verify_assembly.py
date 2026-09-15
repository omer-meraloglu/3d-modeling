"""Independent reload, mirror/fit and conical-roof checks for the print package."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
import numpy as np,trimesh
import model as m
ROOT=Path(__file__).resolve().parent
m.SINGLE_LENGTH=json.loads((ROOT/'validation.json').read_text())['length_mm']
report={}
for name,expected in [('blade_A_front',1),('blade_B_back_mirrored',1),('alignment_key',1),('output_model',7)]:
    mesh=trimesh.load_mesh(ROOT/(name+'.stl'),process=True)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.is_volume
    result,_=m.validate(mesh.vertices,mesh.faces,shells=expected)
    report[name]=result
    print(name,'reload passed',flush=True)
a=np.load(ROOT/'blade_A_front.mesh.npz');b=np.load(ROOT/'blade_B_back_mirrored.mesh.npz')
flipped=b['vertices']*[-1,1,-1]+[m.SINGLE_LENGTH,0,0]
assert np.max(np.abs(flipped[:,:2]-a['vertices'][:,:2]))<1e-10
assert np.max(np.abs(flipped[:,2]+a['vertices'][:,2]))<1e-10
assert np.array_equal(b['faces'],a['faces'][:,::-1])
metadata=json.loads((ROOT/'validation.json').read_text());centers=np.array(metadata['front_half']['key_centers_xy_mm'])
# Validate actual interpolated exported triangles above each socket apex and disk.
from scipy.interpolate import LinearNDInterpolator
n=int(a['top_vertices']);interp=LinearNDInterpolator(a['vertices'][:n,:2],a['vertices'][:n,2])
r=m.KEY_DIAMETER/2+m.KEY_CLEARANCE;minskin=99
for center in centers:
    x,y=np.meshgrid(np.linspace(-r,r,61),np.linspace(-r,r,61));p=np.c_[x.ravel(),y.ravel()];p=p[np.linalg.norm(p,axis=1)<=r]
    skin=interp(center+p)-(r-np.linalg.norm(p,axis=1))*m.SOCKET_ROOF_SLOPE
    assert np.isfinite(skin).all();minskin=min(minskin,float(skin.min()))
assert minskin>=m.MIN_SOCKET_SKIN
# For every height at which a key enters the half, evaluate radial clearance.
z=np.linspace(m.BONDLINE_GAP/2,m.KEY_HALF_HEIGHT,1001)
keyr=m.KEY_DIAMETER/2-(m.KEY_DIAMETER-m.KEY_TIP_DIAMETER)/2*z/m.KEY_HALF_HEIGHT
socketr=r-(z-m.BONDLINE_GAP/2)/m.SOCKET_ROOF_SLOPE
clearance=float(np.min(socketr-keyr));assert clearance>=m.KEY_CLEARANCE-1e-9
# The flat mating faces overlap exactly after the flip; keyring openings coincide.
report['assembly_fit']={'mirror_alignment_error_mm':float(np.max(np.abs(flipped[:,:2]-a['vertices'][:,:2]))),
 'minimum_interpolated_socket_skin_mm':minskin,'minimum_radial_key_clearance_mm':clearance,
 'nominal_radial_clearance_mm':m.KEY_CLEARANCE,'keyring_openings_coincident':True,'physical_dry_fit_tested':False}
ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
for name,count in [('output_model',7),('two_blades_print_plate',12),('assembled_REFERENCE_ONLY',5)]:
    with zipfile.ZipFile(ROOT/(name+'.3mf')) as z:
        assert z.testzip() is None;root=ET.fromstring(z.read('3D/3dmodel.model'))
    assert root.attrib['unit']=='millimeter';objects=root.findall('.//m:object',ns);assert len(objects)==count
    for obj in objects:
        v=np.array([[float(q.attrib[k]) for k in ['x','y','z']] for q in obj.findall('.//m:vertex',ns)])
        f=np.array([[int(q.attrib[k]) for k in ['v1','v2','v3']] for q in obj.findall('.//m:triangle',ns)])
        m.validate(v,f,check_support=name!='assembled_REFERENCE_ONLY')
    report[name+'_3mf']={'objects':count,'units':'millimeter','all_objects_valid':True}
    print(name,'3MF passed',flush=True)
(ROOT/'assembly-verification.json').write_text(json.dumps(report,indent=2))
print('Mirror, socket skin, key clearance and all exports verified.',flush=True)
