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
    return render

RENDER=load_renderer()
HEIGHT_CACHE={}

def font(size,bold=False):
    p=Path('/System/Library/Fonts/Avenir Next.ttc')
    if p.exists():return ImageFont.truetype(str(p),size,index=2 if bold else 7)
    import matplotlib
    p=Path(matplotlib.__file__).parent/'mpl-data/fonts/ttf'
    return ImageFont.truetype(str(p/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)

def render(name,width,height,paint=True,top=False,angle=0):
    item=np.load(ROOT/(name+'.mesh.npz'))
    vertices=item['vertices'].astype(np.float32);faces=item['faces']
    top_count=int(item['top_count']);tri=vertices[faces]
    raw=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    normals=raw/np.maximum(np.linalg.norm(raw,axis=1)[:,None],1e-12)
    vertex_normals=np.zeros_like(vertices)
    for k in range(3):np.add.at(vertex_normals,faces[:top_count,k],raw[:top_count])
    vertex_normals/=np.maximum(np.linalg.norm(vertex_normals,axis=1)[:,None],1e-12)
    nn=np.repeat(normals[:,None,:],3,axis=1)
    nn[:top_count]=vertex_normals[faces[:top_count]]
    materials=np.tile(np.array([151,154,149,.28,0],np.float32),(len(faces),1))
    if paint:
        materials[item['material']==1]=[112,123,128,.46,0]
        materials[item['material']==2]=[65,48,37,.10,0]
        materials[item['material']==3]=[142,117,78,.36,0]
        # Different polished/oxidized steel on the actual perimeter bevel.
        import model,shapely
        variant=model.Variant('single' if name=='single_blade' else 'crossed')
        centers=tri.mean(axis=1)
        edge=shapely.distance(shapely.points(centers[:,:2]),variant.domain.boundary)
        polished=(item['material']==1)&(edge<model.BEVEL_WIDTH)
        materials[polished,:3]=[168,171,163]
    if name not in HEIGHT_CACHE:
        from scipy.interpolate import LinearNDInterpolator
        count=len(vertices)//2
        # Interpolate only the exported top vertices and mask actual holes.
        import model,shapely
        variant=model.Variant('single' if name=='single_blade' else 'crossed')
        x0,y0,x1,y1=variant.domain.bounds;pitch=.18
        xx,yy=np.meshgrid(np.arange(x0-.5,x1+.7,pitch),np.arange(y0-.5,y1+.7,pitch))
        points=np.column_stack([xx.ravel(),yy.ravel()])
        interpolator=LinearNDInterpolator(vertices[:count,:2],vertices[:count,2],fill_value=0)
        hh=interpolator(points)
        hh[~shapely.contains_xy(variant.domain,points[:,0],points[:,1])]=0
        HEIGHT_CACHE[name]=(hh.reshape(xx.shape).astype(np.float32),x0-.5,y0-.5,pitch)
    heights,gx,gy,pitch=HEIGHT_CACHE[name]
    elev=math.radians(90 if top else 60)
    az=math.radians(angle)
    view=np.array([math.sin(az)*math.cos(elev),-math.cos(az)*math.cos(elev),math.sin(elev)],np.float32)
    right=np.array([math.cos(az),math.sin(az),0],np.float32)
    up=np.cross(view,right)
    projection=np.stack([right,-up,view],axis=1).astype(np.float32)
    v=tri.reshape(-1,3)@projection
    low,high=v.min(axis=0),v.max(axis=0)
    scale=min(width*.91/(high[0]-low[0]),height*.87/(high[1]-low[1]))
    v[:,:2]=v[:,:2]*scale+np.array([width/2-(low[0]+high[0])*scale/2,
                                  height/2-(low[1]+high[1])*scale/2])
    out=np.empty((height,width,4),np.uint8)
    RENDER(np.ascontiguousarray(v,np.float32),np.ascontiguousarray(nn,np.float32),
           np.ascontiguousarray(materials,np.float32),np.ascontiguousarray(tri,np.float32),
           np.ascontiguousarray(heights),heights.shape[1],heights.shape[0],gx,gy,pitch,
           len(faces),width,height,
           *map(float,view),out)
    return Image.fromarray(out)

def on_background(im,bg='#171c20'):
    out=Image.new('RGBA',im.size,bg)
    shadow=Image.new('RGBA',im.size,'black')
    shadow.putalpha(im.getchannel('A').point(lambda v:int(v*.6)))
    shadow=shadow.filter(ImageFilter.GaussianBlur(13))
    out.alpha_composite(shadow,(4,14));out.alpha_composite(im)
    return out

def main():
    names=['single_blade','crossed_blades']
    for name in names:
        if not (ROOT/(name+'.mesh.npz')).exists():continue
        size=(1800,900) if name=='single_blade' else (1500,1400)
        on_background(render(name,*size)).convert('RGB').save(ROOT/(name+'-preview.png'))
        on_background(render(name,*size,paint=False,top=True),'#24282b').convert('RGB').save(ROOT/(name+'-geometry.png'))
    canvas=Image.new('RGBA',(2000,1680),'#151a1e');draw=ImageDraw.Draw(canvas)
    draw.text((85,55),'BLADES OF CHAOS',font=font(62,True),fill='#e2ded4')
    draw.text((87,141),'SCULPTED KEYCHAIN  /  REVISED GAME-INSPIRED GEOMETRY',font=font(25),fill='#9aa4a6')
    canvas.alpha_composite(render('single_blade',1850,740,angle=-6),(75,195))
    draw.text((90,908),'CURVED BLADE  ·  SCULPTED GUARD  ·  WRAPPED GRIP',font=font(26),fill='#b1b8b7')
    draw.line((85,970,1915,970),fill='#394045',width=1)
    canvas.alpha_composite(render('single_blade',1120,490,paint=False,top=True),(35,1010))
    draw.text((88,1513),'UNPAINTED GEOMETRY',font=font(26,True),fill='#c7cbc8')
    if (ROOT/'crossed_blades.mesh.npz').exists():
        canvas.alpha_composite(render('crossed_blades',700,590),(1210,993))
        draw.text((1235,1513),'CROSSED VARIANT',font=font(26,True),fill='#c7cbc8')
    draw.text((88,1585),'Actual mesh render. Steel, aged bronze and leather colors illustrate an optional painted finish.',font=font(24),fill='#899597')
    canvas.convert('RGB').save(ROOT/'preview.png')
    print(ROOT/'preview.png')

if __name__=='__main__':main()
