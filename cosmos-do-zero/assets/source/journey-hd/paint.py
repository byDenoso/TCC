"""Original CPU plates. Coordinates are pictorial, with no physical length scale."""
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

W, H = 1600, 900
Y, X = np.mgrid[:H, :W].astype('f') / H
rng = np.random.default_rng(891)
grain = rng.uniform(-1, 1, (256, 256)).astype('f')


def noise(x, y):
    return map_coordinates(grain, [y, x], order=1, mode='grid-wrap')


def field(x, y):
    value = np.zeros_like(x)
    for octave in range(7):
        scale = 2 ** octave
        value += .5 ** (.78 * octave) * noise(x * scale + 17 * octave, y * scale - 11 * octave)
    return value


def pigment(value, stops):
    return np.stack([np.interp(value, np.linspace(0, 1, len(stops)), channel)
                     for channel in zip(*stops)], axis=-1)


def gas(seed):
    x, y = X * 2.8 + seed, Y * 3.1
    a = field(x, y)
    b = field(x + 12 + .45 * a, y - .8 * a)
    return field(x + 1.2 * b, y + .68 * a)


def render(era):
    if era == 'primordial':
        v = gas(23)
        color = pigment(.5 + .31 * v, [(68,15,24),(128,37,30),(216,85,27),
                                         (255,163,61),(255,221,150),(255,247,214)])
    elif era == 'dark-ages':
        v = gas(61)
        density = np.exp(-2.6 * abs(v - .26)) * (.36 + .64 * np.exp(-3 * (Y - .55)**2))
        color = pigment(density, [(5,9,18),(10,20,40),(23,40,62),(45,66,80),(91,104,104)])
    elif era == 'nucleosynthesis':
        # Four nucleons in a compact projected tetrahedron, farthest painted first.
        haze = np.exp(-3 * ((X - 1.1)**2 + (Y - .5)**2))
        color = pigment(haze * (.6 + .13 * gas(9)), [(12,14,28),(31,25,50),(78,48,64)])
        for cx, cy, r, base in [(1.01,.39,.166,[217,109,72]), (1.19,.43,.168,[71,135,176]),
                                (.99,.60,.171,[71,135,176]), (1.18,.59,.175,[217,109,72])]:
            dx, dy = (X-cx)/r, (Y-cy)/r
            rr = dx*dx + dy*dy
            nz = np.sqrt(np.maximum(0,1-rr))
            light = np.maximum(0,-.54*dx-.68*dy+.49*nz)
            relief = .09 * field(7*dx+8*nz,7*dy)
            surface = np.array(base) * (.25 + .84*light + relief)[:,:,None]
            surface += (55 * light**12 + 18*(1-nz)**3)[:,:,None]
            alpha = np.clip((1-rr)*r*H,0,1)[:,:,None]
            color = color*(1-alpha) + surface*alpha
    elif era == 'earth':
        cx, cy, radius = 1.07, .86, .61
        dx, dy = (X-cx)/radius, (Y-cy)/radius
        radial = np.hypot(dx,dy)
        z = np.sqrt(np.maximum(0,1-radial**2))
        lon, lat = np.arctan2(dx,z), np.arcsin(np.clip(dy,-1,1))
        # Warp both angular coordinates before tracing incandescent fissures.
        u = 3.4*lon + 2.1*lat
        v = 3.4*lat - 2.1*lon
        crust = field(u + .96*field(u+9, v), v + .92*field(u, v+13))
        seams = np.exp(-7*abs(crust-.07))
        sun = np.clip(-.65*dx-.59*dy+.17*z,0,1)
        color = pigment(seams, [(25,19,22),(69,36,27),(139,53,21),(231,87,24),(255,166,52)])
        color += sun[:,:,None] * np.array([80,58,40]) * (.65+.35*crust[:,:,None])
        halo = np.exp(-16*abs(radial-1)) * (.15+.85*sun)
        sky = np.array([5,7,15]) + halo[:,:,None]*np.array([136,64,33])
        color = np.where((radial<=1)[:,:,None],color,sky)
    else:
        raise ValueError(era)
    return Image.fromarray(np.uint8(np.clip(color,0,255)))

