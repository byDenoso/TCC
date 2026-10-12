/** Utilidades compartilhadas pelos instrumentos do Observatório. */
const NS = 'http://www.w3.org/2000/svg';
export type Attrs = Record<string, string | number>;

export function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Attrs = {}, parent?: Element, text?: string): SVGElementTagNameMap[K] {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  if (text !== undefined) node.textContent = text;
  parent?.append(node);
  return node;
}
export const clear = (node: Element): void => node.replaceChildren();
export const q = <T extends Element = HTMLElement>(root: ParentNode, sel: string): T => {
  const n = root.querySelector<T>(sel);
  if (!n) throw new Error(`[lab] elemento ausente: ${sel}`);
  return n;
};
export const qa = <T extends Element = HTMLElement>(root: ParentNode, sel: string): T[] => [...root.querySelectorAll<T>(sel)];

/** Número em pt-BR com casas fixas. */
export const fmt = (n: number, digits = 1): string =>
  n.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }).replace('-', '−');
/** Número com algarismos significativos adequados à magnitude. */
export const fmtAuto = (n: number): string => {
  const a = Math.abs(n);
  if (a >= 1000) return Math.round(n).toLocaleString('pt-BR');
  if (a >= 100) return fmt(n, 0);
  if (a >= 10) return fmt(n, 1);
  if (a >= 1) return fmt(n, 2);
  return fmt(n, 3);
};

/** Duração em bilhões de anos → texto legível ("372 mil anos", "470 milhões de anos", "13,8 bilhões de anos"). */
export function duration(gyr: number): string {
  const years = gyr * 1e9;
  if (years < 1e6) return `${Math.round(years / 1e3).toLocaleString('pt-BR')} mil anos`;
  if (years < 1e9) { const m = years / 1e6; return `${m >= 100 ? Math.round(m) : fmt(m, 1)} milhões de anos`.replace(/ (\d+),0 milhões/, ' $1 milhões'); }
  return `${fmt(gyr, gyr >= 100 ? 0 : 1)} bilhões de anos`;
}
/** Distância em Mpc → anos-luz legíveis. */
export function lightYears(mpc: number): string {
  const gly = mpc * 3.261564e-3;
  if (gly >= 1) return `${fmt(gly, gly >= 100 ? 0 : 1)} bilhões de anos-luz`;
  return `${fmt(gly * 1000, gly * 1000 >= 100 ? 0 : 1)} milhões de anos-luz`;
}

export const reduced = (): boolean => matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Palpite: o visitante escolhe antes de mexer; mostramos a resposta e a explicação. */
export function initGuess(root: HTMLElement, onReveal?: (choice: string, right: boolean) => void): void {
  const box = root.querySelector<HTMLElement>('[data-guess]');
  if (!box) return;
  const right = box.dataset.guess!;
  const buttons = qa<HTMLButtonElement>(box, '[data-opt]');
  const out = q(box, '[data-guess-result]');
  buttons.forEach((b) => b.addEventListener('click', () => {
    const ok = b.dataset.opt === right;
    buttons.forEach((x) => { x.disabled = true; x.dataset.state = x.dataset.opt === right ? 'right' : x === b ? 'wrong' : 'idle'; });
    out.hidden = false;
    q(out, '[data-guess-verdict]').textContent = ok ? 'Você acertou. ' : 'Nem sempre é intuitivo. ';
    onReveal?.(b.dataset.opt!, ok);
  }));
}

/** Gerador pseudoaleatório determinístico (mulberry32) e normal por Box–Muller. */
export function rng(seed: number): { next(): number; gauss(): number } {
  let s = seed >>> 0;
  const next = () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return { next, gauss: () => Math.sqrt(-2 * Math.log(1 - next())) * Math.cos(2 * Math.PI * next()) };
}

/** Faz uma animação com requestAnimationFrame que para quando a aba some ou o elemento sai da tela. */
export function animator(host: Element, step: (dt: number) => boolean): { start(): void; stop(): void; running(): boolean } {
  let frame = 0, last = 0, on = false, visible = true;
  const stop = () => { on = false; cancelAnimationFrame(frame); last = 0; };
  const loop = (now: number) => {
    if (!on) return;
    const dt = last ? Math.min(now - last, 64) : 16; last = now;
    if (!step(dt)) { stop(); return; }
    frame = requestAnimationFrame(loop);
  };
  document.addEventListener('visibilitychange', () => document.hidden && stop());
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (!visible) stop(); }).observe(host);
  return { start() { if (on || !visible) return; on = true; frame = requestAnimationFrame(loop); }, stop, running: () => on };
}
