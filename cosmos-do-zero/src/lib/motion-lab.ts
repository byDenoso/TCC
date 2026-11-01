/**
 * Matemática das animações do painel "Ciência em movimento".
 * Tudo aqui é didático: formas reais (curva de Planck, deslocamento da luz), números ilustrativos,
 * nenhum ajuste a dados observados. As cenas só desenham o que estas funções devolvem.
 */

export const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));
export const smoothstep = (a: number, b: number, x: number): number => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };

/** Gerador determinístico (mulberry32): as cenas são iguais a cada visita. */
export function seeded(seed: number): () => number {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let x = s; x = Math.imul(x ^ (x >>> 15), x | 1); x ^= x + Math.imul(x ^ (x >>> 7), x | 61); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
}

/* ───────────── 1. A luz esticada pelo espaço ───────────── */

export const VISIBLE_MIN_NM = 380;
export const VISIBLE_MAX_NM = 750;
export const isVisibleNm = (nm: number): boolean => nm >= VISIBLE_MIN_NM && nm <= VISIBLE_MAX_NM;

/** Se o espaço cresce `growth` vezes, o comprimento de onda cresce o mesmo tanto. */
export const stretchNm = (nm: number, growth: number): number => nm * growth;
/** Desvio para o vermelho z = (λ observado − λ emitido) / λ emitido. */
export const redshiftOf = (growth: number): number => growth - 1;

/** Cor aproximada de uma luz de comprimento de onda `nm` (380–750 nm); fora disso, [0, 0, 0]. */
export function wavelengthRgb(nm: number): [number, number, number] {
  if (!isVisibleNm(nm)) return [0, 0, 0];
  let r = 0, g = 0, b = 0;
  if (nm < 440) { r = (440 - nm) / 60; b = 1; }
  else if (nm < 490) { g = (nm - 440) / 50; b = 1; }
  else if (nm < 510) { g = 1; b = (510 - nm) / 20; }
  else if (nm < 580) { r = (nm - 510) / 70; g = 1; }
  else if (nm < 645) { r = 1; g = (645 - nm) / 65; }
  else r = 1;
  const edge = nm < 420 ? 0.35 + (0.65 * (nm - 380)) / 40 : nm > 700 ? 0.35 + (0.65 * (750 - nm)) / 50 : 1;
  return [r, g, b].map((v) => Math.round(255 * v * edge)) as [number, number, number];
}

/** Nome da cor em linguagem comum; fora da faixa visível, a região do espectro. */
export function lightName(nm: number): string {
  if (nm < VISIBLE_MIN_NM) return 'ultravioleta';
  if (nm < 450) return 'violeta';
  if (nm < 495) return 'azul';
  if (nm < 570) return 'verde';
  if (nm < 590) return 'amarela';
  if (nm < 620) return 'laranja';
  if (nm <= VISIBLE_MAX_NM) return 'vermelha';
  if (nm < 1_000_000) return 'infravermelha';
  return 'de micro-ondas';
}

/* ───────────── 2. Expansão sem centro ───────────── */

export interface Galaxy { x: number; y: number; size: number }

/** Quadriculado com leve desordem, em unidades de distância arbitrárias. Repete-se com período cols × rows. */
export function galaxyField(cols = 11, rows = 7, seed = 5): Galaxy[] {
  const rand = seeded(seed);
  const out: Galaxy[] = [];
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
    out.push({ x: i - (cols - 1) / 2 + (rand() - 0.5) * 0.46, y: j - (rows - 1) / 2 + (rand() - 0.5) * 0.46, size: 0.7 + rand() * 0.6 });
  }
  return out;
}

/** Leva a diferença para o intervalo [−período/2, período/2): o quadriculado repete-se igual em todas as direções. */
export function wrap(d: number, period: number): number { return d - period * Math.round(d / period); }

/** Posição de `p` vista de `o`, com o espaço esticado `scale` vezes. */
export function seenFrom(p: { x: number; y: number }, o: { x: number; y: number }, scale: number, cols = 11, rows = 7): [number, number] {
  return [wrap(p.x - o.x, cols) * scale, wrap(p.y - o.y, rows) * scale];
}

/* ───────────── 3. Diagrama de Hubble se montando ───────────── */

export interface HubblePoint { mpc: number; kms: number }

/**
 * Galáxias fictícias: velocidade ≈ H₀ × distância, com ruído e movimentos próprios.
 * Saem em ordem embaralhada, como se fossem medidas uma a uma.
 */
export function hubbleSample(n = 28, seed = 11, h0 = 70, maxMpc = 400): HubblePoint[] {
  const rand = seeded(seed);
  const gauss = () => Math.sqrt(-2 * Math.log(Math.max(1e-9, rand()))) * Math.cos(2 * Math.PI * rand());
  const slots = Array.from({ length: n }, (_, i) => i);
  for (let i = n - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [slots[i], slots[j]] = [slots[j], slots[i]]; }
  return slots.map((s) => {
    const mpc = maxMpc * (0.04 + 0.94 * ((s + rand() * 0.8) / n));
    const kms = Math.max(40, h0 * mpc * (1 + 0.06 * gauss()) + 220 * gauss());
    return { mpc, kms };
  });
}

/** Inclinação da melhor reta que passa pela origem (mínimos quadrados). */
export function slopeThroughOrigin(points: HubblePoint[]): number {
  let dv = 0, dd = 0;
  for (const p of points) { dv += p.mpc * p.kms; dd += p.mpc * p.mpc; }
  return dd > 0 ? dv / dd : 0;
}

/* ───────────── 4. A luz do começo esfriando ───────────── */

export const CMB_TODAY_K = 2.725;
/** Quanto o espaço cresceu desde que a luz mais antiga se soltou (≈ 1 + z). */
export const LIGHT_RELEASE_GROWTH = 1100;
const WIEN_NM_K = 2_897_771.955;
const PLANCK_C2_NM_K = 1.438776877e7;
export const KELVIN_TO_C = 273.15;

/** Posição do controle (0 = hoje, 1 = luz mais antiga) → fator de esticamento, em escala logarítmica. */
export const growthAt = (p: number): number => Math.pow(LIGHT_RELEASE_GROWTH, clamp01(p));
/** A temperatura da luz de fundo cai na proporção em que o espaço cresce. */
export const lightTemperatureK = (growth: number): number => CMB_TODAY_K * growth;
/** Comprimento de onda onde a curva de um corpo quente é mais alta (lei de Wien). */
export const peakNm = (kelvin: number): number => WIEN_NM_K / kelvin;

/** Forma da curva de Planck por comprimento de onda, dividida pelo valor no pico: 0…1. */
export function planckShape(nm: number, kelvin: number): number {
  const f = (l: number): number => Math.pow(l, -5) / Math.expm1(PLANCK_C2_NM_K / (l * kelvin));
  const v = f(nm) / f(peakNm(kelvin));
  return Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0;
}

/** Cor de um corpo quente (aproximação de Tanner Helland, válida de 1.000 a 40.000 K). */
export function blackbodyRgb(kelvin: number): [number, number, number] {
  const t = Math.min(40000, Math.max(1000, kelvin)) / 100;
  const c = (v: number) => Math.round(Math.min(255, Math.max(0, v)));
  const r = t <= 66 ? 255 : 329.698727446 * Math.pow(t - 60, -0.1332047592);
  const g = t <= 66 ? 99.4708025861 * Math.log(t) - 161.1195681661 : 288.1221695283 * Math.pow(t - 60, -0.0755148492);
  const b = t >= 66 ? 255 : t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  return [c(r), c(g), c(b)];
}

/** Quanto um corpo nessa temperatura brilha aos olhos (0 = invisível, 1 = brilho cheio). Abaixo de ~800 K nada se vê. */
export const visibleGlow = (kelvin: number): number => smoothstep(700, 3000, kelvin);

/* ───────────── 5. Curva de rotação de uma galáxia ───────────── */

const DISK_SCALE = 0.15;
const HALO_PLATEAU = 2.0;
const HALO_CORE = 0.25;

/** Massa do disco de estrelas e gás dentro do raio r (0…1 ≈ toda a massa visível). */
export const visibleMass = (r: number): number => { const x = r / DISK_SCALE; return 1 - (1 + x) * Math.exp(-x); };

/**
 * Rapidez de giro (unidade arbitrária) a uma distância r do centro (0…1 = centro…borda).
 * `dark` ∈ [0, 1] liga o halo invisível: 0 = só o que enxergamos, 1 = o halo que as medidas pedem.
 */
export function rotationSpeed(r: number, dark: number): number {
  const rr = Math.max(1e-3, r);
  const v2 = visibleMass(rr) / rr + clamp01(dark) * HALO_PLATEAU * (rr * rr) / (rr * rr + HALO_CORE * HALO_CORE);
  return Math.sqrt(v2);
}
/** Velocidade angular (unidade arbitrária): estrelas internas dão voltas mais depressa. */
export const angularSpeed = (r: number, dark: number): number => rotationSpeed(r, dark) / Math.max(1e-3, r);
