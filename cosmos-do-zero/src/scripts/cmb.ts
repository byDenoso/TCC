import { motionPreference, motionFactor } from './motion-preference';
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
  // Camada GLSL: o mesmo mapa respira (oscilações acústicas ilustrativas), ondula onde se toca e é varrido por uma faixa de leitura.
  const gl = cmbShader(frame, canvas, img);

  let px = 0.5, py = 0.5;
  const fmt = (n: number) => n.toLocaleString('pt-BR');
  const show = (x: number, y: number) => {
    if (!inEllipse(x, y)) return;
    px = x; py = y;
    probe.hidden = false; probe.style.left = `${x * 100}%`; probe.style.top = `${y * 100}%`;
    const uK = Math.round(f(x, y * 0.5) * SIGMA_UK);
    const diff = Math.abs(uK);
    read.textContent = diff < 8
      ? 'Neste mapa simulado, a temperatura está quase na média. A luz antiga observada no céu também é muito uniforme, com pequenas diferenças.'
      : `Neste mapa simulado, a luz está ${uK > 0 ? 'mais quente' : 'mais fria'} que a média: ${fmt(diff)} milionésimos de kelvin (valor ilustrativo). Um milionésimo de kelvin equivale a um milionésimo de grau Celsius de diferença. No céu, essas pequenas diferenças ajudam a estudar a formação das estruturas do Universo.`;
  };
  const fromEvent = (e: PointerEvent) => { const r = frame.getBoundingClientRect(); show((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); };
  frame.addEventListener('pointermove', fromEvent);
  frame.addEventListener('pointerdown', (e) => { fromEvent(e); const r = frame.getBoundingClientRect(); gl?.ripple((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); });
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

/** Shader WebGL sobre o mapa já calculado. Sem WebGL, fica o canvas 2D. */
function cmbShader(frame: HTMLElement, base: HTMLCanvasElement, img: ImageData): { ripple(x: number, y: number): void } | null {
  const c = document.createElement('canvas');
  c.width = base.width * 2; c.height = base.height * 2; c.className = 'cmb-gl'; c.setAttribute('aria-hidden', 'true');
  const gl = c.getContext('webgl', { premultipliedAlpha: false, alpha: true, failIfMajorPerformanceCaveat: !new URLSearchParams(location.search).has('gl') });
  if (!gl) return null;
  const sh = (type: number, src: string) => { const o = gl.createShader(type)!; gl.shaderSource(o, src); gl.compileShader(o); return gl.getShaderParameter(o, gl.COMPILE_STATUS) ? o : null; };
  const vs = sh(gl.VERTEX_SHADER, 'attribute vec2 p; varying vec2 uv; void main(){ uv = p*0.5+0.5; uv.y = 1.0-uv.y; gl_Position = vec4(p,0.,1.); }');
  const fs = sh(gl.FRAGMENT_SHADER, `precision mediump float;
    varying vec2 uv; uniform sampler2D tex; uniform float t; uniform vec3 rip; uniform float k;
    void main(){
      vec2 u = uv;
      // ondas planas lentas: o mapa "respira" como um fluido que oscila
      u += k * 0.0025 * vec2(sin(uv.y*18.0 + t*0.9), cos(uv.x*14.0 - t*0.7));
      // anel de onda a partir do toque
      float age = t - rip.z; vec2 d = (uv - rip.xy) * vec2(2.0, 1.0); float r = length(d);
      float w = (age > 0.0 && age < 3.0) ? sin(46.0*r - 11.0*age) * exp(-2.2*age) * exp(-4.0*r) : 0.0;
      u += k * normalize(d + 1e-5) * w * 0.012;
      vec4 c = texture2D(tex, u);
      float lum = dot(c.rgb, vec3(0.33));
      c.rgb *= 1.0 + k * 0.10 * sin(t*1.4 + lum*9.0);
      c.rgb += vec3(1.0, 0.95, 0.85) * abs(w) * 0.35 * k;
      // faixa de leitura que varre o mapa
      float sweep = fract(t * 0.11); float band = exp(-pow((uv.x - sweep) * 38.0, 2.0));
      c.rgb += vec3(0.75, 0.70, 1.0) * band * 0.22 * k * c.a;
      gl_FragColor = c;
    }`);
  if (!vs || !fs) return null;
  const prog = gl.createProgram()!; gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null;
  gl.useProgram(prog);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
  const uT = gl.getUniformLocation(prog, 't'), uR = gl.getUniformLocation(prog, 'rip'), uK = gl.getUniformLocation(prog, 'k');
  gl.viewport(0, 0, c.width, c.height);
  base.after(c); frame.classList.add('has-gl');
  const start = performance.now(); let rip: [number, number, number] = [0.5, 0.5, -10], raf = 0, visible = true;
  const hero = frame.closest<HTMLElement>('.hero-shell');
  const still = () => motionPreference.matches || hero?.dataset.ambientPaused === 'true' || document.hidden;
  const draw = () => {
    const t = (performance.now() - start) / 1000;
    gl.uniform1f(uT, t); gl.uniform3f(uR, rip[0], rip[1], rip[2]); gl.uniform1f(uK, still() ? 0 : motionFactor());
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  };
  const loop = () => { raf = 0; draw(); if (visible && !still()) raf = requestAnimationFrame(loop); };
  const kick = () => { if (!raf) raf = requestAnimationFrame(loop); };
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) kick(); }).observe(frame);
  if (hero) new MutationObserver(kick).observe(hero, { attributes: true, attributeFilter: ['data-ambient-paused'] });
  motionPreference.addEventListener('change', kick);
  document.addEventListener('visibilitychange', kick);
  c.addEventListener('webglcontextlost', () => { cancelAnimationFrame(raf); c.remove(); frame.classList.remove('has-gl'); });
  kick();
  return { ripple(x, y) { rip = [x, y, (performance.now() - start) / 1000]; kick(); } };
}
