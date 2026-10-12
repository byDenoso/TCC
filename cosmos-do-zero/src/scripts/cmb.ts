/**
 * Abertura: mapa simulado da radiação cósmica de fundo (estilo Planck).
 * Campo aleatório gaussiano aproximado por soma de ondas planas com potência decrescente.
 * Não é o mapa real; serve para sentir o tamanho das diferenças de temperatura.
 */
const SIGMA_UK = 70; // desvio típico das manchas, em milionésimos de kelvin (ordem de grandeza do CMB)
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
const inEllipse = (x: number, y: number) => ((x - 0.5) / 0.5) ** 2 + ((y - 0.5) / 0.5) ** 2 <= 1;

export function initCmb(): void {
  const root = document.querySelector<HTMLElement>('[data-cmb]');
  if (!root) return;
  const frame = root.querySelector<HTMLElement>('[data-cmb-frame]')!;
  const canvas = root.querySelector<HTMLCanvasElement>('[data-cmb-canvas]')!;
  const probe = root.querySelector<HTMLElement>('[data-cmb-probe]')!;
  const read = root.querySelector<HTMLElement>('[data-cmb-read]')!;
  const f = field(1089);
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const W = canvas.width, H = canvas.height;
  const img = ctx.createImageData(W, H);
  for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
    const x = (i + 0.5) / W, y = (j + 0.5) / H, o = (j * W + i) * 4;
    if (!inEllipse(x, y)) { img.data[o + 3] = 0; continue; }
    const [r, g, b] = color(0.85 * f(x, y * 0.5)); // y em metade: mesmo espaçamento físico que x num mapa 2:1
    img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);

  let px = 0.5, py = 0.5;
  const fmt = (n: number) => n.toLocaleString('pt-BR');
  const show = (x: number, y: number) => {
    if (!inEllipse(x, y)) return;
    px = x; py = y;
    probe.hidden = false; probe.style.left = `${x * 100}%`; probe.style.top = `${y * 100}%`;
    const uK = Math.round(f(x, y * 0.5) * SIGMA_UK);
    const diff = Math.abs(uK);
    read.textContent = diff < 8
      ? 'Aqui a temperatura está praticamente na média. O Universo jovem era quase igualzinho em toda parte.'
      : `Aqui a luz é um tiquinho ${uK > 0 ? 'mais quente' : 'mais fria'} que a média: ${fmt(diff)} milionésimos de grau. Diferenças minúsculas assim foram as sementes das galáxias.`;
  };
  const fromEvent = (e: PointerEvent) => { const r = frame.getBoundingClientRect(); show((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); };
  frame.addEventListener('pointermove', fromEvent);
  frame.addEventListener('pointerdown', fromEvent);
  frame.addEventListener('keydown', (e) => {
    const step = e.shiftKey ? 0.08 : 0.025;
    const d: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step * 2], ArrowDown: [0, step * 2] };
    const m = d[e.key]; if (!m) return;
    e.preventDefault();
    const nx = Math.min(0.98, Math.max(0.02, px + m[0])), ny = Math.min(0.98, Math.max(0.02, py + m[1]));
    if (inEllipse(nx, ny)) show(nx, ny);
  });
  frame.addEventListener('focus', () => show(px, py));
}
