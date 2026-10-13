import { PLANCK, ageAtRedshift, ageNow, cmbTemperature, comovingMpc, densityFractions, lookbackGyr, observedWavelengthNm, zAcceleration } from '../../lib/cosmology';
import { clear, duration, fmt, fmtAuto, initGuess, lightYears, q, qa, reduced, svg } from './common';
import { getParam, setParams } from '../../lib/url-state';
import type { Tempo3D } from './tempo3d';

const Z_MAX = 1100;
const LN = Math.log(1 + Z_MAX);
const zOf = (p: number): number => Math.expm1((p / 1000) * LN);
const pOf = (z: number): number => Math.round((Math.log1p(z) / LN) * 1000);

function band(nm: number): string {
  if (nm < 750) return 'ainda vermelha, um pouco mais escura';
  if (nm < 5000) return 'infravermelho (invisível aos nossos olhos)';
  if (nm < 1e6) return 'infravermelho distante (invisível)';
  return 'micro-ondas';
}
const bandShort = (nm: number): string => (nm < 750 ? 'vermelho' : nm < 1e6 ? 'infravermelho' : 'micro-ondas');
function tempNote(k: number): string {
  if (k < 10) return 'frio extremo, perto do mais frio possível';
  if (k < 250) return 'mais frio que um freezer';
  if (k < 320) return 'como um dia comum aqui na Terra';
  if (k < 1000) return 'quente como um forno';
  if (k < 2500) return 'quente como brasa';
  return 'quente como a superfície de uma estrela fria (o Sol é mais quente)';
}

interface Epoch { from: number; title: string; kind: 'Observado' | 'Calculado pelo modelo'; text: (z: number) => string }
const epochs: Epoch[] = [
  { from: 3400, title: 'Quente demais para existir átomo', kind: 'Calculado pelo modelo', text: () => 'Tudo é uma sopa muito quente de partículas e luz. Nesta fase a luz pesa mais que a matéria. Isso muda por volta dos 50 mil anos de idade.' },
  { from: 1200, title: 'Uma névoa que não deixa a luz passar', kind: 'Calculado pelo modelo', text: () => 'Ainda quente demais para os átomos se formarem. A luz bate o tempo todo nas partículas soltas, como farol na neblina: não dá para enxergar através.' },
  { from: 900, title: 'O Universo fica transparente', kind: 'Observado', text: () => 'Os primeiros átomos se formam e a névoa se dissipa. A luz desse instante viaja até hoje e chega até nós: é a luz mais antiga que conseguimos observar diretamente. Antes disso já havia luz, mas ela não conseguia viajar longe. Saiu de um gás a uns 3.000 K (cerca de 2.700 °C), com a maior parte no infravermelho próximo; o comprimento de onda cresceu umas 1.100 vezes com a expansão, e hoje ela chega como micro-ondas.' },
  { from: 30, title: 'Idade das trevas', kind: 'Calculado pelo modelo', text: () => 'Ainda não existe nenhuma estrela. O gás esfria e a gravidade começa a juntar matéria em montinhos, que vão virar as primeiras galáxias.' },
  { from: 6, title: 'As primeiras estrelas e galáxias se acendem', kind: 'Observado', text: () => 'Surgem as primeiras estrelas e galáxias. O telescópio espacial James Webb já fotografou galáxias desta época.' },
  { from: 3, title: 'As galáxias crescem', kind: 'Observado', text: (z) => `O Universo tinha ${duration(ageAtRedshift(z, PLANCK))}. As galáxias juntam gás e formam muitas estrelas. O auge desse ritmo ainda vem depois, quando o Universo tem cerca de 3 bilhões de anos.` },
  { from: 1.5, title: 'Perto do auge da formação de estrelas', kind: 'Observado', text: (z) => `O Universo tinha ${duration(ageAtRedshift(z, PLANCK))}. Estamos perto da época em que as galáxias, juntas, formaram estrelas no ritmo mais intenso: o auge fica por volta de 3 bilhões de anos, e não acontece de uma vez em todas as galáxias.` },
  { from: zAcceleration(PLANCK), title: 'Depois do auge da formação de estrelas', kind: 'Observado', text: (z) => `O Universo tinha ${duration(ageAtRedshift(z, PLANCK))}. As galáxias continuam formando estrelas, mas o ritmo médio já caiu em relação ao auge, por volta de 3 bilhões de anos. No modelo usado aqui, a expansão ainda está freando; a aceleração começa mais tarde.` },
  { from: 0.02, title: 'Galáxias em um Universo que acelera', kind: 'Calculado pelo modelo', text: (z) => `O Universo tinha ${duration(ageAtRedshift(z, PLANCK))}. O auge da formação de estrelas já passou, mas novas estrelas continuam nascendo. Nesta época a expansão já acelera. Chamamos de "energia escura" o que explica essa aceleração no modelo, mas ainda não sabemos o que ela é.` },
  { from: 0, title: 'Nossa vizinhança', kind: 'Observado', text: () => 'Aqui a luz leva pouco tempo e a expansão quase não aparece. As galáxias vizinhas se movem mais por causa da gravidade umas das outras: Andrômeda, por exemplo, está vindo na nossa direção.' }
];
const epochFor = (z: number): Epoch => epochs.find((e) => z >= e.from) ?? epochs[epochs.length - 1];

export function initTempo(root: HTMLElement): void {
  const range = q<HTMLInputElement>(root, '[data-t-range]');
  const zOut = q(root, '[data-t-z]');
  const svgEl = q<SVGSVGElement>(root, '[data-t-svg]');
  const live = q(root, '[data-t-live]');
  const out = Object.fromEntries(qa(root, '[data-t-out]').map((n) => [n.dataset.tOut!, n])) as Record<string, HTMLElement>;
  const mix = qa(root, '[data-t-mix] span');
  const presets = qa<HTMLButtonElement>(root, '[data-t-preset]');
  const epochBox = q(root, '[data-t-epoch]');
  const age0 = ageNow(PLANCK);

  // ── desenho estático (eixos) ──
  const trackX = 30, trackW = 580, trackY = 70;
  clear(svgEl);
  svg('text', { x: trackX, y: 22, class: 'obs-cap' }, svgEl, 'Do início até hoje · 13,8 bilhões de anos');
  svg('rect', { x: trackX, y: trackY, width: trackW, height: 14, rx: 2, class: 'obs-track' }, svgEl);
  const travel = svg('rect', { x: trackX, y: trackY, width: 0, height: 14, rx: 2, class: 'obs-travel' }, svgEl);
  const pin = svg('g', { class: 'obs-pin' }, svgEl);
  svg('path', { d: 'M0 0 L-7 -12 H7 Z', class: 'obs-pinhead' }, pin);
  const pinText = svg('text', { y: -19, 'text-anchor': 'middle', class: 'obs-cap strong' }, pin, 'a luz sai');
  svg('text', { x: trackX, y: 126, class: 'obs-cap' }, svgEl, 'Início');
  svg('text', { x: trackX + trackW, y: 126, 'text-anchor': 'end', class: 'obs-cap' }, svgEl, 'Hoje');
  // sob o trecho percorrido, numa linha própria para não encostar em Início/Hoje
  const travelLabel = svg('text', { y: 104, 'text-anchor': 'middle', class: 'obs-cap warm' }, svgEl, '');

  // duas janelas: o mesmo pedaço de espaço quando a luz saiu e hoje. A grade é o próprio espaço;
  // a onda acompanha a grade. Na tela o crescimento é comprimido (até ×6); o valor real aparece no texto.
  const winY = 168, winW = 278, winH = 168, winL = 30, winR = 332;
  const uid = Math.random().toString(36).slice(2, 7);
  const defs = svg('defs', {}, svgEl);
  for (const [k, x] of [['l', winL], ['r', winR]] as const) {
    const cp = svg('clipPath', { id: `win-${k}-${uid}` }, defs);
    svg('rect', { x, y: winY, width: winW, height: winH, rx: 10 }, cp);
  }
  const winsG = svg('g', { class: 'obs-wins' }, svgEl);
  const winTitleL = svg('text', { x: winL, y: winY - 12, class: 'obs-cap strong' }, winsG, 'Lá, quando a luz saiu');
  svg('text', { x: winR, y: winY - 12, class: 'obs-cap strong' }, winsG, 'Aqui, hoje');
  const winL_g = svg('g', { 'clip-path': `url(#win-l-${uid})` }, winsG);
  const winR_g = svg('g', { 'clip-path': `url(#win-r-${uid})` }, winsG);
  svg('rect', { x: winL, y: winY, width: winW, height: winH, rx: 10, class: 'obs-win' }, winsG);
  svg('rect', { x: winR, y: winY, width: winW, height: winH, rx: 10, class: 'obs-win' }, winsG);
  const capL = svg('text', { x: winL, y: winY + winH + 24, class: 'obs-cap' }, winsG, '');
  const capR = svg('text', { x: winR, y: winY + winH + 24, class: 'obs-cap warm' }, winsG, '');
  const capR2 = svg('text', { x: winR, y: winY + winH + 44, class: 'obs-cap small' }, winsG, '');
  const note = svg('text', { x: 30, y: winY + winH + 72, class: 'obs-cap small' }, winsG, '');
  void winTitleL;
  const nodes: [number, number][] = [[-3, -1], [-1, 1], [1, -1], [2, 1], [-2, 0], [0, 2], [3, -2], [4, 0], [-4, 2], [5, 1], [-5, -2], [0, -2], [6, -1]];
  const drawWindow = (gEl: SVGGElement, x0: number, cell: number, lam: number, color: string, dashed: boolean): void => {
    clear(gEl);
    const cx = x0 + winW / 2, cy = winY + winH / 2;
    let d = '';
    for (let x = cx - Math.ceil(winW / 2 / cell) * cell; x <= x0 + winW; x += cell) d += `M${x.toFixed(1)} ${winY}V${winY + winH}`;
    for (let y = cy - Math.ceil(winH / 2 / cell) * cell; y <= winY + winH; y += cell) d += `M${x0} ${y.toFixed(1)}H${x0 + winW}`;
    svg('path', { d, class: 'obs-grid-line' }, gEl);
    for (const [i, j] of nodes) svg('circle', { cx: cx + i * cell, cy: cy + j * cell, r: 3.2, class: 'obs-gal' }, gEl);
    let w = '';
    for (let x = x0; x <= x0 + winW; x += 1.5) w += `${w ? 'L' : 'M'}${x.toFixed(1)} ${(cy - 18 * Math.sin(((x - x0) / lam) * Math.PI * 2)).toFixed(1)}`;
    const wave = svg('path', { d: w, fill: 'none', 'stroke-width': 3, 'stroke-linecap': 'round', class: dashed ? 'obs-wave invisible' : 'obs-wave' }, gEl);
    wave.style.stroke = color;
  };

  // cena 3D (Three.js) quando há WebGL e sem movimento reduzido; o SVG das janelas fica como alternativa
  const host3d = root.querySelector<HTMLElement>('[data-t-3d]');
  const note3d = root.querySelector<HTMLElement>('[data-t-3d-note]');
  let view3d: Tempo3D | null = null;
  const use2d = () => { if (host3d) host3d.hidden = true; if (note3d) note3d.hidden = true; winsG.removeAttribute('display'); svgEl.setAttribute('viewBox', '0 0 640 420'); };
  if (host3d && !reduced()) {
    import('./tempo3d').then((m) => m.mountTempo3D(host3d, reduced)).then((v) => {
      if (!v) return;
      view3d = v; host3d.hidden = false; if (note3d) note3d.hidden = false;
      winsG.setAttribute('display', 'none'); svgEl.setAttribute('viewBox', '0 0 640 134');
      host3d.addEventListener('obs3d:lost', () => { view3d?.dispose(); view3d = null; use2d(); }, { once: true });
      render();
    }).catch(() => use2d());
  }
  matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
    if (e.matches) { view3d?.dispose(); view3d = null; use2d(); }
  });
  let exact: number | null = null;
  const render = (): void => {
    const z = exact ?? zOf(Number(range.value));
    const ageThen = ageAtRedshift(z, PLANCK);
    const look = lookbackGyr(z, PLANCK);
    const dc = comovingMpc(z, PLANCK);
    const T = cmbTemperature(z);
    const lam = observedWavelengthNm(z);
    const f = densityFractions(z, PLANCK);

    zOut.textContent = z < 0.005 ? 'agora' : `há ${duration(look)}`;
    range.setAttribute('aria-valuetext', z < 0.005 ? 'agora' : `luz que saiu há ${duration(look)}, quando o Universo tinha ${duration(ageThen)}`);
    out.age.textContent = z < 0.005 ? '13,8 bilhões de anos (hoje)' : z > 800 ? `${duration(ageThen)} (aproximado: o valor muda um pouco com o modelo; costuma-se dizer uns 380 mil)` : duration(ageThen);
    out.look.textContent = z < 0.005 ? 'nenhum: luz de agora' : duration(look);
    out.dnow.textContent = z < 0.005 ? 'aqui perto' : `a ${lightYears(dc)}`;
    out.size.textContent = z < 0.005 ? 'iguais às de hoje' : `${fmtAuto(1 + z)} vezes menores`;
    const C = T - 273.15;
    out.temp.textContent = `${Math.round(C).toLocaleString('pt-BR').replace('-', '\u2212')} °C · ${tempNote(T)}`;
    out.line.textContent = z < 0.005 ? 'vermelha, igual' : band(lam);
    const pct = [f.r, f.m, f.l].map((v) => Math.max(0, v * 100));
    mix.forEach((s, i) => { s.style.flexBasis = `${pct[i]}%`; s.title = `${['Luz', 'Matéria', 'Energia escura'][i]}: ${fmt(pct[i], pct[i] < 1 ? 2 : 1)}%`; });
    q(root, '[data-t-mixtext]').textContent = `Luz ${fmt(pct[0], pct[0] < 1 ? 2 : 1)}% · matéria ${fmt(pct[1], pct[1] < 1 ? 2 : 1)}% · energia escura ${fmt(pct[2], pct[2] < 1 ? 2 : 1)}%`;

    // viagem
    const px = trackX + trackW * Math.min(1, ageThen / age0);
    travel.setAttribute('x', String(px)); travel.setAttribute('width', String(trackX + trackW - px));
    pin.setAttribute('transform', `translate(${px} ${trackY})`);
    // textos centrados no ponto, empurrados para dentro da trilha (a fonte cresce no mobile)
    const fit = (t: SVGTextElement, cx: number) => { const half = t.getComputedTextLength() / 2; return Math.min(Math.max(cx, trackX + half), trackX + trackW - half); };
    pinText.textContent = z < 0.005 ? 'agora' : `a luz sai · ${duration(ageThen)}`;
    pinText.setAttribute('x', String(fit(pinText, px) - px));
    travelLabel.textContent = z < 0.005 ? '' : `a luz viajou ${duration(look)}`;
    travelLabel.setAttribute('x', String(fit(travelLabel, (px + trackX + trackW) / 2)));

    // janelas: crescimento real 1+z, comprimido na tela até ×6
    const grow = Math.pow(1 + z, Math.log(6) / Math.log(1 + Z_MAX));
    const cellR = 46, lamR = 30 * grow;
    const visibleNow = lam < 750;
    drawWindow(winL_g, winL, cellR / grow, 30, '#e5484d', false);
    drawWindow(winR_g, winR, cellR, lamR, visibleNow ? '#e5484d' : 'var(--ink)', !visibleNow);
    capL.textContent = 'luz vermelha · 656 nm';
    capR.textContent = z < 0.005 ? 'luz vermelha · 656 nm' : `chega com ${lam < 1e3 ? `${Math.round(lam)} nm` : lam < 1e6 ? `${fmt(lam / 1e3, lam < 1e4 ? 1 : 0)} µm` : `${fmt(lam / 1e6, 1)} mm`}`;
    capR2.textContent = z < 0.005 ? '' : visibleNow ? 'ainda visível, um pouco mais avermelhada' : `${bandShort(lam)} · invisível aos olhos`;
    note.textContent = z < 0.005 ? 'Luz de agora: nada cresceu no caminho.' : `A grade é o próprio espaço. Distâncias e comprimento de onda cresceram ×${fmtAuto(1 + z)} (na tela, ×${fmt(grow, 1)}).`;
    if (view3d) { view3d.set(z, lam); if (note3d) note3d.textContent = z < 0.005 ? 'Luz de agora: escolha um ponto de parada para ver a luz viajar enquanto o espaço cresce.' : `${capR.textContent}${capR2.textContent ? ' · ' + capR2.textContent : ''}. ${note.textContent}`; }

    if (z >= 1000) root.dispatchEvent(new CustomEvent('cosmos:badge', { bubbles: true, detail: { id: 'luz-antiga' } }));
    const ep = epochFor(z);
    q(epochBox, '[data-t-epoch-title]').textContent = ep.title;
    q(epochBox, '[data-t-epoch-text]').textContent = ep.text(z);
    const tag = q(epochBox, '[data-t-epoch-kind]');
    tag.textContent = ep.kind === 'Observado' ? 'Sabemos · observado' : 'Calculamos · modelo'; tag.dataset.kind = ep.kind;
    live.textContent = z < 0.005 ? 'Agora.' : `A luz saiu quando o Universo tinha ${duration(ageThen)} e viajou ${duration(look)} até aqui. Temperatura então: ${Math.round(C)} graus Celsius. ${ep.title}.`;
    presets.forEach((b) => b.setAttribute('aria-pressed', String(Math.abs(Number(b.dataset.tPreset) - z) / Math.max(1, z) < 0.02 && Math.abs(Number(b.dataset.tPreset) - z) < 5)));
    setParams({ z: z < 0.005 ? null : z < 10 ? z.toFixed(2) : String(Math.round(z)) });
  };

  range.addEventListener('input', () => { cancelAnimationFrame(tween); exact = null; render(); });
  // Viagem animada até o ponto escolhido (em escala logarítmica, como o controle)
  let tween = 0;
  const travelTo = (z: number) => {
    cancelAnimationFrame(tween);
    const from = Number(range.value), to = pOf(z);
    if (reduced() || from === to) { exact = z; range.value = String(to); render(); return; }
    const t0 = performance.now(), dur = 700 + Math.min(900, Math.abs(to - from) * 1.4);
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / dur), e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      range.value = String(Math.round(from + (to - from) * e));
      exact = k >= 1 ? z : null;
      render();
      if (k < 1) tween = requestAnimationFrame(step);
    };
    tween = requestAnimationFrame(step);
  };
  presets.forEach((b) => b.addEventListener('click', () => travelTo(Number(b.dataset.tPreset))));
  const fromUrl = Number(getParam('z'));
  if (Number.isFinite(fromUrl) && fromUrl > 0 && fromUrl <= Z_MAX) { exact = fromUrl; range.value = String(pOf(fromUrl)); }
  initGuess(root, { unlocked: Number.isFinite(fromUrl) && fromUrl > 0 });
  qa<HTMLButtonElement>(root, '[data-t-go]').forEach((b) => b.addEventListener('click', () => { travelTo(Number(b.dataset.tGo)); range.focus({ preventScroll: true }); }));
  render();
}
