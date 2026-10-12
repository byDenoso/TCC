import { PLANCK, ageAtRedshift, ageNow, cmbTemperature, comovingMpc, densityFractions, lookbackGyr, observedWavelengthNm, zAcceleration } from '../../lib/cosmology';
import { clear, duration, fmt, fmtAuto, initGuess, lightYears, q, qa, svg } from './common';
import { getParam, setParams } from '../../lib/url-state';

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
  return 'quente como a superfície de uma estrela';
}

interface Epoch { from: number; title: string; kind: 'Observado' | 'Calculado pelo modelo'; text: (z: number) => string }
const epochs: Epoch[] = [
  { from: 3400, title: 'Quente demais para existir átomo', kind: 'Calculado pelo modelo', text: () => 'Tudo é uma sopa muito quente de partículas e luz. Nesta fase a luz pesa mais que a matéria. Isso muda por volta dos 50 mil anos de idade.' },
  { from: 1200, title: 'Uma névoa que não deixa a luz passar', kind: 'Calculado pelo modelo', text: () => 'Ainda quente demais para os átomos se formarem. A luz bate o tempo todo nas partículas soltas, como farol na neblina: não dá para enxergar através.' },
  { from: 900, title: 'O Universo fica transparente', kind: 'Observado', text: () => 'Os primeiros átomos se formam e a névoa se dissipa. A luz desse instante viaja até hoje e chega até nós: é a luz mais antiga que existe. Saiu alaranjada, de um gás a uns 2.700 °C, e chegou esticada em micro-ondas.' },
  { from: 30, title: 'Idade das trevas', kind: 'Calculado pelo modelo', text: () => 'Ainda não existe nenhuma estrela. O gás esfria e a gravidade começa a juntar matéria em montinhos, que vão virar as primeiras galáxias.' },
  { from: 6, title: 'As primeiras estrelas e galáxias se acendem', kind: 'Observado', text: () => 'Surgem as primeiras estrelas e galáxias. O telescópio espacial James Webb já fotografou galáxias desta época.' },
  { from: 0.5, title: 'A época de mais estrelas', kind: 'Observado', text: () => 'As galáxias crescem e formam estrelas no ritmo mais intenso da história, quando o Universo tinha uns 3 bilhões de anos. Hoje esse ritmo é bem menor.' },
  { from: 0.02, title: 'A energia escura entra em cena', kind: 'Calculado pelo modelo', text: () => `Há uns 6 bilhões de anos, a expansão parou de frear e começou a acelerar. Chamamos de "energia escura" o que causa isso, mas ainda não sabemos o que ela é. (No modelo, a aceleração começa quando a luz foi esticada ${fmt(1 + zAcceleration(PLANCK), 1)} vezes.)` },
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
  const W = 640;
  const trackX = 30, trackW = 580, trackY = 62;
  clear(svgEl);
  svg('text', { x: trackX, y: 22, class: 'obs-cap' }, svgEl, 'Do início até hoje · 13,8 bilhões de anos');
  svg('rect', { x: trackX, y: trackY, width: trackW, height: 14, rx: 2, class: 'obs-track' }, svgEl);
  const travel = svg('rect', { x: trackX, y: trackY, width: 0, height: 14, rx: 2, class: 'obs-travel' }, svgEl);
  const pin = svg('g', { class: 'obs-pin' }, svgEl);
  svg('path', { d: 'M0 0 L-7 -12 H7 Z', class: 'obs-pinhead' }, pin);
  const pinText = svg('text', { y: -15, 'text-anchor': 'middle', class: 'obs-cap strong' }, pin, 'a luz sai');
  svg('text', { x: trackX, y: 102, class: 'obs-cap' }, svgEl, 'Início');
  svg('text', { x: trackX + trackW, y: 102, 'text-anchor': 'end', class: 'obs-cap' }, svgEl, 'Hoje');
  const travelLabel = svg('text', { y: 102, 'text-anchor': 'middle', class: 'obs-cap warm' }, svgEl, '');

  // quadrado do tamanho
  const sqX = 30, sqBottom = 345, sqS = 170;
  svg('text', { x: sqX, y: 142, class: 'obs-cap' }, svgEl, 'Tamanho do Universo');
  svg('rect', { x: sqX, y: sqBottom - sqS, width: sqS, height: sqS, class: 'obs-today' }, svgEl);
  const then = svg('rect', { x: sqX, y: sqBottom - 2, width: 2, height: 2, class: 'obs-then' }, svgEl);
  const sqLabel = svg('text', { x: sqX, y: sqBottom + 24, class: 'obs-cap warm' }, svgEl, '');
  svg('text', { x: sqX + sqS, y: sqBottom - sqS - 8, 'text-anchor': 'end', class: 'obs-cap' }, svgEl, 'hoje (contorno)');

  // espectro (eixo logarítmico 250 nm → 1 mm)
  const spX = 300, spW = 310, spY = 260;
  const l0 = Math.log10(250), l1 = Math.log10(1e6);
  const xOf = (nm: number) => spX + ((Math.log10(Math.max(250, Math.min(1e6, nm))) - l0) / (l1 - l0)) * spW;
  svg('text', { x: spX, y: 142, class: 'obs-cap' }, svgEl, 'A cor da luz se estica');
  const defs = svg('defs', {}, svgEl);
  const grad = svg('linearGradient', { id: `vis-${Math.random().toString(36).slice(2, 7)}`, x1: 0, x2: 1, y1: 0, y2: 0 }, defs);
  [[0, '#7a3bd6'], [.18, '#3b6bff'], [.38, '#27d6ff'], [.55, '#3fe06f'], [.7, '#ffe14a'], [.84, '#ff9a2e'], [1, '#ff3b2e']].forEach(([o, c]) => svg('stop', { offset: o as number, 'stop-color': c as string }, grad));
  svg('rect', { x: spX, y: spY, width: spW, height: 22, class: 'obs-spectrum' }, svgEl);
  svg('rect', { x: xOf(380), y: spY, width: xOf(750) - xOf(380), height: 22, fill: `url(#${grad.id})` }, svgEl);
  svg('text', { x: (xOf(380) + xOf(750)) / 2, y: spY + 46, 'text-anchor': 'middle', class: 'obs-cap small' }, svgEl, 'visível');
  svg('text', { x: xOf(1e4), y: spY + 46, 'text-anchor': 'middle', class: 'obs-cap small hide-sm' }, svgEl, 'infravermelho');
  svg('text', { x: spX + spW, y: spY + 46, 'text-anchor': 'end', class: 'obs-cap small' }, svgEl, 'micro-ondas');
  const rest = svg('g', {}, svgEl);
  svg('path', { d: `M${xOf(656.28)} ${spY - 3} l-5 -10 h10 Z`, class: 'obs-rest' }, rest);
  svg('text', { x: xOf(656.28), y: spY - 18, 'text-anchor': 'middle', class: 'obs-cap small' }, rest, 'cor de saída');
  const seen = svg('g', {}, svgEl);
  const seenArrow = svg('path', { class: 'obs-seen' }, seen);
  const seenText = svg('text', { y: spY + 84, 'text-anchor': 'middle', class: 'obs-cap warm' }, seen, '');

  let exact: number | null = null;
  const render = (): void => {
    const z = exact ?? zOf(Number(range.value));
    const a = 1 / (1 + z);
    const ageThen = ageAtRedshift(z, PLANCK);
    const look = lookbackGyr(z, PLANCK);
    const dc = comovingMpc(z, PLANCK);
    const T = cmbTemperature(z);
    const lam = observedWavelengthNm(z);
    const f = densityFractions(z, PLANCK);

    zOut.textContent = z < 0.005 ? 'agora' : `há ${duration(look)}`;
    q(root, '[data-t-ztech]').textContent = `z = ${z < 10 ? fmt(z, 2) : Math.round(z)}`;
    range.setAttribute('aria-valuetext', z < 0.005 ? 'agora' : `luz que saiu há ${duration(look)}, quando o Universo tinha ${duration(ageThen)}`);
    out.age.textContent = z < 0.005 ? '13,8 bilhões de anos (hoje)' : duration(ageThen);
    out.look.textContent = z < 0.005 ? 'nenhum: luz de agora' : duration(look);
    out.dnow.textContent = z < 0.005 ? 'aqui perto' : `a ${lightYears(dc)}`;
    out.size.textContent = z < 0.005 ? 'do tamanho de hoje' : `${fmtAuto(1 + z)} vezes menor`;
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
    const anchor = px < 120 ? 'start' : px > W - 120 ? 'end' : 'middle';
    pinText.setAttribute('text-anchor', anchor); pinText.setAttribute('x', anchor === 'start' ? '-6' : anchor === 'end' ? '6' : '0');
    pinText.textContent = z < 0.005 ? 'agora' : `a luz sai · ${duration(ageThen)}`;
    travelLabel.textContent = z < 0.005 ? '' : `a luz viajou ${duration(look)}`;
    travelLabel.setAttribute('x', String((px + trackX + trackW) / 2));
    travelLabel.setAttribute('visibility', trackX + trackW - px > 130 ? 'visible' : 'hidden');

    // tamanho
    const s = Math.max(2, sqS * a);
    then.setAttribute('width', String(s)); then.setAttribute('height', String(s)); then.setAttribute('y', String(sqBottom - s));
    sqLabel.textContent = z < 0.005 ? 'mesmo tamanho' : `então: 1/${fmtAuto(1 + z)}`;

    // espectro
    const x = xOf(lam);
    seenArrow.setAttribute('d', `M${x} ${spY - 3} l-5 -10 h10 Z`);
    seenText.textContent = '';
    seenText.setAttribute('x', String(Math.min(spX + spW - 40, Math.max(spX + 40, x))));
    seenText.textContent = z < 0.005 ? '' : `chega como ${bandShort(lam)}`;
    seenArrow.setAttribute('visibility', z < 0.005 ? 'hidden' : 'visible');
    const ep = epochFor(z);
    q(epochBox, '[data-t-epoch-title]').textContent = ep.title;
    q(epochBox, '[data-t-epoch-text]').textContent = ep.text(z);
    const tag = q(epochBox, '[data-t-epoch-kind]');
    tag.textContent = ep.kind; tag.dataset.kind = ep.kind;
    live.textContent = z < 0.005 ? 'Agora.' : `A luz saiu quando o Universo tinha ${duration(ageThen)} e viajou ${duration(look)} até aqui. Temperatura então: ${Math.round(C)} graus Celsius. ${ep.title}.`;
    presets.forEach((b) => b.setAttribute('aria-pressed', String(Math.abs(Number(b.dataset.tPreset) - z) / Math.max(1, z) < 0.02 && Math.abs(Number(b.dataset.tPreset) - z) < 5)));
    setParams({ z: z < 0.005 ? null : z < 10 ? z.toFixed(2) : String(Math.round(z)) });
  };

  range.addEventListener('input', () => { exact = null; render(); });
  presets.forEach((b) => b.addEventListener('click', () => { exact = Number(b.dataset.tPreset); range.value = String(pOf(exact)); render(); }));
  const fromUrl = Number(getParam('z'));
  if (Number.isFinite(fromUrl) && fromUrl > 0 && fromUrl <= Z_MAX) { exact = fromUrl; range.value = String(pOf(fromUrl)); }
  initGuess(root);
  qa<HTMLButtonElement>(root, '[data-t-go]').forEach((b) => b.addEventListener('click', () => { exact = Number(b.dataset.tGo); range.value = String(pOf(exact)); render(); range.focus({ preventScroll: true }); }));
  render();
}
