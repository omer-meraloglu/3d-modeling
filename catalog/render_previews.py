"""Render product previews without a display server or GUI."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
products = json.loads((ROOT/'catalog.json').read_text())
BACKGROUND = '#f3f4f4'
INK = '#21333a'
COLORS = {'B2B': '#248b92', 'B2C': '#d78751'}

def geometry(mesh):
    v = np.asarray(mesh['vertices'], float)
    f = np.asarray(mesh['faces'], int)
    triangles = v[f]
    normals = np.cross(triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:,None], 1e-12)
    edges = {}
    for i, face in enumerate(f):
        for a,b in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
            key = tuple(sorted((tuple(v[a]),tuple(v[b]))))
            edges.setdefault(key, []).append(i)
    lines = [list(edge) for edge, faces in edges.items()
             if len(faces)!=2 or np.dot(normals[faces[0]],normals[faces[1]]) < 0.85]
    return triangles, normals, lines

RENDERS = {}

def raster(item, width=1000, height=720):
    """Orthographic CPU rasterizer with a depth buffer; no hidden-face artifacts."""
    color = np.array(to_rgb(COLORS[item['category']]))*255
    azimuth = -140 if item['id']=='b2c_phone_stand' else -55
    az,el=np.radians(azimuth),np.radians(24)
    camera=np.array([np.cos(az)*np.cos(el),np.sin(az)*np.cos(el),np.sin(el)])
    right=np.array([-np.sin(az),np.cos(az),0])
    up=np.cross(camera,right)
    projection=np.stack([right,-up,camera],axis=1)
    meshes=item['meshes']+item['references']
    projected=np.concatenate([np.asarray(m['vertices'])@projection for m in meshes])
    lo,hi=projected.min(axis=0),projected.max(axis=0)
    scale=min(width*.87/max(hi[0]-lo[0],1),height*.86/max(hi[1]-lo[1],1))
    offset=np.array([width/2-(lo[0]+hi[0])*scale/2,height/2-(lo[1]+hi[1])*scale/2])
    def screen(points):
        p=np.asarray(points)@projection
        p[:,:2]=p[:,:2]*scale+offset
        return p
    background=(np.array(to_rgb(BACKGROUND))*255).astype(np.uint8)
    pixels=np.broadcast_to(background,(height,width,3)).copy()
    depth=np.full((height,width),-np.inf)
    light = np.array([-0.3,-0.6,1.0]); light /= np.linalg.norm(light)
    for mesh in item['meshes']:
        tris,normals,_=geometry(mesh)
        vertices=screen(mesh['vertices'])
        for ids,normal in zip(mesh['faces'],normals):
            if normal@camera<=0:continue
            t=vertices[ids]
            xmin=max(0,int(np.floor(t[:,0].min())))
            xmax=min(width-1,int(np.ceil(t[:,0].max())))
            ymin=max(0,int(np.floor(t[:,1].min())))
            ymax=min(height-1,int(np.ceil(t[:,1].max())))
            if xmin>xmax or ymin>ymax:continue
            x0,y0,z0=t[0];x1,y1,z1=t[1];x2,y2,z2=t[2]
            denominator=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
            if abs(denominator)<1e-9:continue
            yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1]
            xx=xx+.5;yy=yy+.5
            a=((y1-y2)*(xx-x2)+(x2-x1)*(yy-y2))/denominator
            b=((y2-y0)*(xx-x2)+(x0-x2)*(yy-y2))/denominator
            c=1-a-b
            z=a*z0+b*z1+c*z2
            block=depth[ymin:ymax+1,xmin:xmax+1]
            win=(a>=-1e-7)&(b>=-1e-7)&(c>=-1e-7)&(z>block)
            block[win]=z[win]
            bright=max(0,float(normal@light))
            shade=np.clip(color*(.58+.38*bright)+12*bright,0,255).astype(np.uint8)
            pixels[ymin:ymax+1,xmin:xmax+1][win]=shade
    image=Image.fromarray(pixels)
    pen=ImageDraw.Draw(image)
    for mesh in item['references']:
        _,normals,_=geometry(mesh)
        v=np.asarray(mesh['vertices']);faces=mesh['faces'];edges={}
        for fi,face in enumerate(faces):
            for a,b in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
                key=tuple(sorted((tuple(v[a]),tuple(v[b]))))
                edges.setdefault(key,[]).append(fi)
        for edge,fs in edges.items():
            hard=len(fs)!=2 or normals[fs[0]]@normals[fs[1]]<.85
            silhouette=len(fs)==2 and (normals[fs[0]]@camera)*(normals[fs[1]]@camera)<=0
            if not(hard or silhouette):continue
            a,b=screen(edge)[:,:2]
            length=np.linalg.norm(b-a)
            for start in np.arange(0,length,9):
                p=a+(b-a)*start/max(length,1)
                q=a+(b-a)*min(start+4,length)/max(length,1)
                pen.line([tuple(p),tuple(q)],fill='#aab7bc',width=1)
    return image

def draw(ax,item,reference=True):
    if item['id'] not in RENDERS:RENDERS[item['id']]=raster(item)
    ax.imshow(RENDERS[item['id']],interpolation='lanczos')
    ax.set_axis_off()

items=[]
for p in products:
    item={**p,**json.loads((ROOT/p['pid']/'preview_mesh.json').read_text())}
    items.append(item)
    fig=plt.figure(figsize=(8,6),dpi=150,facecolor=BACKGROUND)
    ax=fig.add_axes([0,0.12,1,0.88])
    draw(ax,item)
    fig.text(.06,.08,item['title'],color=INK,fontsize=18,weight='medium')
    fig.text(.06,.04,f"{item['category']}  ·  {item['parts']} printable part(s)  ·  {item['volume_cm3']:.1f} cm³ solid geometry",
             color='#576971',fontsize=10)
    fig.savefig(ROOT/p['pid']/'preview.png',facecolor=BACKGROUND)
    plt.close(fig)

fig=plt.figure(figsize=(15,10.6),dpi=150,facecolor=BACKGROUND)
fig.text(.04,.95,'Six products. Two markets.',fontsize=26,color=INK,weight='medium')
fig.text(.04,.916,'Original parametric CAD designs  /  actual-model previews',fontsize=11,color='#576971')
for i,item in enumerate(items):
    row,col=divmod(i,3)
    left=.02+col*.326
    bottom=.50-row*.405
    ax=fig.add_axes([left,bottom+.065,.315,.315])
    draw(ax,item)
    fig.text(left+.025,bottom+.022,f"{'B' if row==0 else 'C'}{col+1:02d}  {item['title']}",
             fontsize=12,color=INK,weight='medium')
    fig.text(left+.025,bottom-.005,
             f"{item['category']} · {item['parts']} part(s) · {item['volume_cm3']:.1f} cm³",
             fontsize=10,color='#576971')
fig.text(.04,.045,'Gray outlines: reference devices, excluded from print files. Volume is solid CAD volume, not slicer material use.',
         fontsize=9,color='#576971')
fig.text(.04,.023,'All six pass geometry and 45° overhang checks in their exported orientations. Physical fit and load testing remain.',
         fontsize=9,color='#576971')
fig.savefig(ROOT/'hero-products-preview.png',facecolor=BACKGROUND)
plt.close(fig)
(ROOT/'catalog_preview_data.json').write_text(json.dumps(items,separators=(',',':')))

readme=['# Hero product catalog','',
        'Six original CadQuery designs, split evenly between B2B and B2C. Each product folder contains an independent `model.py`, printable STL, assembled STEP, preview PNG, and mesh data.','',
        '![Six product previews](hero-products-preview.png)','',
        '## Run or customize','',
        'Install Python and CadQuery once: `python -m pip install cadquery==2.6.1`. Change into a product folder, edit the exposed parameters at the top of `model.py`, then run `python model.py`. Outputs are relative to your current working directory. Import STL as millimeters.','',
        'Each script is self-contained; `build_catalog.py` and `render_previews.py` are optional catalog maintenance tools. Rerunning `build_catalog.py` restores the catalog defaults and overwrites product scripts.','',
        '## Products','']
for item in items:
    name=item['pid']
    readme += [f"### {item['title']} — {item['category']}",'',item['use'],'',
               f"- Customer: {item['buyer']}",f"- Customize: {item['customize']}",
               f"- Hardware: {item['hardware']}",f"- Printing: {item['print_note']}",
               f"- Output: {item['parts']} printable part(s); {item['footprint_mm'][0]} × {item['footprint_mm'][1]} mm print footprint.",
               f"- Files: [Python]({name}/model.py) · [STL]({name}/output_model.stl) · [STEP]({name}/output_model.step) · [Preview]({name}/preview.png)",'']
readme += ['## Validation and manufacturing','',
           'Defaults and one dimensionally customized variant of each product executed using Python 3.12 and CadQuery 2.6.1; variants used 0.30 mm per-side clearance. Each printable component passed valid-solid and CAD self-intersection checks. Assembled printable components were checked for collisions. Exported STL files passed edge-manifold, winding, facet-normal, shell-count, positive-volume, CAD-volume agreement, and support-free 45-degree overhang checks. The six default jobs contain eight printable components in total.','',
           'Nominal mating clearances are 0.25 mm per side. These checks validate digital geometry; they do not establish print accuracy, load ratings, environmental performance, or sales demand. Calibrate your printer and selected material, then qualify first articles. Slicer estimates are required for actual mass and print time. Gray reference devices are omitted from STL and STEP files.','',
           '## Category references','',
           'These sources establish commercial product categories, not sales estimates or endorsements of these designs:',
           '- [Phoenix Contact: electronics housings](https://www.phoenixcontact.com/en-us/products/electronics-housings)',
           '- [Carr Lane: modular fixturing](https://www.carrlane.com/engineering-resources/technical-information/manual-workholding/modular-fixturing)',
           '- [IKEA: SIGNUM cable management](https://www.ikea.com/gb/en/p/signum-cable-trunking-horizontal-silver-colour-30200253/)',
           '- [Twelve South: BookArc Flex](https://www.twelvesouth.com/products/bookarc-flex)','']
# Project documentation is centralized in the sole root README.
import re
section='\n'.join(readme)
section=re.sub(r'^(#+) ',r'\1# ',section,flags=re.M)
section=re.sub(r'(?<=\]\()([^\)]+)(?=\))',lambda m: m.group(1) if m.group(1).startswith(('http:','https:','#')) else 'catalog/'+m.group(1),section)
target=ROOT.parent/'README.md'
existing=target.read_text() if target.exists() else '# 3d-modeling\n'
start='<!-- BEGIN CATALOG DOCS -->';end='<!-- END CATALOG DOCS -->'
block=start+'\n'+section+'\n'+end
if start in existing and end in existing:
    existing=existing[:existing.index(start)]+block+existing[existing.index(end)+len(end):]
else:existing+='\n\n'+block+'\n'
target.write_text(existing)
print('Rendered six previews and the catalog contact sheet.',flush=True)
