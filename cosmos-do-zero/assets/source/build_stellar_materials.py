"""Original artistic density and spherical granulation. These are not observation arrays."""
from pathlib import Path
from PIL import Image
import numpy as np,json,hashlib
root=Path(__file__).resolve().parents[2];out=root/'public/models/stellar';out.mkdir(exist_ok=True)
N=128;rng=np.random.default_rng(928)
z,y,x=np.mgrid[-1:1:complex(N),-1:1:complex(N),-1:1:complex(N)]
k=np.fft.fftfreq(N)*N;kz,ky,kx=np.meshgrid(k,k,k,indexing='ij');k2=kx*kx+ky*ky+kz*kz
noise=np.zeros((N,N,N),np.float32)
for scale,amp in[(4,.38),(12,.32),(30,.22),(65,.08)]:
 field=np.fft.ifftn(np.fft.fftn(rng.normal(size=noise.shape))*np.exp(-k2/scale**2)).real;field=(field-field.mean())/field.std();noise+=field*amp
lobes=np.maximum.reduce([np.exp(-((x+.43)**2/.60+(y-.1)**2/.54+(z+.12)**2/.6)*2),np.exp(-((x-.38)**2/.50+(y+.26)**2/.35+(z-.06)**2/.5)*2),np.exp(-((x+.1)**2/.3+(y+.5)**2/.25+(z-.3)**2/.4)*2)])
cavity=((x-.18)**2/.34+(y-.24)**2/.22+(z-.7)**2/.72)
density=np.clip(.28+noise*.55,0,1)**1.3*lobes*(1-.89*np.exp(-cavity*2))
# Irregular cavity walls: the perturbation is volumetric noise, not sine ribbons.
front=np.sqrt(np.maximum(cavity,0));wall=np.exp(-((front-1-noise*.14)/.16)**2)*lobes*np.clip(.65+noise*.4,.04,1)
density=np.clip(density*.68+wall*.55,0,1)
density=np.clip(density,0,1);(out/'cloud-density-128.bin').write_bytes((density*255).astype(np.uint8).tobytes())
# Voronoi cells evaluated on the sphere, so poles and seam share the same field.
W,H=1024,512;lat,lon=np.mgrid[-np.pi/2:np.pi/2:complex(H),-np.pi:np.pi:complex(W)];p=np.stack([np.cos(lat)*np.cos(lon),np.sin(lat),np.cos(lat)*np.sin(lon)],axis=-1)*120
cell=np.floor(p);f=p-cell;d1=np.full((H,W),99.);d2=d1.copy()
for dz in[-1,0,1]:
 for dy in[-1,0,1]:
  for dx in[-1,0,1]:
   q=cell+np.array([dx,dy,dz]);a=q[:,:,0]*127.1+q[:,:,1]*311.7+q[:,:,2]*74.7
   jitter=np.stack([(np.sin(a+i*63.21)*43758.5453)%1 for i in range(3)],axis=-1);d=np.sum((np.array([dx,dy,dz])+jitter-f)**2,axis=2)
   d2=np.minimum(d2,np.maximum(d1,d));d1=np.minimum(d1,d)
grain=.69+.30*np.clip((np.sqrt(d2)-np.sqrt(d1))*4,0,1)**.55
Image.fromarray((grain*255).astype(np.uint8)).save(out/'granulation.png')
# Observational colour/detail source; depth is assigned by our artist volume, not inferred.
photo=root/'assets/source/observed/orion-heic0601a.jpg'
if photo.exists():
 from PIL import ImageFilter
 im=Image.open(photo).convert('RGB').resize((1024,1024),Image.Resampling.LANCZOS)
 im=im.filter(ImageFilter.MedianFilter(3))
 im.save(out/'orion-detail.webp',quality=90)
manifest={'author':'Cosmos do Zero','license':'CC0-1.0 (original generated assets only)','scientific_status':'Original illustrations: cloud density/cavity and spherical granulation, not observations or hydrodynamic calculations. Granules enlarged for display.','guides':['https://svs.gsfc.nasa.gov/30957/','https://svs.gsfc.nasa.gov/3412/'],'reproduction':'python assets/source/build_stellar_materials.py','observational_material':{'source':'https://esahubble.org/images/heic0601a/','license':'CC-BY-4.0','credit':'NASA, ESA, M. Robberto (Space Telescope Science Institute/ESA) and the Hubble Space Telescope Orion Treasury Project Team','modifications':'Reduced to 1024 px, median-filtered, projected into an artistic volume. Assigned depth and mechanism colours are not an observational 3D reconstruction.'},'files':[{'path':str(p.relative_to(root)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.glob('*') if p.suffix!='.json']}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print('stellar assets:',len(manifest['files']))
