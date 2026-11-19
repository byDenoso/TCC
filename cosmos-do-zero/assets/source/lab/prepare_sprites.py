"""Prepare local lab sprites from the original M51 image and the project's model fields."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'public/models/lab'
OUT.mkdir(exist_ok=True)

# Crop the main galaxy from the credited Hubble image and feather the field boundary.
with Image.open(ROOT / 'assets/source/observed/heic0506a.jpg') as photo:
    width, height = photo.size
    r = .43 * height
    x, y = .43 * width, .54 * height
    cut = photo.crop((int(x-r), int(y-r), int(x+r), int(y+r)))
    spiral = cut.resize((384, 384), Image.Resampling.LANCZOS).convert('RGBA')
mask = Image.new('L', spiral.size)
ImageDraw.Draw(mask).ellipse((23, 23, 361, 361), fill=255)
spiral.putalpha(mask.filter(ImageFilter.GaussianBlur(9)))
spiral.save(ROOT / 'public/photos/m51/lab-disc.webp', quality=88)

# Convert the dark matte of each illustrative emission map to transparency.
for name in ('barred-spiral', 'elliptical'):
    with Image.open(ROOT / f'public/models/galaxies-v4/512/{name}.webp') as source:
        frame = source.convert('RGBA').resize((320, 320), Image.Resampling.LANCZOS)
    pixels = np.asarray(frame).astype(float) / 255
    alpha = np.sqrt(pixels[:, :, :3].max(axis=2))
    rgb = np.minimum(1, pixels[:, :, :3] / np.maximum(alpha[:, :, None], .005) * 1.3)
    sprite = 255 * np.dstack((rgb, alpha * pixels[:, :, 3]))
    Image.fromarray(sprite.astype('uint8')).save(OUT / f'{name}.webp', quality=90)

# Synthetic contrast texture used only to identify a diffuse emission region.
field = np.load(ROOT / 'assets/source/posters/cmb-synthetic-field.npy')[240:496, 440:696]
value = (field + 1) / 2
y, x = np.mgrid[-1:1:256j, -1:1:256j]
alpha = np.clip(1-x*x-y*y, 0, 1)**1.4
rgba = np.stack([160+80*value, 95+95*value, 70+75*value, 255*alpha*(.6+.4*value)], axis=-1)
Image.fromarray(rgba.astype('uint8')).save(OUT / 'gas-region.webp', quality=88)
