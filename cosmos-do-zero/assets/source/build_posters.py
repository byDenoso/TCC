from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np,json,hashlib
root=Path(__file__).resolve().parents[2];src=root/'assets/source/posters/captures';out=root/'public/posters';out.mkdir(exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',23)
rows=[]
def export(name,image,label,origin,license):
 image=image.convert('RGB');image.thumbnail((1200,800),Image.Resampling.LANCZOS)
 canvas=Image.new('RGB',(1200,800),'#070c18');canvas.paste(image,((1200-image.width)//2,(800-image.height)//2))
 draw=ImageDraw.Draw(canvas);draw.rectangle((0,747,1200,800),fill='#070c18');draw.text((30,761),label,font=font,fill='#d1d9e4')
 canvas.save(out/(name+'.webp'),quality=88,method=4);canvas.resize((600,400),Image.Resampling.LANCZOS).save(out/(name+'-small.webp'),quality=84,method=4)
 canvas.save(root/'assets/source/posters'/(name+'.png'),optimize=True)
 files=[]
 for f in [out/(name+'.webp'),out/(name+'-small.webp')]:files.append(dict(file=f.name,bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
 rows.append(dict(name=name,origin=origin,license=license,caption=label,files=files))
for name,label in [('plasma','Plasma primordial · esquema com luz, elétrons e núcleos · sem estrelas'),('nuclei','Primeiros núcleos · partículas ampliadas · ilustração'),('star','Superfície estelar · granulação ampliada · ilustração'),('galaxies','Galáxia ilustrativa · estrelas e poeira sintetizadas'),('group-local','Grupo Local · posição e morfologia ilustrativas'),('solar-system','Sistema Solar · tamanhos e separações ilustrativos'),('cosmic-web','Distribuição artística · filamentos, aglomerações e vazios')]:
 export(name,Image.open(src/(name+'.png')),label,'Capture of the corresponding interactive scene; capture.json specifies route and state','CC0-1.0 original artwork; solar maps retain credits in solar-materials manifest')
export('earth',Image.open(root/'public/models/portraits/terra.webp'),'Terra · composição MODIS e geometria/iluminação ilustrativas','NASA Earth Observatory Blue Marble Next Generation July2004, rendered original Blender model','NASA media policy; official credits preserved in solar-materials manifest')
# Synthetic angular field on an elliptical full-sky illustration. No observational data.
w,h=1200,640;x,y=np.meshgrid(np.linspace(-1,1,w),np.linspace(-1,1,h));mask=x*x+y*y<1
lon=np.pi*x/np.sqrt(np.maximum(1e-6,1-y*y));lat=np.arcsin(np.clip(y,-1,1));field=np.zeros((h,w));rng=np.random.default_rng(1976)
for frequency in [2,4,8,14,23,37]:
 for j in range(6):field+=np.sin(lon*frequency*rng.uniform(.3,1)+rng.uniform(0,6))*np.cos(lat*frequency*rng.uniform(.5,1)+rng.uniform(0,6))/frequency**.45
field=np.tanh(field*.7);warm=np.array([211,108,54]);cool=np.array([43,92,167]);middle=np.array([213,190,125]);rgb=np.where((field>0)[:,:,None],middle+(warm-middle)*np.maximum(field,0)[:,:,None],middle+(cool-middle)*np.maximum(-field,0)[:,:,None]);rgb[~mask]=[7,12,24]
np.save(root/'assets/source/posters/cmb-synthetic-field.npy',field.astype('float32'))
export('cmb',Image.fromarray(rgb.astype('uint8')),'CMB · mapa ilustrativo do céu · contraste ampliado · não são dados','Original angular-field illustration; not Planck/WMAP data or a material shell','CC0-1.0')
(out/'manifest.json').write_text(json.dumps(dict(method='Real captures of interactive scenes plus explicitly synthetic full-sky map',source='assets/source/build_posters.py',assets=rows),indent=2,ensure_ascii=False),encoding='utf-8')
print([(r['name'],sum(f['bytes'] for f in r['files'])) for r in rows])
