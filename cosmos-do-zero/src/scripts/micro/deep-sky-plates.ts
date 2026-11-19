import type { StagePaint } from '../stage-surface';
import { expansionPositions, projectExpansion, separation } from '../../lib/expansion';
import { rng } from './draw';

type Surface = StagePaint;
type Painter = (s: Surface, value: number, phase: number) => void;
type Point = readonly [number, number];
const tau = 2 * Math.PI;
const gold = '#ffcf88';
const ice = '#a6e2ff';
const muted = '#a1b7c8';
const galaxy = '/models/galaxies-v4/512/';
const turntable = '/models/solar-turntable/';
const reel = '/renders/reel-cycles/';
const clamp = (v: number, max = 1) => Math.max(0, Math.min(max, v));
const choice = (v: number, max: number) => Math.round(clamp(v, max));
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const fmt = (n: number, digits = 2) => n.toFixed(digits).replace('.', ',');

function line(s: Surface, a: Point, b: Point, color: string, width = 1) {
  const c = s.ctx;
  c.beginPath();
  c.moveTo(...a);
  c.lineTo(...b);
  c.strokeStyle = color;
  c.lineWidth = width;
  c.stroke();
}
function dot(s: Surface, x: number, y: number, r: number, color: string) {
  const c = s.ctx;
  c.fillStyle = color;
  c.beginPath();
  c.arc(x, y, r, 0, tau);
  c.fill();
}
function ring(s: Surface, x: number, y: number, rx: number, ry: number, color: string) {
  const c = s.ctx;
  c.beginPath();
  c.ellipse(x, y, rx, ry, 0, 0, tau);
  c.strokeStyle = color;
  c.lineWidth = 1.4;
  c.stroke();
}
function band(s: Surface, title: string, detail: string) {
  s.ctx.fillStyle = '#081422ee';
  s.ctx.fillRect(0, 293, 640, 67);
  s.label(title, 22, 319, { size: 19, color: '#fff0d9' });
  s.label(detail, 22, 344, { size: 15, color: '#c8dbe7' });
}
function earlySky(s: Surface, opacity: number) {
  // Before the first stars, use a diffuse illustration without the stage's star field.
  s.ctx.fillStyle = '#090e18';
  s.ctx.fillRect(0, 0, 640, 360);
  s.sprite('/renders/ancient-light-small.webp', 320, 145, 640, 427, opacity);
}
function globe(s: Surface, name: string, x: number, y: number, w: number, frame = 0) {
  s.sprite(turntable + name + '/' + String(frame % 36).padStart(2, '0') + '.webp', x, y, w, w);
}
function sun(s: Surface, x: number, y: number, size: number) {
  const c = s.ctx;
  c.save();
  c.beginPath();
  c.arc(x, y, size * 0.48, 0, tau);
  c.clip();
  c.globalCompositeOperation = 'screen';
  s.sprite('/renders/star-small.webp', x, y, size * 1.5, size);
  c.restore();
}
function disc(s: Surface, texture: string, x: number, y: number, w: number, h: number, angle = 0) {
  const c = s.ctx;
  c.save();
  c.translate(x, y);
  c.scale(1, h / w);
  c.rotate(angle);
  c.globalCompositeOperation = 'screen';
  s.sprite(galaxy + texture + '.webp', 0, 0, w, w);
  c.restore();
}
function orbit(s: Surface, x: number, y: number, r: number, a: number): Point {
  ring(s, x, y, r, 0.36 * r, '#9db3c26b');
  return [x + r * Math.cos(a), y + 0.36 * r * Math.sin(a)];
}

const sizes = ['Terra', 'Sistema Solar', 'Via Láctea', 'Grupo Local', 'Teia cósmica'];
const distances = [
  'Diâmetro ≈ 12.700 km',
  'Sol a Netuno ≈ 4,5 bilhões de km',
  'Diâmetro do disco ≈ 100 mil anos-luz',
  'Extensão ≈ 10 milhões de anos-luz',
  'Filamentos se estendem por milhões de anos-luz',
];
const worlds = ['mercurio', 'venus', 'terra', 'marte', 'jupiter', 'saturno', 'urano', 'netuno'];
function address(s: Surface, v: number, t: number) {
  const k = choice(v, 4);
  if (k === 0) {
    globe(s, 'terra', 320, 142, 278, Math.round(t * 12));
    // The rendered terrestrial limb spans 266 of the 320 atlas pixels.
    const halfDiameter = (278 * 266) / 640;
    line(s, [320 - halfDiameter, 271], [320 + halfDiameter, 271], ice);
    for (const x of [320 - halfDiameter, 320 + halfDiameter]) line(s, [x, 266], [x, 276], ice);
  } else if (k === 1) {
    const bodies = worlds.map((name, i) => {
      const [x, y] = orbit(s, 320, 147, 34 + i * 33, i * 2.4 + t * (1.8 - i * 0.19));
      return { name, x, y, size: [12, 17, 19, 14, 46, 49, 26, 25][i] };
    });
    bodies.sort((a, b) => a.y - b.y);
    for (const body of bodies.filter((b) => b.y < 147)) globe(s, body.name, body.x, body.y, body.size);
    sun(s, 320, 147, 65);
    for (const body of bodies.filter((b) => b.y >= 147)) globe(s, body.name, body.x, body.y, body.size);
  } else if (k === 2) {
    const a = 0.5 + t * 0.18;
    disc(s, 'barred-spiral', 320, 145, 475, 266, a);
    const x = 320 + 105 * Math.cos(a),
      y = 145 + 60 * Math.sin(a);
    ring(s, x, y, 6, 6, gold);
    line(s, [x + 6, y], [x + 37, y - 25], gold);
    s.label('Sol', x + 40, y - 25, { size: 16, color: gold });
  } else if (k === 3) {
    disc(s, 'grand-spiral', 408 + 6 * t, 112, 169, 69, -0.6);
    disc(s, 'barred-spiral', 209 - 4 * t, 185, 150, 81, 0.7);
    for (let i = 0; i < 13; i++)
      disc(s, 'irregular', 110 + i * 33, 134 + 81 * Math.sin(i * 3.7 + t * 0.12), 19, 10, i);
    s.label('Via Láctea', 155, 249, { size: 15 });
    s.label('Andrômeda', 390, 72, { size: 15 });
  } else {
    s.sprite(reel + 'cosmic-web.webp', 320, 142, 445 + 22 * t, 345 + 17 * t);
    s.label('Distribuição ilustrativa', 24, 40, { size: 15, color: ice });
  }
  band(
    s,
    sizes[k] + ' · ' + distances[k],
    k === 2
      ? 'Sistema Solar a ≈ 26 mil anos-luz do centro.'
      : 'Escalas de tamanho e de distância mudam entre as vistas.',
  );
}

function morphology(s: Surface, v: number, t: number) {
  const k = choice(v, 3),
    a = 0.35 + t * 0.22;
  if (k === 2) {
    s.ctx.setLineDash([5, 5]);
    for (const ry of [45, 104]) ring(s, 320, 144, 236, ry, '#8ce4f5aa');
    ring(s, 320, 144, 83, 119, '#8ce4f57a');
    s.ctx.setLineDash([]);
  }
  disc(
    s,
    k === 3 ? 'elliptical' : k === 0 ? 'stars-only' : 'grand-spiral',
    320,
    143,
    k === 3 ? 312 : 438,
    k === 3 ? 223 : 210,
    a,
  );
  if (k === 2) s.label('Contorno do halo inferido', 28, 33, { size: 16, color: ice });
  band(
    s,
    ['Disco estelar', 'Gás e poeira no disco', 'Massa inferida pela rotação', 'Galáxia elíptica'][k],
    [
      'Textura de densidade estelar ilustrativa.',
      'As faixas escuras acompanham os braços.',
      'O contorno marca a interpretação gravitacional.',
      'Família de estrelas com distribuição esferoidal.',
    ][k],
  );
}

const nodes: Point[] = [
  [82, 80],
  [195, 51],
  [325, 104],
  [501, 55],
  [87, 236],
  [230, 176],
  [409, 225],
  [570, 172],
  [297, 268],
];
const edges = [
  [0, 1],
  [0, 4],
  [1, 2],
  [2, 3],
  [2, 5],
  [3, 7],
  [4, 5],
  [5, 6],
  [6, 7],
  [5, 8],
  [2, 6],
];
const random = rng(38521);
const dust = Array.from({ length: 390 }, (_, i) => {
  const [a, b] = edges[i % edges.length],
    f = random(),
    depth = random();
  return {
    x: 24 + 592 * random(),
    y: 22 + 253 * random(),
    depth,
    endX: mix(nodes[a][0], nodes[b][0], f) + (random() - 0.5) * 17,
    endY: mix(nodes[a][1], nodes[b][1], f) + (random() - 0.5) * 13,
  };
}).sort((a, b) => a.depth - b.depth);
function web(s: Surface, v: number, t: number) {
  const growth = clamp(v),
    f = 1 - (1 - growth) ** 2;
  earlySky(s, 0.07 * (1 - growth));
  for (const p of dust) {
    const x = mix(p.x, p.endX, f) + (t - 0.5) * (p.depth - 0.5) * 9;
    dot(s, x, mix(p.y, p.endY, f), 0.65 + 1.45 * p.depth, p.depth > 0.55 ? '#ffddb4' : '#89a6bc');
  }
  for (const [x, y] of nodes) if (growth > 0.1) disc(s, 'elliptical', x, y, 3 + growth * 23, 2 + growth * 12);
  if (growth > 0.85) {
    s.label('Nó', 410, 253, { size: 15, color: gold });
    s.label('Vazio', 405, 116, { size: 15, color: ice });
  }
  band(
    s,
    'Formação da teia · ' + Math.round(growth * 100) + '% do percurso',
    'Partículas do modelo convergem para filamentos e nós.',
  );
}

// Feather the observed texture once. Each mechanism uses the same dust distribution.
const cloudTextures = new WeakMap<HTMLImageElement, Map<number, HTMLCanvasElement>>();
function cloudTexture(s: Surface, mode: number) {
  const image = s.image('/models/stellar/orion-detail.webp');
  if (!image) return null;
  const modes = cloudTextures.get(image) ?? new Map<number, HTMLCanvasElement>();
  let texture = modes.get(mode);
  if (texture) return texture;
  texture = document.createElement('canvas');
  texture.width = 368;
  texture.height = 256;
  const c = texture.getContext('2d');
  if (!c) return null;
  c.filter = ['saturate(1.15)', 'saturate(0.7) hue-rotate(325deg)', 'brightness(0.14) saturate(0.6)'][mode];
  c.drawImage(image, 0, 0, 368, 256);
  c.filter = 'none';
  c.scale(184, 128);
  const mask = c.createRadialGradient(1, 1, 0.33, 1, 1, 1);
  mask.addColorStop(0, '#fff');
  mask.addColorStop(0.73, '#ffffffbe');
  mask.addColorStop(1, '#ffffff00');
  c.globalCompositeOperation = 'destination-in';
  c.fillStyle = mask;
  c.fillRect(0, 0, 2, 2);
  modes.set(mode, texture);
  cloudTextures.set(image, modes);
  return texture;
}
function nebula(s: Surface, v: number, t: number) {
  const k = choice(v, 2),
    c = s.ctx;
  const source: Point = k === 0 ? [270, 148] : [103, 193];
  const cloud: Point = [291, 137],
    eye: Point = [549, 173];
  const path: Point[] = [source, cloud, eye];
  if (k === 2)
    for (let i = 0; i < 55; i++)
      dot(s, 155 + ((i * 89) % 258), 51 + ((i * 43) % 182), 1 + (i % 3) * 0.4, '#d1dfef');
  if (k !== 2) sun(s, ...source, 65);
  const texture = cloudTexture(s, k);
  if (texture) {
    c.save();
    c.translate(...cloud);
    c.rotate(-0.17);
    for (let depth = 0; depth < 2; depth++) {
      c.globalAlpha = depth === 0 ? 0.65 : 0.85;
      c.drawImage(
        texture,
        -155 + depth * 12 + (t - 0.5) * depth * 9,
        -96 + depth * 8,
        310 - depth * 15,
        192 - depth * 10,
      );
    }
    c.restore();
  }
  if (k === 0) sun(s, ...source, 43);
  if (k === 2) path[0] = [111, 201];
  line(s, path[0], cloud, '#ffcb8c88');
  if (k !== 2) line(s, cloud, eye, k === 1 ? '#aacfff88' : '#ff9d9088');
  if (k !== 2 || t <= 0.5) {
    const i = t < 0.5 ? 0 : 1,
      f = i === 0 ? t * 2 : t * 2 - 1;
    dot(
      s,
      mix(path[i][0], path[i + 1][0], f),
      mix(path[i][1], path[i + 1][1], f),
      5,
      i === 0 ? gold : k === 0 ? '#ff917d' : ice,
    );
  }
  ring(s, ...eye, 9, 5, ice);
  s.label('Observador', 508, 201, { size: 15 });
  band(
    s,
    ['Emissão · gás excitado', 'Reflexão · poeira iluminada', 'Absorção · poeira em primeiro plano'][k],
    'Textura de Órion (Hubble) · cores, profundidade e trajetórias ilustrativas.',
  );
}

function lightTravel(s: Surface, v: number, t: number) {
  const k = choice(v, 2);
  if (k === 0) globe(s, 'lua', 92, 150, 105);
  else sun(s, 92, 150, k === 1 ? 102 : 58);
  globe(s, 'terra', 548, 150, 101);
  line(s, [138, 150], [504, 150], '#a2bcce99');
  for (let i = 0; i <= 4; i++) line(s, [138 + i * 91.5, 146], [138 + i * 91.5, 155], muted);
  const x = mix(138, 504, t);
  ring(s, x, 150, 4, 11, '#ffe8ba');
  dot(s, x, 150, 4, gold);
  const elapsed = [1.3, 500, 4.2][k] * t;
  s.label(fmt(elapsed, k === 1 ? 0 : 1) + (k === 2 ? ' anos' : ' s'), x, 113, {
    size: 16,
    align: 'center',
    color: gold,
  });
  s.label(['Lua', 'Sol', 'Proxima Centauri'][k], 92, 220, { size: 16, align: 'center' });
  s.label('Terra', 548, 220, { size: 16, align: 'center' });
  band(
    s,
    'Viagem da luz · ' + ['1,3 segundo', '8 minutos e 20 segundos', '4,2 anos'][k],
    'O relógio indica o tempo físico. A animação comprime o percurso.',
  );
}

const observers: Point[] = [
  [245, 158],
  [414, 176],
  [287, 92],
];
function horizon(s: Surface, v: number, t: number) {
  const k = choice(v, 2),
    to = observers[k],
    from = observers[(k + 2) % 3],
    radius = 105;
  const ease = t * t * (3 - 2 * t),
    x = mix(from[0], to[0], ease),
    y = mix(from[1], to[1], ease);
  for (let i = 0; i < 52; i++) {
    const p = dust[i * 7],
      inside = Math.hypot(p.x - x, p.y - y) <= radius;
    s.ctx.save();
    s.ctx.globalAlpha = inside ? 0.98 : 0.41;
    disc(s, i % 3 ? 'elliptical' : 'grand-spiral', p.x, p.y, 16 + p.depth * 21, 10 + p.depth * 10, i);
    s.ctx.restore();
  }
  ring(s, x, y, radius, radius, '#9bd6eeaa');
  const a = 0.4 + t * 0.7;
  line(s, [x, y], [x + radius * Math.cos(a), y + radius * Math.sin(a)], '#96d4ef77');
  dot(s, x, y, 5, gold);
  s.label('Observador', x + 11, y - 8, { size: 15, color: gold });
  band(
    s,
    'Horizonte de ' + ['quem está aqui', 'uma galáxia à direita', 'uma galáxia acima'][k],
    'O círculo delimita o alcance da luz nesta fatia ilustrativa.',
  );
}

function expansion(s: Surface, v: number, t: number) {
  const scale = Math.max(1, clamp(v, 2)),
    pos = expansionPositions.map((_, i) => {
      const [x, y] = projectExpansion(i, 0, scale);
      return [x, y - 56] as Point;
    });
  for (const i of [1, 2]) line(s, pos[0], pos[i], '#fcce8aab');
  for (const i of expansionOrder) {
    const [x, y] = pos[i];
    disc(s, i % 2 ? 'grand-spiral' : 'elliptical', x, y, 38, 22, i * 0.8 + t * 0.08);
    if (i < 3) s.label(['A', 'B', 'C'][i], x + 11, y - 6, { size: 15, color: gold });
  }
  const c = s.ctx;
  c.fillStyle = '#101b2ded';
  c.fillRect(451, 9, 180, 79);
  const [x, y] = orbit(s, 487, 43, 20, t * tau);
  sun(s, 487, 43, 17);
  globe(s, 'terra', x, y, 13);
  s.label('Órbita ligada', 515, 37, { size: 14 });
  s.label('raio fixo', 515, 59, { size: 14, color: ice });
  band(
    s,
    'Expansão · fator ' + fmt(scale),
    'Distâncias 3D em unidades do catálogo: AB = ' +
      fmt(separation(1, 0) * scale) +
      '   AC = ' +
      fmt(separation(2, 0) * scale),
  );
}
const expansionOrder = expansionPositions
  .map((_, i) => i)
  .sort((a, b) => expansionPositions[a][2] - expansionPositions[b][2]);

function wave(s: Surface, x: number, y: number, w: number, period: number, t: number, color: string) {
  const c = s.ctx;
  c.beginPath();
  for (let i = 0; i <= w; i += 2) {
    const h = y + 11 * Math.sin(tau * (i / period - t));
    if (i === 0) c.moveTo(x, h);
    else c.lineTo(x + i, h);
  }
  c.lineWidth = 2.4;
  c.strokeStyle = color;
  c.stroke();
}
function redshift(s: Surface, v: number, t: number) {
  const factor = Math.max(1, clamp(v, 3)),
    c = s.ctx;
  disc(s, 'grand-spiral', 75, 101, 126, 77, 0.7);
  globe(s, 'terra', 559, 168, 94);
  s.label('Emitida', 148, 48, { size: 16, color: ice });
  wave(s, 148, 70, 343, 32, t, ice);
  s.label('Recebida', 148, 117, { size: 16, color: gold });
  wave(s, 148, 139, 343, 32 * factor, t, gold);
  const nm = (w: number) => 31 + ((w - 380) / (2000 - 380)) * 576;
  const spectrum = c.createLinearGradient(nm(380), 0, nm(750), 0);
  ['#8557be', '#4287df', '#42b093', '#e5bb57', '#ab4938'].forEach((col, i) =>
    spectrum.addColorStop(i / 4, col),
  );
  c.fillStyle = spectrum;
  c.fillRect(31, 224, nm(750) - 31, 21);
  c.fillStyle = '#4d4657';
  c.fillRect(nm(750), 224, 607 - nm(750), 21);
  for (const n of [434, 486, 656]) {
    line(s, [nm(n), 216], [nm(n), 224], ice, 2);
    line(s, [nm(n * factor), 224], [nm(n * factor), 245], '#0a1018', 3);
  }
  s.label('Linhas de referência', 30, 202, { size: 14, color: ice });
  for (const n of [380, 750, 1200, 1600, 2000]) {
    line(s, [nm(n), 246], [nm(n), 252], muted);
    s.label(String(n), nm(n), 271, { size: 14, align: 'center' });
  }
  band(
    s,
    'Desvio para o vermelho · z = ' + fmt(factor - 1),
    'Régua em nm · linha de 656 nm recebida em ' + fmt(656 * factor, 1) + ' nm.',
  );
}

function bead(s: Surface, x: number, y: number, r: number, color: string) {
  const g = s.ctx.createRadialGradient(x - r * 0.28, y - r * 0.38, 0.1, x, y, r);
  g.addColorStop(0, '#fff4dd');
  g.addColorStop(0.38, color);
  g.addColorStop(1, '#151827');
  s.ctx.fillStyle = g;
  s.ctx.beginPath();
  s.ctx.arc(x, y, r, 0, tau);
  s.ctx.fill();
}
function nuclei(s: Surface, v: number, t: number) {
  const k = choice(v, 3),
    binding = k === 0 ? 0 : k === 1 ? t : 1;
  earlySky(s, 0.23 - k * 0.035);
  // 24 H nuclei + 2 He-4 nuclei after assembly: helium accounts for 8/32 of the mass.
  for (let i = 0; i < 32; i++) {
    const p = dust[(i * 11) % dust.length],
      bound = i < 8;
    const group = i < 4 ? 0 : 1,
      cx = group ? 398 : 209,
      cy = group ? 160 : 99;
    const offset = (i % 2 ? 1 : -1) * 4;
    let x = 60 + (p.x - 24) * 0.87 + 6 * Math.sin(i + t * 6),
      y = 40 + (p.y - 22) * 0.81 + 4 * Math.cos(i + t * 7);
    if (bound) {
      x = mix(x, cx + offset, binding);
      y = mix(y, cy + (i % 4 < 2 ? -4 : 4), binding);
    }
    if (k === 3 && !bound) {
      ring(s, x, y, 10, 7, '#89c9ff99');
      dot(s, x + 10 * Math.cos(i + t * tau), y + 7 * Math.sin(i + t * tau), 1.8, ice);
    }
    bead(s, x, y, 4.3 + p.depth * 2, bound && i % 4 >= 2 ? '#adbad0' : '#f48765');
  }
  for (let i = 0; i < 28; i++) {
    if (k === 3 && i >= 4) break;
    if (k === 3) {
      const cx = i < 2 ? 209 : 398,
        cy = i < 2 ? 99 : 160,
        a = t * tau + i * Math.PI;
      ring(s, cx, cy, 17, 11, '#89c9ff77');
      dot(s, cx + 17 * Math.cos(a), cy + 11 * Math.sin(a), 2, ice);
    } else {
      const p = dust[5 * i];
      dot(s, 24 + ((p.x + t * 85) % 588), 24 + ((p.y + i + t * 28) % 246), 2, ice);
    }
  }
  s.label('Próton', 28, 28, { size: 15, color: '#ffab8d' });
  s.label('Nêutron', 104, 28, { size: 15, color: '#c7d3df' });
  s.label('Elétron', 196, 28, { size: 15, color: ice });
  band(
    s,
    [
      '1 segundo · partículas livres',
      '3 minutos · montagem de núcleos',
      '20 minutos · núcleos leves',
      '380 mil anos · átomos neutros',
    ][k],
    [
      'Temperatura aproximada: 10 bilhões °C',
      'Temperatura aproximada: 1 bilhão °C',
      'Mistura ilustrada por massa: 75% hidrogênio e 25% hélio.',
      'Temperatura aproximada: 2.700 °C. Elétrons ligados aos núcleos.',
    ][k],
  );
}

const scatterPath: Point[] = [
  [44, 156],
  [118, 81],
  [163, 202],
  [228, 117],
  [276, 214],
  [340, 72],
  [403, 164],
  [458, 102],
  [522, 190],
  [592, 129],
];
function structures(s: Surface, v: number, t: number) {
  const g = clamp(v),
    epoch = g < 0.15 ? 0 : g < 0.45 ? 1 : g < 0.75 ? 2 : 3;
  earlySky(s, 0.23 * (1 - g));
  for (const [index, [x, y]] of nodes.entries()) {
    const size = 68 - 45 * g,
      cx = x + 6 * Math.sin(index),
      cy = 38 + y * 0.7;
    for (let i = 0; i < 25; i++) {
      const p = dust[index * 25 + i];
      const drift = (t - 0.5) * (1 - g) * 8;
      dot(
        s,
        cx + (p.x / 620 - 0.5) * size + drift * (p.depth - 0.5),
        cy + (p.y / 270 - 0.5) * size * 0.7,
        1 + p.depth,
        g < 0.45 ? '#9099a8' : '#c8b7a9',
      );
    }
    if (g > 0.45) {
      const lit = clamp((g - 0.45) / 0.35),
        bubble = clamp((g - 0.55) / 0.45);
      if (bubble > 0) {
        const r = (42 + (index % 4) * 15) * bubble;
        const shell = s.ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        shell.addColorStop(0, '#65bef00e');
        shell.addColorStop(0.88, '#74c5f12a');
        shell.addColorStop(1, '#6096c100');
        s.ctx.fillStyle = shell;
        s.ctx.fillRect(cx - r, cy - r, 2 * r, 2 * r);
      }
      sun(s, cx, cy, 6 + lit * (10 + 2 * Math.sin(t * tau + index)));
      if (g > 0.75) disc(s, 'irregular', cx + 6, cy + 3, 45 * (g - 0.75) * 4, 22 * (g - 0.75) * 4, index);
    }
  }
  s.ctx.fillStyle = '#dbb47840';
  s.ctx.fillRect(40 + 560 * 0.45, 260, 560 * 0.3, 12);
  line(s, [40, 266], [600, 266], muted);
  dot(s, 40 + 560 * g, 266, 5, gold);
  band(
    s,
    [
      '380 mil anos · gás quase uniforme',
      'Dezenas de milhões de anos · gás em colapso',
      '≈ 100–250 milhões de anos · primeiras estrelas?',
      '≈ 0,5–1 bilhão de anos · bolhas ionizadas',
    ][epoch],
    'Faixa dourada: época aproximada das primeiras estrelas · percurso não linear.',
  );
}
function evidence(s: Surface, v: number, t: number) {
  const k = choice(v, 3);
  earlySky(s, 0.1);
  const stops = [75, 182, 300, 404, 535],
    y = 164;
  line(s, [43, y], [602, y], '#758797', 2);
  for (let i = 0; i < 5; i++) line(s, [stops[i], y - 8], [stops[i], y + 9], muted);
  const c = s.ctx;
  // Only the M51 plate is an observation; the other two thumbnails illustrate the probes.
  s.sprite('/posters/nuclei-small.webp', 300, 107, 100, 70, 0.9);
  s.sprite('/posters/cmb-field.webp', 404, 106, 92, 49, 0.95);
  s.sprite('/photos/m51/m51-480.webp', 535, 102, 132, 92);
  ['Núcleos leves', 'Luz antiga', 'M51 · Hubble/ACS'].forEach((name, i) => {
    s.label(name, stops[i + 2], 196, { size: 15, align: 'center' });
    dot(s, stops[i + 2], y, 4, k === 0 ? gold : muted);
  });
  if (k >= 1) {
    c.setLineDash([5, 4]);
    line(s, [209, y - 3], [535, y - 3], ice, 2);
    c.setLineDash([]);
    s.label('Modelo', 241, 227, { size: 15, color: ice });
  }
  if (k >= 2) {
    c.strokeStyle = gold;
    for (let i = 0; i < 9; i++) line(s, [124 + i * 9, y + 5], [132 + i * 9, y - 6], '#d8ad75');
    s.label('Inflação?', 169, 139, { size: 15, color: gold, align: 'center' });
  }
  if (k === 3) s.label('?', 75, 143, { size: 32, color: gold, align: 'center' });
  const span = [
    [300, 535],
    [209, 535],
    [125, 202],
    [50, 102],
  ][k];
  dot(s, mix(span[0], span[1], t), y, 5, gold);
  s.label('M51: NASA, ESA, S. Beckwith (STScI), and The Hubble Heritage Team', 26, 257, {
    size: 14,
    color: muted,
  });
  s.label('(STScI/AURA) · CC BY 4.0. Núcleos e mapa de fundo: ilustrações.', 26, 279, {
    size: 14,
    color: muted,
  });
  band(
    s,
    ['Pistas observáveis', 'Evolução calculada', 'Hipótese de inflação', 'Domínio desconhecido'][k],
    [
      'Abundâncias, radiação de fundo e observações de galáxias.',
      'A física do modelo liga as épocas apoiadas por medidas.',
      'O trecho hachurado marca uma hipótese para o Universo primordial.',
      'O começo absoluto está fora do alcance das medidas mostradas.',
    ][k],
  );
}

const scenes: Readonly<Record<string, Painter>> = {
  'galaxias-e-nebulosas-via-lactea': address,
  'galaxias-e-nebulosas-tipos': morphology,
  'galaxias-e-nebulosas-teia-cosmica': web,
  'galaxias-e-nebulosas-nebulosas': nebula,
  'galaxias-e-nebulosas-gas-e-estrelas': lightTravel,
  'galaxias-e-nebulosas-centros-galacticos': horizon,
  'origem-do-universo-o-universo': expansion,
  'origem-do-universo-expansao': redshift,
  'origem-do-universo-fase-quente': nuclei,
  'origem-do-universo-primeiras-estruturas': structures,
  'origem-do-universo-nossa-epoca': evidence,
};

export function paint(canvas: StagePaint, id: string, value: number, phase: number): boolean {
  if (!Object.hasOwn(scenes, id) || !Number.isFinite(value) || !Number.isFinite(phase)) return false;
  canvas.ctx.save();
  try {
    if (!id.startsWith('origem-do-universo-') || id.endsWith('-o-universo') || id.endsWith('-expansao'))
      canvas.backdrop();
    scenes[id](canvas, value, clamp(phase));
    return true;
  } finally {
    canvas.ctx.restore();
  }
}
