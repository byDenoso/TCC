"""Rebuild the story's transparent Sun, procedural studio backplate and compact-object study."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

root = Path(__file__).resolve().parents[1]
out = root / 'public/media/stories'
rng = np.random.default_rng(1808)
w, h = 1200, 675
y,x = np.mgrid[:h,:w]
base = np.empty((h,w,3))
dist = np.sqrt(((x-820)/750)**2 + ((y-370)/500)**2)
base[:] = [4,8,14] + np.exp(-dist[...,None]**2*2)*[5,10,15]
noise=rng.normal(0,.75,(h,w,1))
base+=noise
for _ in range(1450):
    sx,sy=rng.integers(0,w),rng.integers(0,h)
    q=.25+rng.random()**4*2.7
    shade=rng.choice([[.65,.80,1.0],[1,.88,.7],[.9,.95,1]])
    bright=rng.uniform(40,175)
    xs=np.arange(max(0,sx-4), min(w,sx+5))
    ys=np.arange(max(0,sy-4), min(h,sy+5))
    mask=np.exp(-((xs-sx)[None,:]**2+(ys-sy)[:,None]**2)/(q*.58))
    base[ys[:,None],xs]+=mask[...,None]*bright*shade
def as_image(rgb):
    return Image.fromarray(np.uint8(rgb.clip(0,255)))
as_image(base).save(out/'studio-field.webp',quality=87)
# White dwarf and magnetized neutron star shown at independent illustrative scales.
# The accretion disk is artistic; emitting matter is outside the dark centre.
frame=base.copy()
for sx,sy,size,color in [(220,246,25,[.77,.88,1]),(543,249,17,[.57,.8,1])]:
    rx=(x-sx)/size; ry=(y-sy)/size; rr=np.hypot(rx,ry)
    glow=60*np.exp(-rr*1.1)+22*np.exp(-rr*.30)
    disc=(rr<1)*(145+80*np.sqrt(np.maximum(0,1-rr**2)))
    frame+=(disc+glow)[...,None]*color
beam=np.exp(-((x-543+.30*(y-249))/13)**2)*np.exp(-abs(y-249)/67)
frame+=beam[...,None]*[38,85,110]
dx=(x-928)/71;dy=(y-238)/71
xr=dx*.97-dy*.24; yr=dx*.24+dy*.97; r=np.hypot(xr,yr)
ring=np.hypot(xr,yr*4.9)
ann=np.exp(-((ring-1.65)/.64)**2)*(1+.18*np.sin(ring*36+np.arctan2(yr,xr)*3))
lens=np.exp(-((r-1.03)/.08)**2)*np.clip(-yr*2,0,1)
sided=np.clip(1.1-xr*.35,.4,1.9)
shadow=np.clip((r-.90)*24,0,1)
frame*=np.where((yr<0)|(ring<1.35),shadow,1)[...,None]
frame+=(ann*(100+32*np.cos(ring*20))*sided+lens*155)[...,None]*[1,.64,.32]
as_image(frame).save(out/'stellar-remnants.webp',quality=89)
src=Image.open(root/'public/renders/star.webp').convert('RGB')
sz=690; x0,y0=600,400
sun=src.crop((x0-sz//2,y0-sz//2,x0+sz//2,y0+sz//2)).resize((320,320),Image.Resampling.LANCZOS).convert('RGBA')
sy,sx=np.mgrid[:320,:320];radius=np.hypot(sx-160,sy-160)
sun.putalpha(Image.fromarray(np.uint8(np.clip((158-radius)/29,0,1)*255)))
sun.save(out/'solar-disc.webp',quality=86)
Image.open(root/'src/assets/photos/iss-sunrise.webp').resize((1152,768),Image.Resampling.LANCZOS).save(out/'limbo-terrestre.webp',quality=88)
