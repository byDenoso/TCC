/** Ferramentas de desenho das cenas (SVG 480 × 270). Cores vêm dos tokens do tema. */
const NS = 'http://www.w3.org/2000/svg';
export const W = 480, H = 270;
export const C = {
  ink: 'var(--ink)', ink2: 'var(--ink-2)', muted: 'var(--muted)', accent: 'var(--accent)', accentInk: 'var(--accent-ink)',
  blue: 'var(--accent-2)', gold: 'var(--c-rad)', line: 'var(--line-strong)', soft: 'var(--surface-2)', bg: 'var(--bg)', surface: 'var(--surface)',
  dm: 'var(--c-dm)', ob: 'var(--c-ob)', de: 'var(--c-de)'
};
type V = string | number;
export function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, V> = {}, parent?: Element, text?: string): SVGElementTagNameMap[K] {
  const n = document.createElementNS(NS, tag);
  set(n, attrs);
  if (text !== undefined) n.textContent = text;
  parent?.append(n);
  return n;
}
/** Atualiza atributos; cores com var() vão para style (atributos SVG não aceitam var). */
export function set(n: Element, attrs: Record<string, V>): void {
  for (const [k, v] of Object.entries(attrs)) {
    if ((k === 'fill' || k === 'stroke' || k === 'stop-color') && typeof v === 'string' && v.includes('var(')) (n as SVGElement).style.setProperty(k, v);
    else n.setAttribute(k, String(v));
  }
}
export const g = (parent: Element, attrs: Record<string, V> = {}): SVGGElement => el('g', attrs, parent);
export const text = (parent: Element, x: number, y: number, s: string, attrs: Record<string, V> = {}): SVGTextElement => el('text', { x, y, ...attrs }, parent, s);
export const clear = (n: Element): void => n.replaceChildren();
export const lerp = (a: number, b: number, k: number): number => a + (b - a) * k;
export const clamp = (x: number, lo = 0, hi = 1): number => Math.min(hi, Math.max(lo, x));
export const ease = (k: number): number => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
/** Gerador determinístico (mulberry32): as cenas são iguais a cada visita. */
export function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => { s = (s + 0x6d2b79f5) >>> 0; let x = s; x = Math.imul(x ^ (x >>> 15), x | 1); x ^= x + Math.imul(x ^ (x >>> 7), x | 61); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
}
export const fmt = (n: number, d = 0): string => n.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }).replace('-', '−');
/** Barra horizontal rotulada, usada em comparações. */
export function bar(parent: Element, x: number, y: number, w: number, max: number, value: number, label: string, valueText: string, color: string): void {
  text(parent, x, y - 6, label, { class: 'mx-t small' });
  el('rect', { x, y, width: w, height: 14, rx: 3, fill: C.soft }, parent);
  el('rect', { x, y, width: Math.max(2, (w * Math.min(value, max)) / max), height: 14, rx: 3, fill: color, class: 'mx-grow' }, parent);
  text(parent, x + w + 8, y + 12, valueText, { class: 'mx-t small strong' });
}
/** Seta de a até b. */
export function arrow(parent: Element, x1: number, y1: number, x2: number, y2: number, color: string, width = 2.5): SVGGElement {
  const gg = g(parent);
  el('line', { x1, y1, x2, y2, stroke: color, 'stroke-width': width, 'stroke-linecap': 'round' }, gg);
  const a = Math.atan2(y2 - y1, x2 - x1), h = 7 + width;
  el('path', { d: `M${x2} ${y2} L${x2 - h * Math.cos(a - 0.45)} ${y2 - h * Math.sin(a - 0.45)} L${x2 - h * Math.cos(a + 0.45)} ${y2 - h * Math.sin(a + 0.45)} Z`, fill: color }, gg);
  return gg;
}
/** Volume e halo analíticos, sem filtros de desfoque caros a cada quadro. IDs locais e determinísticos. */
export function sphere(parent: Element, x: number, y: number, r: number, color: string, luminous = false): void {
  const svg = parent.closest('svg')!;
  const prefix = svg.closest<HTMLElement>('[data-mx]')?.dataset.mx ?? svg.getAttribute('data-star-svg') ?? 'stellar';
  const id = `${prefix}-volume-${svg.querySelectorAll('[data-volume]').length}`;
  const defs = el('defs', { 'data-volume': '' }, parent);
  const body = el('radialGradient', { id, cx: '35%', cy: '30%', r: '75%' }, defs);
  el('stop', { offset: '0%', 'stop-color': luminous ? `color-mix(in srgb, ${color} 42%, white)` : `color-mix(in srgb, ${color} 75%, white)` }, body);
  el('stop', { offset: '50%', 'stop-color': color }, body);
  el('stop', { offset: '100%', 'stop-color': `color-mix(in srgb, ${color} ${luminous ? 65 : 22}%, black)` }, body);
  if (luminous) {
    const halo = el('radialGradient', { id: `${id}-halo` }, defs);
    el('stop', { offset: '25%', 'stop-color': color, 'stop-opacity': 0.3 }, halo);
    el('stop', { offset: '60%', 'stop-color': color, 'stop-opacity': 0.12 }, halo);
    el('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': 0 }, halo);
    el('circle', { cx: x, cy: y, r: r * 2.3, fill: `url(#${id}-halo)` }, parent);
  }
  el('circle', { cx: x, cy: y, r, fill: `url(#${id})` }, parent);
}
export const star = (parent: Element, x: number, y: number, r: number, color: string, glow = true): void => sphere(parent, x, y, r, color, glow);
