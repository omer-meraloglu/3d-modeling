#!/usr/bin/env python3
"""Headless views of the exported Venom mesh. Colors illustrate optional painting."""
from pathlib import Path
import ctypes,math,platform,subprocess,argparse,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
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

PALETTE=np.array([[48,63,77,.95,.11],[230,235,226,.6,.05],[219,199,155,.48,.03],
                  [88,28,38,.30,.05],[172,49,75,.7,.07],[54,60,69,.3,.06],
                  [214,224,216,.4,.05],[46,63,79,.85,.07]],np.float32)

def render(item,width,height,elevation=10,angle=20,clay=False,head=False):
    v=item['vertices'];f=item['faces'];mat=item['material'].copy()
    center=v[f].mean(axis=1);canonical=center*(179.1/float(v[:,2].max()))
    cavity=(canonical[:,0]/27.5)**2+((canonical[:,1]+30)/30)**2+((canonical[:,2]-128)/17)**2
    mat[(mat==0)&(np.abs(cavity-1)<.18)&(canonical[:,1]<5)&(canonical[:,2]>110)&(canonical[:,2]<147)]=3
    if head:
        keep=v[f,:,][...,2].min(axis=1)>104;f=f[keep];mat=mat[keep]
    tri=np.ascontiguousarray(v[f],np.float32)
    raw=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);vn=np.zeros_like(v)
    for k in range(3):np.add.at(vn,f[:,k],raw)
    vn/=np.maximum(np.linalg.norm(vn,axis=1)[:,None],1e-12)
    nn=np.ascontiguousarray(vn[f],np.float32)
    materials=np.tile([169,174,170,.35,.06],(len(f),1)).astype(np.float32) if clay else np.ascontiguousarray(PALETTE[mat])
    lo=v.min(axis=0);hi=v.max(axis=0);pitch=.25;gx=float(lo[0]-1);gy=float(lo[1]-1)
    gw=int(np.ceil((hi[0]-lo[0]+2)/pitch));gh=int(np.ceil((hi[1]-lo[1]+2)/pitch))
    hh=np.zeros((gh,gw),np.float32);HEIGHT(tri,len(f),gw,gh,gx,gy,pitch,hh)
    el=math.radians(elevation);az=math.radians(angle)
    view=np.array([math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)],np.float32)
    right=np.array([math.cos(az),math.sin(az),0],np.float32);up=np.cross(view,right)
    projection=np.stack([right,-up,view],axis=1).astype(np.float32)
    pp=tri.reshape(-1,3)@projection;low=pp.min(axis=0);high=pp.max(axis=0)
    scale=min(width*.94/(high[0]-low[0]),height*.93/(high[1]-low[1]))
    pp[:,:2]=pp[:,:2]*scale+[width/2-(low[0]+high[0])*scale/2,height/2-(low[1]+high[1])*scale/2]
    out=np.empty((height,width,4),np.uint8)
    RENDER(np.ascontiguousarray(pp,np.float32),nn,materials,tri,hh,gw,gh,gx,gy,pitch,len(f),width,height,*map(float,view),out)
    return Image.fromarray(out)

def background(im):
    w,h=im.size
    yy,xx=np.ogrid[:h,:w];glow=np.clip(1-np.sqrt(((xx-w*.5)/(w*.9))**2+((yy-h*.36)/(h*.9))**2),0,1)
    rgb=np.stack([18+glow*11,23+glow*14,30+glow*18],axis=2).astype(np.uint8)
    out=Image.fromarray(rgb).convert('RGBA');out.alpha_composite(im);return out

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--draft',action='store_true');args=ap.parse_args()
    path=ROOT/('draft_preview.mesh.npz' if args.draft else 'sculpture_preview.mesh.npz')
    data=dict(np.load(path));prefix='draft-' if args.draft else ''
    canvas=Image.new('RGBA',(1700,2200),'#151c25');d=ImageDraw.Draw(canvas)
    d.text((75,48),'VENOM',font=font(93,True),fill='#e0e4da')
    d.text((80,170),'SYMBIOTE BUST  /  180 MM  /  ALL-SIDED SCULPT',font=font(26),fill='#96aaa9')
    canvas.alpha_composite(background(render(data,1600,1770,angle=18,elevation=9)),(50,230))
    d.text((78,2050),'Original fan-art sculpture · Actual model geometry',font=font(26),fill='#bac3bb')
    d.text((78,2100),'Optional painted finish shown · FDM supports required',font=font(24),fill='#93a3a7')
    canvas.convert('RGB').save(ROOT/(prefix+'preview.png'),optimize=True)
    background(render(data,1550,1750,angle=-18,elevation=12,clay=True)).convert('RGB').save(ROOT/(prefix+'clay-preview.png'),optimize=True)
    background(render(data,1550,1750,angle=155,elevation=15,clay=True)).convert('RGB').save(ROOT/(prefix+'back-preview.png'),optimize=True)
    background(render(data,1600,1450,angle=20,elevation=5,head=True)).convert('RGB').save(ROOT/(prefix+'head-detail.png'),optimize=True)
    print(ROOT/(prefix+'preview.png'),flush=True)
if __name__=='__main__':main()
