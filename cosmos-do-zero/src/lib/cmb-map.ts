/**
 * Abertura: mapa simulado da radiação cósmica de fundo (estilo Planck).
 * Campo aleatório gaussiano aproximado por soma de ondas planas com potência decrescente.
 * Não é o mapa real; serve para sentir o tamanho das diferenças de temperatura.
 */
const SIGMA_UK = 70; // escala ilustrativa em µK; não é uma calibração de dados observados
const STOPS: [number, [number, number, number]][] = [
  [-3, [16, 42, 92]], [-2, [30, 79, 160]], [-1, [91, 147, 214]], [-0.35, [191, 216, 242]], [0, [255, 244, 220]],
  [0.35, [251, 211, 162]], [1, [243, 154, 85]], [2, [217, 81, 42]], [3, [143, 31, 16]]
];
function color(v: number): [number, number, number] {
  if (v <= STOPS[0][0]) return STOPS[0][1];
  for (let i = 1; i < STOPS.length; i++) if (v <= STOPS[i][0]) {
    const [a, ca] = STOPS[i - 1], [b, cb] = STOPS[i]; const t = (v - a) / (b - a);
    return [0, 1, 2].map((k) => Math.round(ca[k] + (cb[k] - ca[k]) * t)) as [number, number, number];
  }
  return STOPS[STOPS.length - 1][1];
}
function field(seed: number): (x: number, y: number) => number {
  let s = seed >>> 0;
  const rnd = () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const N = 260, kx = new Float32Array(N), ky = new Float32Array(N), ph = new Float32Array(N), am = new Float32Array(N);
  let norm = 0;
  for (let i = 0; i < N; i++) {
    const k = 5 + 85 * Math.pow(rnd(), 1.35), th = rnd() * Math.PI * 2; // número de onda (ciclos por largura)
    kx[i] = k * Math.cos(th) * 2 * Math.PI; ky[i] = k * Math.sin(th) * 2 * Math.PI; ph[i] = rnd() * Math.PI * 2;
    am[i] = Math.pow(k, -0.42); norm += am[i] * am[i] / 2;
  }
  const n = 1 / Math.sqrt(norm);
  return (x, y) => { let v = 0; for (let i = 0; i < N; i++) v += am[i] * Math.cos(kx[i] * x + ky[i] * y + ph[i]); return v * n; };
}
export const inCmbMap = (x: number, y: number) => ((x - 0.5) / 0.5) ** 2 + ((y - 0.5) / 0.5) ** 2 <= 1;

const sample = field(1089);

export function cmbTemperature(x: number, y: number): number {
  return Math.round(sample(x, y * 0.5) * SIGMA_UK);
}

export function cmbMapPixels(width: number, height: number): Uint8Array {
  const pixels = new Uint8Array(width * height * 4);
  for (let row = 0; row < height; row++) {
    for (let column = 0; column < width; column++) {
      const x = (column + 0.5) / width;
      const y = (row + 0.5) / height;
      if (!inCmbMap(x, y)) continue;
      const [red, green, blue] = color(0.85 * sample(x, y * 0.5));
      pixels.set([red, green, blue, 255], (row * width + column) * 4);
    }
  }
  return pixels;
}
