/**
 * Viagem pelo tempo (home): estados ilustrativos de partículas, um por marco de eras.json.
 * TOY_MODEL: os pontos são esquemáticos, fora de escala, e não vêm de dados observacionais.
 * Cada partícula tem um centro (gx, gy) e, opcionalmente, uma órbita elíptica em torno dele.
 * Cores: 0 = matéria (tinta), 1 = destaque quente (terracota), 2 = luz ou atmosfera (azul).
 */
export const JOURNEY_ERAS = [
  'primordial', 'nucleosynthesis', 'cmb', 'dark-ages', 'first-stars', 'reionization', 'galaxies',
  'acceleration', 'solar-system', 'earth', 'oxygen', 'present'
] as const;
export type JourneyEra = typeof JOURNEY_ERAS[number];

export interface JourneyLayout {
  id: JourneyEra;
  /** Estados que preenchem o palco inteiro, em vez do quadro central. */
  fill: boolean;
  /** Tremor térmico ilustrativo, em unidades do quadro. */
  jitter: number;
  gx: Float32Array; gy: Float32Array;
  r: Float32Array; th: Float32Array; w: Float32Array;
  q: Float32Array; ca: Float32Array; sa: Float32Array;
  s: Float32Array; a: Float32Array; c: Uint8Array;
  /** Pontos de interesse para rótulos e brilhos. */
  marks: { x: number; y: number; r: number }[];
}

/** Gerador determinístico: a mesma semente produz a mesma cena em qualquer navegador. */
export function seeded(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function blank(id: JourneyEra, n: number, fill: boolean, jitter: number): JourneyLayout {
  const f = () => new Float32Array(n);
  const layout: JourneyLayout = { id, fill, jitter, gx: f(), gy: f(), r: f(), th: f(), w: f(), q: f(), ca: f(), sa: f(), s: f(), a: f(), c: new Uint8Array(n), marks: [] };
  layout.q.fill(1); layout.ca.fill(1); layout.s.fill(1.8); layout.a.fill(0.8);
  return layout;
}

const TAU = Math.PI * 2;
const gauss = (rnd: () => number): number => Math.sqrt(-2 * Math.log(1 - rnd() * 0.999999)) * Math.cos(TAU * rnd());
const FIRST_STAR_CENTERS = [[-0.6, 0.5], [0.42, 0.62], [0.08, 0.05], [-0.5, -0.4], [0.62, -0.3], [-0.05, -0.74], [0.1, 0.9], [-0.9, 0.02]];

/** Gás difuso com regiões mais densas antes do surgimento de estrelas. */
function earlyGas(id: 'dark-ages' | 'reionization', n: number): JourneyLayout {
  const rnd = seeded(39);
  const L = blank(id, n, false, 0.002);
  for (let i = 0; i < n; i++) {
    if (i % 3 === 0) {
      const [x, y] = FIRST_STAR_CENTERS[(i / 3) % FIRST_STAR_CENTERS.length];
      L.gx[i] = x + 0.14 * gauss(rnd);
      L.gy[i] = y + 0.14 * gauss(rnd);
    } else {
      L.gx[i] = 2.3 * rnd() - 1.15;
      L.gy[i] = 1.8 * rnd() - 0.9;
    }
    L.s[i] = 1 + 0.7 * rnd();
    L.a[i] = 0.17 + 0.21 * rnd();
  }
  return L;
}

/** Galáxias em disco vistas com inclinações diferentes; a mesma lista serve para "crescem" e "afastam-se". */
function galaxies(id: JourneyEra, n: number, spread: number, size: number): JourneyLayout {
  const rnd = seeded(404);
  const L = blank(id, n, false, 0.003);
  const centers = [[-0.55, 0.48], [0.5, 0.55], [0.02, 0.02], [-0.62, -0.42], [0.6, -0.36], [-0.02, -0.72], [0.05, 0.78]];
  const shape = centers.map(() => ({ R: 0.13 + 0.09 * rnd(), q: 0.35 + 0.6 * rnd(), pa: rnd() * Math.PI, arms: rnd() < 0.75, dir: rnd() < 0.5 ? -1 : 1 }));
  for (let i = 0; i < n; i++) {
    const k = i % centers.length, g = shape[k];
    const u = rnd(), r = g.R * size * Math.pow(u, 0.62);
    const arm = Math.floor(rnd() * 2) * Math.PI;
    L.gx[i] = centers[k][0] * spread; L.gy[i] = centers[k][1] * spread;
    L.r[i] = r;
    L.th[i] = g.arms ? arm + g.dir * 3.4 * Math.log(1 + r / (0.035 * size)) + 0.32 * gauss(rnd) : rnd() * TAU;
    L.w[i] = g.dir * 0.05 / (r / size + 0.045);
    L.q[i] = g.q; L.ca[i] = Math.cos(g.pa); L.sa[i] = Math.sin(g.pa);
    L.s[i] = u < 0.12 ? 2.4 : 1.5; L.a[i] = u < 0.12 ? 0.95 : 0.7;
    L.c[i] = u < 0.1 ? 1 : 0;
  }
  centers.forEach((c, k) => L.marks.push({ x: c[0] * spread, y: c[1] * spread, r: shape[k].R * size }));
  return L;
}

function earth(id: JourneyEra, n: number, atmosphere: boolean): JourneyLayout {
  const rnd = seeded(733);
  const L = blank(id, n, false, 0.002);
  const R = 0.5, cx = -0.06, cy = 0.02;
  for (let i = 0; i < n; i++) {
    const u = rnd(), v = rnd(), kind = rnd(), moon = i % 19 === 0;
    if (moon) { L.gx[i] = 0.74; L.gy[i] = 0.5; L.r[i] = 0.065 * Math.sqrt(u); L.c[i] = 0; L.a[i] = 0.75; }
    else {
      L.gx[i] = cx; L.gy[i] = cy;
      const air = atmosphere && i % 4 === 1;
      L.r[i] = air ? R * (1.06 + 0.11 * u) : R * Math.sqrt(u);
      L.c[i] = air ? 2 : kind < 0.58 ? 2 : kind < 0.86 ? 0 : 1;
      L.a[i] = air ? 0.6 : 0.85;
      L.w[i] = 0.035;
    }
    L.th[i] = v * TAU; L.s[i] = 1.9;
  }
  L.marks.push({ x: cx, y: cy, r: R }, { x: 0.74, y: 0.5, r: 0.065 });
  return L;
}

export function buildJourney(n: number): JourneyLayout[] {
  const out: JourneyLayout[] = [];

  // 1. Fase quente e densa: matéria e luz misturadas, em agitação intensa.
  { const rnd = seeded(11), L = blank('primordial', n, true, 0.03);
    for (let i = 0; i < n; i++) { L.gx[i] = rnd() * 2 - 1; L.gy[i] = rnd() * 2 - 1; const k = rnd(); L.c[i] = k < 0.42 ? 1 : k < 0.62 ? 2 : 0; L.s[i] = 1.5 + 1.3 * rnd(); L.a[i] = 0.9; }
    out.push(L); }

  // 2. Primeiros núcleos: cerca de um quarto das partículas se agrupa de quatro em quatro (hélio); o resto segue solto.
  { const rnd = seeded(23), L = blank('nucleosynthesis', n, true, 0.011);
    const grouped = Math.floor(n * 0.25 / 4) * 4;
    let cx = 0, cy = 0;
    for (let i = 0; i < n; i++) {
      if (i < grouped) {
        if (i % 4 === 0) { cx = rnd() * 1.9 - 0.95; cy = rnd() * 1.9 - 0.95; if (L.marks.length < 1 && Math.abs(cx) < 0.5 && Math.abs(cy) < 0.5) L.marks.push({ x: cx, y: cy, r: 0.04 }); }
        const k = i % 4;
        L.gx[i] = cx + (k % 2 ? 0.011 : -0.011); L.gy[i] = cy + (k < 2 ? 0.011 : -0.011);
        L.c[i] = k === 0 || k === 3 ? 1 : 0; L.s[i] = 2.3; L.a[i] = 0.95;
      } else { L.gx[i] = rnd() * 2 - 1; L.gy[i] = rnd() * 2 - 1; L.c[i] = 1; L.s[i] = 1.9; L.a[i] = 0.75; }
    }
    out.push(L); }

  // 3. A luz atravessa: átomos neutros, espaço transparente, agitação baixa.
  { const rnd = seeded(37), L = blank('cmb', n, true, 0.004);
    for (let i = 0; i < n; i++) { L.gx[i] = rnd() * 2 - 1; L.gy[i] = rnd() * 2 - 1; L.c[i] = 0; L.s[i] = 1.5; L.a[i] = 0.42; }
    out.push(L); }

  // Idade das Trevas: o gás neutro se concentra, antes das primeiras fontes de luz.
  out.push(earlyGas('dark-ages', n));

  // Primeiras estrelas: a gravidade junta o gás em regiões densas.
  { const rnd = seeded(41), L = blank('first-stars', n, false, 0.004);
    const centers = FIRST_STAR_CENTERS;
    for (let i = 0; i < n; i++) {
      if (i % 5 === 0) { L.gx[i] = rnd() * 2.2 - 1.1; L.gy[i] = rnd() * 2.2 - 1.1; L.a[i] = 0.25; L.s[i] = 1.4; continue; }
      const c = centers[i % centers.length], d = Math.abs(gauss(rnd)) * 0.075;
      L.gx[i] = c[0]; L.gy[i] = c[1]; L.r[i] = d; L.th[i] = rnd() * TAU; L.w[i] = 0.05;
      L.c[i] = d < 0.03 ? 1 : 0; L.s[i] = d < 0.03 ? 2.4 : 1.6; L.a[i] = d < 0.03 ? 1 : 0.7;
    }
    centers.slice(0, 6).forEach(c => L.marks.push({ x: c[0], y: c[1], r: 0.11 }));
    out.push(L); }

  // Reionização: regiões ilustrativas de gás ionizado em torno de fontes de ultravioleta.
  { const L = earlyGas('reionization', n);
    const bubbles = [{ source: 0, radius: 0.38 }, { source: 2, radius: 0.5 }, { source: 4, radius: 0.34 }];
    for (const { source, radius } of bubbles) {
      const [x, y] = FIRST_STAR_CENTERS[source];
      L.marks.push({ x, y, r: radius });
    }
    for (let i = 0; i < n; i++) {
      if (L.marks.some(({ x, y, r }) => Math.hypot(L.gx[i] - x, L.gy[i] - y) < r)) {
        L.c[i] = 2;
        L.a[i] = 0.82;
      }
    }
    out.push(L); }

  // Galáxias crescem; depois, o espaço entre elas aumenta mais depressa.
  out.push(galaxies('galaxies', n, 1, 1));
  out.push(galaxies('acceleration', n, 1.42, 0.78));

  // Sistema Solar: disco de gás e poeira, com órbitas mais rápidas perto do Sol.
  { const rnd = seeded(59), L = blank('solar-system', n, false, 0.002);
    const orbits = [0.16, 0.25, 0.35, 0.47, 0.66, 0.86];
    for (let i = 0; i < n; i++) {
      const k = rnd();
      L.q[i] = 0.44; L.th[i] = rnd() * TAU;
      if (i % 7 === 0) { L.r[i] = Math.abs(gauss(rnd)) * 0.035; L.c[i] = 1; L.s[i] = 2.6; L.a[i] = 1; L.w[i] = 0.3; continue; }
      const o = orbits[i % orbits.length];
      const planet = i < orbits.length * 7 && i % 7 === 1;
      L.r[i] = planet ? o : k < 0.6 ? o + 0.012 * gauss(rnd) : 0.1 + 0.8 * rnd();
      L.w[i] = 0.42 * Math.pow(0.16 / Math.max(L.r[i], 0.08), 1.5);
      L.c[i] = planet ? (o < 0.4 ? 0 : 2) : 0; L.s[i] = planet ? 5.5 : 1.3; L.a[i] = planet ? 1 : k < 0.6 ? 0.5 : 0.22;
    }
    orbits.forEach(o => L.marks.push({ x: 0, y: 0, r: o }));
    out.push(L); }

  // A Terra se forma; depois, o oxigênio se acumula na atmosfera.
  out.push(earth('earth', n, false));
  out.push(earth('oxygen', n, true));

  // O Universo observado hoje: galáxias organizadas em nós e filamentos.
  { const rnd = seeded(71), L = blank('present', n, true, 0.002);
    const nodes: number[][] = [];
    for (let gy = 0; gy < 5; gy++) for (let gx = 0; gx < 6; gx++) nodes.push([-0.92 + gx * 0.37 + 0.16 * (rnd() - 0.5), -0.88 + gy * 0.44 + 0.2 * (rnd() - 0.5)]);
    for (let i = 0; i < n; i++) {
      const a = nodes[Math.floor(rnd() * nodes.length)];
      if (rnd() < 0.62) { L.gx[i] = a[0] + 0.028 * gauss(rnd); L.gy[i] = a[1] + 0.028 * gauss(rnd); L.s[i] = 1.7; L.a[i] = 0.85; L.c[i] = rnd() < 0.12 ? 1 : 0; }
      else {
        let best = nodes[0], bd = 9;
        for (const b of nodes) { const d = Math.hypot(b[0] - a[0], b[1] - a[1]); if (d > 0.01 && d < bd) { bd = d; best = b; } }
        const t = rnd();
        L.gx[i] = a[0] + (best[0] - a[0]) * t + 0.012 * gauss(rnd); L.gy[i] = a[1] + (best[1] - a[1]) * t + 0.012 * gauss(rnd);
        L.s[i] = 1.2; L.a[i] = 0.4;
      }
    }
    const here = nodes[16]; L.marks.push({ x: here[0], y: here[1], r: 0.07 });
    out.push(L); }

  return out;
}

/** Posição de uma partícula no instante t (s), em unidades do quadro. */
export function journeyPoint(L: JourneyLayout, i: number, t: number, out: [number, number]): [number, number] {
  const r = L.r[i];
  if (r === 0) { out[0] = L.gx[i]; out[1] = L.gy[i]; return out; }
  const ang = L.th[i] + L.w[i] * t, px = r * Math.cos(ang), py = L.q[i] * r * Math.sin(ang);
  out[0] = L.gx[i] + px * L.ca[i] - py * L.sa[i];
  out[1] = L.gy[i] + px * L.sa[i] + py * L.ca[i];
  return out;
}

/**
 * Progresso contínuo da leitura: 0 no primeiro marco, n-1 no último.
 * centers = posição vertical do centro de cada passo; anchor = linha de leitura da janela.
 */
export function journeyProgress(centers: readonly number[], anchor: number): number {
  const n = centers.length;
  if (n === 0) return 0;
  if (anchor <= centers[0]) return 0;
  for (let i = 0; i < n - 1; i++) {
    if (anchor < centers[i + 1]) return i + (anchor - centers[i]) / (centers[i + 1] - centers[i]);
  }
  return n - 1;
}

export const smooth = (x: number): number => { const v = Math.min(1, Math.max(0, x)); return v * v * (3 - 2 * v); };
