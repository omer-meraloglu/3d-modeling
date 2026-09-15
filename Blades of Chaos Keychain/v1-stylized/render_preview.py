#!/usr/bin/env python3
"""Headless previews from the exact exported CAD meshes. Requires NumPy/Pillow.

Preview bronze/steel/red tones illustrate an optional painted finish; STL is
single-material geometry. This does not generate or edit imagery through AI.
"""
from pathlib import Path
import ctypes
import json
import math
import platform
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parent


def load_renderer():
    binary=ROOT/('rasterizer.dylib' if platform.system()=='Darwin' else 'rasterizer.so')
    source=ROOT/'rasterizer.cpp'
    if not binary.exists() or source.stat().st_mtime>binary.stat().st_mtime:
        flags=[]
        if platform.system()=='Darwin':
            sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
            flags=['-isysroot',sdk,'-isystem',str(Path(sdk)/'usr/include/c++/v1')]
        subprocess.run(['clang++','-O3','-std=c++17','-shared','-fPIC',*flags,
                        str(source),'-o',str(binary)],check=True)
    library=ctypes.CDLL(str(binary));render=library.render_mesh
    f=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
    u=np.ctypeslib.ndpointer(dtype=np.uint8,flags='C_CONTIGUOUS')
    render.argtypes=[f,f,f,ctypes.c_int,ctypes.c_int,ctypes.c_int,
                     ctypes.c_float,ctypes.c_float,ctypes.c_float,u]
    return render


RENDER=load_renderer()


def font(size,bold=False):
    p=Path('/System/Library/Fonts/Avenir Next.ttc')
    if p.exists():return ImageFont.truetype(str(p),size,index=2 if bold else 7)
    import matplotlib
    p=Path(matplotlib.__file__).parent/'mpl-data/fonts/ttf'
    return ImageFont.truetype(str(p/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)


def render(item,width,height,paint=True,top=False):
    vertices=np.array(item['vertices'],np.float32)
    faces=np.array(item['faces'],np.int32)
    tri=vertices[faces]
    n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
    # Smooth tangential tessellation edges only; keep the sculptural shoulders.
    adjacent={}
    for i,ids in enumerate(faces):
        for j in ids:adjacent.setdefault(tuple(np.round(vertices[j],5)),[]).append(i)
    normals=[]
    for i,ids in enumerate(faces):
        for j in ids:
            nearby=n[adjacent[tuple(np.round(vertices[j],5))]]
            vec=nearby[nearby@n[i]>.90].sum(axis=0)
            vec/=max(np.linalg.norm(vec),1e-12)
            normals.append(vec)
    materials=np.tile(np.array([171,184,182,.28,0],np.float32),(len(faces),1))
    z=tri[:,:,2].mean(axis=1)
    if paint:
        body=item.get('body_thickness_mm',3.6)
        grip=item.get('grip_relief_mm',.6)
        guard=item.get('guard_relief_mm',1.2)
        depth=item.get('groove_depth_mm',.48)
        rises=[0,item.get('crossed_layer_rise_mm',0)]
        for rise in rises:
            h=body+rise
            relief=((z>h+.04)&(z<h+grip+.012)) | ((z>h+guard-.3)&(z<h+guard+.26))
            materials[relief,:3]=[180,133,70]
        for rise in rises:
            h=body+rise
            materials[(np.abs(z-h)<.012)&(n[:,2]>.9),:3]=[171,184,182]
            engraved=(np.abs(z-(h-depth))<.012)&(n[:,2]>.9)
            materials[engraved,:3]=[105,40,29]
            materials[(np.abs(z-(h+guard+.24-depth))<.012)&(n[:,2]>.9),:3]=[66,45,30]
    angle=math.radians(90 if top else 61)
    view=np.array([.12*math.cos(angle),-math.cos(angle),math.sin(angle)],np.float32)
    view/=np.linalg.norm(view)
    right=np.cross([0,0,1],view) if not top else np.array([1,0,0],np.float32)
    right=right/np.linalg.norm(right);up=np.cross(view,right)
    projection=np.stack([right,-up,view],axis=1).astype(np.float32)
    v=tri.reshape(-1,3)@projection
    low,high=v.min(axis=0),v.max(axis=0)
    scale=min(width*.89/(high[0]-low[0]),height*.91/(high[1]-low[1]))
    v[:,:2]=v[:,:2]*scale+np.array([width/2-(low[0]+high[0])*scale/2,
                                  height/2-(low[1]+high[1])*scale/2])
    out=np.empty((height,width,4),np.uint8)
    RENDER(np.ascontiguousarray(v,np.float32),np.ascontiguousarray(normals,np.float32),
           np.ascontiguousarray(materials,np.float32),len(faces),width,height,
           *map(float,view),out)
    return Image.fromarray(out,'RGBA')


def main():
    data=[json.loads((ROOT/(name+'.mesh.json')).read_text()) for name in ('single_blade','crossed_blades')]
    canvas=Image.new('RGB',(1800,1420),'#151a1d').convert('RGBA');d=ImageDraw.Draw(canvas)
    d.text((95,65),'BLADES OF CHAOS',font=font(64,True),fill='#eee9df')
    d.text((99,156),'3D-PRINTABLE KEYCHAINS  /  ACTUAL CAD GEOMETRY',font=font(24),fill='#8f9c9c')
    for i,item in enumerate(data):
        x=75+850*i
        d.rounded_rectangle((x,245,x+800,1180),radius=22,fill='#20272b',outline='#354044',width=2)
        im=render(item,1050,1200).resize((700,800),Image.Resampling.LANCZOS)
        shadow=Image.new('RGBA',im.size);shadow.putalpha(im.getchannel('A').point(lambda v:int(v*.25)))
        shadow=shadow.filter(ImageFilter.GaussianBlur(10))
        canvas.alpha_composite(shadow,(x+56,286))
        canvas.alpha_composite(im,(x+40,268))
        title='SINGLE BLADE' if i==0 else 'CROSSED BLADES'
        d.text((x+45,1093),title,font=font(30,True),fill='#eee9df')
        size=' × '.join(f'{v:.1f}' for v in item['size_mm'])+' mm'
        d.text((x+45,1136),size,font=font(25),fill='#aeb8b7')
        individual=Image.new('RGBA',(1050,1300),'#20272b')
        individual.alpha_composite(render(item,1000,1150),(25,45))
        ImageDraw.Draw(individual).text((70,1202),title+'  |  '+size,font=font(25),fill='#eee9df')
        individual.convert('RGB').save(ROOT/(item['style']+'-preview.png'))
        flat=Image.new('RGBA',(1200,1200),'#f0ede5')
        flat.alpha_composite(render(item,1120,1120,paint=False,top=True),(40,40))
        flat.convert('RGB').save(ROOT/(item['style']+'-top-view.png'))
    d.text((99,1234),'FLAT BACK    •    4.6 mm KEYRING HOLES    •    ONE SOLID PER DESIGN',font=font(27),fill='#d6c19b')
    d.text((99,1291),'Steel, bronze and red illustrate an optional painted finish; STL files contain geometry only.',
           font=font(25),fill='#98a4a4')
    d.text((99,1334),'Stylized miniature fan art  /  no game-extracted mesh',font=font(24),fill='#7a888a')
    canvas.convert('RGB').save(ROOT/'preview.png')
    print(ROOT/'preview.png')


if __name__=='__main__':main()
