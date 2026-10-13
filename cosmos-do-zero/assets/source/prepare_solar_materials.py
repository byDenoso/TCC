"""Solar material authoring: observed maps unchanged as originals; resized exports + declared artistic layers."""
from pathlib import Path
from PIL import Image,ImageEnhance
import numpy as np,json,hashlib
root=Path(__file__).resolve().parents[2];src=root/'assets/source/observed';out=root/'assets/source/solar-materials';out.mkdir(exist_ok=True)
manifest=[]
entries=[('terra','earth-bmng-200407.jpg','NASA Earth Observatory / Blue Marble: Next Generation / MODIS','Observed monthly composite, July2004, not current weather','https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/'),('lua','moon-lroc-color-2025.jpg',"NASA Scientific Visualization Studio / Ernie Wright (USRA), Noah Petro (NASA/GSFC); LRO/LOLA/LROC/ASU",'Observed LROC mosaic, December2025 rendering-optimized colors; polar gaps filled by source authors','https://svs.gsfc.nasa.gov/4720/'),('jupiter','jupiter-hubble-opal-2015.tif',"NASA Goddard Space Flight Center / Space Telescope Science Institute; Amy Simon, Michael Wong, Glenn Orton",'Hubble WFC3 OPAL observed global color composite, 2015; unobserved polar strips filled visually, not data','https://svs.gsfc.nasa.gov/12021/'),('marte','mars-nasa.jpg','NASA/Jet Propulsion Laboratory & Caltech; Viking/USGS','Viking composite texture processed at USGS','https://science.nasa.gov/3d-resources/mars/'),('saturno','saturn-nasa-illustrative.jpg','JPL/Caltech planetary-map collection','Fictional/illustrative map as classified by NASA','https://science.nasa.gov/3d-resources/saturn/'),('netuno','neptune-nasa-illustrative.jpg','Don Davis & JPL/Caltech','Fictional/illustrative map as classified by NASA; not an observed globe map','https://science.nasa.gov/3d-resources/neptune/')]
for name,file,credit,status,url in entries:
 image=Image.open(src/file).convert('RGB')
 if name=='jupiter':
  pixels=np.asarray(image).copy();valid=np.where(pixels.mean(axis=(1,2))>8)[0];top,bottom=valid[0],valid[-1];pixels[:top]=pixels[top:top+4].mean(axis=(0,1)).astype(np.uint8);pixels[bottom+1:]=pixels[bottom-3:bottom+1].mean(axis=(0,1)).astype(np.uint8);image=Image.fromarray(pixels)
 image.thumbnail((2048,1024),Image.Resampling.LANCZOS);image.save(out/(name+'.jpg'),quality=94)
 if name=='saturno':ImageEnhance.Color(image).enhance(.38).save(out/(name+'.jpg'),quality=94)
 manifest.append(dict(world=name,original='assets/source/observed/'+file,source_url=url,credit=credit,status=status,modification='resize/recompression for the browser; geometry and illumination illustrative',license='NASA resource usage policy; retain listed credits, no endorsement implied'))
W,H=1024,512;lat,lon=np.mgrid[-np.pi/2:np.pi/2:complex(H),-np.pi:np.pi:complex(W)];rng=np.random.default_rng(1724)
def field(seed,stretch=1):
 r=np.random.default_rng(seed);z=np.zeros((H,W),np.float32)
 for freq,amp in [(4,.45),(9,.25),(23,.17),(61,.08),(137,.05)]:
  phase=r.uniform(0,2*np.pi);z+=amp*np.sin(np.cos(lon)*freq+np.sin(lat*stretch)*freq*.7+phase)*np.cos(np.sin(lon)*freq*.8+np.cos(lat*stretch)*freq+.3*phase)
 return z
# Mercury: explicitly original crater field; no claim of observed terrain reconstruction.
xyz=np.stack([np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)],axis=-1);height=field(811)*.0006
for i in range(390):
 vec=rng.normal(size=3);vec/=np.linalg.norm(vec);a=np.arccos(np.clip(xyz@vec,-1,1));radius=rng.uniform(.007,.08)**1.04;q=a/radius
 height+=(-.003*np.exp(-(q/.73)**4)+.0015*np.exp(-((q-1)/.16)**2))*np.clip(1-q/2.4,0,1)
shade=np.clip(.51+field(45)*.055+height*10,.32,.63);rgb=np.dstack([shade*.98,shade*.96,shade*.94]);Image.fromarray((rgb*255).astype(np.uint8)).save(out/'mercurio.jpg',quality=95)
# Tangent-space normal maps derived from a relative relief field (not quantitative altitude).
def normal(a,file,strength):
 dy,dx=np.gradient(a);v=np.dstack([-dx*strength,-dy*strength,np.ones(a.shape)]);v/=np.linalg.norm(v,axis=2)[:,:,None];Image.fromarray(((v*.5+.5)*255).astype(np.uint8)).save(out/file)
normal(height,'mercurio-normal.png',140)
h=np.asarray(Image.open(src/'moon-lola-height.jpg').convert('L'),dtype=np.float32)/255;normal(h,'lua-normal.png',5)
# Venus optical cloud appearance and Uranus: original illustrations, not surface geography.
for name,base,seed in [('venus',np.array([.81,.74,.57]),55),('urano',np.array([.43,.71,.73]),18)]:
 noise=field(seed)*np.cos(lat)**2;bands=np.sin(lat*16+field(seed+1)*.7*np.cos(lat)**2)*(.016 if name=='urano' else .025);color=np.clip(base[None,None,:]*(1+noise[:,:,None]*(.025 if name=='urano' else .10)+bands[:,:,None]),0,1);Image.fromarray((color*255).astype(np.uint8)).save(out/(name+'.jpg'),quality=95)
# Earth cloud layer: weather is original illustration, with fine multiscale density and large spirals.
density=np.zeros((H,W),np.float32)
for scale,weight in [(12,.5),(28,.28),(65,.14),(143,.08)]:
 small=Image.fromarray((rng.random((scale//2,scale))*255).astype(np.uint8));density+=np.asarray(small.resize((W,H),Image.Resampling.BICUBIC),dtype=np.float32)/255*weight
# Periodic longitudinal warping avoids repeated straight wave bands.
indices=(np.arange(W)[None,:]+(20*np.sin(lat*7)+12*np.sin(lat*17)).astype(int))%W;density=np.take_along_axis(density,indices,axis=1)
alpha=np.clip((density-.56)*7.5,0,.85);cloud=np.dstack([np.full((H,W,3),235,np.uint8),(alpha*225).astype(np.uint8)]);Image.fromarray(cloud).save(out/'terra-clouds.png')
earth=np.asarray(Image.open(out/'terra.jpg').resize((W,H)),dtype=np.float32)/255;sea=(earth[:,:,2]>earth[:,:,0]*1.22)&(earth[:,:,2]>earth[:,:,1]*1.08);rough=np.where(sea,.28,.92);Image.fromarray((rough*255).astype(np.uint8)).save(out/'terra-roughness.png')
manifest += [dict(world=n,credit='Cosmos do Zero original authoring',license='CC0-1.0',status=s,source='assets/source/prepare_solar_materials.py') for n,s in [('mercurio','Original illustrative crater field, not a MESSENGER map'),('venus','Original illustrative optical cloud layer, no radar surface'),('urano','Original illustrative atmospheric colors, not observed global texture'),('terra-clouds','Original weather/cloud illustration, not satellite weather data'),('terra-roughness','Visual land/ocean roughness inferred from color composition; not a scientific surface mask')]]
manifest=[m for m in manifest if m['world']!='mercurio']
mercury=Image.open(src/'mercury-messenger-enhanced.jpg').convert('RGB');mercury.thumbnail((2048,1024),Image.Resampling.LANCZOS);mercury.save(out/'mercurio.jpg',quality=94)
manifest.append(dict(world='mercurio',original='assets/source/observed/mercury-messenger-enhanced.jpg',source_url='https://science.nasa.gov/resource/enhanced-color-mercury-map/',credit='NASA/Johns Hopkins University Applied Physics Laboratory/Carnegie Institution of Washington',status='MESSENGER PIA17386 enhanced-color global map; not human-eye colors',modification='Resize and recompression; colors enhanced by source authors, not recolored by Cosmos; normalized sphere and lighting illustrative',license='NASA resource usage policy; retain listed credit'))
next(m for m in manifest if m['world']=='saturno')['modification']='Illustrative NASA map desaturated for cream atmospheric appearance; resize and recompression; geometry and illumination illustrative'
# Original radial density for thin Saturn rings; explicit geometry/density illustration.
x=np.linspace(1.11,2.32,1024);opacity=np.zeros_like(x)
for lo,hi,k in[(1.23,1.53,.31),(1.53,1.95,.9),(2.02,2.27,.62),(2.30,2.32,.19)]:opacity+=((x>=lo)&(x<=hi))*k
opacity*=np.clip(.88+.06*np.sin(x*330)+.04*np.sin(x*733+.8)+.025*np.sin(x*1257),.1,1);t=.75+.06*np.sin(x*23);ring=np.zeros((16,1024,4),np.uint8);ring[:,:,:3]=(np.stack([t,t*.88,t*.69],axis=-1)*255)[None,:,:];ring[:,:,3]=(opacity*255)[None,:];Image.fromarray(ring).save(out/'saturno-rings.png')
files=[dict(path=str(p.relative_to(root)).replace('\\','/'),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in list(out.glob('*'))+list(src.glob('*')) if p.is_file() and p.suffix!='.json']
(out/'manifest.json').write_text(json.dumps(dict(materials=manifest,files=files,policy_url='https://www.nasa.gov/nasa-brand-center/images-and-media/',note='Lighting, atmosphere thickness, normal strength and ring density are illustrative. No shared CC0 claim for NASA/third-party maps.'),indent=2),encoding='utf-8');print('solar maps prepared:',len(files))
