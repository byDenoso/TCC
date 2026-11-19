"""Prepare two parallax layers and face-on dust textures for the educational renderer.
Install NumPy, SciPy and Pillow. Source JPEGs are retained alongside this script.
"""
from pathlib import Path
import hashlib, json, math
import numpy as np
from scipy.ndimage import map_coordinates
from PIL import Image, ImageFilter

here = Path(__file__).resolve().parent
out = here.parents[2]/'public/renders/formation'
out.mkdir(exist_ok=True, parents=True)

def save(name, rgb, alpha=None):
    image = Image.fromarray(np.uint8(np.clip(rgb, 0, 255)))
    if alpha is not None:
        image.putalpha(Image.fromarray(np.uint8(255*np.clip(alpha,0,1))))
    image.save(out/(name+'.webp'),quality=88,method=6)

cloud=Image.open(here/'eso1233a.jpg').convert('RGB')
cloud=cloud.crop((0,236,1280,956)).resize((1152,648),Image.Resampling.LANCZOS)
original=np.asarray(cloud).astype(np.float32)
diffuse=np.asarray(cloud.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(.65))).astype(np.float32)
save('cloud',diffuse)
save('cloud-stars',np.maximum(original-diffuse,0))

def unpack(name, center, radius, tilt, ratio, size):
    image=np.asarray(Image.open(here/(name+'.jpg')).convert('RGB')).astype(np.float32)
    yy,xx=np.mgrid[-1:1:complex(size),-1:1:complex(size)]
    rad=np.hypot(xx,yy)
    angle=math.radians(tilt)
    sx=center[0]+radius*(xx*math.cos(angle)-yy*ratio*math.sin(angle))
    sy=center[1]+radius*(xx*math.sin(angle)+yy*ratio*math.cos(angle))
    color=np.stack([map_coordinates(ch,(sy,sx),order=1,mode='nearest') for ch in image.transpose(2,0,1)],axis=-1)
    return rad,color

r,dust=unpack('eso1436f',(607,390),633,-19,.31,896)
smooth=lambda x: np.clip(x,0,1)**2*(3-2*np.clip(x,0,1))
edge=smooth((1-r)/.18)
save('disc',dust,edge)
# The central layer moves at a slightly different angular speed.
save('disc-inner',dust,smooth((.54-r)/.23))
r,obs=unpack('eso1436a',(900,900),930,-52,.66,720)
save('hl-tauri',obs,smooth((1-r)/.18)*smooth(obs[:,:,0]/28))
sources=[('eso1233a','screen','Barnard 59','ESO'),('eso1436f','screen','Artist’s impression of a young star surrounded by a protoplanetary disc','ESO/L. Calçada'),('eso1436a','large','ALMA image of the protoplanetary disc around HL Tauri','ALMA (ESO/NAOJ/NRAO)')]
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'licenseURL':'https://creativecommons.org/licenses/by/4.0/','sources':[dict(id=n,name=title,credit=credit,page=f'https://www.eso.org/public/images/{n}/',download=f'https://cdn.eso.org/images/{kind}/{n}.jpg',sha256=sha(here/(n+'.jpg'))) for n,kind,title,credit in sources],
 'method':'Illustrative motion and depth. Cloud cropped, divided into diffuse and point-like light. Discs geometrically resampled and alpha feathered for projection, using an artistic inclination. The measurements of HL Tauri are not measurements of the early Solar System.',
 'textures':[{'name':name,'sha256':sha(out/(name+'.webp'))} for name in ['cloud','cloud-stars','disc','disc-inner','hl-tauri']],
 'aggregates':'Mineral and ice-rich aggregates are original Blender Cycles illustrations. See build_aggregates.py and aggregates.blend.'}
(here/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

