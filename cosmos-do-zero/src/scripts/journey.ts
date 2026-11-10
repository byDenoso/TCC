/**
 * Viagem pelo tempo: a rolagem conduz uma única cena de partículas pelos marcos de eras.json.
 * Canvas 2D (não disputa o contexto WebGL das cenas 3D). Só desenha com a seção visível e a aba aberta.
 * Com movimento reduzido, nada se move sozinho: a cena salta de um marco ao outro conforme a leitura.
 */
import { buildJourney, JOURNEY_ERAS, journeyPoint, journeyProgress, smooth, type JourneyEra, type JourneyLayout } from '../lib/journey';
import { motionPreference, motionFactor } from './motion-preference';

export function initJourney(): void {
  const root = document.querySelector<HTMLElement>('[data-journey]');
  const canvas = root?.querySelector<HTMLCanvasElement>('[data-journey-canvas]');
  const steps = root ? [...root.querySelectorAll<HTMLElement>('[data-journey-step]')] : [];
  const ctx = canvas?.getContext('2d');
  if (!root || !canvas || !ctx || steps.length === 0) return;
  const stage = canvas.parentElement as HTMLElement;
  const when = root.querySelector<HTMLElement>('[data-journey-when]');
  const count = root.querySelector<HTMLElement>('[data-journey-count]');
  const ticks = [...root.querySelectorAll<HTMLElement>('[data-journey-tick]')];
  const labels = steps.map(s => s.dataset.journeyShort ?? '');

  const small = matchMedia('(max-width: 860px)');
  let n = small.matches ? 460 : 780;
  let layouts: JourneyLayout[] = buildJourney(n);
  let W = 0, H = 0, dpr = 1;
  let colors = { ink: '#1b2330', hot: '#c8461f', light: '#1f5fa8', bg: '#f1e9d6', muted: '#5b6472' };
  let visible = false, raf = 0, last = 0, clock = 0, progress = 0, active = -1, dirty = true;
  const pa: [number, number] = [0, 0], pb: [number, number] = [0, 0];

  const readColors = () => {
    const cs = getComputedStyle(root);
    const v = (name: string, fallback: string) => cs.getPropertyValue(name).trim() || fallback;
    colors = { ink: v('--ink', colors.ink), hot: v('--accent', colors.hot), light: v('--accent-2', colors.light), bg: v('--bg', colors.bg), muted: v('--muted', colors.muted) };
    dirty = true;
  };

  const resize = () => {
    const rect = stage.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = Math.max(1, Math.round(rect.width)); H = Math.max(1, Math.round(rect.height));
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    const want = small.matches ? 460 : 780;
    if (want !== n) { n = want; layouts = buildJourney(n); }
    dirty = true;
  };

  /** Quadro central: à direita no desktop (o texto ocupa a esquerda), no alto no celular. */
  const frame = () => {
    const wide = !small.matches;
    return { cx: W * (wide ? 0.66 : 0.5), cy: H * (wide ? 0.46 : 0.36), k: Math.min(W * (wide ? 0.27 : 0.42), H * (wide ? 0.34 : 0.17)) };
  };

  const measure = () => {
    const anchor = window.innerHeight * 0.58;
    const centers = steps.map(s => { const r = s.getBoundingClientRect(); return r.top + r.height / 2; });
    const p = journeyProgress(centers, anchor);
    // Cada marco tem uma zona de repouso: a cena só se transforma no trecho central entre dois passos.
    const base = Math.floor(p), settle = base + smooth((p - base - 0.18) / 0.64);
    const next = motionPreference.matches ? Math.round(p) : settle;
    if (next !== progress) { progress = next; dirty = true; }
    const index = Math.round(p);
    if (index !== active) {
      active = index;
      steps.forEach((s, i) => s.classList.toggle('is-active', i === index));
      ticks.forEach((t, i) => t.classList.toggle('is-active', i === index));
      if (when) when.textContent = labels[index] ?? '';
      if (count) count.textContent = `${String(index + 1).padStart(2, '0')} / ${String(steps.length).padStart(2, '0')}`;
    }
  };

  const eraIndex = (id: JourneyEra) => JOURNEY_ERAS.indexOf(id);
  const layout = (id: JourneyEra) => layouts[eraIndex(id)];
  const weight = (id: JourneyEra) => Math.max(0, 1 - Math.abs(progress - eraIndex(id)));
  const fill = (color: string, alpha: number) => { ctx.fillStyle = color; ctx.globalAlpha = Math.max(0, Math.min(1, alpha)); };
  const glow = (x: number, y: number, r: number, color: string, alpha: number) => {
    if (alpha <= 0.01 || r <= 0) return;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, color); g.addColorStop(1, 'transparent');
    ctx.globalAlpha = Math.min(1, alpha); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  };
  const label = (text: string, x: number, y: number, alpha: number, color = colors.ink) => {
    if (alpha <= 0.02) return;
    ctx.globalAlpha = Math.min(1, alpha); ctx.fillStyle = color;
    ctx.font = `650 ${small.matches ? 12 : 13}px 'Inter Tight Variable', 'Inter Tight', Arial, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, x, y);
  };

  /** Camadas de contexto de cada marco, com peso máximo no centro do passo correspondente. */
  const overlays = (f: { cx: number; cy: number; k: number }, t: number) => {
    const at = (L: JourneyLayout, m: number): [number, number, number] => {
      const mark = L.marks[m]; if (!mark) return [f.cx, f.cy, 0];
      return L.fill ? [W / 2 + mark.x * W / 2, H / 2 + mark.y * H / 2, mark.r * f.k] : [f.cx + mark.x * f.k, f.cy - mark.y * f.k, mark.r * f.k];
    };
    let w = weight('primordial');
    if (w > 0) glow(W / 2, H / 2, Math.max(W, H) * 0.75, colors.hot, 0.2 * w);
    w = weight('nucleosynthesis');
    if (w > 0) { const [x, y] = at(layout('nucleosynthesis'), 0); ctx.globalAlpha = w; ctx.strokeStyle = colors.hot; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y, 22, 0, Math.PI * 2); ctx.stroke(); label('núcleo de hélio', x, y - 36, w, colors.hot); }
    w = weight('cmb');
    if (w > 0) {
      ctx.lineWidth = 2; ctx.strokeStyle = colors.light;
      for (let ray = 0; ray < 7; ray++) {
        const y0 = H * (0.12 + ray * 0.125), phase = t * 2.2 + ray * 1.7, dir = ray % 2 ? -1 : 1;
        ctx.globalAlpha = 0.62 * w; ctx.beginPath();
        for (let x = 0; x <= W; x += 6) { const y = y0 + 9 * Math.sin((x * dir) / 26 + phase) + (x - W / 2) * 0.06 * (ray - 3); if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
        ctx.stroke();
      }
      label('luz livre para viajar', f.cx, H * (small.matches ? 0.56 : 0.182), w, colors.light);
    }
    w = weight('dark-ages');
    if (w > 0) {
      glow(f.cx, f.cy, f.k * 1.24, colors.muted, 0.14 * w);
      label('gás neutro antes das estrelas', f.cx, f.cy + f.k * 1.08, w);
    }
    w = weight('first-stars');
    if (w > 0) {
      const stars = layout('first-stars');
      stars.marks.forEach((_, m) => { const [x, y, r] = at(stars, m); glow(x, y, r * (1.5 + 0.12 * Math.sin(t * 1.3 + m)), colors.hot, 0.5 * w); });
    }
    w = weight('reionization');
    if (w > 0) {
      const ionized = layout('reionization');
      ctx.strokeStyle = colors.light; ctx.lineWidth = 1.2; ctx.setLineDash([4, 6]);
      ionized.marks.forEach((_, m) => {
        const [x, y, r] = at(ionized, m);
        glow(x, y, r, colors.light, 0.24 * w);
        glow(x, y, r * 0.32, colors.hot, 0.85 * w);
        fill(colors.hot, w); ctx.beginPath(); ctx.arc(x, y, 3, 0, 2 * Math.PI); ctx.fill();
        ctx.globalAlpha = 0.48 * w; ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
      });
      ctx.setLineDash([]);
      label('gás ionizado em torno das fontes', f.cx, f.cy + f.k * 1.08, w, colors.light);
    }
    w = weight('acceleration');
    if (w > 0) {
      ctx.strokeStyle = colors.light; ctx.lineWidth = 1.2; ctx.setLineDash([5, 7]);
      for (let ring = 1; ring <= 3; ring++) { ctx.globalAlpha = 0.4 * w; ctx.beginPath(); ctx.arc(f.cx, f.cy, f.k * 0.42 * ring * (0.9 + 0.1 * smooth(progress - eraIndex('galaxies'))), 0, Math.PI * 2); ctx.stroke(); }
      ctx.setLineDash([]);
      label('o espaço entre as galáxias cresce', f.cx, f.cy - f.k * 0.3, w, colors.light);
    }
    w = weight('solar-system');
    if (w > 0) {
      glow(f.cx, f.cy, f.k * 0.2, colors.hot, 0.6 * w);
      ctx.strokeStyle = colors.ink; ctx.lineWidth = 1;
      layout('solar-system').marks.forEach(mark => { ctx.globalAlpha = 0.22 * w; ctx.beginPath(); ctx.ellipse(f.cx, f.cy, mark.r * f.k, mark.r * f.k * 0.44, 0, 0, Math.PI * 2); ctx.stroke(); });
      label('perto do Sol, as órbitas são mais rápidas', f.cx, f.cy + f.k * 0.52, w);
    }
    const we = Math.min(1, weight('earth') + weight('oxygen'));
    if (we > 0) {
      const earth = layout('earth');
      const [x, y, r] = at(earth, 0);
      ctx.globalAlpha = 0.5 * we; ctx.strokeStyle = colors.ink; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
      const [mx, my, mr] = at(earth, 1);
      label('Lua', mx, my - mr - 16, we);
      const wo = weight('oxygen');
      if (wo > 0) { ctx.globalAlpha = 0.5 * wo; ctx.strokeStyle = colors.light; ctx.lineWidth = 7; ctx.beginPath(); ctx.arc(x, y, r * 1.12, 0, Math.PI * 2); ctx.stroke(); label('atmosfera com oxigênio', x, y - r * 1.3, wo, colors.light); }
    }
    w = weight('present');
    if (w > 0) { const [x, y] = at(layout('present'), 0); ctx.globalAlpha = w; ctx.strokeStyle = colors.hot; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 20 + 3 * Math.sin(t * 2), 0, Math.PI * 2); ctx.stroke(); label('estamos em uma destas', x, y - 36, w, colors.hot); }
    ctx.globalAlpha = 1;
  };

  const draw = () => {
    dirty = false;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const f = frame();
    const i0 = Math.min(layouts.length - 1, Math.max(0, Math.floor(progress)));
    const i1 = Math.min(layouts.length - 1, i0 + 1);
    const A = layouts[i0], B = layouts[i1], mix = smooth(progress - i0);
    const t = clock, jitter = (A.jitter + (B.jitter - A.jitter) * mix) * (motionPreference.matches ? 0 : motionFactor());
    const palette = [colors.ink, colors.hot, colors.light];
    overlays(f, t);
    for (let i = 0; i < n; i++) {
      journeyPoint(A, i, t, pa); journeyPoint(B, i, t, pb);
      const ax = A.fill ? W / 2 + pa[0] * W / 2 : f.cx + pa[0] * f.k, ay = A.fill ? H / 2 + pa[1] * H / 2 : f.cy - pa[1] * f.k;
      const bx = B.fill ? W / 2 + pb[0] * W / 2 : f.cx + pb[0] * f.k, by = B.fill ? H / 2 + pb[1] * H / 2 : f.cy - pb[1] * f.k;
      let x = ax + (bx - ax) * mix, y = ay + (by - ay) * mix;
      if (jitter > 0) { const ph = i * 12.9898; x += jitter * f.k * Math.sin(t * 7.1 + ph); y += jitter * f.k * Math.cos(t * 6.3 + ph * 1.7); }
      const size = A.s[i] + (B.s[i] - A.s[i]) * mix, alpha = A.a[i] + (B.a[i] - A.a[i]) * mix;
      fill(palette[(mix < 0.5 ? A : B).c[i]], alpha);
      ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  };

  const loop = (now: number) => {
    raf = 0;
    if (!visible || document.hidden) return;
    const moving = !motionPreference.matches;
    if (moving) { clock += Math.min(0.05, Math.max(0, (now - last) / 1000)) * motionFactor(); dirty = true; }
    last = now;
    if (dirty) draw();
    if (moving) raf = requestAnimationFrame(loop);
  };
  const kick = () => { if (!raf && visible && !document.hidden) { last = performance.now(); raf = requestAnimationFrame(loop); } };
  const onScroll = () => { if (!visible) return; measure(); kick(); };

  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    root.dataset.journeyVisible = String(visible);
    if (visible) { resize(); measure(); kick(); } else if (raf) { cancelAnimationFrame(raf); raf = 0; }
  }, { rootMargin: '120px 0px' }).observe(root);
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', () => { if (visible) { resize(); measure(); kick(); } });
  document.addEventListener('visibilitychange', kick);
  motionPreference.addEventListener('change', () => { measure(); dirty = true; kick(); });
  new MutationObserver(() => { readColors(); kick(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // O palco só ocupa espaço depois de pronto; sem JavaScript, os marcos viram uma lista comum.
  root.dataset.journeyReady = 'true';
  readColors(); resize(); measure();
  draw();
}
