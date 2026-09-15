#!/usr/bin/env python3
"""Headless previews from CAD tessellation; colors illustrate painted finishes.
Requires a C++17 compiler, NumPy and Pillow. No GUI or external media is used.
Run: python render_catalog.py [model_directory_name ...]
"""
from pathlib import Path
import ctypes, math, platform, subprocess, json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT=Path(__file__).resolve().parent
BG='#eceee8'
INK='#203b38'
CAMERAS={'01':(-25,44),'02':(-26,40),'03':(55,35),'04':(30,38),'05':(25,49),'06':(15,50)}

def load_renderer():
    binary=ROOT/('rasterizer.dylib' if platform.system()=='Darwin' else 'rasterizer.so')
    source=ROOT/'rasterizer.cpp'
    if not binary.exists() or source.stat().st_mtime>binary.stat().st_mtime:
        flags=[]
        if platform.system()=='Darwin':
            sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
            flags=['-isysroot',sdk,'-isystem',str(Path(sdk)/'usr/include/c++/v1')]
        subprocess.run(['clang++','-O3','-std=c++17','-shared','-fPIC',*flags,str(source),'-o',str(binary)],check=True)
    lib=ctypes.CDLL(str(binary));render=lib.render_mesh;hf=lib.build_heightfield
    f=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
    u=np.ctypeslib.ndpointer(dtype=np.uint8,flags='C_CONTIGUOUS')
    render.argtypes=[f,f,f,f,f,ctypes.c_int,ctypes.c_int,ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_float,ctypes.c_float,ctypes.c_float,u]
    hf.argtypes=[f,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_float,ctypes.c_float,ctypes.c_float,f]
    return render,hf
RENDER,HEIGHT=load_renderer()

def font(size,bold=False):
    p=Path('/System/Library/Fonts/Avenir Next.ttc')
    if p.exists():return ImageFont.truetype(str(p),size,index=2 if bold else 7)
    import matplotlib
    return ImageFont.truetype(str(Path(matplotlib.__file__).parent/'mpl-data/fonts/ttf'/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)

def render(scene,width,height,angle=25,elevation=40,monochrome=False):
    triangles=[];mats=[]
    for item in scene['meshes']:
        v=np.asarray(item['vertices'],np.float32);f=np.asarray(item['faces'],np.int32)
        triangles.append(v[f])
        color='#bec9c3' if monochrome else item['color']
        rgb=[int(color[i:i+2],16) for i in (1,3,5)]
        mats.append(np.tile(np.array([*rgb,.14,.10],np.float32),(len(f),1)))
    tri=np.ascontiguousarray(np.concatenate(triangles),np.float32)
    tri[:,:,2]-=tri[:,:,2].min()
    raw=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    normals=raw/np.maximum(np.linalg.norm(raw,axis=1)[:,None],1e-12)
    nn=np.ascontiguousarray(np.repeat(normals[:,None,:],3,axis=1))
    materials=np.ascontiguousarray(np.concatenate(mats))
    lo=tri.reshape(-1,3).min(axis=0);hi=tri.reshape(-1,3).max(axis=0)
    pitch=.25;gx=float(lo[0]-1);gy=float(lo[1]-1)
    gw=int(np.ceil((hi[0]-lo[0]+2)/pitch));gh=int(np.ceil((hi[1]-lo[1]+2)/pitch))
    hh=np.zeros((gh,gw),np.float32)
    HEIGHT(tri,len(tri),gw,gh,gx,gy,pitch,hh)
    az=math.radians(angle);el=math.radians(elevation)
    view=np.array([math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)],np.float32)
    right=np.array([math.cos(az),math.sin(az),0],np.float32);up=np.cross(view,right)
    projection=np.stack([right,-up,view],axis=1).astype(np.float32)
    v=tri.reshape(-1,3)@projection;low=v.min(axis=0);high=v.max(axis=0)
    scale=min(width*.92/(high[0]-low[0]),height*.91/(high[1]-low[1]))
    v[:,:2]=v[:,:2]*scale+[width/2-(low[0]+high[0])*scale/2,height/2-(low[1]+high[1])*scale/2]
    out=np.empty((height,width,4),np.uint8)
    RENDER(np.ascontiguousarray(v,np.float32),nn,materials,tri,hh,gw,gh,gx,gy,pitch,len(tri),width,height,*map(float,view),out)
    return Image.fromarray(out)

def compose(im,bg=BG):
    canvas=Image.new('RGBA',im.size,bg)
    shadow=Image.new('RGBA',im.size,'#54625c');shadow.putalpha(im.getchannel('A').point(lambda x:int(x*.19)))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)),(3,11))
    canvas.alpha_composite(im);return canvas

def product(folder):
    data=json.loads((folder/'preview_mesh.json').read_text())
    stats=json.loads((folder/'validation.json').read_text())
    az,el=CAMERAS[folder.name[:2]]
    arch=folder.name[:2] in ('04','05')
    w,h=(2000,1450) if arch else (1600,1250)
    canvas=Image.new('RGBA',(w,h),BG);d=ImageDraw.Draw(canvas)
    d.text((65,40),'polukal',font=font(38,True),fill=INK)
    d.text((w-500,52),'INDUSTRY COLLECTION  /  '+folder.name[:2],font=font(21),fill='#668079')
    d.line((65,108,w-65,108),fill='#c2ccc4',width=2)
    d.text((65,133),data['title'],font=font(54 if arch else 46,True),fill=INK)
    if arch:
        sub='1:200  /  180 × 140 mm site  /  Single connected print'
    else:sub=stats['category']+'  /  Editable parametric CAD'
    d.text((68,211),sub,font=font(25 if arch else 22),fill='#638078')
    im=render(data,w-60,h-405,az,el)
    canvas.alpha_composite(compose(im),(30,275))
    footer='Actual CAD geometry · Color illustrates an optional painted finish'
    if folder.name.startswith('01'):footer='Actual CAD geometry · Gray steel bushings shown for reference; sourced separately'
    if folder.name.startswith('02'):footer='Exploded lid view · Body and lid print separately · Electronics not included'
    if folder.name.startswith('06'):footer='GENERIC TRAINING DEMO · Not for clinical, intraoral or patient use'
    d.text((65,h-108),footer,font=font(23 if arch else 20),fill='#536c63')
    d.text((65,h-62),'STL  /  3MF  /  STEP  /  Python source',font=font(20,True),fill=INK)
    canvas.convert('RGB').save(folder/'preview.png',optimize=True)
    if arch:
        compose(render(data,1800,1450,angle=0,elevation=90)).convert('RGB').save(folder/'plan-view.png',optimize=True)
        compose(render(data,2000,1400,angle=az,elevation=el,monochrome=True)).convert('RGB').save(folder/'unpainted-preview.png',optimize=True)
    print(folder/'preview.png',flush=True)

def contact_sheet():
    paths=[p for p in ROOT.glob('[0-9][0-9]_*/preview.png')]
    if len(paths)!=6:return
    canvas=Image.new('RGB',(2200,2290),BG);d=ImageDraw.Draw(canvas)
    d.text((70,44),'polukal / Industry applications',font=font(64,True),fill=INK)
    d.text((74,139),'Architecture & landscape editions, plus four practical CAD examples.',font=font(29),fill='#637b72')
    order=['04','05','01','02','03','06']
    for i,prefix in enumerate(order):
        p=next(p for p in paths if p.parent.name.startswith(prefix))
        im=Image.open(p).convert('RGB');im.thumbnail((1025,680))
        x=55+(i%2)*1090;y=220+(i//2)*680
        canvas.paste(im,(x+(1025-im.width)//2,y))
    canvas.save(ROOT/'catalog-preview.png',optimize=True)

if __name__=='__main__':
    folders=[ROOT/a for a in sys.argv[1:]] if len(sys.argv)>1 else sorted(ROOT.glob('[0-9][0-9]_*'))
    for folder in folders:
        if (folder/'preview_mesh.json').exists():product(folder)
    contact_sheet()
