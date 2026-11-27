"""Constrói os modelos 3D (GLB) e os pôsteres (Cycles) da viagem guiada do Cosmos.

Na pasta cosmos-do-zero:
  blender -b -t 3 --python-exit-code 1 -P assets/source/viagem/build_viagem.py -- [estacao ...] [--sem-poster]

Sem estações na linha de comando, constrói as nove. A câmera, a luz e as posições
vêm de escola/src/components/viagem/cenas.json, o mesmo arquivo que a página lê,
para que pôster e cena interativa mostrem o mesmo enquadramento.
"""

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

SRC = Path(__file__).resolve().parent
ROOT = SRC.parents[2]
ESCOLA = ROOT / 'escola'
MAPS = ROOT / 'assets' / 'source' / 'solar-materials'
OBS = ROOT / 'assets' / 'source' / 'observed'
OUT = ESCOLA / 'public' / 'viagem'
GEN = SRC / 'gerado'
CENAS = json.loads((ESCOLA / 'src' / 'components' / 'viagem' / 'cenas.json').read_text(encoding='utf-8'))
FUNDO = CENAS['fundo']


# ---------------------------------------------------------------- utilidades

def b(v):
    """Coordenadas da página (y para cima) para o Blender (z para cima)."""
    x, y, z = v
    return Vector((x, -z, y))


def b_array(p):
    return np.stack([p[:, 0], -p[:, 2], p[:, 1]], axis=1)


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def srgb_to_linear(c):
    c = np.asarray(c, dtype='float64')
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def kelvin_rgb(T):
    """Cor aproximada de um corpo negro (ajuste de Tanner Helland), valores 0–1 em sRGB."""
    t = np.asarray(T, dtype='float64') / 100.0
    r = np.where(t <= 66, 255.0, 329.698727446 * np.power(np.maximum(t - 60, 1e-6), -0.1332047592))
    g = np.where(t <= 66, 99.4708025861 * np.log(t) - 161.1195681661,
                 288.1221695283 * np.power(np.maximum(t - 60, 1e-6), -0.0755148492))
    bl = np.where(t >= 66, 255.0, np.where(t <= 19, 0.0, 138.5177312231 * np.log(np.maximum(t - 10, 1e-6)) - 305.0447927307))
    return np.clip(np.stack([r, g, bl], axis=-1) / 255.0, 0, 1)


def image(path, width=None):
    img = bpy.data.images.load(str(path), check_existing=False)
    if width and img.size[0] > width:
        img.scale(width, round(img.size[1] * width / img.size[0]))
    return img


def image_from_array(name, arr):
    """arr: altura × largura × 4 em sRGB 0–1, linha 0 no topo."""
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1], dtype='float32').ravel())
    GEN.mkdir(parents=True, exist_ok=True)
    img.filepath_raw = str(GEN / (name + '.png'))
    img.file_format = 'PNG'
    img.save()
    img.pack()
    return img


def material(name, color=(1, 1, 1, 1), rough=0.9, tex=None, emission_tex=None, emission=None,
             strength=1.0, alpha_tex=False, normal=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Specular IOR Level'].default_value = 0.15
    if tex is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = tex
        nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
        if alpha_tex:
            nt.links.new(t.outputs['Alpha'], bsdf.inputs['Alpha'])
            m.surface_render_method = 'BLENDED'
            m.use_backface_culling = False
    if emission_tex is not None:
        e = nt.nodes.new('ShaderNodeTexImage')
        e.image = emission_tex
        nt.links.new(e.outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = strength
        if tex is None:
            bsdf.inputs['Base Color'].default_value = (0, 0, 0, 1)
        if alpha_tex and tex is None:
            nt.links.new(e.outputs['Alpha'], bsdf.inputs['Alpha'])
            m.surface_render_method = 'BLENDED'
            m.use_backface_culling = False
    elif emission is not None:
        bsdf.inputs['Emission Color'].default_value = emission
        bsdf.inputs['Emission Strength'].default_value = strength
    if normal is not None:
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = normal
        n.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = 0.8
        nt.links.new(n.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def sphere(name, r, mat, seg=128, rings=64, polar=1.0, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r, location=b(loc))
    ob = bpy.context.active_object
    ob.name = name
    ob.data.name = name
    ob.scale.z = polar
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(mat)
    return ob


def annulus(name, r0, r1, mat, count=256, radial=1):
    """Anel no plano equatorial. UV: u cresce para fora, v dá a volta."""
    verts = []
    for i in range(count + 1):
        a = i * math.tau / count
        for k in range(radial + 1):
            r = r0 + (r1 - r0) * k / radial
            verts.append((r * math.cos(a), r * math.sin(a), 0.0))
    step = radial + 1
    faces = []
    for i in range(count):
        for k in range(radial):
            p = i * step + k
            faces.append((p, p + step, p + step + 1, p + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            uv.data[li].uv = ((vi % step) / radial, (vi // step) / count)
    me.materials.append(mat)
    return link(bpy.data.objects.new(name, me))


def points(name, pos, rgb, size):
    """Nuvem de pontos com cor (COLOR_0) e raio (_RADIUS no glTF) por ponto; pos em coordenadas da página."""
    n = len(pos)
    pc = bpy.data.pointclouds.new(name)
    pc.resize(n)
    pc.attributes['position'].data.foreach_set('vector', b_array(pos).astype('float32').ravel())
    if 'radius' not in pc.attributes:
        pc.attributes.new('radius', 'FLOAT', 'POINT')
    pc.attributes['radius'].data.foreach_set('value', np.asarray(size, dtype='float32'))
    rgba = np.concatenate([np.clip(rgb, 0, None), np.ones((n, 1))], axis=1).astype('float32')
    col = pc.attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    # COLOR_0 é linear no glTF e no Cycles; a página e o pôster leem os mesmos valores
    col.data.foreach_set('color', rgba.ravel())
    return link(bpy.data.objects.new(name, pc))


def point_material(obs, strength=2.5):
    m = bpy.data.materials.new('pontos')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'Col'
    em.inputs['Strength'].default_value = strength
    nt.links.new(at.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    for ob in obs:
        ob.data.materials.clear()
        ob.data.materials.append(m)


def tingir(mat, rgb):
    """Multiplica a textura de emissão por uma cor (cópia da imagem; usado só no pôster)."""
    tex = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
    img = tex.image.copy()
    px = np.empty(img.size[0] * img.size[1] * 4, 'float32')
    img.pixels.foreach_get(px)
    for c in range(3):
        px[c::4] *= float(rgb[c])
    img.pixels.foreach_set(px)
    tex.image = img


def limbo(mat, k=0.62):
    """Escurecimento do limbo: a borda do disco estelar emite menos (só no pôster)."""
    nt = mat.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    tex = [n for n in nt.nodes if n.type == 'TEX_IMAGE'][0]
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    m = nt.nodes.new('ShaderNodeMath')
    m.operation = 'MULTIPLY_ADD'
    m.inputs[1].default_value = -k
    m.inputs[2].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], m.inputs[0])
    vm = nt.nodes.new('ShaderNodeVectorMath')
    vm.operation = 'SCALE'
    nt.links.new(tex.outputs['Color'], vm.inputs[0])
    nt.links.new(m.outputs[0], vm.inputs['Scale'])
    nt.links.new(vm.outputs['Vector'], bsdf.inputs['Emission Color'])


# ------------------------------------------------------- campos aleatórios

def sphere_dirs(w, h):
    lon = (np.arange(w) + 0.5) / w * 2 * np.pi - np.pi
    lat = np.pi / 2 - (np.arange(h) + 0.5) / h * np.pi
    lon, lat = np.meshgrid(lon, lat)
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], -1).astype('float32')


def wave_field(dirs, ells, rng, chunk=24):
    """Campo isotrópico na esfera: soma de ondas planas cos(ℓ k·n + φ) com direções aleatórias."""
    h, w, _ = dirs.shape
    flat = dirs.reshape(-1, 3)
    k = rng.normal(size=(len(ells), 3))
    k /= np.linalg.norm(k, axis=1, keepdims=True)
    k = (k * np.asarray(ells)[:, None]).astype('float32')
    ph = rng.uniform(0, 2 * np.pi, len(ells)).astype('float32')
    out = np.zeros(len(flat), 'float32')
    for i in range(0, len(ells), chunk):
        out += np.cos(flat @ k[i:i + chunk].T + ph[i:i + chunk]).sum(1)
    out = out.reshape(h, w)
    return (out - out.mean()) / out.std()


def ramp(x, stops):
    xs = np.array([s[0] for s in stops])
    cs = np.array([s[1] for s in stops])
    return np.stack([np.interp(x, xs, cs[:, i]) for i in range(3)], -1)


def granulation(rng, w=1024, h=512):
    d = sphere_dirs(w, h)
    fine = wave_field(d, rng.uniform(140, 360, 560), rng, chunk=8)
    coarse = wave_field(d, rng.uniform(10, 40, 90), rng, chunk=8)
    return np.tanh(0.55 * fine + 0.35 * coarse)


def pixels(img):
    w, h = img.size
    a = np.empty(w * h * 4, 'float32')
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)[::-1]


def mapa_zonal(nome, fonte, w, h, rng, turbulencia=0.0035, contraste=0.05, polos=72):
    """Mapa de planeta gasoso em alta resolução a partir de um mapa observado de baixa resolução.

    As cores de cada latitude vêm da mediana do mapa original ao longo da longitude; as bordas das
    faixas ondulam com um campo aleatório e ganham variação fina de brilho. Acima de |lat| = polos
    o original ampliado é mantido (hexágono e capuz polar de Saturno).
    """
    src = pixels(image(fonte))[..., :3]
    H = src.shape[0]
    perfil = np.median(src, axis=1)
    # campos anisotrópicos: quase nada varia ao longo da longitude (m pequeno e inteiro, sem
    # emenda) e muito ao longo da latitude, como as faixas e estrias zonais dos planetas gasosos
    x = (np.arange(w, dtype='float32') + 0.5) / w
    y = (np.arange(h, dtype='float32') + 0.5) / h
    campo = np.zeros((h, w), 'float32')
    for _ in range(28):
        m = int(rng.integers(1, 12))
        n = rng.uniform(3, 40)
        campo += np.cos(2 * np.pi * (m * x[None, :] + n * y[:, None]) + rng.uniform(0, 6.3)) / m
    campo /= campo.std()
    fino = np.zeros((h, w), 'float32')
    for _ in range(70):
        m = int(rng.integers(0, 4))
        n = rng.uniform(60, h / 5)
        fino += np.cos(2 * np.pi * (m * x[None, :] + n * y[:, None]) + rng.uniform(0, 6.3))
    fino /= fino.std()
    lat = (np.arange(h) + 0.5) / h
    latp = np.clip(lat[:, None] + turbulencia * campo, 0, 1)
    idx = latp * H - 0.5
    i0 = np.clip(np.floor(idx).astype(int), 0, H - 1)
    i1 = np.clip(i0 + 1, 0, H - 1)
    f = (idx - i0)[..., None]
    cor = perfil[i0] * (1 - f) + perfil[i1] * f
    cor *= (1 + contraste * fino)[..., None]
    # mantém os polos do original (ampliado bilinearmente)
    graus = np.abs(90 - lat * 180)
    peso = np.clip((graus - polos) / 6, 0, 1)[:, None, None]
    if peso.max() > 0:
        yy = np.clip(lat * H - 0.5, 0, H - 1)
        xx = np.clip((np.arange(w) + 0.5) / w * src.shape[1] - 0.5, 0, src.shape[1] - 1)
        y0 = np.floor(yy).astype(int); y1 = np.minimum(y0 + 1, H - 1); fy = (yy - y0)[:, None, None]
        x0 = np.floor(xx).astype(int); x1 = np.minimum(x0 + 1, src.shape[1] - 1); fx = (xx - x0)[None, :, None]
        amp = (src[y0][:, x0] * (1 - fx) + src[y0][:, x1] * fx) * (1 - fy) + (src[y1][:, x0] * (1 - fx) + src[y1][:, x1] * fx) * fy
        cor = cor * (1 - peso) + amp * peso
    return image_from_array(nome, np.concatenate([np.clip(cor, 0, 1), np.ones((h, w, 1))], -1))


def aneis_alta(nome, rng, largura=4096):
    """Perfil radial dos anéis ampliado, com divisões finas (ilustrativas) somadas ao perfil observado."""
    src = pixels(image(MAPS / 'saturno-rings.png'))
    prof = src.mean(axis=0)
    u0 = (np.arange(prof.shape[0]) + 0.5) / prof.shape[0]
    u = (np.arange(largura) + 0.5) / largura
    p = np.stack([np.interp(u, u0, prof[:, c]) for c in range(4)], -1)
    ondas = sum(np.sin(2 * np.pi * (fq * u + rng.uniform())) / (1 + i * 0.4)
                for i, fq in enumerate(rng.uniform(180, 1400, 40)))
    ondas = ondas / np.abs(ondas).max()
    p[:, 3] = np.clip(p[:, 3] * (1 + 0.22 * ondas), 0, 1)
    p[:, :3] = np.clip(p[:, :3] * (1 + 0.06 * ondas[:, None]), 0, 1)
    return image_from_array(nome, np.repeat(p[None], 8, axis=0))


# ---------------------------------------------------------------- estações

def luz(cfg):
    terra = material('Terra', tex=image(OBS / 'earth-bmng-200407.jpg', 4096), rough=0.75)
    sphere('terra', 1.0, terra, seg=192, rings=96)
    lua = material('Lua', tex=image(MAPS / 'lua.jpg', 2048), normal=image(MAPS / 'lua-normal.png', 1024), rough=0.95)
    sphere('lua', 0.273, lua, seg=128, rings=64, loc=cfg['lua'])
    def extras():
        pulso = material('Pulso', emission=(1.0, 0.86, 0.55, 1), strength=18)
        sphere('pulso', 0.07, pulso, seg=24, rings=12, loc=(4.6, 0, 0))
        bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=3.6, location=b((2.8, 0, 0)), rotation=(0, math.pi / 2, 0))
        feixe = bpy.context.active_object
        feixe.data.materials.append(material('Feixe', emission=(1.0, 0.8, 0.5, 1), strength=6))
    return extras


PLANETAS = [
    # nome, arquivo, raio visual, semieixo maior (UA), ângulo inicial (graus)
    ('mercurio', 'mercurio.jpg', 0.2, 0.387, 40),
    ('venus', 'venus.jpg', 0.32, 0.723, 160),
    ('terra', 'terra.jpg', 0.34, 1.0, 250),
    ('marte', 'marte.jpg', 0.24, 1.524, 320),
    ('jupiter', 'jupiter.jpg', 0.95, 5.20, 20),
    ('saturno', 'saturno.jpg', 0.82, 9.58, 120),
    ('urano', 'urano.jpg', 0.55, 19.2, 215),
    ('netuno', 'netuno.jpg', 0.53, 30.1, 300),
]


def orbit_radius(a):
    """Escala visual comprimida (não proporcional); a página usa a mesma função."""
    return 2.6 + 3.2 * a ** 0.55


def sistema_solar(cfg, rng):
    g = granulation(rng, 2048, 1024)
    sol_rgb = ramp(0.5 + 0.5 * g, [(0, (0.78, 0.28, 0.04)), (0.55, (1.0, 0.62, 0.18)), (1, (1.0, 0.93, 0.68))])
    sol_img = image_from_array('sol', np.concatenate([sol_rgb, np.ones(g.shape + (1,))], -1))
    sol = sphere('sol', 1.6, material('Sol', emission_tex=sol_img, strength=6.0))
    sol.visible_shadow = False  # a luz pontual fica dentro da esfera do Sol
    anel = aneis_alta('aneis-sistema', rng, 2048)
    mapas = {
        'jupiter': lambda: image(OBS / 'jupiter-hubble-opal-2015.tif', 2048),
        'saturno': lambda: mapa_zonal('saturno-sistema', MAPS / 'saturno.jpg', 2048, 1024, rng),
        'urano': lambda: mapa_zonal('urano-sistema', MAPS / 'urano.jpg', 1024, 512, rng, 0.002, 0.03, 90),
        'netuno': lambda: mapa_zonal('netuno-sistema', MAPS / 'netuno.jpg', 1024, 512, rng, 0.004, 0.05, 90),
    }
    for nome, arq, r, a, ang in PLANETAS:
        R = orbit_radius(a)
        t = math.radians(ang)
        loc = (R * math.cos(t), 0, -R * math.sin(t))
        tex = mapas[nome]() if nome in mapas else image(MAPS / arq, 2048 if nome in ('terra', 'mercurio') else 1440)
        ob = sphere(nome, r, material(nome, tex=tex, rough=0.9),
                    seg=64, rings=32, polar=0.902 if nome == 'saturno' else 1.0, loc=loc)
        if nome == 'saturno':
            ring = annulus('saturno-aneis', r * 1.11, r * 2.32, material('Anéis', tex=anel, alpha_tex=True, rough=1.0), count=128)
            ring.location = ob.location
            ring.rotation_euler = (math.radians(26.7), 0, 0)
    def extras():
        luzes_sol()
        for nome, arq, r, a, ang in PLANETAS:
            R = orbit_radius(a)
            bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.009, major_segments=256, minor_segments=6)
            bpy.context.active_object.data.materials.append(material('Órbita', color=(0, 0, 0, 1), emission=(0.42, 0.56, 0.57, 1), strength=0.35))
        limbo(bpy.data.materials['Sol'])
    return extras


def luzes_sol():
    """Luz pontual no Sol com decaimento constante, para os planetas externos não sumirem."""
    lamp = bpy.data.lights.new('Sol', 'POINT')
    lamp.energy = 90000
    lamp.shadow_soft_size = 1.6
    link(bpy.data.objects.new('Sol', lamp))


def saturno(cfg):
    rng = np.random.default_rng(97)
    globo = material('Saturno', tex=mapa_zonal('saturno-4k', MAPS / 'saturno.jpg', 4096, 2048, rng, 0.003, 0.026), rough=0.92)
    sphere('saturno', 1.0, globo, seg=192, rings=96, polar=0.902)
    aneis = material('Anéis', tex=aneis_alta('aneis-4k', rng, 4096), alpha_tex=True, rough=1.0)
    annulus('aneis', 1.11, 2.32, aneis, count=512)
    def extras():
        incl = math.radians(cfg['inclinacao'])
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                ob.rotation_euler = (incl, 0, math.radians(-18))
    return extras


def estrelas(cfg, rng):
    g = granulation(rng, 4096, 2048)
    tons = 0.8 + 0.2 * (0.5 + 0.5 * g)
    img = image_from_array('estrela', np.concatenate([np.repeat(tons[..., None], 3, -1), np.ones(g.shape + (1,))], -1))
    sphere('estrela', 1.0, material('Estrela', emission_tex=img, strength=3.0), seg=128, rings=64)
    n = 2600
    d = rng.normal(size=(n, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    r = rng.uniform(45, 130, n)
    # distribuição de temperaturas dominada por estrelas frias, com poucas quentes
    T = np.exp(rng.normal(np.log(5200), 0.42, n)).clip(2600, 38000)
    brilho = (T / 5772) ** 1.6 * rng.uniform(0.25, 1.0, n)
    cor = kelvin_rgb(T) * np.clip(brilho, 0.15, 3.0)[:, None]
    points('campo', d * r[:, None], cor, 0.05 + 0.09 * np.clip(brilho, 0, 2))
    def extras():
        tingir(bpy.data.materials['Estrela'], kelvin_rgb(cfg['temperatura']))
        limbo(bpy.data.materials['Estrela'])
        point_material([bpy.data.objects['campo']], 2.2)
    return extras


def ceu_estrelado(rng, w=4096, h=2048, n=9000):
    """Céu de fundo em projeção equirretangular (linha 0 = polo +y): estrelas com cor de corpo negro
    e uma faixa difusa ao longo de um grande círculo, como a Via Láctea."""
    lon = (np.arange(w) + 0.5) / w * 2 * np.pi - np.pi
    lat = np.pi / 2 - (np.arange(h) + 0.5) / h * np.pi
    polo = np.array([0.35, 0.25, 0.9])
    polo /= np.linalg.norm(polo)

    def direcao(lo, la):
        # (x, y, z) com y para cima, igual ao traçado de raios
        return np.stack([np.cos(la) * np.cos(lo), np.sin(la), np.cos(la) * np.sin(lo)], -1)

    LO, LA = np.meshgrid(lon[::4], lat[::4])
    bgal = np.arcsin(np.clip(direcao(LO, LA) @ polo, -1, 1))
    nuvem = wave_field(sphere_dirs(w // 4, h // 4), rng.uniform(4, 40, 70), rng)
    faixa = np.exp(-(bgal / 0.2) ** 2) * np.clip(0.65 + 0.35 * nuvem, 0, None) * 0.05
    img = np.kron(faixa, np.ones((4, 4), 'float32'))[..., None] * np.array([0.78, 0.8, 0.88], 'float32')
    # estrelas, mais densas perto da faixa
    v = rng.normal(size=(n * 3, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    pb = np.arcsin(np.clip(v @ polo, -1, 1))
    v = v[rng.random(len(v)) < 0.3 + 0.7 * np.exp(-(pb / 0.35) ** 2)][:n]
    la = np.arcsin(np.clip(v[:, 1], -1, 1))
    lo = np.arctan2(v[:, 2], v[:, 0])
    px = (lo + np.pi) / (2 * np.pi) * w
    py = (np.pi / 2 - la) / np.pi * h
    T = np.exp(rng.normal(np.log(5600), 0.45, len(v))).clip(2800, 30000)
    brilho = np.clip(0.12 + rng.pareto(2.3, len(v)) * 0.25, 0, 2.5)
    cor = kelvin_rgb(T) * brilho[:, None]
    flat = img.reshape(-1, 3)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            xi = (np.floor(px).astype(int) + dx) % w
            yi = np.clip(np.floor(py).astype(int) + dy, 0, h - 1)
            ddx = xi + 0.5 - px
            ddx = (ddx + w / 2) % w - w / 2
            peso = np.exp(-(ddx ** 2 + (yi + 0.5 - py) ** 2) / (2 * (0.55 + 0.35 * brilho) ** 2))
            np.add.at(flat, yi * w + xi, cor * peso[:, None])
    return np.clip(img, 0, 1)


def disco_textura(rng):
    """Disco fino de Shakura e Sunyaev de r = 3 r_s (última órbita estável) a 12 r_s.
    Linhas = ângulo (2048), colunas = raio (1024)."""
    nr, na = 1024, 2048
    r = np.linspace(3.0, 12.0, nr)
    th = np.linspace(0, 2 * np.pi, na, endpoint=False)
    R, TH = np.meshgrid(r, th)
    perfil = R ** -3 * (1 - np.sqrt(3.0 / R))
    perfil /= perfil.max()
    # turbulência: ondas espirais de mesmo enrolamento (a rotação diferencial estica as
    # irregularidades em arcos); m inteiro mantém a textura contínua na volta completa
    soma = np.zeros_like(R)
    for _ in range(140):
        m = int(rng.integers(1, 64))
        k = rng.uniform(6, 48)
        soma += np.cos(m * TH + k * np.log(R) + rng.uniform(0, 6.3)) / (1 + 0.05 * m)
    estrias = 1 + 0.3 * soma / soma.std()
    I = np.clip(perfil ** 0.45 * estrias, 0, None)
    borda = np.clip((R - 3.0) / 0.2, 0, 1) * np.clip((12.0 - R) / 3.5, 0, 1)
    rn = (R - 3.0) / 9.0
    base = ramp(rn, [(0, (1.0, 0.94, 0.82)), (0.18, (1.0, 0.74, 0.38)), (0.5, (0.92, 0.42, 0.14)), (1, (0.5, 0.13, 0.05))])
    cor = base * (I * borda)[..., None]
    alpha = np.clip(I * borda * 1.4, 0, 1)
    return np.concatenate([np.clip(cor, 0, 1), alpha[..., None]], -1)


def tracar_buraco(cfg, disco, ceu, largura, altura, brilho=1.7, giro=0.0):
    """Traçado de raios na geometria de Schwarzschild (r_s = 1), o mesmo da página.

    Em coordenadas espaciais planas, a trajetória da luz obedece a x'' = -1,5 h² x / r⁵, com
    h = |x × v| conservado. O raio sai da câmera para trás; ao cruzar o plano do disco (y = 0)
    entre 3 e 12 r_s soma a emissão com o fator g = 1 / [u^t (1 - Ω L_y)], que reúne o desvio
    gravitacional e o Doppler da órbita kepleriana; a intensidade escala com g³.
    """
    cam = cfg['camera']
    pos = np.array(cam['pos'], 'float64')
    alvo = np.array(cam['alvo'], 'float64')
    f = alvo - pos
    f /= np.linalg.norm(f)
    direita = np.cross(f, [0, 1, 0])
    direita /= np.linalg.norm(direita)
    cima = np.cross(direita, f)
    th = math.tan(math.radians(cam['fov']) / 2)
    asp = largura / altura
    jj, ii = np.meshgrid(np.arange(largura), np.arange(altura))
    nx = (2 * (jj + 0.5) / largura - 1) * th * asp
    ny = (1 - 2 * (ii + 0.5) / altura) * th
    D = nx[..., None] * direita + ny[..., None] * cima + f
    D = (D / np.linalg.norm(D, axis=-1, keepdims=True)).reshape(-1, 3)
    saida = np.zeros((len(D), 3), 'float32')
    na, nr = disco.shape[:2]
    H, W = ceu.shape[:2]
    for c0 in range(0, len(D), 250000):
        v = D[c0:c0 + 250000].copy()
        n = len(v)
        x = np.repeat(pos[None], n, 0)
        h2 = np.sum(np.cross(x, v) ** 2, 1)
        Ly = np.cross(x, -v)[:, 1]
        cor = np.zeros((n, 3))
        a = np.zeros(n)
        vivo = np.ones(n, bool)
        caiu = np.zeros(n, bool)
        for _ in range(700):
            idx = np.nonzero(vivo)[0]
            if len(idx) == 0:
                break
            xs, vs = x[idx], v[idx]
            r = np.linalg.norm(xs, axis=1)
            dentro = r < 1.0
            fora = (r > 80) & (np.sum(xs * vs, 1) > 0)
            caiu[idx[dentro]] = True
            vivo[idx[dentro | fora]] = False
            ok = ~(dentro | fora)
            idx, xs, vs, r = idx[ok], xs[ok], vs[ok], r[ok]
            dt = np.clip(0.06 * r, 0.02, 3.0)[:, None]
            a0 = -1.5 * h2[idx, None] * xs / r[:, None] ** 5
            xn = xs + vs * dt + 0.5 * a0 * dt * dt
            rn = np.linalg.norm(xn, axis=1)
            a1 = -1.5 * h2[idx, None] * xn / rn[:, None] ** 5
            vs = vs + 0.5 * (a0 + a1) * dt
            cruza = xs[:, 1] * xn[:, 1] < 0
            if cruza.any():
                k = np.nonzero(cruza)[0]
                t = xs[k, 1] / (xs[k, 1] - xn[k, 1])
                p = xs[k] + (xn[k] - xs[k]) * t[:, None]
                rc = np.hypot(p[:, 0], p[:, 2])
                no = (rc > 3.0) & (rc < 12.0)
                k, p, rc = k[no], p[no], rc[no]
                if len(k):
                    fi = np.arctan2(-p[:, 2], p[:, 0])
                    om = np.sqrt(0.5 / rc ** 3)
                    ang = (fi - giro * om) % (2 * np.pi)
                    col = np.clip(((rc - 3.0) / 9.0 * (nr - 1)).astype(int), 0, nr - 1)
                    lin = np.clip((ang / (2 * np.pi) * na).astype(int), 0, na - 1)
                    tx = disco[lin, col]
                    ut = 1 / np.sqrt(1 - 1.5 / rc)
                    g = 1 / (ut * (1 - om * Ly[idx[k]]))
                    c = tx[:, :3] * (g ** 3)[:, None] * np.stack([g ** -0.5, np.ones_like(g), g ** 0.7], 1) * brilho
                    al = tx[:, 3]
                    gi = idx[k]
                    cor[gi] += ((1 - a[gi]) * al)[:, None] * c
                    a[gi] += (1 - a[gi]) * al
            x[idx] = xn
            v[idx] = vs
        # o que escapou mostra o céu na direção final, deformado pela lente
        esc = ~caiu & (a < 0.98)
        d = v[esc] / np.linalg.norm(v[esc], axis=1, keepdims=True)
        u = np.arctan2(d[:, 2], d[:, 0]) / (2 * np.pi) + 0.5
        w = np.arccos(np.clip(d[:, 1], -1, 1)) / np.pi
        ceu_c = ceu[np.clip((w * H).astype(int), 0, H - 1), np.clip((u * W).astype(int), 0, W - 1)]
        cor[esc] += (1 - a[esc])[:, None] * ceu_c
        saida[c0:c0 + n] = cor
    img = saida.reshape(altura, largura, 3)
    img = img + np.array(hex_rgb(FUNDO)) * 0.6
    img = img / (1 + img * 0.35)  # compressão suave dos realces
    return np.clip(img, 0, 1)


def buraco_negro(cfg, rng):
    """Na página o buraco negro é desenhado por traçado de raios; o GLB leva as texturas
    (disco e céu) e a geometria de referência, oculta na página."""
    sphere('horizonte', 1.0, material('Horizonte', color=(0, 0, 0, 1), rough=1.0), seg=64, rings=32)
    d = disco_textura(rng)
    img = image_from_array('disco', d)
    annulus('disco', 3.0, 12.0, material('Disco', emission_tex=img, strength=1.0, alpha_tex=True), count=128, radial=4)
    ceu = ceu_estrelado(rng)
    ceu_img = image_from_array('ceu', np.concatenate([ceu, np.ones(ceu.shape[:2] + (1,))], -1))
    sphere('ceu', 200.0, material('Céu', emission_tex=ceu_img, strength=1.0), seg=32, rings=16)

    def extras():
        for largura, altura, nome in ((2400, 1500, 'buraco-negro.webp'), (1200, 750, 'buraco-negro-1200.webp')):
            arr = tracar_buraco(cfg, d, ceu, largura, altura)
            im = bpy.data.images.new('poster', largura, altura, alpha=False)
            im.pixels.foreach_set(np.concatenate([arr[::-1], np.ones((altura, largura, 1))], -1).astype('float32').ravel())
            im.filepath_raw = str(OUT / nome)
            im.file_format = 'WEBP'
            im.save()
            print('traçado', nome)
        return 'pronto'
    return extras


def galaxia_pts(rng, n_disk, n_bar, n_bulge, n_hii, raio, escala=1.0):
    pitch = math.radians(16)
    r = rng.exponential(3.4, n_disk * 3)
    r = r[(r > 1.6) & (r < raio)][:n_disk]
    arm = rng.integers(0, 2, len(r))
    th_arm = np.log(r / 4.2) / math.tan(pitch) + arm * np.pi
    no_braco = rng.random(len(r)) < 0.74
    th = np.where(no_braco, th_arm + rng.normal(0, 0.2 + 0.02 * r, len(r)), rng.uniform(0, 2 * np.pi, len(r)))
    disco = np.stack([r * np.cos(th), rng.normal(0, 0.1 + 0.01 * r, len(r)), r * np.sin(th)], 1)
    Td = np.where(no_braco, rng.uniform(7000, 16000, len(r)), rng.uniform(4300, 6200, len(r)))
    bd = np.where(no_braco, 0.75, 0.38) * np.exp(-r / 14)
    xb = rng.normal(0, 1.7, n_bar * 2)
    xb = xb[np.abs(xb) < 4.3][:n_bar]
    barra = np.stack([xb, rng.normal(0, 0.18, len(xb)), rng.normal(0, 0.42, len(xb))], 1)
    bojo = rng.normal(0, 0.75, (n_bulge, 3)) * [1, 0.7, 1]
    rh = rng.uniform(3.2, raio * 0.8, n_hii)
    armh = rng.integers(0, 2, n_hii)
    thh = np.log(rh / 4.2) / math.tan(pitch) + armh * np.pi + rng.normal(0, 0.08, n_hii)
    hii = np.stack([rh * np.cos(thh), rng.normal(0, 0.06, n_hii), rh * np.sin(thh)], 1)
    pos = np.concatenate([disco, barra, bojo, hii]) * escala
    cor = np.concatenate([
        kelvin_rgb(Td) * bd[:, None],
        kelvin_rgb(rng.uniform(4000, 5200, len(xb))) * 0.75,
        kelvin_rgb(rng.uniform(3900, 4900, n_bulge)) * 1.1,
        np.tile([1.0, 0.36, 0.52], (n_hii, 1)) * 0.95,
    ])
    tam = np.concatenate([np.full(len(r), 0.032), np.full(len(xb), 0.036), np.full(n_bulge, 0.042), np.full(n_hii, 0.07)]) * escala
    return pos, cor, tam


def galaxias(cfg, rng):
    pos, cor, tam = galaxia_pts(rng, 26000, 5500, 4500, 900, 15.0)
    g = points('galaxia', pos, cor, tam)
    def extras():
        point_material([g], 2.0)
        bpy.ops.mesh.primitive_torus_add(major_radius=cfg['raio'], minor_radius=0.035, major_segments=256, minor_segments=6)
        bpy.context.active_object.data.materials.append(material('Raio', emission=(0.62, 0.86, 0.86, 1), strength=2))
    return extras


def teia(cfg, rng):
    """Teia cósmica pela aproximação de Zel'dovich truncada.

    Um campo gaussiano de densidade com o espectro da matéria escura fria (P ∝ k^0,965 T²,
    transferência de BBKS com Γ = 0,21 e h = 0,7) dá o deslocamento ψ = ∇∇⁻²δ; as partículas
    andam ψ a partir de uma grade de 128³ numa caixa de 160 Mpc. Filamentos, paredes, aglomerados
    e vazios surgem do próprio campo, como nas condições iniciais de simulações de N corpos.
    """
    N, L = 128, 160.0
    kf = 2 * np.pi * np.fft.fftfreq(N, d=L / N)
    kz = 2 * np.pi * np.fft.rfftfreq(N, d=L / N)
    KX, KY, KZ = np.meshgrid(kf, kf, kz, indexing='ij')
    K2 = KX ** 2 + KY ** 2 + KZ ** 2
    K = np.sqrt(K2)
    K2[0, 0, 0] = 1.0
    q = K / (0.21 * 0.7) + 1e-9
    T = np.log(1 + 2.34 * q) / (2.34 * q) * (1 + 3.89 * q + (16.1 * q) ** 2 + (5.46 * q) ** 3 + (6.71 * q) ** 4) ** -0.25
    P = K ** 0.965 * T ** 2 * np.exp(-(K * 1.6) ** 2)  # truncamento gaussiano em 1,6 Mpc
    dk = np.fft.rfftn(rng.normal(size=(N, N, N)).astype('float32')) * np.sqrt(P)
    dk[0, 0, 0] = 0
    psi = [np.fft.irfftn(1j * Ki / K2 * dk, s=(N, N, N)).astype('float32') for Ki in (KX, KY, KZ)]
    rms = np.sqrt(np.mean(psi[0] ** 2 + psi[1] ** 2 + psi[2] ** 2))
    escala = 5.2 / rms  # deslocamento quadrático médio de 5,2 Mpc: estrutura bem desenvolvida
    g = (np.arange(N, dtype='float32') + 0.5) * L / N - L / 2
    QX, QY, QZ = np.meshgrid(g, g, g, indexing='ij')
    pos = np.stack([QX + escala * psi[0], QY + escala * psi[1], QZ + escala * psi[2]], -1).reshape(-1, 3)
    pos = (pos + L / 2) % L - L / 2
    # densidade por célula, suavizada, lida de volta em cada partícula
    ijk = np.clip(((pos + L / 2) / L * N).astype(int), 0, N - 1)
    lin = (ijk[:, 0] * N + ijk[:, 1]) * N + ijk[:, 2]
    rho = np.bincount(lin, minlength=N ** 3).reshape(N, N, N).astype('float32')
    rho = np.fft.irfftn(np.fft.rfftn(rho) * np.exp(-0.5 * K2 * 1.25 ** 2), s=(N, N, N))
    rho = np.clip(rho / rho.mean(), 1e-3, None).ravel()[lin]
    # amostra favorece as regiões densas; os vazios ficam quase vazios, como nos mapas de galáxias
    dentro = np.linalg.norm(pos, axis=1) < 62
    pos, rho = pos[dentro], rho[dentro]
    peso = rho ** 1.5
    prob = peso * (70000 / peso.sum())
    sel = rng.random(len(pos)) < prob
    pos, rho = pos[sel], rho[sel]
    t = np.clip((np.log10(rho) - 0.1) / 1.9, 0, 1)
    cor = ramp(t, [(0, (0.28, 0.38, 0.68)), (0.35, (0.5, 0.66, 1.0)), (0.7, (0.98, 0.82, 0.58)), (1, (1.0, 0.95, 0.86))])
    cor *= (0.12 + 1.0 * t ** 1.2)[:, None]
    o = points('teia', pos, cor, 0.055 + 0.1 * t)
    print('teia: %d pontos (Zel\'dovich, %d³, %.0f Mpc)' % (len(pos), N, L))
    return lambda: point_material([o], 1.5)


def expansao(cfg, rng):
    pos, cor, tam = galaxia_pts(rng, 1600, 260, 240, 60, 15.0, escala=0.24)
    g = points('galaxia', pos, cor, tam * 2.2)
    def extras():
        point_material([g], 3.0)
        lado, passo = cfg['lado'], cfg['passo']
        meio = (lado - 1) / 2
        for i in range(lado):
            for j in range(lado):
                for k in range(lado):
                    if (i, j, k) == (0, 0, 0):
                        g.location = b(((i - meio) * passo, (j - meio) * passo, (k - meio) * passo))
                        continue
                    c = g.copy()
                    c.location = b(((i - meio) * passo, (j - meio) * passo, (k - meio) * passo))
                    c.rotation_euler = tuple(rng.uniform(0, 6.28, 3))
                    link(c)
    return extras


def luz_fossil(cfg, rng):
    w, h = 3072, 1536
    ell = np.arange(2, 1600)
    D = (1000 + 4700 * np.exp(-((ell - 220) / 85) ** 2) + 1900 * np.exp(-((ell - 540) / 95) ** 2)
         + 2000 * np.exp(-((ell - 810) / 95) ** 2)) * np.exp(-(ell / 1300) ** 2)
    pdf = D / ell
    pdf /= pdf.sum()
    ells = rng.choice(ell, size=4200, p=pdf).astype('float64') + rng.uniform(-0.5, 0.5, 4200)
    f = wave_field(sphere_dirs(w, h), ells, rng, chunk=8)
    x = np.clip(f / 2.6, -1, 1)
    cor = ramp(x, [(-1, (0.02, 0.05, 0.32)), (-0.5, (0.12, 0.42, 0.92)), (0, (0.94, 0.94, 0.9)),
                   (0.5, (1.0, 0.62, 0.16)), (1, (0.55, 0.12, 0.04))])
    img = image_from_array('cmb', np.concatenate([cor, np.ones((h, w, 1))], -1))
    sphere('cmb', 10.0, material('Radiação cósmica de fundo', emission_tex=img, strength=1.6), seg=192, rings=96)
    return lambda: None


ESTACOES = {
    'luz': lambda c, r: luz(c),
    'sistema-solar': sistema_solar,
    'saturno': lambda c, r: saturno(c),
    'estrelas': estrelas,
    'buraco-negro': buraco_negro,
    'galaxias': galaxias,
    'teia-cosmica': teia,
    'expansao': expansao,
    'luz-fossil': luz_fossil,
}


# ------------------------------------------------------- exportação e render

def export(estacao):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f'{estacao}.glb'
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', export_yup=True, export_apply=True,
        export_image_format='WEBP', export_image_quality=92, export_pointclouds=True,
        export_vertex_color='NAME', export_vertex_color_name='Col', export_attributes=True,
        export_cameras=False, export_lights=False, use_selection=False)
    return path


def render(estacao, cfg, largura=2400, altura=1500, amostras=56):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = amostras
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 3
    sc.render.resolution_x = largura
    sc.render.resolution_y = altura
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'WEBP'
    sc.render.image_settings.quality = 86
    sc.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('fundo')
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (*srgb_to_linear(hex_rgb(FUNDO)), 1)
    bg.inputs['Strength'].default_value = 1.0
    sc.world = world
    if 'sol' in cfg:
        lamp = bpy.data.lights.new('Sol', 'SUN')
        lamp.energy = 4.0
        ob = link(bpy.data.objects.new('Sol', lamp))
        ob.rotation_euler = b(cfg['sol']).to_track_quat('Z', 'Y').to_euler()
    cam_cfg = cfg['camera']
    cam = bpy.data.cameras.new('camera')
    cam.sensor_fit = 'VERTICAL'
    cam.angle_y = math.radians(cam_cfg['fov'])
    cam.clip_end = 2000
    ob = link(bpy.data.objects.new('camera', cam))
    ob.location = b(cam_cfg['pos'])
    ob.rotation_euler = (b(cam_cfg['alvo']) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = ob
    sc.render.filepath = str(OUT / f'{estacao}.webp')
    bpy.ops.render.render(write_still=True)
    # cópia de 1200 px para telas pequenas
    img = bpy.data.images.load(sc.render.filepath)
    img.scale(1200, 750)
    img.filepath_raw = str(OUT / f'{estacao}-1200.webp')
    img.file_format = 'WEBP'
    try:
        img.save(quality=88)
    except TypeError:
        img.save()
    return Path(sc.render.filepath)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    poster = '--sem-poster' not in argv
    alvo = [a for a in argv if not a.startswith('--')] or list(ESTACOES)
    manifest_path = OUT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'estacoes': {}}
    manifest['blender'] = bpy.app.version_string
    for i, est in enumerate(ESTACOES):
        if est not in alvo:
            continue
        reset()
        cfg = CENAS['estacoes'][est]
        rng = np.random.default_rng(20261126 + i)
        extras = ESTACOES[est](cfg, rng)
        glb = export(est)
        item = {'glb': glb.name, 'bytes': glb.stat().st_size, 'sha256': sha(glb)}
        if poster:
            feito = extras()
            png = OUT / f'{est}.webp' if feito == 'pronto' else render(est, cfg)
            item['poster'] = png.name
            item['poster_sha256'] = sha(png)
        manifest['estacoes'][est] = item
        print('VIAGEM', est, item)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


main()
