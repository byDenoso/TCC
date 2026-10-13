"""Original galaxy artwork V4. Integrated stellar population + multiscale dust, CC0.
Illustrative morphology, not an observation or gravitational simulation.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
import hashlib,json,sys
out=Path(__file__).resolve().parents[2]/'public'/'models'/'galaxies-v4';out.mkdir(parents=True,exist_ok=True)
N=1536
y,x=np.mgrid[-1:1:complex(N),-1:1:complex(N)].astype(np.float32)
rows=[];runtime=[]
for k,name in enumerate(['grand-spiral','barred-spiral','many-arms','lenticular','elliptical','irregular']):
 if len(sys.argv)>1 and name!=sys.argv[1]:
  for collection,suffix in [(rows,'.png'),(runtime,'.webp')]:
   p=out/(name+suffix);collection.append(dict(file=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
  continue
 rng=np.random.default_rng(38176+k)
 def noise(res):
  a=rng.normal(0,1,(res,res)).astype(np.float32)
  z=np.asarray(Image.fromarray(a,mode='F').resize((N,N),Image.Resampling.BICUBIC),dtype=np.float32)
  return z/(z.std()+1e-6)
 coarse=noise(13);medium=noise(57);fine=noise(231);micro=noise(769)
 turbulence=coarse*.45+medium*.28+fine*.15
 xx=x;yy=y*(1.34 if k==4 else 1)
 r=np.sqrt(xx*xx+yy*yy);a=np.arctan2(yy,xx)
 taper=np.clip((1-r)/.18,0,1)**2
 disk=np.exp(-r/[.25,.29,.22,.3,.28,.24][k])*taper
 core=.93*np.exp(-(r/[.047,.041,.05,.068,.075,.04][k])**[.73,.8,.7,.65,.54,.8][k])
 core*=np.exp(-(r/.5)**4)*taper
 arms=np.zeros_like(r);dust=np.ones_like(r)
 if k<3:
  m=[2,2,3][k];pitch=[1.47,1.92,2.25][k]
  phase=m*(a-pitch*np.log(r+.038))+.05*coarse
  widths=[2.3,1.65,1.5][k]
  arms=np.exp((np.cos(phase)-1)*widths)*np.exp(-r/[.36,.39,.33][k])*taper*np.clip((r-.075)*10,0,1)
  if k==2:
   branches=np.exp((np.cos(5*(a-1.6*np.log(r+.06))+.5)-1)*3)*np.exp(-r/.32)*taper*np.clip((r-.19)*7,0,1)
   arms=arms*(.84+.18*coarse+.12*medium)+branches*.24
  # A lane on one side of each arm, broken by patchy gas; no sinusoidal scalloped edges.
  lane=np.exp((np.cos(phase+.33)-1)*(16 if k==0 else 25))*np.clip(r*10,0,1)
  patch=np.clip(.64+coarse*.15+medium*.18+fine*.09,.12,1)
  dust=np.clip(1-lane*patch*(1.18 if k==0 else .8)-.10*np.maximum(medium,0)*disk,(.06 if k==0 else .16),1)
  if k==1:core+=.16*np.exp(-x*x/.09-y*y/.0017)
 elif k==3:
  dust=1-.28*np.exp(-((r-.31)/.045)**2)*(1+coarse*.08)
 elif k==4:
  disk*=.48
 else:
  core*=.35;disk*=.8
  for j in range(9):
   cx,cy=rng.uniform(-.46,.46,2);sx,sy=rng.uniform(.06,.19,2)
   arms+=rng.uniform(.09,.25)*np.exp(-((x-cx)/sx)**2-((y-cy)/sy)**2)
  arms*=taper;dust=np.clip(.84+medium*.11+coarse*.07,.3,1)
 population=(disk*.15+arms*.8+core*.16)*np.clip(1+turbulence*.23,.25,1.7)*(1 if k==0 else dust)
 # Stars are integrated into a high resolution density field; their PSF is subpixel in the scene.
 density=(population+disk*.008+core*.20).ravel();density/=density.sum()
 idx=rng.choice(N*N,size=230000,p=density)
 stars=np.zeros(N*N,dtype=np.float32);np.add.at(stars,idx,rng.lognormal(-1.2,.6,len(idx)).astype(np.float32));stars=stars.reshape(N,N)
 # Separable smooth PSF, entirely authored in arrays (Pillow F blur unsupported).
 stars=(stars*4+np.roll(stars,1,0)+np.roll(stars,-1,0)+np.roll(stars,1,1)+np.roll(stars,-1,1))/8
 stellar=np.clip(stars*.60,0,.38)*dust
 smooth=(disk*.028+arms*.45)*np.clip(1+medium*.07+fine*.09+micro*.025,.55,1.4)*dust
 warm=np.array([1.,.78,.50],dtype=np.float32)
 armcolor=np.array([[.60,.77,1.],[.60,.75,.91],[.48,.72,1.],[.88,.80,.69],[.91,.83,.72],[.66,.79,.88]][k],dtype=np.float32)
 rgb=smooth[:,:,None]*armcolor+stellar[:,:,None]*np.array([.9,.84,.72],dtype=np.float32)+core[:,:,None]*warm
 if k==4:rgb+=(disk*.12*(1+fine*.012))[:,:,None]*warm
 # Soft photographic response with a compact warm nucleus and no flat white clipping.
 rgb=np.clip((1-np.exp(-rgb*2.05))**.90,0,.93)
 alpha=(np.clip((1-r)/.12,0,1)**2*255).astype(np.uint8)
 if k==0:
  bare=(disk*.028+arms*.45)*np.clip(1+medium*.07+fine*.09+micro*.025,.55,1.4)
  bare_rgb=bare[:,:,None]*armcolor+np.clip(stars*.60,0,.38)[:,:,None]*np.array([.9,.84,.72])+core[:,:,None]*warm
  bare_rgb=np.clip((1-np.exp(-bare_rgb*2.05))**.90,0,.93)
  bare_image=Image.fromarray(np.dstack([(bare_rgb*255).astype(np.uint8),alpha]))
  bare_image.save(out/'stars-only.png',optimize=True);bare_image.save(out/'stars-only.webp',quality=94,method=4)
 rgba=np.dstack([(rgb*255).astype(np.uint8),alpha]);path=out/(name+'.png');Image.fromarray(rgba).save(path,optimize=True)
 rows.append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 webp=out/(name+'.webp');Image.fromarray(rgba).save(webp,quality=94,method=4)
 runtime.append(dict(file=webp.name,bytes=webp.stat().st_size,sha256=hashlib.sha256(webp.read_bytes()).hexdigest()))
(out/'manifest.json').write_text(json.dumps({'version':4,'author':'Cosmos do Zero original mathematical artwork','license':'CC0-1.0','method':'High resolution integrated stellar density, smooth multi-scale gas, asymmetric absorption lanes, variable pitch and radial bulge profiles','interpretation':'Original illustration, no observed data, no N-body calculation','source':'assets/source/build_galaxies_v4.py','assets':rows,'runtime_assets':runtime},indent=2),encoding='utf-8')
print(rows)

# Shared resolution variants: no per-galaxy image copies.
for size in (768,512):
 folder=out/str(size);folder.mkdir(exist_ok=True)
 assets=[]
 for row in rows:
  image=Image.open(out/row['file']).resize((size,size),Image.Resampling.LANCZOS)
  target=folder/(Path(row['file']).stem+'.webp');image.save(target,quality=92,method=4)
  assets.append(dict(file=target.name,bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
 (folder/'manifest.json').write_text(json.dumps({'size':size,'source':'../manifest.json','assets':assets},indent=2),encoding='utf-8')

for size in (768,512):
 Image.open(out/'stars-only.png').resize((size,size),Image.Resampling.LANCZOS).save(out/str(size)/'stars-only.webp',quality=92,method=4)

# The teaching stars-only comparison is separate from the six shared expansion maps.
manifest_path=out/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
for ext,key in [('png','assets'),('webp','runtime_assets')]:
 path=out/('stars-only.'+ext);manifest[key].append(dict(file=path.name,role='stars-only comparison without dust absorption',bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for size in (768,512):
 path=out/str(size)/'stars-only.webp';mp=path.parent/'manifest.json';m=json.loads(mp.read_text(encoding='utf-8'));m['assets'].append(dict(file=path.name,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()));mp.write_text(json.dumps(m,indent=2),encoding='utf-8')
