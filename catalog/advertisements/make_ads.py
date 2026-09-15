#!/usr/bin/env python3
"""Headless product advertisements using the catalog's actual CAD meshes.

Dependencies: cadquery==2.6.1, numpy, Pillow, imageio-ffmpeg==0.6.0; clang++ or g++.
Run: python make_ads.py --previews
     python make_ads.py --render --workers 2
No UI, browser, external media, or network is used during generation.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import argparse
import ctypes
import json
import math
import os
import platform
import subprocess
import time
import wave

import cadquery as cq
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE=Path(__file__).resolve().parent
CATALOG=HERE.parent
DATA_FILE=CATALOG/'catalog_preview_data.json'
if not DATA_FILE.exists():DATA_FILE=HERE/'source-data'/'catalog_preview_data.json'
WIDTH,HEIGHT=1080,1920
FPS,DURATION=24,12
STAGE_W,STAGE_H=1000,1040
STAGE_X,STAGE_Y=40,505
FOOTER='CUSTOMIZABLE DESIGN. MADE TO FIT.'
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
for directory in ('videos','posters','storyboards'):(HERE/directory).mkdir(exist_ok=True)

CREATIVE={
 'b2b_sensor_plate':dict(short='SLOTTED SENSOR PLATE',
   hooks=['Your sensor.\nYour alignment.','Adjust.\nAlign. Mount.','Designed around\nyour sensor.'],
   features=['A CLEANER MOUNTING SETUP','SLOTS THAT MAKE ROOM TO ADJUST','CHOOSE YOUR APERTURE AND SPACING'],
   cta='CONFIGURE YOUR MOUNT'),
 'b2b_pcb_cradle':dict(short='PCB INSPECTION CRADLE',
   hooks=['Hands free.\nBoard supported.','Set the spacing.\nSeat the board.','Build your\nbench setup.'],
   features=['SUPPORT FOR LIGHT BENCH WORK','TWO MOVABLE BOARD SUPPORTS','FIT THE BOARD YOU WORK WITH'],
   cta='CUSTOMIZE YOUR CRADLE'),
 'b2b_assembly_nest':dict(short='CUSTOM ASSEMBLY NEST',
   hooks=['A place for\nevery part.','Locate.\nAssemble. Repeat.','Made for\nyour workflow.'],
   features=['GIVE YOUR WORKPIECE A HOME','A POCKET SHAPED AROUND YOUR PART','CUSTOM SHAPE. CONSISTENT SETUP.'],
   cta='CONFIGURE YOUR NEST'),
 'b2c_cable_rail':dict(short='CABLE LANDING RAIL',
   hooks=['Keep cables\nwithin reach.','Drop in.\nPick up.','Your desk.\nConnected.'],
   features=['GIVE EVERY LEAD A LANDING PLACE','OPEN SLOTS. EASY ACCESS.','CHOOSE YOUR CABLE LAYOUT'],
   cta='MAKE IT YOURS'),
 'b2c_divider_tray':dict(short='DESK VALET WITH DIVIDER',
   hooks=['Give the small\nthings a home.','Your essentials.\nYour layout.','Make it\nyour own.'],
   features=['A LITTLE ORDER FOR EVERY DAY','A REMOVABLE, DROP-IN DIVIDER','SIZE IT FOR YOUR DAILY SETUP'],
   cta='DESIGN YOUR DESK SETUP'),
 'b2c_phone_stand':dict(short='CABLEPASS PHONE STAND',
   hooks=['Make room\nfor focus.','A better angle.\nRoom to charge.','Find your\nviewing angle.'],
   features=['ONE PLACE FOR YOUR PHONE','AN OPEN PATH FOR YOUR CABLE','CUSTOMIZE THE ANGLE AND FIT'],
   cta='MAKE IT YOURS'),
}

def smooth(x):
    x=np.clip(x,0,1)
    return x*x*(3-2*x)

def rgb(value):return np.array([int(value[i:i+2],16) for i in (1,3,5)],np.float32)

def ensure_renderer():
    extension='.dylib' if platform.system()=='Darwin' else '.so'
    path=HERE/('rasterizer'+extension)
    source=HERE/'rasterizer.cpp'
    if not path.exists() or source.stat().st_mtime>path.stat().st_mtime:
        flags=[]
        if platform.system()=='Darwin':
            sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
            flags=['-isysroot',sdk,'-isystem',str(Path(sdk)/'usr/include/c++/v1')]
        subprocess.run(['clang++','-O3','-std=c++17','-shared','-fPIC',*flags,str(source),'-o',str(path)],check=True)
    library=ctypes.CDLL(str(path))
    fn=library.render_mesh
    ptr=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
    out=np.ctypeslib.ndpointer(dtype=np.uint8,flags='C_CONTIGUOUS')
    fn.argtypes=[ptr,ptr,ptr,ctypes.c_int,ctypes.c_int,ctypes.c_int,
                 ctypes.c_float,ctypes.c_float,ctypes.c_float,out]
    fn.restype=None
    return fn

RENDER=ensure_renderer()

@lru_cache(maxsize=100)
def font(size,bold=False):
    avenir=Path('/System/Library/Fonts/Avenir Next.ttc')
    if avenir.exists():return ImageFont.truetype(str(avenir),size,index=2 if bold else 7)
    import matplotlib
    path=Path(matplotlib.__file__).parent/'mpl-data/fonts/ttf'/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    return ImageFont.truetype(str(path),size)

def box(l,w,h,z=0,r=0,x=0,y=0):
    obj=cq.Workplane('XY',origin=(x,y,z)).box(l,w,h,centered=(True,True,False))
    if r:obj=obj.edges('|Z').fillet(r)
    return obj.val()

def cylinder(radius,height,origin=(0,0,0),direction=(0,0,1)):
    return cq.Solid.makeCylinder(radius,height,cq.Vector(*origin),cq.Vector(*direction))

def raw_mesh(shape):
    v,f=shape.tessellate(.10,.16)
    return {'vertices':[[p.x,p.y,p.z] for p in v],'faces':[list(t) for t in f]}

class Mesh:
    def __init__(self,raw,color,spec=.15,emission=0,role='product',offset=(0,0,0),matrix=None):
        v=np.asarray(raw['vertices'],np.float32)+np.asarray(offset,np.float32)
        f=np.asarray(raw['faces'],np.int32)
        if matrix is not None:v=v@np.asarray(matrix,np.float32).T
        tris=v[f]
        ns=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0])
        ns/=np.maximum(np.linalg.norm(ns,axis=1)[:,None],1e-12)
        adjacent={}
        for i,ids in enumerate(f):
            for j in ids:adjacent.setdefault(tuple(np.round(v[j],4)),[]).append(i)
        normals=[]
        for i,ids in enumerate(f):
            for j in ids:
                nearby=ns[adjacent[tuple(np.round(v[j],4))]]
                candidates=nearby[nearby@ns[i]>.82]
                n=candidates.sum(axis=0);n/=max(np.linalg.norm(n),1e-12)
                normals.append(n)
        self.vertices=tris.reshape(-1,3)
        self.normals=np.asarray(normals,np.float32)
        self.material=np.tile(np.r_[rgb(color),spec,emission],(len(f),1)).astype(np.float32)
        self.role=role

def prop(shape,color,**kwargs):return Mesh(raw_mesh(shape),color,**kwargs)

def build_scene(item):
    slug=item['id'];business=item['category']=='B2B'
    body='#47b8b1' if business else '#c98b62'
    scene=[]
    for mesh in item['meshes']:
        role='divider' if mesh['name']=='Divider' else 'product'
        scene.append(Mesh(mesh,body,role=role))
    if slug=='b2b_sensor_plate':
        scene.append(Mesh(item['references'][0],'#aebcc4',.65,role='device'))
        nut=cq.Workplane('XY',origin=(0,0,10)).polygon(6,25).circle(9.0).extrude(4).val()
        scene.append(prop(nut,'#d5dbdf',spec=.70,role='device'))
    elif slug=='b2b_pcb_cradle':
        scene.append(Mesh(item['references'][0],'#2c594b',.08,role='device'))
        for y,z in [(-27,42),(-8,54),(17,44),(27,64)]:
            scene.append(prop(box(2.6,10,10,z=z,x=2,y=y),'#253035',role='device'))
        for y in range(-34,35,7):
            scene.append(prop(box(.12,2.5,9,z=69,x=.86,y=y),'#bcaf78',spec=.6,role='device'))
    elif slug=='b2b_assembly_nest':
        scene.append(Mesh(item['references'][0],'#c6ced2',.28,role='device'))
    elif slug=='b2c_cable_rail':
        for i,d in enumerate((3,3,4,4,5,6)):
            x=(i-2.5)*18
            role='cable'+str(i)
            scene.append(prop(cylinder(d/2,38,(x,-10,-30)),'#393c40',role=role))
            scene.append(prop(box(d+5,5,12,z=8,r=1.6,x=x,y=-10),'#4a4e52',role=role))
            scene.append(prop(box(d+1.5,2.8,3,z=20,r=.6,x=x,y=-10),'#bcc1c6',spec=.7,role=role))
    elif slug=='b2c_divider_tray':
        for x,color in [(35,'#334442'),(46,'#eee5d4')]:
            scene.append(prop(cylinder(2.2,60,(x,-30,4.8),(0,1,0)),color,role='contents'))
            scene.append(prop(cylinder(2.3,7,(x,-32,4.8),(0,1,0)),'#a5a9a5',spec=.65,role='contents'))
        key=cq.Workplane('XY',origin=(-32,13,2.4)).rect(16,13).extrude(2)
        key=key.edges('|Z').fillet(3).cut(cq.Workplane('XY',origin=(-36,13,2.3)).circle(3).extrude(2.2))
        key=key.union(cq.Workplane('XY',origin=(-18,13,2.4)).box(19,5,2,centered=(True,True,False)))
        scene.append(prop(key.val(),'#c3ac70',spec=.65,role='contents'))
    elif slug=='b2c_phone_stand':
        angle=math.radians(63)
        transform=np.array([[0,math.cos(angle),-math.sin(angle)],[-1,0,0],[0,math.sin(angle),math.cos(angle)]])
        position=np.array([17,0,10],np.float32)
        def phone_piece(shape,color,spec=.25,emission=0):
            m=prop(shape,color,spec=spec,emission=emission,role='phone',matrix=transform)
            m.vertices+=position;return m
        scene.append(phone_piece(box(68,136,8,r=8,y=68),'#343c42',.5))
        scene.append(phone_piece(box(62,125,.15,z=8,r=6,y=68),'#38716f',.35,.20))
        scene.append(phone_piece(box(18,3,.1,z=8.2,r=1,y=126),'#202c31',.25))
        for yy,l in [(102,35),(94,25),(60,40),(48,40),(36,40)]:
            scene.append(phone_piece(box(l,3,.08,z=8.2,r=1,y=yy),'#c7dad3',.1,.15))
        start=np.array([-30,0,10]);end=np.array([13.4,0,11.8]);direction=end-start
        scene.append(prop(cylinder(1.35,float(np.linalg.norm(direction)),start,direction/np.linalg.norm(direction)),
                          '#3d454a',role='phone'))
    return scene

@lru_cache(maxsize=2)
def background(business):
    yy,xx=np.mgrid[0:HEIGHT,0:WIDTH]
    glow=np.exp(-(((xx-WIDTH*.61)/(WIDTH*.72))**2+((yy-HEIGHT*.59)/(HEIGHT*.44))**2))
    base=np.array([14,24,34]) if business else np.array([242,237,229])
    accent=np.array([18,42,45]) if business else np.array([12,8,3])
    arr=base[None,None,:]+glow[:,:,None]*accent[None,None,:]
    noise=np.random.default_rng(23).normal(0,.38,(HEIGHT,WIDTH,1))
    image=Image.fromarray(np.clip(arr+noise,0,255).astype(np.uint8),'RGB').convert('RGBA')
    draw=ImageDraw.Draw(image)
    line=(96,136,145,45) if business else (132,113,88,36)
    draw.line((90,1780,990,1780),fill=line,width=1)
    return image

def tracking(draw,xy,text,size,color,spacing=3):
    x,y=xy
    f=font(size)
    for char in text:
        draw.text((x,y),char,font=f,fill=color)
        x+=draw.textlength(char,font=f)+spacing

def fade_paste(frame,layer,xy,alpha=1):
    if alpha<=0:return
    if alpha<.999:
        layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda v:int(v*alpha)))
    frame.alpha_composite(layer,(int(xy[0]),int(xy[1])))

class Ad:
    def __init__(self,item):
        self.item=item;self.slug=item['id'];self.business=item['category']=='B2B'
        self.config=CREATIVE[self.slug];self.meshes=build_scene(item)
        self.ink='#f2f6f5' if self.business else '#2d3738'
        self.muted='#98b0b9' if self.business else '#766f67'
        self.accent='#66d1c5' if self.business else '#a25e39'
        self.base_angle=-140 if self.slug=='b2c_phone_stand' else -55
        self.titles=[]
        for title in self.config['hooks']:
            size=102
            while max(font(size,True).getlength(line) for line in title.split('\n'))>900:size-=2
            layer=Image.new('RGBA',(940,270));draw=ImageDraw.Draw(layer)
            for i,line in enumerate(title.split('\n')):
                draw.text((0,i*119),line,font=font(size,True),fill=self.ink)
            self.titles.append(layer)
        self.header=Image.new('RGBA',(WIDTH,230));d=ImageDraw.Draw(self.header)
        tracking(d,(90,113),'WORKSHOP SERIES' if self.business else 'DESK COLLECTION',24,self.accent,4)
        d.text((90,179),self.config['short'],font=font(29,True),fill=self.ink)
        self.foot=Image.new('RGBA',(WIDTH,90));d=ImageDraw.Draw(self.foot)
        tracking(d,(90,18),FOOTER,20,self.muted,2)
        self.shadow=Image.new('RGBA',(STAGE_W,280))
        d=ImageDraw.Draw(self.shadow)
        d.ellipse((100,90,900,175),fill=(0,0,0,62 if self.business else 30))
        self.shadow=self.shadow.filter(ImageFilter.GaussianBlur(37))

    def placements(self,t):
        active=[]
        for mesh in self.meshes:
            offset=np.zeros(3,np.float32);role=mesh.role
            if role=='divider':
                u=float(np.clip((t-3.7)/3.3,0,1));offset[2]=30*math.sin(math.pi*u)**2
            elif role=='device':
                if t<3.8 or t>8.0:continue
                entry=1-float(smooth((t-3.8)/1.5));exit=float(smooth((t-7.0)/1.0))
                offset[2]=65*(entry+exit)
            elif role.startswith('cable'):
                delay=int(role[-1])*.14
                if t<3.7+delay:continue
                offset[1]=-45*(1-float(smooth((t-3.7-delay)/1.0)))
            elif role=='contents':
                if t<6.0:continue
                offset[2]=50*(1-float(smooth((t-6.0)/1.3)))
            elif role=='phone':
                if t<3.7:continue
                offset[2]=70*(1-float(smooth((t-3.7)/1.6)))
            active.append((mesh,offset))
        return active

    def model(self,t):
        az=math.radians(self.base_angle-20+28*math.sin(math.pi*t/DURATION))
        el=math.radians(26+6*math.sin(math.pi*t/DURATION))
        view=np.array([math.cos(az)*math.cos(el),math.sin(az)*math.cos(el),math.sin(el)],np.float32)
        right=np.array([-math.sin(az),math.cos(az),0],np.float32)
        up=np.cross(view,right);projection=np.stack([right,-up,view],axis=1)
        product=[m.vertices for m in self.meshes if m.role in ('product','divider')]
        allpoints=[m.vertices for m in self.meshes]
        p=np.concatenate(product)@projection;q=np.concatenate(allpoints)@projection
        blend=float(smooth((t-3.0)/1.0))
        if self.business:blend*=1-float(smooth((t-7.6)/.8))
        low=p.min(axis=0)*(1-blend)+q.min(axis=0)*blend
        high=p.max(axis=0)*(1-blend)+q.max(axis=0)*blend
        scale=min(STAGE_W*.86/max(high[0]-low[0],1),STAGE_H*.79/max(high[1]-low[1],1))
        scale*=.94+.06*float(smooth(t/.8))
        offset=np.array([STAGE_W/2-(low[0]+high[0])*scale/2,
                         STAGE_H*.5-(low[1]+high[1])*scale/2],np.float32)
        vertices=[];normals=[];materials=[]
        for mesh,translation in self.placements(t):
            projected=(mesh.vertices+translation)@projection
            projected[:,:2]=projected[:,:2]*scale+offset
            vertices.append(projected);normals.append(mesh.normals);materials.append(mesh.material)
        v=np.ascontiguousarray(np.concatenate(vertices),np.float32)
        n=np.ascontiguousarray(np.concatenate(normals),np.float32)
        mat=np.ascontiguousarray(np.concatenate(materials),np.float32)
        rgba=np.empty((STAGE_H,STAGE_W,4),np.uint8)
        RENDER(v,n,mat,len(v)//3,STAGE_W,STAGE_H,float(view[0]),float(view[1]),float(view[2]),rgba)
        return Image.fromarray(rgba,'RGBA')

    def frame(self,t):
        image=background(self.business).copy()
        reveal=1.0;end=1-float(smooth((t-11.6)/.4))
        fade_paste(image,self.header,(0,0),reveal)
        fade_paste(image,self.shadow,(STAGE_X,1280),reveal*.8)
        model=self.model(t)
        fade_paste(image,model,(STAGE_X,STAGE_Y+28*(1-reveal)),reveal)
        weights=[1-float(smooth((t-3.75)/.5)),
                 float(smooth((t-3.75)/.5))*(1-float(smooth((t-7.75)/.5))),
                 float(smooth((t-7.75)/.5))]
        for index,weight in enumerate(weights):
            fade_paste(image,self.titles[index],(90,264+20*(1-weight)),weight*reveal)
        d=ImageDraw.Draw(image)
        scene=min(2,int(t/4))
        feature=self.config['features'][scene]
        size=25
        while font(size,True).getlength(feature)>900:size-=1
        d.text((90,1518),feature,font=font(size,True),fill=self.accent)
        if t>=8:
            opacity=float(smooth((t-8.0)/.55))
            cta=Image.new('RGBA',(920,160));cd=ImageDraw.Draw(cta)
            cd.rounded_rectangle((0,12,900,120),radius=54,fill=self.ink)
            text=self.config['cta'];fs=31
            while font(fs,True).getlength(text)>760:fs-=1
            inverse='#12212c' if self.business else '#f5f0e8'
            cd.text((44,44),text,font=font(fs,True),fill=inverse)
            cd.line((819,66,858,66),fill=inverse,width=3)
            cd.line((845,53,858,66,845,79),fill=inverse,width=3)
            fade_paste(image,cta,(90,1600),opacity)
        else:
            d.text((90,1628),'Designed to fit your setup.',font=font(36),fill=self.ink)
        fade_paste(image,self.foot,(0,1790),reveal)
        if end<1:image=Image.blend(background(self.business),image,end)
        return image.convert('RGB')

def soundtrack():
    sr=44100;length=int(DURATION*sr);audio=np.zeros((length,2),np.float64)
    rng=np.random.default_rng(14)
    def add(signal,start,pan=0):
        offset=int(start*sr);count=min(len(signal),length-offset)
        if count<=0:return
        gains=np.array([math.cos((pan+1)*math.pi/4),math.sin((pan+1)*math.pi/4)])
        audio[offset:offset+count]+=signal[:count,None]*gains
    roots=[130.8128,130.8128,103.8262,103.8262,155.5635,130.8128]
    for bar,root in enumerate(roots):
        t=np.arange(int(2.05*sr))/sr
        envelope=np.minimum(1,t/.12)*np.clip((2.05-t)/.45,0,1)
        pad=sum(np.sin(2*np.pi*root*2**(step/12)*t) for step in (0,3,7))/3
        add(pad*envelope*.055,bar*2,(-1)**bar*.3)
    for beat in range(24):
        start=beat*.5;root=roots[min(beat//4,5)]
        t=np.arange(int(.48*sr))/sr
        pitch=2**([12,19,15,22][beat%4]/12)*root
        pluck=(np.sin(2*np.pi*pitch*t)+.25*np.sin(2*np.pi*pitch*2*t))*np.exp(-t*9)
        add(pluck*.11,start,(-1)**beat*.48)
        kick=np.sin(2*np.pi*(46*t+22*(1-np.exp(-t*24))/24))*np.exp(-t*17)
        add(kick*.12,start)
        if beat%2:
            noise=rng.normal(0,1,len(t));noise=np.r_[0,np.diff(noise)]
            add(noise*np.exp(-t*65)*.026,start)
        for subdivision in (0,.25):
            tt=np.arange(int(.08*sr))/sr
            n=rng.normal(0,1,len(tt));n=np.r_[0,np.diff(n)]
            add(n*np.exp(-tt*80)*.009,start+subdivision,.4)
    for start in (3.72,7.72):
        t=np.arange(int(.55*sr))/sr
        noise=rng.normal(0,1,len(t));noise=np.convolve(noise,np.ones(12)/12,mode='same')
        add(noise*np.sin(np.pi*t/.55)**2*.075,start,-.2)
    fade=np.minimum(1,np.arange(length)/sr/.3)*np.minimum(1,(length-np.arange(length))/sr/.65)
    audio*=fade[:,None]
    audio*=min(.72/max(np.abs(audio).max(),1e-9),.13/max(np.sqrt(np.mean(audio**2)),1e-9))
    path=HERE/'original-sound-bed.wav'
    with wave.open(str(path),'wb') as out:
        out.setnchannels(2);out.setsampwidth(2);out.setframerate(sr)
        out.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
    return path

def render_video(ad,audio):
    output=HERE/'videos'/(ad.slug+'.mp4')
    cmd=[FFMPEG,'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
         '-s',f'{WIDTH}x{HEIGHT}','-r',str(FPS),'-i','-', '-i',str(audio),
         '-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','19',
         '-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709',
         '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv',
         '-pix_fmt','yuv420p','-profile:v','high','-level','4.1','-threads','3',
         '-c:a','aac','-b:a','192k','-t',str(DURATION),'-movflags','+faststart',
         '-metadata','comment=Original CAD product animation and synthesized sound bed',str(output)]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    started=time.time()
    try:
        for frame in range(FPS*DURATION):
            image=ad.frame(frame/FPS)
            process.stdin.write(image.tobytes())
            if frame%(FPS*4)==0:print(f'{ad.slug}: {frame//FPS}/{DURATION}s',flush=True)
        process.stdin.close()
        error=process.stderr.read().decode()
        if process.wait():raise RuntimeError(error)
    except BaseException:
        process.kill();process.wait();raise
    ad.frame(9.5).save(HERE/'posters'/(ad.slug+'.jpg'),quality=95)
    print(f'{ad.slug}: finished in {time.time()-started:.1f}s',flush=True)
    return output

def previews(ads):
    for business in (True,False):
        selected=[ad for ad in ads if ad.business==business]
        sheet=Image.new('RGB',(1080,1920),(22,31,38) if business else (242,237,229))
        for row,ad in enumerate(selected):
            for col,t in enumerate((1.8,5.9,9.6)):
                frame=ad.frame(t)
                frame.resize((360,640),Image.Resampling.LANCZOS)
                sheet.paste(frame.resize((360,640),Image.Resampling.LANCZOS),(col*360,row*640))
            ad.frame(9.6).save(HERE/'posters'/(ad.slug+'.jpg'),quality=95)
        path=HERE/'storyboards'/('b2b.jpg' if business else 'b2c.jpg')
        sheet.save(path,quality=95)
        print('Storyboard:',path,flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--previews',action='store_true')
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--product')
    args=parser.parse_args()
    data=json.loads(DATA_FILE.read_text())
    ads=[Ad(item) for item in data if not args.product or args.product==item['id']]
    if not ads:raise ValueError('Unknown product')
    if args.previews:previews(ads)
    if args.render:
        audio=soundtrack()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            videos=list(pool.map(lambda ad:render_video(ad,audio),ads))
        manifest=[{'product':ad.item['title'],'file':str(p.relative_to(HERE)),
                   'seconds':DURATION,'resolution':[WIDTH,HEIGHT],'fps':FPS} for ad,p in zip(ads,videos)]
        (HERE/'video-manifest.json').write_text(json.dumps(manifest,indent=2))
    if not(args.previews or args.render):parser.print_help()

if __name__=='__main__':main()
