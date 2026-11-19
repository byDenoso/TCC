"""Prepare photographic sprites for the chapter experiments."""
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / 'public/renders/micro-hd'
OUT.mkdir(parents=True, exist_ok=True)
files = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(img, name, source):
    dest = OUT / (name + '.webp')
    img.save(dest, quality=86, method=4)
    files.append(dict(file=dest.name, size=img.size, bytes=dest.stat().st_size,
                      sha256=digest(dest), source=str(source.relative_to(ROOT)).replace('\\', '/')))


def feather(img, begin=.85):
    yy, xx = np.indices((img.height, img.width))
    r = np.hypot((xx+.5)/img.width*2-1, (yy+.5)/img.height*2-1)
    img.putalpha(Image.fromarray((255*np.clip((1-r)/(1-begin), 0, 1)).astype('uint8')))
    return img


# The right-hand SDO disk is the solar maximum panel. Crop clear of both labels.
src = HERE / 'sdo.png'
im = Image.open(src).convert('RGB')
red = np.asarray(im)[:,:,0]
yy, xx = np.where((red > 105) & (np.indices(red.shape)[1] > 960) & (np.indices(red.shape)[0] > 240))
box = (xx.min(), yy.min(), xx.max()+1, yy.max()+1)
disk = feather(im.crop(box), .992)
save(disk, 'sol', src)
for name, bright in [('gigante', '#ffb593'), ('azul', '#c0dcff'), ('branca', '#fff8dd')]:
    luminous = ImageOps.colorize(ImageOps.grayscale(disk), '#231b26', bright, whitepoint=211)
    luminous.putalpha(disk.getchannel('A'))
    save(luminous, name, src)

src = ROOT/'assets/source/observed/heic0506a.jpg'
im = Image.open(src).convert('RGB')
r = round(im.height*.41)
cx, cy = round(im.width*.39), round(im.height*.48)
save(feather(im.crop((cx-r,cy-r,cx+r,cy+r)).resize((832,832), Image.Resampling.LANCZOS), .73), 'espiral', src)
src = ROOT/'src/assets/photos/andromeda-wise.webp'
im = Image.open(src).convert('RGB')
save(feather(im.resize((768,768), Image.Resampling.LANCZOS),.87), 'andromeda',src)
src = HERE/'hartley.jpg'
im = Image.open(src).convert('RGB').crop((160,137,636,490))
save(feather(im,.71), 'hartley', src)
src = ROOT/'src/assets/photos/planck-cmb.webp'
im = Image.open(src).convert('RGB')
save(im.crop((29,26,870,470)), 'fundo-planck',src)
src = ROOT/'src/assets/photos/iss-sunrise.webp'
im=Image.open(src).convert('RGB')
im.thumbnail((1120,800),Image.Resampling.LANCZOS)
save(im,'limbo-iss',src)

for name, source in [('gas','public/renders/ancient-light.webp'),
                     ('molecular','assets/source/formation/eso1233a.jpg')]:
    src = ROOT/source
    im = Image.open(src).convert('RGB')
    tile = ImageOps.fit(im,(832,624),method=Image.Resampling.LANCZOS)
    save(feather(tile,.62),name,src)

(HERE/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

