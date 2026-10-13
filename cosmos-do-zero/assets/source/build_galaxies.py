"""Original continuous galaxy emission fields, CC0. Not an observed image or N-body result."""
from pathlib import Path
import numpy as np
from PIL import Image
import hashlib,json
out=Path(__file__).resolve().parents[2]/'public'/'models'/'galaxies';out.mkdir(parents=True,exist_ok=True)
N=1024
y,x=np.mgrid[-1:1:complex(N),-1:1:complex(N)]
rows=[]
for k,name in enumerate(['grand-spiral','barred-spiral','many-arms','lenticular','elliptical','irregular']):
 rng=np.random.default_rng(8712+k)
 xx=x*(1.08 if k==4 else 1); yy=y*(1.6 if k==4 else 1)
 r=np.sqrt(xx*xx+yy*yy);a=np.arctan2(yy,xx)
 # Continuous multi-frequency gas structure; no point cloud or discrete star beads.
 turbulence=np.zeros_like(r)
 for j in range(18):
  f=rng.uniform(5,90);ang=rng.uniform(0,6.28)
  turbulence+=np.sin(f*(x*np.cos(ang)+y*np.sin(ang))+rng.uniform(0,6.28))/(3+j*.35)
 turbulence=np.tanh(turbulence*.55)
 disk=np.exp(-r*2.4)*np.maximum(0,1-r)**1.8
 core=np.exp(-r*r/(.07 if k in [3,4] else .009))
 halo=np.exp(-r*r/.25)*.12
 arms=np.zeros_like(r);dust=np.ones_like(r)
 if k in [0,1,2]:
  m=[2,2,5][k];phase=m*(a-2.4*np.log(r+.055))+.33*turbulence
  arms=np.exp((np.cos(phase)-1)*1.65)*np.exp(-r*1.15)*np.maximum(0,1-r)**.7
  arms*=np.clip((r-.07)*12,0,1)
  dust=1-.63*np.exp((np.cos(phase+.5)-1)*12)*np.clip(r*6,0,1)
  if k==1:core+=.65*np.exp(-x*x/.13-y*y/.003)
 elif k==3:
  arms=.15*np.exp(-((r-.35)/.09)**2)
 elif k==5:
  core*=.4;disk*=.6
  for j in range(7):
   cx,cy=rng.uniform(-.5,.5,2);sx,sy=rng.uniform(.07,.22,2)
   arms+=rng.uniform(.15,.35)*np.exp(-((x-cx)/sx)**2-((y-cy)/sy)**2)
  arms*=np.maximum(0,1-r)**2
 fine=np.clip(1+turbulence*.5,.3,1.5)
 emission=(disk*.65+arms*.73)*fine*dust+core*.73+halo*.5
 if k==4:emission=core*.7+disk*.8+halo*.25
 alpha=np.clip(emission,0,.97)*np.clip((1-r)*12,0,1)
 warm=np.array([1.,.83,.6]);cold=np.array([.47,.69,1.])
 mix=np.clip(np.exp(-r*r/.035),0,1)
 if k in [3,4]:mix=np.clip(mix*.4+.6,0,1)
 rgb=cold[None,None,:]*(1-mix[:,:,None])+warm[None,None,:]*mix[:,:,None]
 rgb*=np.clip(.72+emission*.5,.65,1.15)[:,:,None]
 rgba=np.dstack([np.clip(rgb*255,0,255).astype(np.uint8),(alpha*255).astype(np.uint8)])
 path=out/(name+'.png');Image.fromarray(rgba).save(path,optimize=True)
 rows.append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(out/'manifest.json').write_text(json.dumps({'author':'Cosmos do Zero original mathematical artwork','license':'CC0-1.0','method':'Continuous emission fields with log-spiral arms, smooth gas turbulence, absorption lanes and Gaussian nucleus','interpretation':'Illustration; no observed data and no physical dynamical simulation','source':'assets/source/build_galaxies.py','assets':rows},indent=2),encoding='utf-8')
print(rows)
