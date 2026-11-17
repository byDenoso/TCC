"""Prepare maps and optical layers. Run before build.py (Python, NumPy, Pillow)."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

root=Path(__file__).resolve().parents[3]
out=root/'public/models/atlas-studies/plates'
out.mkdir(exist_ok=True, parents=True)
work=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/cosmos-study-maps')
work.mkdir(exist_ok=True,parents=True)
rng=np.random.default_rng(601)
n=384
y,x=np.mgrid[-1.4:1.4:complex(n),-1.4:1.4:complex(n)]
r=np.hypot(x,y); theta=np.arctan2(y,x)

def layer(name,color,alpha):
    rgb=np.broadcast_to(color,(*r.shape,3)); rgba=np.dstack((rgb,np.clip(alpha,0,1)*255))
    pic=Image.fromarray(np.uint8(np.clip(rgba,0,255)))
    pic.save(out/(name+'.webp'),method=6,quality=88)
    pic.save(work/(name+'.png'))

def noise(size):
    return np.asarray(Image.fromarray(rng.integers(0,255,(size,size),dtype='uint8')).resize((n,n),Image.Resampling.BICUBIC)).astype(float)/255

# The same solar-temperature surface is sampled on both reference and variable stars.
grain=Image.open(root/'public/models/stellar/granulation.png').convert('L')
g=np.asarray(grain.resize((512,256)),dtype=float)
g=(g - np.percentile(g,3))/(np.percentile(g,97)-np.percentile(g,3))
g=np.clip(g,0,1)
b=np.dstack((210+45*g,114+129*g,59+132*g))
Image.fromarray(b.astype('uint8')).save(work/'photosphere.jpg',quality=86)
mu=np.sqrt(np.maximum(0,1-r*r))
lon=(np.arctan2(x,mu)/(2*np.pi)+.5)%1
lat=np.arcsin(np.clip(y,-1,1))/np.pi+.5
grain3=b[(lat*255).astype(int),(lon*511).astype(int)]
limb=np.where(r<=1,.46+.54*mu**.72,0)
flame=np.maximum(r-1,0); stream=np.sin(theta*57+noise(31)*2)*.07+1
edge=np.exp(-flame*(21+8*noise(16)))*(.22+.32*noise(55))*stream
disk=np.where((r<=1)[...,None],grain3*limb[...,None],np.array([255,144,58]))
layer('photosphere',disk,np.where(r<=1,1,edge))
halo=Image.fromarray(np.uint8(np.dstack((np.ones_like(r)*255,np.ones_like(r)*164,np.ones_like(r)*76,np.where(r<.985,0,edge*150)))))
halo.save(work/'corona.png')
# Circular, smoothly resolved image of a perfectly aligned source. Relative angular radius is measured at the ridge.
mott=.72+.15*np.sin(theta*5+.7)+.07*np.cos(theta*12)+.06*noise(34)
ring=(.8*np.exp(-((r-1)/.025)**2)+.36*np.exp(-((r-1)/.094)**2))*mott
layer('einstein',np.stack([152+56*mott,188+50*mott,255+0*mott],axis=-1),ring)
# Illustration of extended foreground lens light with elliptical isophotes.
rr=np.sqrt((.88*x+.46*y)**2 + ((.46*x-.88*y)*1.65)**2)
light=np.exp(-3.8*rr)*(.90+.10*noise(32))
bulge=np.stack((255-16*rr,236-76*rr,196-80*rr),axis=-1)
layer('lens-galaxy',bulge,np.clip(1.5*light,0,1))
# Shared sky: only a contextual, synthetic field, never presented as an observation.
sky=Image.new('RGB',(960,450),(4,8,15)); d=ImageDraw.Draw(sky)
for _ in range(1000):
    px=int(rng.uniform(0,960)); py=int(rng.uniform(0,450))
    brightness=int(140*rng.random()**3+16); color=(brightness,brightness+3,min(255,brightness+8))
    d.point((px,py),fill=color)
    if brightness>143:
        d.ellipse((px-1,py-1,px+1,py+1),fill=color)
sky.save(out/'sky.webp',quality=86,method=6)
# WebGL uses the same observed Earth map as the Solar Studio planet.
Image.open(root/'assets/source/solar-materials/terra.jpg').resize((512,256),Image.Resampling.LANCZOS).save(work/'earth.jpg',quality=86)
