import type { StagePaint } from '../stage-surface';
import { deltaMagnitude, linearFit } from '../../lib/teaching-numerics';
import { vHalo, vLum, vTotal } from '../../lib/rotation';
import { fmt, rng } from './draw';

type Plate = (s: StagePaint, v: number, t: number) => void;
type Ink = CanvasRenderingContext2D;
const TAU = 2 * Math.PI;
const gold = '#ffce82',
  ice = '#9fdfff',
  pink = '#ffa194';
const library = '/models/stellar/plates/';
// Spherical projections of the project's granulation.png. Cloud billboards sample
// orion-detail.webp (Hubble Orion Treasury Project; credit in stellar/manifest.json).
const amber = library + 'amber.webp',
  red = library + 'red.webp';
const white = library + 'white.webp',
  blue = library + 'blue.webp',
  cloud = library + 'cloud.webp';
const galaxy = '/models/galaxies-v4/512/grand-spiral.webp';
const cmbField = '/posters/cmb-field.webp';
const mix = (a: number, b: number, t: number) => a + (b - a) * t;

function label(s: StagePaint, text: string, x: number, y: number, size = 16, color = '#f0f4fa') {
  s.label(text, x, y, { size, color, align: 'left' });
}
function dot(c: Ink, x: number, y: number, r: number, fill: string | CanvasGradient) {
  c.beginPath();
  c.arc(x, y, r, 0, TAU);
  c.fillStyle = fill;
  c.fill();
}
function line(c: Ink, x: number, y: number, u: number, v: number, color: string, width = 1) {
  c.beginPath();
  c.moveTo(x, y);
  c.lineTo(u, v);
  c.strokeStyle = color;
  c.lineWidth = width;
  c.stroke();
}
function ellipse(c: Ink, x: number, y: number, rx: number, ry: number, color: string) {
  c.beginPath();
  c.ellipse(x, y, rx, ry, 0, 0, TAU);
  c.strokeStyle = color;
  c.lineWidth = 1;
  c.stroke();
}
function arrow(c: Ink, x: number, y: number, u: number, v: number, color: string) {
  const a = Math.atan2(v - y, u - x);
  line(c, x, y, u, v, color, 2);
  for (const side of [-0.52, 0.52])
    line(c, u, v, u - 8 * Math.cos(a + side), v - 8 * Math.sin(a + side), color, 2);
}
const seeded = rng(29);
const grains = Array.from({ length: 84 }, () => ({
  angle: seeded() * TAU,
  radius: Math.sqrt(seeded()),
  depth: seeded() * 2 - 1,
  size: 1 + seeded() * 2,
}));

// Front and back passes let the opaque photosphere actually occult the far stream.
function stream(s: StagePaint, x: number, y: number, r: number, flat: number, t: number, front: boolean) {
  for (const p of grains) {
    const a = p.angle + t * (1.25 - 0.65 * p.radius);
    const depth = Math.sin(a);
    if (depth > 0 !== front) continue;
    const distance = r * (0.22 + 0.78 * p.radius);
    const scale = 1 + 0.09 * depth;
    dot(
      s.ctx,
      x + distance * Math.cos(a) * scale,
      y + distance * flat * depth + p.depth * 4,
      p.size * scale,
      front ? '#ffc98ab8' : '#a0aacc85',
    );
  }
}
function eject(s: StagePaint, x: number, y: number, r: number, t: number) {
  const width = r * (1.25 + 1.2 * t);
  s.sprite(library + 'ejecta.webp', x, y, width, width * 0.87, 0.94);
}
const collapse: Plate = (s, v, t) => {
  const radii = [139, 95, 67, 42];
  const radius = mix(radii[Math.max(v - 1, 0)], radii[v], t);
  const flatten = v < 2 ? 0.78 : mix(v === 2 ? 0.78 : 0.21, 0.21, t);
  for (let i = 0; i < 18; i++) {
    const p = grains[i],
      a = p.angle + t * 0.28;
    s.sprite(
      cloud,
      219 + radius * p.radius * Math.cos(a),
      177 + radius * p.radius * Math.sin(a) * flatten,
      radius * 1.38,
      radius * flatten * 1.5,
      0.35,
    );
  }
  const span = v >= 2 ? 143 : radius;
  stream(s, 219, 177, span, flatten, t, false);
  if (v) s.sprite(v === 3 ? amber : red, 219, 177, 14 + v * 13 + 5 * t);
  stream(s, 219, 177, span, flatten, t, true);
  label(s, ['Nuvem molecular', 'Contração', 'Protoestrela e disco', 'Fusão de hidrogênio'][v], 395, 141, 19);
  label(s, ['−260 °C', 'Milhares de °C', '≈ 1 milhão °C', '≈ 10 milhões °C'][v], 395, 177, 22, gold);
  label(s, v === 0 ? 'Gás e poeira' : 'Temperatura central', 395, 202, 15);
};
function nucleon(c: Ink, x: number, y: number, r: number, proton: boolean) {
  const g = c.createRadialGradient(x - r * 0.3, y - r * 0.4, 0, x, y, r);
  g.addColorStop(0, proton ? '#ffe6b7' : '#effaff');
  g.addColorStop(0.55, proton ? '#ee8a47' : '#78b8dc');
  g.addColorStop(1, proton ? '#844029' : '#31516b');
  dot(c, x, y, r, g);
}
const fusion: Plate = (s, v, t) => {
  const c = s.ctx;
  if (v === 3) {
    s.sprite(amber, 247, 176, 231);
    for (let i = 0; i < 6; i++) {
      const a = (i * TAU) / 6 + 0.2,
        b = a + 0.39;
      arrow(
        c,
        247 + 138 * Math.cos(a),
        176 + 138 * Math.sin(a),
        247 + (108 - 8 * t) * Math.cos(a),
        176 + (108 - 8 * t) * Math.sin(a),
        ice,
      );
      arrow(
        c,
        247 + 45 * Math.cos(b),
        176 + 45 * Math.sin(b),
        247 + (76 + 8 * t) * Math.cos(b),
        176 + (76 + 8 * t) * Math.sin(b),
        gold,
      );
    }
    label(s, 'Equilíbrio no interior', 410, 121, 19);
    label(s, 'Gravidade para dentro', 410, 157, 16, ice);
    label(s, 'Gradiente de pressão', 410, 188, 16, gold);
    label(s, 'para fora', 410, 210);
    return;
  }
  s.sprite(amber, 92, 180, 145);
  ellipse(c, 92, 180, 18, 18, gold);
  line(c, 110, 174, 197, 117, '#dfb27988');
  line(c, 110, 188, 197, 240, '#dfb27988');
  ellipse(c, 308, 177, 116, 116, '#dfb27988');
  const separation = v === 0 ? mix(82, 63, t) : v === 1 ? mix(63, 12, t) : 12;
  for (let i = 0; i < 4; i++) {
    const a = 0.76 + (i * Math.PI) / 2 + 0.3 * t,
      x = 308 + Math.cos(a) * separation,
      y = 177 + Math.sin(a) * separation * 0.84;
    nucleon(c, x, y, 14, v === 0 || i % 2 === 0 || (v === 1 && t < 0.55));
  }
  if (v === 2)
    for (let i = 0; i < 8; i++) {
      const a = (i * TAU) / 8 + 0.21,
        d = 32 + 62 * t;
      line(
        c,
        308 + (d - 12) * Math.cos(a),
        177 + (d - 12) * Math.sin(a),
        308 + d * Math.cos(a),
        177 + d * Math.sin(a),
        gold,
        3,
      );
    }
  label(s, ['4 prótons', 'Núcleo de hélio', 'Massa em energia'][v], 440, 146, 19);
  label(s, ['Hidrogênio', '2 prótons + 2 nêutrons', '≈ 0,7% da massa'][v], 440, 181, 16, gold);
  label(s, 'Núcleo solar ampliado', 62, 308, 15);
};
const solar: Plate = (s, v, t) => {
  const c = s.ctx,
    x = 218,
    y = 175;
  s.sprite(amber, x, y, 300);
  c.save();
  c.beginPath();
  c.moveTo(x, y);
  c.arc(x, y, 120, -1.2, 1.15);
  c.closePath();
  c.clip();
  const radii = [120, 115, 83, 30],
    colors = ['#ef9954', '#b44f29', '#df7b36', '#ffda7e'];
  radii.forEach((r, i) => dot(c, x, y, r, colors[i]));
  if (v === 0) dot(c, x + 11, y, 5 + 5 * t, '#fff2bb');
  if (v === 1) {
    const count = Math.round(5 + 18 * t);
    for (let i = 0; i < count; i++) {
      const px = x + 31 + i * 2.05,
        py = y + 9 * Math.sin(i * 2.8);
      line(c, px, py, px + 2.05, y + 9 * Math.sin((i + 1) * 2.8), ice, 1.7);
    }
  }
  if (v === 2)
    for (const a of [-0.63, 0, 0.63]) {
      c.save();
      c.translate(x + 97 * Math.cos(a), y + 97 * Math.sin(a));
      c.rotate(a);
      ellipse(c, 0, 0, 13, 9, '#ffcf92');
      dot(c, 13 * Math.cos(t * TAU + a), 9 * Math.sin(t * TAU + a), 3, ice);
      c.restore();
    }
  c.restore();
  if (v === 3)
    for (const a of [-0.55, 0, 0.55]) {
      const d = 126 + 42 * t;
      arrow(c, x + 122 * Math.cos(a), y + 122 * Math.sin(a), x + d * Math.cos(a), y + d * Math.sin(a), gold);
    }
  const mark = [14, 58, 98, 120][v];
  line(c, x + mark, y + 12, x + mark, 290, ice);
  line(c, x + mark, 290, 394, 290, ice);
  label(s, ['Núcleo', 'Zona radiativa', 'Zona convectiva', 'Fotosfera'][v], 400, 151, 22);
  label(s, ['≈ 15 milhões °C', 'Milhões de °C', '≈ 2 milhões a 6 mil °C', '≈ 5.500 °C'][v], 400, 184, 17, gold);
  label(s, ['Fusão', 'Difusão da radiação', 'Circulação do gás', 'A luz escapa'][v], 400, 295, 15, ice);
};
const smallStars: Plate = (s, v, t) => {
  const sizes = [63, 83, 221, 19, 13];
  const size = mix(sizes[Math.max(0, v - 1)], sizes[v], t);
  if (v === 3) eject(s, 194, 175, 138, t);
  s.sprite(
    v < 2 ? amber : v === 2 ? red : white,
    194,
    175,
    size * (1 + 0.018 * Math.sin(t * TAU)),
    size,
    v === 4 ? 0.62 : 1,
  );
  s.sprite(v === 4 ? white : red, 464, 175, v === 4 ? 14 : 36);
  label(
    s,
    ['Hoje', '+5 bilhões de anos', '+7 bilhões de anos', '+8 bilhões de anos', 'Trilhões de anos'][v],
    30,
    38,
    20,
  );
  label(
    s,
    ['Sol', 'Sol em expansão', 'Gigante vermelha', 'Anã branca e nebulosa', 'Anã branca fria'][v],
    68,
    303,
    18,
    gold,
  );
  label(s, v === 4 ? 'Fim previsto' : 'Anã vermelha · ⅓ M☉', 370, 303, 18, pink);
};
const massive: Plate = (s, v, t) => {
  if (v === 3) {
    eject(s, 171, 172, 130, t);
    s.sprite(blue, 171, 172, 21);
    const c = s.ctx;
    for (const front of [false, true]) {
      c.save();
      c.translate(465, 172);
      c.rotate(-0.22);
      c.beginPath();
      c.rect(-120, front ? 0 : -48, 240, 48);
      c.clip();
      c.scale(1, 0.28);
      c.rotate(0.68 * t);
      s.sprite(library + 'disk.webp', 0, 0, 236);
      c.restore();
      if (!front) dot(c, 465, 172, 26, '#020307');
    }
    label(s, 'Estrela de nêutrons', 75, 285, 18, ice);
    label(s, 'Buraco negro', 408, 285, 18, gold);
    label(s, 'ou', 309, 178);
    return;
  }
  const size = v === 0 ? 120 + 6 * t : v === 1 ? mix(120, 255, t) : mix(255, 163, t);
  s.sprite(v === 0 ? blue : red, 221, 171, size);
  if (v > 0) {
    const k = v === 2 ? 1 - 0.76 * t : 1;
    for (const [i, color] of ['#e69748', '#ddb066', '#a8b4c0', '#657887'].entries())
      dot(s.ctx, 221, 171, (48 - i * 11) * k, color);
    if (v === 2)
      for (let i = 0; i < 6; i++) {
        const a = (i * TAU) / 6;
        arrow(
          s.ctx,
          221 + 56 * Math.cos(a),
          171 + 56 * Math.sin(a),
          221 + (42 - 19 * t) * Math.cos(a),
          171 + (42 - 19 * t) * Math.sin(a),
          ice,
        );
      }
  }
  label(s, ['Sequência principal', 'Supergigante', 'Colapso do núcleo'][v], 395, 146, 20);
  label(s, ['Hidrogênio → hélio', 'Camadas de fusão', 'Núcleo de ferro'][v], 395, 182, 17, gold);
};
const elements: Plate = (s, v, t) => {
  const x = 229,
    y = 172;
  if (v === 0) {
    for (let i = 0; i < 15; i++) {
      const p = grains[i],
        d = 42 + (60 + 47 * t) * p.radius;
      nucleon(s.ctx, x + Math.cos(p.angle) * d, y + Math.sin(p.angle) * d * 0.72, 3 + 3 * p.radius, true);
    }
    s.sprite(cloud, x, y, 285, 176, 0.3);
  } else if (v === 4) {
    const approach = Math.min(1, t / 0.66);
    const a = approach * 4.1 + 0.36,
      r = 74 * (1 - approach);
    if (approach < 1) {
      ellipse(s.ctx, x, y, r, r * 0.45, '#9fdfff66');
      s.sprite(blue, x + r * Math.cos(a), y + r * 0.45 * Math.sin(a), 27);
      s.sprite(white, x - r * Math.cos(a), y - r * 0.45 * Math.sin(a), 25);
    } else {
      const expansion = (t - 0.66) / 0.34;
      s.sprite(white, x, y, 30 + 20 * (1 - expansion));
      s.ctx.save();
      s.ctx.translate(x, y);
      s.ctx.rotate(-0.32);
      s.sprite(library + 'ejecta.webp', 0, 0, 40 + 224 * expansion, 25 + 92 * expansion);
      s.ctx.restore();
    }
  } else {
    if (v === 1) s.sprite(red, x, y, 119);
    else s.sprite(v === 2 ? blue : white, x, y, v === 2 ? 114 : 28);
    eject(s, x, y, v === 1 ? 78 : 136, t);
    if (v === 3) s.sprite(red, x + 107, y + 23, 49);
  }
  label(s, ['H · Hidrogênio', 'C · Carbono', 'O · Oxigênio', 'Fe · Ferro', 'Au · Ouro'][v], 392, 113, 23, gold);
  const lines = [
    ['Universo primordial', 'Núcleos leves'],
    ['Estrelas como o Sol', 'e estrelas massivas', 'Ventos dispersam carbono'],
    ['Estrelas massivas', 'Expulsão na supernova'],
    ['Supernovas', 'Incluem explosões de', 'anãs brancas em binárias'],
    ['Fusão de estrelas', 'de nêutrons', 'Possível contribuição de', 'supernovas raras'],
  ];
  lines[v].forEach((text, i) => label(s, text, 392, 156 + i * 24, 16));
};
function spectrum(s: StagePaint, x: number, y: number, w: number, shift: number) {
  const c = s.ctx,
    gradient = c.createLinearGradient(x, y, x + w, y);
  for (const [i, color] of ['#7661c6', '#6095ce', '#82bfa3', '#dbcd82', '#f7a865', '#c2685e'].entries())
    gradient.addColorStop(i / 5, color);
  c.fillStyle = gradient;
  c.fillRect(x, y, w, 19);
  for (const pos of [0.19, 0.35, 0.61]) {
    const mark = pos * (1 + shift);
    if (mark <= 1) {
      c.fillStyle = '#162231';
      c.fillRect(x + w * mark, y, 3, 19);
    }
  }
}
function spiral(s: StagePaint, x: number, y: number, w: number, h: number, angle = 0) {
  const c = s.ctx;
  c.save();
  c.translate(x, y);
  c.globalCompositeOperation = 'screen';
  c.scale(1, h / w);
  c.rotate(angle);
  s.sprite(galaxy, 0, 0, w, w);
  c.restore();
}
const method: Plate = (s, v, t) => {
  spiral(s, 132, 124, 206, 140, -0.36);
  const c = s.ctx;
  for (let i = 0; i < 7; i++) {
    const p = (i / 7 + t * 0.6) % 1;
    dot(c, mix(155, 319, p), mix(128, 189, p), 1.4 + p, ice);
  }
  // Section through the collecting mirror and its focal plane.
  c.save();
  c.translate(329, 196);
  c.rotate(0.36);
  c.beginPath();
  c.moveTo(-5, -32);
  c.quadraticCurveTo(21, 0, -5, 32);
  c.lineTo(5, 33);
  c.quadraticCurveTo(31, 0, 5, -33);
  c.closePath();
  c.fillStyle = '#a1afbf';
  c.fill();
  for (const y of [-23, 0, 23]) line(c, -55, y, 2, y, '#a5d6e8a0');
  line(c, 2, -23, -30, 0, ice);
  line(c, 2, 23, -30, 0, ice);
  c.restore();
  if (v >= 1) {
    spectrum(s, 369, 134, 238, 0);
    spectrum(s, 369, 190, 238, 0.28 * (v === 1 ? t : 1));
    label(s, 'Laboratório', 369, 124, 14);
    label(s, 'Galáxia', 369, 181, 14);
  }
  if (v >= 2) {
    const k = v === 2 ? t : 1;
    for (const pos of [0.19, 0.35, 0.61])
      line(c, 369 + 238 * pos, 154, 369 + 238 * pos * (1 + 0.28 * k), 188, '#a1d7eaa8');
  }
  label(
    s,
    ['1 · Luz coletada', '2 · Espectro medido', '3 · Comparação com modelos', '4 · Inferência sobre a expansão'][
      v
    ],
    31,
    281,
    21,
    gold,
  );
  label(
    s,
    [
      'Abertura e foco do telescópio',
      'A posição das linhas registra o deslocamento.',
      'O conjunto de linhas se desloca para o vermelho.',
      'Pergunta aberta: por que a expansão atual acelera?',
    ][v],
    31,
    314,
    16,
  );
};
const spectra: Plate = (s, v, t) => {
  const exp = [0, 22, 120][v],
    local = [-14, 10, 8][v];
  spiral(s, 151, 153, [212, 160, 107][v], [125, 99, 70][v], -0.4);
  const x = 291,
    y = 91,
    w = 307;
  spectrum(s, x, y, w, 0);
  spectrum(s, x, y + 70, w, ((exp + local) / 190) * t);
  label(s, 'Laboratório', x, y - 10);
  label(s, 'Recebido', x, y + 60);
  line(s.ctx, x, y + 100, x + w, y + 100, '#cddaf5');
  label(s, 'Azul', x, y + 121, 14, ice);
  label(s, 'Vermelho', x + w - 62, y + 121, 14, pink);
  label(s, ['Andrômeda', 'Média distância', 'Muito distante'][v], 48, 260, 20);
  label(s, 'Expansão', x, 253, 15);
  label(s, 'Movimento local', x, 289, 15);
  const zero = 438;
  line(s.ctx, zero, 233, zero, 299, '#8594ae');
  if (exp) arrow(s.ctx, zero, 247, zero + exp * t, 247, gold);
  if (t > 0) arrow(s.ctx, zero, 283, zero + local * t, 283, ice);
  label(s, 'Espectros simulados · deslocamentos ampliados', 32, 330, 14);
};
const microwave: Plate = (s, v, t) => {
  const c = s.ctx,
    x = 320,
    y = 160,
    rx = 234,
    ry = 116;
  c.save();
  c.beginPath();
  c.ellipse(x, y, rx, ry, 0, 0, TAU);
  c.clip();
  c.fillStyle = '#d6b78b';
  c.fillRect(x - rx, y - ry, rx * 2, ry * 2);
  const opacity = v < 2 ? 0.13 : v === 2 ? mix(0.13, 0.93, t) : mix(0.93, 0.013, t);
  s.sprite(cmbField, x, y, rx * 2, ry * 2, opacity);
  const foreground = v === 0 ? 1 : v === 1 ? 1 - t : 0;
  if (foreground > 0) {
    c.save();
    c.translate(x, y);
    c.rotate(-0.08);
    c.globalAlpha = foreground;
    for (let i = -4; i <= 4; i++)
      s.sprite(cloud, i * 55, 6 * Math.sin(i * 0.8), 135, 35 + 12 * Math.cos(i), foreground * 0.72);
    c.restore();
  }
  // Scanning meridian. It traces the map; sky features stay fixed.
  c.beginPath();
  const lon = mix(-1.35, 1.35, t);
  for (let i = 0; i <= 48; i++) {
    const lat = (i / 48 - 0.5) * Math.PI,
      px = x + rx * Math.sin(lon) * Math.cos(lat),
      py = y + ry * Math.sin(lat);
    if (i === 0) c.moveTo(px, py);
    else c.lineTo(px, py);
  }
  c.strokeStyle = '#e8f3ff70';
  c.lineWidth = 1;
  c.stroke();
  c.restore();
  ellipse(c, x, y, rx, ry, '#c7d5db');
  label(
    s,
    [
      'Céu bruto · primeiro plano galáctico',
      'Remoção do primeiro plano',
      'Contraste ampliado',
      'Contraste natural aproximado',
    ][v],
    44,
    308,
    20,
  );
  label(s, 'Mapa simulado de temperatura · cores atribuídas', 44, 333, 15, ice);
};

function trace(c: Ink, points: readonly (readonly number[])[], color: string, width = 2) {
  if (!points.length) return;
  c.beginPath();
  points.forEach(([x, y], i) => {
    if (i === 0) c.moveTo(x, y);
    else c.lineTo(x, y);
  });
  c.strokeStyle = color;
  c.lineWidth = width;
  c.stroke();
}
const rotation: Plate = (s, v, t) => {
  const c = s.ctx,
    x = 169,
    y = 168;
  if (v === 2) {
    const g = c.createRadialGradient(x, y, 16, x, y, 144);
    g.addColorStop(0, '#929fef28');
    g.addColorStop(0.8, '#9492fe25');
    g.addColorStop(1, '#9492fe00');
    dot(c, x, y, 144, g);
  }
  spiral(s, x, y, 277, 142, -0.35);
  for (const r of [26, 52, 80]) {
    const speed = v === 0 ? vLum(r) : vTotal(r);
    const a = (t * speed * 4.2) / r - Math.PI / 2,
      rad = r * 1.57;
    ellipse(c, x, y, rad, rad * 0.5, '#b9c9e187');
    dot(c, x + rad * Math.cos(a), y + rad * 0.5 * Math.sin(a), 3.7 + Math.sin(a) * 0.6, gold);
  }
  const X = (r: number) => 359 + 2.72 * r,
    Y = (speed: number) => 249 - 1.85 * speed;
  label(s, 'Velocidade (km/s)', 350, 48, 16);
  for (const speed of [0, 40, 80]) {
    line(c, 355, Y(speed), 610, Y(speed), '#a9bdd244');
    label(s, String(speed), 328, Y(speed) + 4, 13);
  }
  for (const r of [0, 40, 80]) label(s, String(r), X(r) - 5, 271, 13);
  label(s, 'Raio · unidades do modelo', 361, 298, 15);
  const domain = Array.from({ length: 91 }, (_, i) => i);
  trace(
    c,
    domain.map((r) => [X(r), Y(vLum(r))]),
    ice,
  );
  if (v >= 1) for (let r = 8; r <= 88; r += 10) dot(c, X(r), Y(vTotal(r) + Math.sin(r) * 1.5), 3, gold);
  if (v === 2) {
    trace(
      c,
      domain.map((r) => [X(r), Y(vTotal(r))]),
      gold,
    );
    c.setLineDash([3, 4]);
    trace(
      c,
      domain.map((r) => [X(r), Y(vHalo(r))]),
      '#b6a9ff',
    );
    c.setLineDash([]);
  }
  label(s, ['Massa visível', 'Velocidades sintéticas', 'Halo inferido'][v], 42, 295, 18, ice);
  label(
    s,
    v === 2 ? 'Azul: visível · violeta: halo · dourado: total' : 'Curva azul: previsão da massa visível',
    42,
    333,
    15,
  );
};

const snRandom = rng(8),
  fitRandom = rng(64);
// Same samples, draw order, seed and model as the analytical SVG.
const supernovae = Array.from({ length: 22 }, () => {
  const z = 0.05 + snRandom() * 1.1;
  const noise = (snRandom() + snRandom() + snRandom() - 1.5) * 0.18;
  return { z, delta: deltaMagnitude(z) + noise, error: 0.12 + snRandom() * 0.12 };
});
const model = Array.from({ length: 61 }, (_, i) => [i / 50, deltaMagnitude(i / 50)]);
const measures = Array.from({ length: 40 }, (): [number, number] => {
  const x = 0.5 + fitRandom() * 9.5;
  return [x, 2 * x + 1 + (fitRandom() + fitRandom() + fitRandom() + fitRandom() - 2) * 2.4];
});
const candles: Plate = (s, v, t) => {
  const c = s.ctx;
  spiral(s, 109, 154, 178, 121, -0.43);
  s.sprite(white, 144, 130, 18 + 12 * Math.sin(t * Math.PI));
  ellipse(c, 144, 130, 19 + 7 * t, 19 + 7 * t, '#c1dcfa9a');
  label(s, 'Supernova Ia', 48, 246, 17);
  const X = (z: number) => 258 + 284 * z,
    Y = (m: number) => 251 - 171 * m;
  label(s, 'Δ magnitude · referência só de matéria', 211, 48, 17);
  for (const d of [0, 0.4, 0.8]) {
    line(c, 256, Y(d), 605, Y(d), '#abbad347');
    label(s, fmt(d, 1), 216, Y(d) + 5, 13);
  }
  for (const z of [0, 0.4, 0.8, 1.2]) label(s, fmt(z, 1), X(z) - 6, 292, 13);
  label(s, 'Redshift z', 474, 316, 15);
  for (const p of supernovae) {
    line(c, X(p.z), Y(p.delta - p.error), X(p.z), Y(p.delta + p.error), '#97b5cf');
    dot(c, X(p.z), Y(p.delta), 3, ice);
  }
  if (v >= 1) line(c, X(0), Y(0), X(1.2 * (v === 1 ? t : 1)), Y(0), pink, 2.4);
  if (v === 2)
    trace(
      c,
      model.slice(0, 1 + Math.ceil(t * 60)).map(([z, d]) => [X(z), Y(d)]),
      gold,
      2.5,
    );
  label(s, ['22 medidas sintéticas', 'Referência desacelerada', 'Modelo acelerado'][v], 28, 334, 17, gold);
};
const inference: Plate = (s, n, t) => {
  const points = measures.slice(0, n),
    fit = linearFit(points)!;
  const X = (x: number) => 249 + x * 35,
    Y = (y: number) => 272 - y * 8;
  const c = s.ctx;
  spiral(s, 108, 145, 176, 115, -0.3);
  const scan = 64 + 88 * t;
  line(c, scan, 106, scan, 180, ice, 1.5);
  label(s, String(n) + ' medidas', 28, 238, 21);
  label(s, 'Amostra sintética', 28, 265, 15);
  const domain = Array.from({ length: 42 }, (_, i) => i / 4);
  c.save();
  c.beginPath();
  c.rect(238, 46, 380, 232);
  c.clip();
  c.beginPath();
  for (const [side, xs] of [
    [1, domain],
    [-1, [...domain].reverse()],
  ] as const) {
    xs.forEach((x, i) => {
      const y = Y(fit.a + fit.b * x + side * 2 * fit.meanSE(x));
      if (side === 1 && i === 0) c.moveTo(X(x), y);
      else c.lineTo(X(x), y);
    });
  }
  c.closePath();
  c.fillStyle = '#67aed64d';
  c.fill();
  for (const d of [0, 10, 20]) line(c, X(0), Y(d), X(10), Y(d), '#afbcd644');
  line(c, X(0), Y(fit.a), X(10), Y(fit.a + 10 * fit.b), ice, 2);
  for (const [x, y] of points) dot(c, X(x), Y(y), 3.4, gold);
  c.restore();
  for (const x of [0, 5, 10]) label(s, String(x), X(x) - 3, 294, 13);
  for (const y of [0, 10, 20]) label(s, String(y), 215, Y(y) + 4, 13);
  label(s, 'Inclinação ' + fmt(fit.b, 2) + ' ± ' + fmt(fit.slopeSE, 2) + ' (1 EP)', 242, 34, 17, ice);
  label(s, 'Faixa da média ajustada · ±2 erros padrão', 242, 324, 15);
};

const scenes: Record<string, { last: number; draw: Plate }> = {
  'vida-das-estrelas-colapso': { last: 3, draw: collapse },
  'vida-das-estrelas-fusao': { last: 3, draw: fusion },
  'vida-das-estrelas-sol': { last: 3, draw: solar },
  'vida-das-estrelas-pequenas-e-medias': { last: 4, draw: smallStars },
  'vida-das-estrelas-massivas': { last: 3, draw: massive },
  'vida-das-estrelas-elementos': { last: 4, draw: elements },
  'misterios-do-cosmos-horizonte': { last: 3, draw: method },
  'misterios-do-cosmos-exoplanetas': { last: 2, draw: spectra },
  'misterios-do-cosmos-vida': { last: 3, draw: microwave },
  'misterios-do-cosmos-materia-escura': { last: 2, draw: rotation },
  'misterios-do-cosmos-energia-escura': { last: 2, draw: candles },
  'misterios-do-cosmos-limites': { last: 40, draw: inference },
};

export function paint(canvas: StagePaint, id: string, value: number, phase: number): boolean {
  if (!Object.hasOwn(scenes, id) || !Number.isFinite(value) || !Number.isFinite(phase)) return false;
  const scene = scenes[id];
  const lower = scene.draw === inference ? 3 : 0;
  const v = Math.min(scene.last, Math.max(lower, Math.round(value)));
  canvas.ctx.save();
  try {
    canvas.backdrop();
    scene.draw(canvas, v, Math.max(0, Math.min(1, phase)));
  } finally {
    canvas.ctx.restore();
  }
  return true;
}
