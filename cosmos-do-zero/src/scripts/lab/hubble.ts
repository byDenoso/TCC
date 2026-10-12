import { C_KMS, HALPHA_NM, fitHubble } from '../../lib/cosmology';
import { clear, fmt, fmtAuto, initGuess, q, rng, svg } from './common';

const N = 16;
const SIGMA_V = 250; // km/s, movimento próprio típico de galáxias
const SIGMA_D = 0.07; // erro relativo da distância por supernova Ia
const W = 640, H = 400;
interface Gal { id: number; x: number; y: number; d: number; v: number; dm: number; node?: SVGGElement; done: boolean }

export function initHubble(root: HTMLElement): void {
  const sky = q<SVGSVGElement>(root, '[data-h-sky]');
  const plot = q<SVGSVGElement>(root, '[data-h-plot]');
  const spec = q<SVGSVGElement>(root, '[data-h-spec]');
  const reading = q(root, '[data-h-reading]');
  const result = q(root, '[data-h-result]');
  const live = q(root, '[data-h-live]');
  const nextBtn = q<HTMLButtonElement>(root, '[data-h-next]');
  const allBtn = q<HTMLButtonElement>(root, '[data-h-all]');
  const newBtn = q<HTMLButtonElement>(root, '[data-h-new]');
  const revealBtn = q<HTMLButtonElement>(root, '[data-h-reveal]');
  let seed = 11, gals: Gal[] = [], trueH0 = 70, selected: Gal | null = null, revealed = false, lastCount = 0;

  const make = (): void => {
    const r = rng(seed);
    trueH0 = 66 + 8 * r.next();
    gals = [];
    let guard = 0;
    while (gals.length < N && guard++ < 4000) {
      const x = 48 + r.next() * (W - 96), y = 44 + r.next() * (H - 88);
      if (gals.some((g) => Math.hypot(g.x - x, g.y - y) < 62)) continue;
      const d = 18 + r.next() * 312; // Mpc
      const v = trueH0 * d + SIGMA_V * r.gauss();
      gals.push({ id: gals.length + 1, x, y, d, v, dm: d * (1 + SIGMA_D * r.gauss()), done: false });
    }
    selected = null; revealed = false;
    drawSky(); render();
  };

  const drawSky = (): void => {
    clear(sky);
    const defs = svg('defs', {}, sky);
    const g = svg('radialGradient', { id: 'h-glow' }, defs);
    svg('stop', { offset: '0', style: 'stop-color: var(--glow-core)' }, g); svg('stop', { offset: '.4', style: 'stop-color: var(--glow-mid); stop-opacity: .55' }, g); svg('stop', { offset: '1', style: 'stop-color: var(--glow-mid); stop-opacity: 0' }, g);
    const r = rng(seed + 99);
    for (let i = 0; i < 70; i++) svg('circle', { cx: r.next() * W, cy: r.next() * H, r: 0.5 + r.next() * 0.9, class: 'h-star' }, sky);
    for (const gal of gals) {
      const n = svg('g', { class: 'h-gal', transform: `translate(${gal.x.toFixed(1)} ${gal.y.toFixed(1)})`, tabindex: 0, role: 'button', 'aria-label': `Galáxia ${gal.id}` }, sky);
      svg('circle', { r: 22, fill: 'url(#h-glow)' }, n);
      svg('ellipse', { rx: 11, ry: 4.5, class: 'h-body', transform: `rotate(${(gal.id * 37) % 180})` }, n);
      svg('circle', { r: 17, class: 'h-ring' }, n);
      svg('text', { y: 34, 'text-anchor': 'middle', class: 'obs-cap small' }, n, String(gal.id));
      n.addEventListener('click', () => select(gal));
      n.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(gal); } });
      gal.node = n;
    }
  };

  const select = (g: Gal): void => { selected = g; g.done = true; render(); };

  // gráfico
  const PW = 640, PH = 380, PL = 70, PB = 54, PT = 16, PR = 20, DMAX = 350, VMAX = 27000;
  const px = (d: number) => PL + (d / DMAX) * (PW - PL - PR);
  const py = (v: number) => PH - PB - (v / VMAX) * (PH - PB - PT);
  const drawPlot = (): void => {
    clear(plot);
    svg('line', { x1: PL, y1: PH - PB, x2: PW - PR, y2: PH - PB, class: 'obs-axis' }, plot);
    svg('line', { x1: PL, y1: PT, x2: PL, y2: PH - PB, class: 'obs-axis' }, plot);
    for (const ly of [300, 600, 900]) { const d = ly / 3.261564; svg('line', { x1: px(d), x2: px(d), y1: PH - PB, y2: PH - PB + 5, class: 'obs-tick' }, plot); svg('text', { x: px(d), y: PH - PB + 20, 'text-anchor': 'middle', class: 'obs-cap small' }, plot, String(ly)); }
    for (const v of [10000, 20000]) { svg('line', { x1: PL - 5, x2: PL, y1: py(v), y2: py(v), class: 'obs-tick' }, plot); svg('text', { x: PL - 8, y: py(v) + 4, 'text-anchor': 'end', class: 'obs-cap small' }, plot, (v / 1000).toFixed(0) + ' mil'); }
    svg('text', { x: (PL + PW - PR) / 2, y: PH - 4, 'text-anchor': 'middle', class: 'obs-cap small' }, plot, 'distância (milhões de anos-luz)');
    svg('text', { x: 12, y: (PT + PH - PB) / 2, 'text-anchor': 'middle', class: 'obs-cap small', transform: `rotate(-90 12 ${(PT + PH - PB) / 2})` }, plot, 'velocidade (km por segundo)');
    const pts = gals.filter((g) => g.done).map((g) => ({ d: g.dm, v: g.v, id: g.id }));
    if (revealed) svg('line', { x1: px(0), y1: py(0), x2: px(DMAX), y2: py(trueH0 * DMAX), class: 'h-true' }, plot);
    const f = fitHubble(pts);
    if (f) svg('line', { x1: px(0), y1: py(0), x2: px(DMAX), y2: py(f.h0 * DMAX), class: pts.length !== lastCount ? 'h-fit is-draw' : 'h-fit', pathLength: 1 }, plot);
    for (const p of pts) svg('circle', { cx: px(p.d), cy: py(p.v), r: p.id === selected?.id ? 5.5 : 3.8, class: `h-pt${p.id === selected?.id ? ' sel' : ''}${p.id === selected?.id && pts.length !== lastCount ? ' is-new' : ''}` }, plot);
    lastCount = pts.length;
  };

  const drawSpec = (g: Gal | null): void => {
    clear(spec);
    const X0 = 24, X1 = 536, lo = 640, hi = 730;
    const x = (nm: number) => X0 + ((nm - lo) / (hi - lo)) * (X1 - X0);
    svg('rect', { x: X0, y: 24, width: X1 - X0, height: 28, class: 'obs-spectrum dark' }, spec);
    svg('text', { x: X0, y: 74, class: 'obs-cap small' }, spec, '← mais azulada'); svg('text', { x: X1, y: 74, 'text-anchor': 'end', class: 'obs-cap small' }, spec, 'mais avermelhada →');
    svg('line', { x1: x(HALPHA_NM), x2: x(HALPHA_NM), y1: 20, y2: 56, class: 'h-line rest' }, spec);
    svg('text', { x: x(HALPHA_NM), y: 13, 'text-anchor': 'middle', class: 'obs-cap small' }, spec, 'no laboratório');
    if (g) {
      const lam = HALPHA_NM * (1 + g.v / C_KMS);
      svg('line', { x1: x(lam), x2: x(lam), y1: 20, y2: 56, class: 'h-line seen' }, spec);
      svg('text', { x: Math.min(X1 - 40, Math.max(X0 + 40, x(lam))), y: 13, 'text-anchor': 'middle', class: 'obs-cap small warm' }, spec, 'nesta galáxia');
    }
  };

  const render = (): void => {
    const done = gals.filter((g) => g.done);
    for (const g of gals) {
      g.node?.classList.toggle('is-done', g.done);
      g.node?.classList.toggle('is-selected', g === selected);
      g.node?.setAttribute('aria-label', `Galáxia ${g.id}${g.done ? ', medida' : ', ainda não medida'}${g === selected ? ', selecionada' : ''}`);
    }
    reading.replaceChildren();
    const add = (label: string, value: string) => { const row = document.createElement('div'); const dt = document.createElement('dt'); dt.textContent = label; const dd = document.createElement('dd'); dd.textContent = value; row.append(dt, dd); reading.append(row); };
    if (selected) {
      const z = selected.v / C_KMS;
      add('Galáxia', `nº ${selected.id}`);
      add('Distância', `${fmt(selected.dm * 3.261564, 0)} milhões de anos-luz`);
      add('A cor da luz', z < 0.02 ? 'chega um pouquinho mais avermelhada' : z < 0.05 ? 'chega um pouco mais avermelhada' : 'chega bem mais avermelhada');
      add('Velocidade de afastamento', `${fmtAuto(selected.v)} km por segundo`);
    } else add('Como medir', 'Toque numa galáxia: o telescópio mede a distância e a velocidade dela.');
    drawSpec(selected);
    drawPlot();
    if (done.length >= 8) root.dispatchEvent(new CustomEvent('cosmos:badge', { bubbles: true, detail: { id: 'hubble' } }));
    const f = fitHubble(done.map((g) => ({ d: g.dm, v: g.v })));
    nextBtn.disabled = allBtn.disabled = done.length >= N;
    revealBtn.hidden = done.length < 6 || revealed;
    if (!f) { result.textContent = done.length ? 'Meça pelo menos mais uma galáxia para traçar a reta.' : 'Nenhuma medida ainda.'; live.textContent = `${done.length} de ${N} galáxias medidas.`; return; }
    const perMly = (h: number) => fmt(h / 3.261564, 0);
    result.innerHTML = '';
    const big = document.createElement('p'); big.className = 'h-big'; big.textContent = `Cerca de ${perMly(f.h0)} km/s mais rápido a cada milhão de anos-luz`;
    const small = document.createElement('p');
    small.textContent = `Você mediu ${done.length} de ${N} galáxias. Quanto mais longe, mais rápido elas fogem, sempre na mesma proporção. Esse é o ritmo em que o Universo cresce hoje, e foi com medidas assim que descobrimos que ele tem uns 14 bilhões de anos.`;
    result.append(big, small);
    if (revealed) { const r = document.createElement('p'); r.className = 'h-reveal'; r.textContent = `O valor certo do jogo era ${perMly(trueH0)}. A pequena diferença vem dos erros de medida e do vaivém próprio de cada galáxia, que atrapalha mais nas mais próximas.`; result.append(r); }
    live.textContent = `${done.length} de ${N} galáxias medidas. Ritmo medido: ${perMly(f.h0)} quilômetros por segundo a mais a cada milhão de anos-luz.`;
  };

  nextBtn.addEventListener('click', () => { const g = gals.find((x) => !x.done); if (g) select(g); });
  allBtn.addEventListener('click', () => { gals.forEach((g) => (g.done = true)); selected = gals[gals.length - 1]; render(); });
  newBtn.addEventListener('click', () => { seed++; make(); });
  revealBtn.addEventListener('click', () => { revealed = true; render(); });
  initGuess(root);
  make();
}
