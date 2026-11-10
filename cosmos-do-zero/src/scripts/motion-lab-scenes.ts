/**
 * Cenas do painel "Ciência em movimento": cinco animações em SVG (480 × 300).
 * Cada cena desenha só o que lib/motion-lab.ts calcula. Texto dentro do SVG é curto;
 * a explicação completa vai no parágrafo abaixo da figura (atualizado a cada controle).
 */
import { C, clamp, ease, el, fmt, g, set, text } from './micro/draw';
import {
  VISIBLE_MAX_NM, VISIBLE_MIN_NM, angularSpeed, blackbodyRgb, galaxyField, growthAt, hubbleSample, isVisibleNm, lightName,
  lightTemperatureK, peakNm, planckShape, rotationSpeed, seenFrom, slopeThroughOrigin, stretchNm, visibleGlow, wavelengthRgb, KELVIN_TO_C
} from '../lib/motion-lab';

export interface SciContext { canAnimate(): boolean; redraw(): void }
export interface SciFrame {
  /** Texto de leitura (parágrafo abaixo da figura). */
  read: string;
  /** Valor mostrado ao lado do rótulo da barra. */
  value: string;
  /** Resumo curto para leitores de tela. */
  aria: string;
}
export interface SciScene {
  mount(svg: SVGSVGElement, ctx: SciContext): void;
  /** p ∈ [0, 1] é o valor do controle; time, os segundos de movimento contínuo (ondas, órbitas). */
  render(p: number, time: number): SciFrame;
  /** Há movimento contínuo mesmo com o controle parado. */
  ambient?: boolean;
  /** Movimento automático do controle até a pessoa mexer. */
  sweep?: { seconds: number; mode: 'fill' | 'bounce' };
  /** Posições visitadas pelo botão "Avançar" (movimento reduzido). */
  steps: number[];
  /** Valor inicial do controle. */
  start: number;
  action?: { label: string; run(): void };
  dispose?(): void;
}

type Anchor = 'start' | 'middle' | 'end';
const label = (parent: Element, x: number, y: number, s: string, cls = '', anchor: Anchor = 'start'): SVGTextElement =>
  text(parent, x, y, s, { class: `sci-t ${cls}`.trim(), 'text-anchor': anchor });
const pathOf = (pts: [number, number][]): string => pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join('');
const rgb = ([r, gg, b]: [number, number, number]): string => `rgb(${r},${gg},${b})`;
const plural = (n: number, one: string, many: string): string => (n === 1 ? one : many);
const arrowPath = (x1: number, y1: number, x2: number, y2: number, head: number): string => {
  const a = Math.atan2(y2 - y1, x2 - x1);
  const h = (da: number) => `${(x2 - head * Math.cos(a + da)).toFixed(1)} ${(y2 - head * Math.sin(a + da)).toFixed(1)}`;
  return `M${x1.toFixed(1)} ${y1.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}M${h(0.5)}L${x2.toFixed(1)} ${y2.toFixed(1)}L${h(-0.5)}`;
};

/* ───────────── 1. A luz que se estica ───────────── */
function luzScene(): SciScene {
  const X0 = 24, X1 = 456, W0 = 64, W1 = 416, CY = 72, AMP = 24, BASE_PX = 34, EMIT = 460, GMAX = 2.2;
  const LINES = [410, 434, 486, 656];
  const nmX = (nm: number): number => X0 + ((nm - VISIBLE_MIN_NM) / (VISIBLE_MAX_NM - VISIBLE_MIN_NM)) * (X1 - X0);
  let wave!: SVGPathElement, bracket!: SVGPathElement, dim!: SVGTextElement, shift!: SVGPathElement, off!: SVGTextElement;
  const lines: SVGLineElement[] = [];
  return {
    start: 0, steps: [0, 0.25, 0.5, 0.75, 1], ambient: true, sweep: { seconds: 5.5, mode: 'bounce' },
    mount(svg) {
      const defs = el('defs', {}, svg);
      const grad = el('linearGradient', { id: 'sci-luz-spectrum', x1: 0, x2: 1, y1: 0, y2: 0 }, defs);
      for (let i = 0; i <= 14; i++) el('stop', { offset: i / 14, 'stop-color': rgb(wavelengthRgb(VISIBLE_MIN_NM + ((VISIBLE_MAX_NM - VISIBLE_MIN_NM) * i) / 14)) }, grad);
      const gal = g(svg, { transform: `translate(30 ${CY})` });
      el('ellipse', { rx: 16, ry: 6, transform: 'rotate(-24)', fill: C.ink2, opacity: 0.8 }, gal);
      el('circle', { r: 4, fill: C.ink }, gal);
      label(svg, 8, 112, 'galáxia', 'mute');
      const us = g(svg, { transform: `translate(450 ${CY})` });
      el('circle', { r: 11, fill: 'none', stroke: C.accentInk, 'stroke-width': 2.5 }, us);
      el('circle', { r: 4, fill: C.accentInk }, us);
      label(svg, 472, 112, 'nós', 'mute', 'end');
      wave = el('path', { fill: 'none', 'stroke-width': 4.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
      bracket = el('path', { fill: 'none', stroke: C.ink2, 'stroke-width': 2 }, svg);
      label(svg, W0, 148, 'uma onda', 'mute');
      dim = label(svg, 240, 26, 'invisível aos olhos', 'strong', 'middle');
      label(svg, X0, 176, 'arco-íris da galáxia', 'mute');
      el('rect', { x: X0, y: 184, width: X1 - X0, height: 32, rx: 6, fill: 'url(#sci-luz-spectrum)' }, svg);
      for (const nm of LINES) el('line', { x1: nmX(nm), x2: nmX(nm), y1: 218, y2: 226, stroke: C.ink2, 'stroke-width': 2, opacity: 0.55 }, svg);
      for (let i = 0; i < LINES.length; i++) lines.push(el('line', { y1: 184, y2: 216, stroke: '#0a0f1f', 'stroke-width': 3.4 }, svg));
      shift = el('path', { fill: 'none', stroke: C.accentInk, 'stroke-width': 2.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
      off = label(svg, X1, 258, '→ infravermelho', 'warm', 'end');
      label(svg, X0, 288, 'azul', 'mute');
      label(svg, 240, 288, 'luz visível', 'mute', 'middle');
      label(svg, X1, 288, 'vermelho', 'mute', 'end');
    },
    render(p, time) {
      const gr = 1 + (GMAX - 1) * p;
      const nm = stretchNm(EMIT, gr), vis = isVisibleNm(nm), lam = BASE_PX * gr, phase = time * 2.6;
      const pts: [number, number][] = [];
      for (let x = W0; x <= W1; x += 3) pts.push([x, CY + AMP * Math.sin(((x - W0) / lam) * 2 * Math.PI - phase)]);
      wave.style.stroke = vis ? rgb(wavelengthRgb(nm)) : 'var(--muted)';
      set(wave, { d: pathOf(pts), 'stroke-dasharray': vis ? 'none' : '1 8' });
      set(bracket, { d: `M${W0} 118V130M${W0} 124H${(W0 + lam).toFixed(1)}M${(W0 + lam).toFixed(1)} 118V130` });
      set(dim, { opacity: vis ? 0 : 1 });
      LINES.forEach((l0, i) => { const l = l0 * gr, x = nmX(l); set(lines[i], { x1: x, x2: x, opacity: clamp((VISIBLE_MAX_NM - l) / 18) }); });
      const xa = nmX(656), xb = Math.min(X1, nmX(656 * gr));
      set(shift, { d: xb - xa > 9 ? arrowPath(xa, 234, xb, 234, 7) : '' });
      set(off, { opacity: 656 * gr > VISIBLE_MAX_NM ? 1 : 0 });
      const x = fmt(gr, 1);
      let read: string;
      if (gr <= 1.03) read = 'Sem expansão, a luz azul chega do jeito que saiu. Aperte "Reproduzir" ou mova a barra: o espaço vai crescer.';
      else {
        read = `O espaço cresceu ${x}× e a onda esticou junto: ficou ${x}× mais comprida. `;
        read += vis ? `A luz, que saiu azul, chega ${lightName(nm)}.` : 'A luz, que saiu azul, chega infravermelha: nossos olhos não veem, mas telescópios como o James Webb sim.';
        read += ' As linhas escuras do arco-íris andam junto: é assim que os astrônomos medem o quanto uma galáxia se afastou.';
      }
      return { read, value: `${x}×`, aria: `Espaço ${x} vezes maior; luz ${vis ? lightName(nm) : 'infravermelha'}.` };
    }
  };
}

/* ───────────── 2. Expansão sem centro ───────────── */
function expansaoScene(): SciScene {
  const COLS = 11, ROWS = 7, K = 44, CX = 240, CY = 150, SMAX = 2.2;
  const field = galaxyField(COLS, ROWS);
  const observers = [38, 13, 63, 20, 56];
  let obsIdx = 0, from = { x: field[observers[0]].x, y: field[observers[0]].y }, to = from, cur = { ...from }, anim = 0;
  let grid!: SVGPathElement, svgRef!: SVGSVGElement, ctxRef!: SciContext, onTap!: (e: MouseEvent) => void;
  const dots: SVGEllipseElement[] = [], arrows: SVGPathElement[] = [];
  const goTo = (target: { x: number; y: number }): void => {
    cancelAnimationFrame(anim);
    from = { ...cur }; to = { x: target.x, y: target.y };
    if (!ctxRef.canAnimate()) { cur = { ...to }; ctxRef.redraw(); return; }
    const t0 = performance.now();
    const step = (now: number): void => {
      const k = ctxRef.canAnimate() ? ease(clamp((now - t0) / 700)) : 1;
      cur = { x: from.x + (to.x - from.x) * k, y: from.y + (to.y - from.y) * k };
      ctxRef.redraw();
      if (k < 1) anim = requestAnimationFrame(step);
    };
    anim = requestAnimationFrame(step);
  };
  return {
    start: 0, steps: [0, 0.25, 0.5, 0.75, 1], sweep: { seconds: 5, mode: 'bounce' },
    action: { label: 'Ver de outra galáxia', run: () => { obsIdx = (obsIdx + 1) % observers.length; goTo(field[observers[obsIdx]]); } },
    mount(svg, ctx) {
      svgRef = svg; ctxRef = ctx;
      svg.querySelector('[data-sci-static-expansion]')?.remove();
      grid = el('path', { fill: 'none', stroke: C.line, 'stroke-width': 1.2, opacity: 0.7 }, svg);
      const arrowLayer = g(svg), dotLayer = g(svg);
      for (const gl of field) {
        arrows.push(el('path', { fill: 'none', stroke: C.accentInk, 'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', opacity: 0.85 }, arrowLayer));
        const rx = 4.4 + gl.size * 3;
        dots.push(el('ellipse', { rx, ry: rx * 0.5, fill: C.ink2, opacity: 0.92 }, dotLayer));
      }
      el('circle', { cx: CX, cy: CY, r: 12, fill: 'none', stroke: C.accentInk, 'stroke-width': 3 }, svg);
      label(svg, CX + 17, CY - 14, 'nós', 'strong halo');
      onTap = (e: MouseEvent) => {
        const m = svg.getScreenCTM(); if (!m) return;
        const { x: sx, y: sy } = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
        let best = -1, bd = 26 * 26;
        dots.forEach((d, i) => { const dx = Number(d.getAttribute('cx')) - sx, dy = Number(d.getAttribute('cy')) - sy; const q = dx * dx + dy * dy; if (q < bd && d.style.display !== 'none') { bd = q; best = i; } });
        if (best >= 0) goTo(field[best]);
      };
      svg.addEventListener('click', onTap);
    },
    render(p) {
      const s = 1 + (SMAX - 1) * p;
      field.forEach((gl, i) => {
        const [dx, dy] = seenFrom(gl, cur, s, COLS, ROWS);
        const x = CX + dx * K, y = CY + dy * K, on = x > -8 && x < 488 && y > -8 && y < 308;
        set(dots[i], { cx: x, cy: y, transform: `rotate(${(i * 47) % 180} ${x.toFixed(1)} ${y.toFixed(1)})` }); dots[i].style.display = on ? '' : 'none';
        const len = Math.hypot(dx, dy) * K * 0.17;
        set(arrows[i], { d: on && len > 3 ? arrowPath(x, y, x + (dx / Math.hypot(dx, dy)) * len, y + (dy / Math.hypot(dx, dy)) * len, 4.5) : '' });
      });
      let d = '';
      for (let i = 0; i < COLS; i++) { const dx = seenFrom({ x: i - (COLS - 1) / 2, y: 0 }, cur, s, COLS, ROWS)[0]; const x = CX + dx * K; if (x > -2 && x < 482) d += `M${x.toFixed(1)} 0V300`; }
      for (let j = 0; j < ROWS; j++) { const dy = seenFrom({ x: 0, y: j - (ROWS - 1) / 2 }, cur, s, COLS, ROWS)[1]; const y = CY + dy * K; if (y > -2 && y < 302) d += `M0 ${y.toFixed(1)}H480`; }
      set(grid, { d });
      const x = fmt(s, 1);
      const read = s < 1.03
        ? 'Aqui o espaço ainda não cresceu. Role a página ou use os controles para mudar as distâncias. Toque numa galáxia para ver o Universo dali.'
        : `O espaço cresceu ${x}×. As setas mostram o afastamento: quanto mais longe a galáxia, maior a seta. Toque em outra galáxia (ou no botão) e veja que, neste desenho, o padrão é o mesmo de qualquer ponto.`;
      return { read, value: `${x}×`, aria: `Espaço ${x} vezes maior. Galáxias mais distantes se afastam mais depressa, de qualquer galáxia observadora.` };
    },
    dispose() { cancelAnimationFrame(anim); svgRef?.removeEventListener('click', onTap); }
  };
}

/* ───────────── 3. Diagrama de Hubble se montando ───────────── */
function hubbleScene(): SciScene {
  const data = hubbleSample(), N = data.length;
  const LX = 64, RX = 456, TY = 36, BY = 244, DMAX = 400, VMAX = 31500;
  const px = (d: number): number => LX + (d / DMAX) * (RX - LX);
  const py = (v: number): number => Math.max(TY + 4, BY - (v / VMAX) * (BY - TY));
  const dots: SVGCircleElement[] = [];
  let pulse!: SVGCircleElement, fit!: SVGLineElement, guide!: SVGPathElement, g1!: SVGTextElement, g2!: SVGTextElement;
  return {
    start: 0, steps: [0, 0.14, 0.36, 0.64, 1], sweep: { seconds: 8, mode: 'fill' },
    mount(svg) {
      let d = '';
      for (const f of [0.25, 0.5, 0.75, 1]) d += `M${px(DMAX * f).toFixed(1)} ${TY}V${BY}M${LX} ${py(VMAX * f).toFixed(1)}H${RX}`;
      el('path', { d, fill: 'none', stroke: C.line, 'stroke-width': 1, opacity: 0.6 }, svg);
      el('path', { d: `M${LX} ${TY - 6}V${BY}H${RX + 6}`, fill: 'none', stroke: C.ink2, 'stroke-width': 2.2, 'stroke-linecap': 'round' }, svg);
      el('path', { d: `M${LX - 5} ${TY + 2}L${LX} ${TY - 6}L${LX + 5} ${TY + 2}M${RX + 1} ${BY - 5}L${RX + 7} ${BY}L${RX + 1} ${BY + 5}`, fill: 'none', stroke: C.ink2, 'stroke-width': 2.2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
      label(svg, RX, 276, 'Distância →', 'mute', 'end');
      label(svg, LX + 12, 24, 'Rapidez ↑', 'mute');
      guide = el('path', { fill: 'none', stroke: C.accentInk, 'stroke-width': 1.8, 'stroke-dasharray': '5 5', opacity: 0 }, svg);
      fit = el('line', { stroke: C.accentInk, 'stroke-width': 3.2, 'stroke-linecap': 'round', opacity: 0 }, svg);
      g1 = label(svg, LX + 14, TY + 24, 'dobro da distância', 'warm strong');
      g2 = label(svg, LX + 14, TY + 48, '→ dobro da rapidez', 'warm strong');
      pulse = el('circle', { r: 5, fill: 'none', stroke: C.accentInk, 'stroke-width': 2.4, opacity: 0 }, svg);
      for (const pt of data) dots.push(el('circle', { cx: px(pt.mpc), cy: py(pt.kms), r: 5.2, fill: C.accent, stroke: C.surface, 'stroke-width': 1.6, opacity: 0 }, svg));
    },
    render(p) {
      const n = Math.min(N, Math.floor(p * N + 1e-9));
      dots.forEach((d, i) => set(d, { opacity: i < n ? 1 : 0 }));
      const f = n < N ? p * N - n : 1;
      if (n > 0 && n < N) set(pulse, { cx: px(data[n - 1].mpc), cy: py(data[n - 1].kms), r: 5 + 15 * f, opacity: 1 - f }); else set(pulse, { opacity: 0 });
      if (n >= 3) {
        const k = slopeThroughOrigin(data.slice(0, n)), dEnd = Math.min(DMAX, (VMAX * 0.98) / k);
        set(fit, { x1: px(0), y1: py(0), x2: px(dEnd), y2: py(k * dEnd), opacity: clamp((n - 2) / 5) });
        const a = clamp((n - 14) / 4);
        set(guide, { d: `M${px(100)} ${BY}V${py(k * 100)}H${LX}M${px(200)} ${BY}V${py(k * 200)}H${LX}`, opacity: a * 0.9 });
        set(g1, { opacity: a }); set(g2, { opacity: a });
      } else { set(fit, { opacity: 0 }); set(guide, { opacity: 0 }); set(g1, { opacity: 0 }); set(g2, { opacity: 0 }); }
      let read: string;
      if (n === 0) read = 'Cada ponto vai ser uma galáxia: quanto mais à direita, mais longe ela está; quanto mais alto, mais depressa se afasta. Aperte "Reproduzir" para medir uma a uma.';
      else if (n < 8) read = `${n} ${plural(n, 'galáxia simulada', 'galáxias simuladas')}. Por enquanto parece só um monte de pontos soltos.`;
      else if (n < 17) read = `${n} galáxias simuladas. Um padrão começa a aparecer: as mais distantes estão mais acima.`;
      else read = `${n} galáxias simuladas. Nesta ilustração, os pontos seguem uma reta: ao dobrar a distância, dobra a rapidez. Um padrão semelhante nas observações ajudou a descobrir a expansão do Universo.`;
      return { read, value: `${n} de ${N}`, aria: `${n} de ${N} galáxias simuladas.` };
    }
  };
}

/* ───────────── 4. A luz do começo esfriando ───────────── */
function frioScene(): SciScene {
  const X0 = 24, X1 = 456, TOP = 128, BASE = 250, LMIN = 300, LMAX = 3e6;
  const lx = (nm: number): number => X0 + ((Math.log10(nm) - Math.log10(LMIN)) / (Math.log10(LMAX) - Math.log10(LMIN))) * (X1 - X0);
  let core!: SVGCircleElement, halo!: SVGCircleElement, curve!: SVGPathElement, area!: SVGPathElement, peak!: SVGCircleElement, peakLine!: SVGLineElement, big!: SVGTextElement, sub!: SVGTextElement;
  let stopA!: SVGStopElement, stopB!: SVGStopElement;
  const bandIn = (nm: number): string => (nm < VISIBLE_MIN_NM ? 'no ultravioleta' : nm <= VISIBLE_MAX_NM ? 'na luz visível' : nm < 1e6 ? 'no infravermelho' : 'nas micro-ondas');
  const colourWords = (k: number): string => (k < 1000 ? 'vermelha fraca' : k < 1800 ? 'vermelha' : k < 2500 ? 'laranja' : k < 3500 ? 'laranja-clara' : k < 5500 ? 'amarelada' : 'branca');
  const temp = (k: number): string => {
    const c = k - KELVIN_TO_C;
    return `${fmt(k > 1000 ? Math.round(c / 50) * 50 : Math.round(c))}\u00a0°C`;
  };
  return {
    start: 0, steps: [0, 0.3, 0.55, 0.8, 1], sweep: { seconds: 6, mode: 'bounce' },
    mount(svg) {
      const defs = el('defs', {}, svg);
      const glow = el('radialGradient', { id: 'sci-frio-glow' }, defs);
      stopA = el('stop', { offset: 0, 'stop-color': '#ffb070', 'stop-opacity': 0.95 }, glow);
      stopB = el('stop', { offset: 1, 'stop-color': '#ffb070', 'stop-opacity': 0 }, glow);
      const rain = el('linearGradient', { id: 'sci-frio-rainbow', x1: 0, x2: 1, y1: 0, y2: 0 }, defs);
      for (let i = 0; i <= 10; i++) el('stop', { offset: i / 10, 'stop-color': rgb(wavelengthRgb(VISIBLE_MIN_NM + ((VISIBLE_MAX_NM - VISIBLE_MIN_NM) * i) / 10)) }, rain);
      halo = el('circle', { cx: 52, cy: 58, r: 50, fill: 'url(#sci-frio-glow)' }, svg);
      core = el('circle', { cx: 52, cy: 58, r: 27 }, svg);
      big = label(svg, 108, 54, '', 'big');
      sub = label(svg, 108, 84, '', 'mute');
      el('path', { d: `M${X0} ${BASE}H${X1}`, stroke: C.ink2, 'stroke-width': 2.2, 'stroke-linecap': 'round' }, svg);
      area = el('path', { fill: C.accent, opacity: 0.22 }, svg);
      curve = el('path', { fill: 'none', stroke: C.accentInk, 'stroke-width': 3.4, 'stroke-linejoin': 'round' }, svg);
      peakLine = el('line', { y2: BASE, stroke: C.accentInk, 'stroke-width': 1.6, 'stroke-dasharray': '4 4', opacity: 0.8 }, svg);
      peak = el('circle', { r: 5.5, fill: C.accent, stroke: C.surface, 'stroke-width': 1.8 }, svg);
      el('rect', { x: lx(VISIBLE_MIN_NM), y: BASE + 4, width: lx(VISIBLE_MAX_NM) - lx(VISIBLE_MIN_NM), height: 10, rx: 2, fill: 'url(#sci-frio-rainbow)' }, svg);
      label(svg, lx(560), 288, 'visível', 'mute', 'middle');
      label(svg, lx(2e4), 288, 'infravermelho', 'mute', 'middle');
      label(svg, lx(1e6), 288, 'micro-ondas', 'mute', 'middle');
    },
    render(p) {
      const gr = growthAt(p), T = lightTemperatureK(gr), pk = peakNm(T), glow = visibleGlow(T);
      const [r, gg, b] = blackbodyRgb(T), col = `rgb(${r},${gg},${b})`;
      set(stopA, { 'stop-color': col, 'stop-opacity': 0.9 * glow }); set(stopB, { 'stop-color': col });
      set(halo, { opacity: glow });
      if (glow > 0.02) { core.style.fill = col; core.style.stroke = 'none'; set(core, { opacity: 0.25 + 0.75 * glow, 'stroke-dasharray': 'none' }); }
      else { core.style.fill = 'none'; core.style.stroke = 'var(--muted)'; set(core, { 'stroke-width': 2.4, 'stroke-dasharray': '3 6', opacity: 1 }); }
      big.textContent = temp(T);
      sub.textContent = glow > 0.02 ? `cor ${colourWords(T)}` : 'invisível aos olhos';
      const pts: [number, number][] = [];
      for (let i = 0; i <= 120; i++) { const nm = LMIN * Math.pow(LMAX / LMIN, i / 120); pts.push([lx(nm), BASE - (BASE - TOP - 8) * planckShape(nm, T)]); }
      const d = pathOf(pts);
      set(curve, { d }); set(area, { d: `${d}L${X1} ${BASE}L${X0} ${BASE}Z` });
      const peakX = lx(pk), peakY = BASE - (BASE - TOP - 8);
      set(peak, { cx: peakX, cy: peakY }); set(peakLine, { x1: peakX, x2: peakX, y1: peakY });
      const x = gr < 1.5 ? 'hoje' : `${fmt(Math.round(gr))}× mais quente`;
      let read: string;
      if (gr < 1.5) read = `Hoje a luz do começo está a ${temp(T)}, quase no zero absoluto. A parte mais forte da curva está ${bandIn(pk)}: invisível aos olhos. Mova a barra para voltar no tempo.`;
      else if (gr > 900) read = `Quando essa luz se soltou, estava a uns ${temp(T)}: brilhava com cor ${colourWords(T)}. Desde então o espaço cresceu cerca de ${fmt(gr > 1000 ? 1100 : Math.round(gr))}× e a luz esfriou na mesma proporção.`;
      else read = `Voltando no tempo, a luz era ${x}: ${temp(T)}. O pico da curva está ${bandIn(pk)}${glow > 0.02 ? `, e a cor já é ${colourWords(T)}` : ''}. O espaço esticou a luz, e ela foi esfriando.`;
      return { read, value: x, aria: `Luz do começo a ${temp(T)}; pico ${bandIn(pk)}.` };
    }
  };
}

/* ───────────── 5. Galáxia que gira rápido demais ───────────── */
function giroScene(): SciScene {
  const GX = 118, GY = 150, R = 100;
  const LX = 270, RX = 462, TY = 38, BY = 224, VMAX = 2;
  const rings = [0.12, 0.2, 0.3, 0.42, 0.55, 0.68, 0.8, 0.9, 1];
  const counts = [3, 4, 5, 6, 7, 8, 9, 10, 11];
  const speedScale = 0.14;
  const rx = (r: number): number => LX + r * (RX - LX);
  const vy = (v: number): number => BY - (v / VMAX) * (BY - TY);
  const stars: { el: SVGCircleElement; ring: number; a: number }[] = [];
  const dots: SVGCircleElement[] = [];
  let halo!: SVGCircleElement, haloLabel!: SVGTextElement, now!: SVGPathElement, last = 0;
  const curve = (dark: number): string => pathOf(Array.from({ length: 41 }, (_, i) => { const r = 0.04 + (0.96 * i) / 40; return [rx(r), vy(rotationSpeed(r, dark))] as [number, number]; }));
  return {
    start: 0, steps: [0, 0.25, 0.5, 0.75, 1], ambient: true, sweep: { seconds: 6, mode: 'bounce' },
    mount(svg) {
      const defs = el('defs', {}, svg);
      const hg = el('radialGradient', { id: 'sci-giro-halo' }, defs);
      el('stop', { offset: 0.35, 'stop-color': 'var(--accent)', 'stop-opacity': 0 }, hg);
      el('stop', { offset: 1, 'stop-color': 'var(--accent)', 'stop-opacity': 0.34 }, hg);
      const dg = el('radialGradient', { id: 'sci-giro-disc' }, defs);
      el('stop', { offset: 0, 'stop-color': 'var(--ink-2)', 'stop-opacity': 0.28 }, dg);
      el('stop', { offset: 1, 'stop-color': 'var(--ink-2)', 'stop-opacity': 0 }, dg);
      halo = el('circle', { cx: GX, cy: GY, r: R + 12, fill: 'url(#sci-giro-halo)', stroke: C.accentInk, 'stroke-width': 2, 'stroke-dasharray': '4 6' }, svg);
      haloLabel = label(svg, GX, 28, 'matéria escura', 'warm strong', 'middle');
      el('circle', { cx: GX, cy: GY, r: R, fill: 'url(#sci-giro-disc)' }, svg);
      rings.forEach((r) => el('circle', { cx: GX, cy: GY, r: r * R, fill: 'none', stroke: C.line, 'stroke-width': 1, opacity: 0.55 }, svg));
      el('circle', { cx: GX, cy: GY, r: 8, fill: C.ink }, svg);
      rings.forEach((_, ri) => { for (let k = 0; k < counts[ri]; k++) stars.push({ ring: ri, a: ((k + ((ri * 0.37) % 1)) / counts[ri]) * 2 * Math.PI, el: el('circle', { r: ri === rings.length - 1 && k === 0 ? 5 : 2.6, fill: ri === rings.length - 1 && k === 0 ? C.accentInk : C.ink2, opacity: 0.92 }, svg) }); });
      el('path', { d: `M${LX} ${TY - 6}V${BY}H${RX + 6}`, fill: 'none', stroke: C.ink2, 'stroke-width': 2.2, 'stroke-linecap': 'round' }, svg);
      label(svg, LX + 12, 24, 'Rapidez ↑', 'mute');
      label(svg, RX, 252, 'Centro → borda', 'mute', 'end');
      el('path', { d: curve(0), fill: 'none', stroke: C.muted, 'stroke-width': 2.4, 'stroke-dasharray': '6 6' }, svg);
      now = el('path', { fill: 'none', stroke: C.accentInk, 'stroke-width': 3.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
      rings.forEach(() => dots.push(el('circle', { r: 4.4, fill: C.accent, stroke: C.surface, 'stroke-width': 1.5 }, svg)));
    },
    render(p, time) {
      const dt = clamp(time - last, 0, 0.1); last = time;
      for (const s of stars) {
        s.a += angularSpeed(rings[s.ring], p) * speedScale * dt;
        set(s.el, { cx: GX + Math.cos(s.a) * rings[s.ring] * R, cy: GY + Math.sin(s.a) * rings[s.ring] * R });
      }
      set(halo, { opacity: p }); set(haloLabel, { opacity: clamp(p * 1.6) });
      set(now, { d: curve(p) });
      rings.forEach((r, i) => set(dots[i], { cx: rx(r), cy: vy(rotationSpeed(r, p)) }));
      const pct = Math.round(p * 100);
      let read: string;
      if (p < 0.04) read = 'Neste modelo, usando apenas estrelas e gás, a velocidade cai na borda. Aperte "Reproduzir" para comparar com o efeito de acrescentar matéria escura.';
      else if (p > 0.96) read = 'Neste modelo, a matéria escura mantém a velocidade alta na borda. Em muitas galáxias observadas, curvas de rotação mostram um comportamento semelhante.';
      else read = `Com ${pct}% do efeito ilustrativo da matéria escura, a velocidade na borda aumenta. A linha tracejada usa só matéria visível; a linha cheia mostra este modelo.`;
      return { read, value: `${pct}%`, aria: `Efeito ilustrativo da matéria escura em ${pct}%.` };
    }
  };
}

export const SCI_SCENES: Record<string, () => SciScene> = { luz: luzScene, expansao: expansaoScene, hubble: hubbleScene, frio: frioScene, giro: giroScene };
