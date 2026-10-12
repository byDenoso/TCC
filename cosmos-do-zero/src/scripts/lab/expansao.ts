import { animator, clear, fmt, initGuess, q, qa, reduced, svg } from './common';

/** Grade homogênea de galáxias. Unidade de distância = espaçamento da grade. */
const COLS = 21, ROWS = 15, GAP = 56;
const SCALE_MAX = 2.5;
const VIEW_W = 640, VIEW_H = 400;
interface G { i: number; col: number; row: number; x: number; y: number; node: SVGGElement; arrow: SVGLineElement; selectable: boolean }

export function initExpansao(root: HTMLElement): void {
  const stage = q<SVGSVGElement>(root, '[data-e-svg]');
  const plot = q<SVGSVGElement>(root, '[data-e-plot]');
  const range = q<HTMLInputElement>(root, '[data-e-range]');
  const out = q(root, '[data-e-scale]');
  const play = q<HTMLButtonElement>(root, '[data-e-play]');
  const arrowsToggle = q<HTMLInputElement>(root, '[data-e-arrows]');
  const reading = q(root, '[data-e-reading]');
  const live = q(root, '[data-e-live]');

  clear(stage);
  const defs = svg('defs', {}, stage);
  const rg = svg('radialGradient', { id: 'e-glow' }, defs);
  svg('stop', { offset: '0', style: 'stop-color: var(--glow-core)' }, rg);
  svg('stop', { offset: '.35', style: 'stop-color: var(--glow-mid); stop-opacity: .9' }, rg);
  svg('stop', { offset: '1', style: 'stop-color: var(--glow-mid); stop-opacity: 0' }, rg);
  const mg = svg('radialGradient', { id: 'e-fade' }, defs);
  svg('stop', { offset: '.55', 'stop-color': '#fff' }, mg);
  svg('stop', { offset: '1', 'stop-color': '#fff', 'stop-opacity': '0' }, mg);
  const mask = svg('mask', { id: 'e-mask' }, defs);
  svg('rect', { width: VIEW_W, height: VIEW_H, fill: 'url(#e-fade)' }, mask);
  const layer = svg('g', { mask: 'url(#e-mask)' }, stage);
  const arrowLayer = svg('g', { class: 'e-arrows' }, layer);
  const galaxyLayer = svg('g', {}, layer);
  const ring = svg('circle', { r: 17, class: 'e-observer-ring' }, stage);
  svg('text', { x: VIEW_W / 2, y: VIEW_H / 2 + 36, 'text-anchor': 'middle', class: 'obs-cap warm' }, stage, 'você, aqui');

  const gs: G[] = [];
  for (let row = 0; row < ROWS; row++) for (let col = 0; col < COLS; col++) {
    const x = (col - (COLS - 1) / 2) * GAP, y = (row - (ROWS - 1) / 2) * GAP;
    const selectable = Math.abs(col - (COLS - 1) / 2) <= 3 && Math.abs(row - (ROWS - 1) / 2) <= 2;
    const node = svg('g', { class: 'e-galaxy', ...(selectable ? { tabindex: 0, role: 'button', 'aria-label': `Morar na galáxia ${gs.length + 1}` } : { 'aria-hidden': 'true' }) }, galaxyLayer);
    svg('circle', { r: selectable ? 9 : 7, fill: 'url(#e-glow)' }, node);
    svg('circle', { r: 2.4, class: 'e-core' }, node);
    const arrow = svg('line', { class: 'e-arrow' }, arrowLayer);
    gs.push({ i: gs.length, col, row, x, y, node, arrow, selectable });
  }
  let obs = gs.find((g) => g.col === 10 && g.row === 7)!;
  const selectables = gs.filter((g) => g.selectable);

  // gráfico lei de Hubble (afastamento × distância inicial)
  const PW = 560, PH = 230, PL = 48, PB = 40, PT = 14, PR = 16;
  const maxD = 5; // em espaçamentos
  const maxY = (SCALE_MAX - 1) * maxD;
  clear(plot);
  svg('line', { x1: PL, y1: PH - PB, x2: PW - PR, y2: PH - PB, class: 'obs-axis' }, plot);
  svg('line', { x1: PL, y1: PT, x2: PL, y2: PH - PB, class: 'obs-axis' }, plot);
  svg('text', { x: (PL + PW - PR) / 2, y: PH - 6, 'text-anchor': 'middle', class: 'obs-cap small' }, plot, 'distância antes');
  svg('text', { x: 10, y: (PT + PH - PB) / 2, 'text-anchor': 'middle', class: 'obs-cap small', transform: `rotate(-90 10 ${(PT + PH - PB) / 2})` }, plot, 'quanto se afastou');
  const px = (d: number) => PL + (d / maxD) * (PW - PL - PR);
  const py = (v: number) => PH - PB - (v / maxY) * (PH - PB - PT);
  const fit = svg('line', { class: 'e-fit' }, plot);
  const dots = new Map<number, SVGCircleElement>();
  for (const g of gs) dots.set(g.i, svg('circle', { r: 2.2, class: 'e-dot' }, plot));

  const place = (scale: number): void => {
    for (const g of gs) {
      const dx = g.x - obs.x, dy = g.y - obs.y;
      const sx = VIEW_W / 2 + dx * scale, sy = VIEW_H / 2 + dy * scale;
      g.node.setAttribute('transform', `translate(${sx.toFixed(2)} ${sy.toFixed(2)})`);
      g.node.classList.toggle('is-observer', g === obs);
      if (g.selectable) g.node.setAttribute('aria-pressed', String(g === obs));
      const d0 = Math.hypot(dx, dy) / GAP;
      const show = arrowsToggle.checked && d0 > 0 && d0 <= 4.2 && scale > 1.01;
      g.arrow.style.display = show ? '' : 'none';
      if (show) {
        const k = scale - 1; // deslocamento acumulado, em unidades da distância inicial
        g.arrow.setAttribute('x1', (VIEW_W / 2 + dx * 1).toFixed(2)); g.arrow.setAttribute('y1', (VIEW_H / 2 + dy * 1).toFixed(2));
        g.arrow.setAttribute('x2', (VIEW_W / 2 + dx * (1 + k)).toFixed(2)); g.arrow.setAttribute('y2', (VIEW_H / 2 + dy * (1 + k)).toFixed(2));
      }
    }
    ring.setAttribute('cx', String(VIEW_W / 2)); ring.setAttribute('cy', String(VIEW_H / 2));
    for (const [i, c] of dots) { const g = gs[i]; const d0 = Math.hypot(g.x - obs.x, g.y - obs.y) / GAP; c.setAttribute('cx', px(Math.min(maxD, d0)).toFixed(1)); c.setAttribute('cy', py((scale - 1) * Math.min(maxD, d0)).toFixed(1)); c.style.display = d0 <= maxD && d0 > 0 ? '' : 'none'; }
    fit.setAttribute('x1', String(px(0))); fit.setAttribute('y1', String(py(0))); fit.setAttribute('x2', String(px(maxD))); fit.setAttribute('y2', String(py((scale - 1) * maxD)));
  };

  const render = (): void => {
    const s = Number(range.value);
    out.textContent = `${fmt(s, 2)} ×`;
    place(s);
    const near = 1, far = 4, k = s - 1;
    reading.innerHTML = '';
    const li = (t: string) => { const p = document.createElement('p'); p.textContent = t; reading.append(p); };
    if (k < 0.005) li('Mexa no controle ou aperte o botão: o espaço entre as galáxias vai crescer.');
    else {
      li(`A galáxia vizinha estava a ${near} passo de você. Agora está a ${fmt(near * s, 1)}: afastou-se ${fmt(k * near, 1)}.`);
      li(`Uma que estava a ${far} passos agora está a ${fmt(far * s, 1)}: afastou-se ${fmt(k * far, 1)}, ou seja, ${far} vezes mais.`);
      li('Quanto mais longe, mais ela se afasta, sempre na mesma proporção. Os astrônomos chamam isso de lei de Hubble.');
    }
    live.textContent = `O espaço cresceu ${fmt(s, 2)} vezes. Você está na galáxia ${obs.i + 1}. ${k < 0.005 ? 'Nada se afastou ainda.' : `Quem estava a ${far} passos afastou-se ${fmt(k * far, 1)}; quem estava a ${near}, ${fmt(k * near, 1)}.`}`;
  };

  const choose = (g: G): void => { if (!g.selectable) return; obs = g; render(); };
  for (const g of selectables) {
    g.node.addEventListener('click', () => choose(g));
    g.node.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(g); } });
  }
  range.addEventListener('input', () => { anim.stop(); syncPlay(); render(); });
  arrowsToggle.addEventListener('change', render);

  const syncPlay = () => { play.setAttribute('aria-pressed', String(anim.running())); play.textContent = anim.running() ? 'Pausar' : Number(range.value) >= SCALE_MAX - 0.001 ? 'Recomeçar' : 'Deixar o espaço crescer'; };
  const anim = animator(root, (dt) => { const next = Math.min(SCALE_MAX, Number(range.value) + dt * 0.00022); range.value = String(next); render(); const more = next < SCALE_MAX; if (!more) queueMicrotask(syncPlay); return more; });
  play.addEventListener('click', () => {
    if (anim.running()) { anim.stop(); syncPlay(); return; }
    if (reduced()) { range.value = Number(range.value) >= SCALE_MAX - 0.001 ? '1' : String(SCALE_MAX); render(); syncPlay(); return; }
    if (Number(range.value) >= SCALE_MAX - 0.001) range.value = '1';
    anim.start(); syncPlay();
  });
  qa<HTMLButtonElement>(root, '[data-e-reset]').forEach((b) => b.addEventListener('click', () => { anim.stop(); range.value = '1'; obs = gs.find((g) => g.col === 10 && g.row === 7)!; render(); syncPlay(); }));
  initGuess(root);
  render(); syncPlay();
}
