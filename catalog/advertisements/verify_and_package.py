"""Check every rendered ad, create a combined preview, and package deliverables."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess
import zipfile
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parent
FFMPEG=imageio_ffmpeg.get_ffmpeg_exe()
manifest=json.loads((ROOT/'video-manifest.json').read_text())

def verify(entry):
    path=ROOT/entry['file']
    info=subprocess.run([FFMPEG,'-hide_banner','-i',str(path)],capture_output=True,text=True).stderr
    expected=['1080x1920','24 fps','Audio: aac','bt709']
    for text in expected:
        if text not in info:raise RuntimeError(f'{path.name}: missing {text}')
    duration=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',info)
    seconds=sum(float(v)*m for v,m in zip(duration.groups(),(3600,60,1)))
    if abs(seconds-12)>.05:raise RuntimeError(f'{path.name}: duration {seconds}')
    decode=subprocess.run([FFMPEG,'-v','error','-nostats','-i',str(path),'-map','0',
                           '-progress','pipe:1','-f','null','-'],capture_output=True,text=True)
    if decode.returncode or decode.stderr.strip():raise RuntimeError(decode.stderr)
    counts=re.findall(r'^frame=(\d+)',decode.stdout,re.M)
    if not counts or int(counts[-1])!=288:raise RuntimeError(f'{path.name}: frame count {counts}')
    result={**entry,'verified_seconds':seconds,'decoded_frames':288,'full_decode':'passed',
            'color_space':'BT.709','bytes':path.stat().st_size}
    print('Verified:',path.name,flush=True)
    return result

with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(verify,manifest))

inputs=[];filters=[];sequence=[]
for i,entry in enumerate(manifest):
    inputs+=['-i',str(ROOT/entry['file'])]
    filters += [f'[{i}:v]setpts=PTS-STARTPTS[v{i}]',
                f'[{i}:a]atrim=duration=12,asetpts=PTS-STARTPTS[a{i}]']
    sequence += [f'[v{i}][a{i}]']
filters.append(''.join(sequence)+f'concat=n={len(manifest)}:v=1:a=1[v][a]')
combined=ROOT/'all-six-product-ads.mp4'
subprocess.run([FFMPEG,'-y','-loglevel','error',*inputs,'-filter_complex',';'.join(filters),
                '-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','19',
                '-pix_fmt','yuv420p','-r','24','-color_primaries','bt709','-color_trc','bt709',
                '-colorspace','bt709','-color_range','tv','-c:a','aac','-b:a','192k',
                '-t',str(12*len(manifest)),'-threads','4','-movflags','+faststart',str(combined)],check=True)
decode=subprocess.run([FFMPEG,'-v','error','-nostats','-i',str(combined),'-map','0',
                       '-progress','pipe:1','-f','null','-'],capture_output=True,text=True)
counts=re.findall(r'^frame=(\d+)',decode.stdout,re.M)
if decode.returncode or decode.stderr.strip() or not counts or int(counts[-1])!=288*len(manifest):
    raise RuntimeError('Combined preview failed decode/frame-count verification: '+decode.stderr)

volume=subprocess.run([FFMPEG,'-hide_banner','-i',str(ROOT/manifest[0]['file']),'-vn',
                       '-af','volumedetect','-f','null','-'],capture_output=True,text=True).stderr
audio={k:float(v) for k,v in re.findall(r'(mean_volume|max_volume):\s*(-?[\d.]+) dB',volume)}
if not audio or audio['max_volume']>=0:raise RuntimeError('Audio peak check failed')
(ROOT/'verification-report.json').write_text(json.dumps({'individual_ads':results,
    'combined_frames':int(counts[-1]),'audio_dbfs':audio},indent=2))

frame_dir=ROOT/'storyboards'
for index,entry in enumerate(manifest):
    subprocess.run([FFMPEG,'-y','-loglevel','error','-ss','5.5','-i',str(ROOT/entry['file']),
                    '-frames:v','1',str(frame_dir/(Path(entry['file']).stem+'-encoded.png'))],check=True)

archive=ROOT/'six-product-advertisements.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
    for folder in ('videos','posters','storyboards'):
        for path in sorted((ROOT/folder).glob('*')):
            if path.suffix=='.png':continue
            z.write(path,path.relative_to(ROOT))
    for name in ('make_ads.py','rasterizer.cpp','original-sound-bed.wav',
                 'video-manifest.json','verification-report.json','verify_and_package.py',
                 'all-six-product-ads.mp4'):
        z.write(ROOT/name,name)
    data=ROOT.parent/'catalog_preview_data.json'
    if not data.exists():data=ROOT/'source-data'/'catalog_preview_data.json'
    z.write(data,'source-data/catalog_preview_data.json')
print('Combined preview:',combined,flush=True)
print('Package:',archive,flush=True)
print('Audio:',audio,flush=True)
