#!/usr/bin/env python3
"""Render the actual exported mesh without a GUI. Color is an optional finish.

Requires numpy, Pillow and a C++17 compiler. CAD geometry is never AI-generated
or retouched in these previews. The monochrome view shows the same relief.
"""
from pathlib import Path
import ctypes, math, platform, subprocess
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
    render.argtypes=[f,f,f,f,f,ctypes.c_int,ctypes.c_int,
                     ctypes.c_float,ctypes.c_float,ctypes.c_float,
                     ctypes.c_int,ctypes.c_int,ctypes.c_int,
                     ctypes.c_float,ctypes.c_float,ctypes.c_float,u]
    height=library.build_heightfield
    height.argtypes=[f,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_float,ctypes.c_float,ctypes.c_float,f]
    return render,height

RENDER,HEIGHT=load_renderer()
HEIGHT_CACHE={}

def font(size,bold=False):
    p=Path('/System/Library/Fonts/Avenir Next.ttc')
    if p.exists():return ImageFont.truetype(str(p),size,index=2 if bold else 7)
    import matplotlib
    p=Path(matplotlib.__file__).parent/'mpl-data/fonts/ttf'
    return ImageFont.truetype(str(p/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)

def render(item,width,height,paint=True,elevation=45,angle=-6):
    if isinstance(item,str):item=dict(np.load(ROOT/(item+'.mesh.npz')))
    vertices=item['vertices'].astype(np.float32).copy();faces=item['faces']
    original_z=vertices[:,2].copy();vertices[:,2]-=vertices[:,2].min()
    tri=vertices[faces];raw=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    normals=raw/np.maximum(np.linalg.norm(raw,axis=1)[:,None],1e-12)
    mask=item.get('smooth_faces',np.arange(len(faces))<int(item.get('top_count',0)))
    vertex_normals=np.zeros_like(vertices)
    for k in range(3):np.add.at(vertex_normals,faces[mask,k],raw[mask])
    vertex_normals/=np.maximum(np.linalg.norm(vertex_normals,axis=1)[:,None],1e-12)
    nn=np.repeat(normals[:,None,:],3,axis=1);nn[mask]=vertex_normals[faces[mask]]
    materials=np.tile(np.array([157,162,160,.23,.25],np.float32),(len(faces),1))
    if paint:
        materials[item['material']==1]=[111,124,130,.48,0]
        materials[item['material']==2]=[69,49,35,.10,0]
        materials[item['material']==3]=[150,119,72,.36,0]
        edge=(item['material']==1)&(np.abs(original_z[faces].mean(axis=1))<2.25)
        materials[edge,:3]=[163,169,164]
    pitch=.16;lo=vertices.min(axis=0);hi=vertices.max(axis=0)
    gw=int(np.ceil((hi[0]-lo[0]+2)/pitch));gh=int(np.ceil((hi[1]-lo[1]+2)/pitch))
    hh=np.zeros((gh,gw),np.float32);gx=float(lo[0]-1);gy=float(lo[1]-1)
    HEIGHT(np.ascontiguousarray(tri),len(faces),gw,gh,gx,gy,pitch,hh)
    elev=math.radians(elevation);az=math.radians(angle)
    view=np.array([math.sin(az)*math.cos(elev),-math.cos(az)*math.cos(elev),math.sin(elev)],np.float32)
    right=np.array([math.cos(az),math.sin(az),0],np.float32);up=np.cross(view,right)
    projection=np.stack([right,-up,view],axis=1).astype(np.float32)
    v=tri.reshape(-1,3)@projection;low,high=v.min(axis=0),v.max(axis=0)
    scale=min(width*.91/(high[0]-low[0]),height*.87/(high[1]-low[1]))
    v[:,:2]=v[:,:2]*scale+[width/2-(low[0]+high[0])*scale/2,height/2-(low[1]+high[1])*scale/2]
    out=np.empty((height,width,4),np.uint8)
    RENDER(np.ascontiguousarray(v,np.float32),np.ascontiguousarray(nn,np.float32),np.ascontiguousarray(materials),
           np.ascontiguousarray(tri),hh,gw,gh,gx,gy,pitch,len(faces),width,height,*map(float,view),out)
    return Image.fromarray(out)


def on_background(im,bg='#171c20'):
    out=Image.new('RGBA',im.size,bg)
    shadow=Image.new('RGBA',im.size,'black')
    shadow.putalpha(im.getchannel('A').point(lambda v:int(v*.6)))
    shadow=shadow.filter(ImageFilter.GaussianBlur(13))
    out.alpha_composite(shadow,(4,14));out.alpha_composite(im)
    return out

def main():
    import json
    from PIL import ImageDraw
    metadata=json.loads((ROOT/'one-piece-validation.json').read_text())
    model=dict(np.load(ROOT/'one_piece_model.mesh.npz'))
    model['smooth_faces']=np.arange(len(model['faces']))<2*int(model['top_count'])
    model['vertices'][:,2]-=np.ptp(model['vertices'][:,2])/2
    back={**model,'vertices':model['vertices']*[-1,1,-1]}
    tilted=dict(np.load(ROOT/'one_piece_FDM_oriented.mesh.npz'))
    tilted['smooth_faces']=model['smooth_faces']
    on_background(render(model,2000,1000,elevation=38)).convert('RGB').save(ROOT/'one-piece-beauty.png')
    on_background(render(back,2000,1000,paint=False,elevation=40)).convert('RGB').save(ROOT/'reverse-face-preview.png')
    on_background(render(tilted,1000,1400,paint=False,elevation=25,angle=-55)).convert('RGB').save(ROOT/'FDM-orientation-preview.png')
    canvas=Image.new('RGBA',(2100,1550),'#151a1e');d=ImageDraw.Draw(canvas)
    d.text((75,48),'ONE-PIECE FDM BLADE',font=font(61,True),fill='#e1ded3')
    d.text((78,135),'110 mm  /  FULLY SCULPTED  /  SINGLE CLOSED SOLID',font=font(26),fill='#a0acad')
    canvas.alpha_composite(render(model,1400,650,elevation=42),(0,195))
    canvas.alpha_composite(render(back,1370,570,paint=False,elevation=43),(12,785))
    d.text((90,820),'FRONT',font=font(25,True),fill='#b7c0bd')
    d.text((90,1340),'REVERSE FACE OF THE SAME MODEL',font=font(25,True),fill='#b7c0bd')
    canvas.alpha_composite(render(tilted,730,1190,paint=False,elevation=25,angle=-55),(1360,205))
    d.text((1410,1340),'SUGGESTED FDM POSE',font=font(25,True),fill='#b7c0bd')
    d.text((85,1444),'Supports must be added in your slicer. No assembly required.',font=font(30,True),fill='#d2c1a0')
    d.text((85,1490),'Actual mesh views. Surface color illustrates an optional painted finish.',font=font(23),fill='#859395')
    canvas.convert('RGB').save(ROOT/'preview.png');print(ROOT/'preview.png')

if __name__=='__main__':main()
