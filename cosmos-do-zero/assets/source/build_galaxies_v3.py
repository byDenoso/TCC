"""Original galaxy artwork V3. Integrated stellar population + multiscale dust, CC0.
Illustrative morphology, not an observation or gravitational simulation.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
import hashlib,json,sys
out=Path(__file__).resolve().parents[2]/'public'/'models'/'galaxies-v3';out.mkdir(parents=True,exist_ok=True)
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
 core=.82*np.exp(-(r/[.047,.041,.05,.068,.075,.04][k])**[.73,.8,.7,.65,.54,.8][k])
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
  lane=np.exp((np.cos(phase+.33)-1)*25)*np.clip(r*10,0,1)
  patch=np.clip(.64+coarse*.15+medium*.18+fine*.09,.12,1)
  dust=np.clip(1-lane*patch*.8-.10*np.maximum(medium,0)*disk,.16,1)
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
 population=(disk*.15+arms*.8+core*.16)*np.clip(1+turbulence*.23,.25,1.7)*dust
 # Stars are integrated into a high resolution density field; their PSF is subpixel in the scene.
 density=(population+disk*.018+core*.20).ravel();density/=density.sum()
 idx=rng.choice(N*N,size=230000,p=density)
 stars=np.zeros(N*N,dtype=np.float32);np.add.at(stars,idx,rng.lognormal(-1.2,.6,len(idx)).astype(np.float32));stars=stars.reshape(N,N)
 # Separable smooth PSF, entirely authored in arrays (Pillow F blur unsupported).
 stars=(stars*4+np.roll(stars,1,0)+np.roll(stars,-1,0)+np.roll(stars,1,1)+np.roll(stars,-1,1))/8
 stellar=np.clip(stars*.35,0,.22)*dust
 smooth=(disk*.11+arms*.46)*np.clip(1+medium*.07+fine*.09+micro*.025,.55,1.4)*dust
 warm=np.array([1.,.62,.30],dtype=np.float32)
 armcolor=np.array([[.60,.77,1.],[.95,.77,.52],[.48,.72,1.],[.88,.80,.69],[.91,.83,.72],[.66,.79,.88]][k],dtype=np.float32)
 rgb=smooth[:,:,None]*armcolor+stellar[:,:,None]*np.array([.9,.84,.72],dtype=np.float32)+core[:,:,None]*warm
 if k==4:rgb+=(disk*.12*(1+fine*.012))[:,:,None]*warm
 # Soft photographic response with a compact warm nucleus and no flat white clipping.
 rgb=np.clip((1-np.exp(-rgb*2.05))**.58,0,.93)
 alpha=(np.clip((1-r)/.12,0,1)**2*255).astype(np.uint8)
 rgba=np.dstack([(rgb*255).astype(np.uint8),alpha]);path=out/(name+'.png');Image.fromarray(rgba).save(path,optimize=True)
 rows.append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 webp=out/(name+'.webp');Image.fromarray(rgba).save(webp,quality=94,method=4)
 runtime.append(dict(file=webp.name,bytes=webp.stat().st_size,sha256=hashlib.sha256(webp.read_bytes()).hexdigest()))
(out/'manifest.json').write_text(json.dumps({'version':3,'author':'Cosmos do Zero original mathematical artwork','license':'CC0-1.0','method':'High resolution integrated stellar density, smooth multi-scale gas, asymmetric absorption lanes, variable pitch and radial bulge profiles','interpretation':'Original illustration, no observed data, no N-body calculation','source':'assets/source/build_galaxies_v3.py','assets':rows,'runtime_assets':runtime},indent=2),encoding='utf-8')
print(rows)
