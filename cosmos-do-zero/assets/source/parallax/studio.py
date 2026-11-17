"""Prefilter the tabletop's three softboxes into a PlayCanvas reflection atlas.

Run with Python, NumPy and Pillow. RGBM stores linear radiance above white.
The identical light directions are used for the full-resolution Cycles still.
"""
from pathlib import Path

import numpy as np
from PIL import Image

out = Path(__file__).resolve().parents[3] / "public/models/parallax/studio.png"
atlas = np.zeros((512, 512, 4), dtype=np.uint8)
panels = [((-3, 7, 3), (4.0, 3.25, 2.15), .24),
          ((1, 4, -5), (1.75, 2.60, 3.70), .18),
          ((5, 2, 1), (1.30, 1.05, .72), .17)]


def tile(x, y, width, height, spread):
    # The engine samples one pixel inside each cell to avoid neighboring mips.
    u, v = np.meshgrid(np.clip((np.arange(width) - .5)/(width - 2), 0, 1),
                       np.clip((np.arange(height) - .5)/(height - 2), 0, 1))
    longitude, latitude = (u-.5)*2*np.pi, (.5-v)*np.pi
    directions = np.stack((np.sin(longitude)*np.cos(latitude), np.sin(latitude),
                           np.cos(longitude)*np.cos(latitude)), axis=-1)
    sky = np.clip((directions[..., 1]+.25)/1.25, 0, 1)[..., None]
    rgb = .018 + sky * np.array([.060, .072, .085])
    for origin, color, angular_width in panels:
        axis = np.array(origin) / np.linalg.norm(origin)
        cosine = np.clip(directions @ axis, -1, 1)
        variance = angular_width**2 + spread**2
        lobe = np.exp((cosine-1) / variance) * angular_width**2 / variance
        rgb += lobe[..., None] * color
    values = np.sqrt(rgb)
    m = np.ceil(255*np.maximum(values.max(axis=-1), 1)/8)/255
    encoded = np.dstack((values / (8*m[..., None]), m))
    atlas[y:y+height, x:x+width] = np.rint(255*encoded).clip(0, 255).astype(np.uint8)


for level in range(6):
    size = 512 >> level
    offset = 512 - size
    tile(offset, offset, size, size//2, 0)
    if level:
        tile(0, offset, size, size//2, .02 * 2**level)
tile(128, 384, 64, 32, .85)
Image.fromarray(atlas).save(out, optimize=True)
