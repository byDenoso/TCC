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

const guesses = new WeakMap<HTMLElement, (focus: boolean) => void>();
/** O palpite funciona desde a abertura, mesmo quando o desenho ainda não foi carregado. */
export function initGuesses(): void {
  qa<HTMLElement>(document, '[data-station]').forEach((root) => initGuess(root));
}
export function readyStation(root: HTMLElement): void {
  root.dataset.stationReady = 'true';
  qa<HTMLElement>(root, '.obs-grid, .obs-epoch, .obs-tension').forEach((g) => g.removeAttribute('inert'));
}

/**
 * Palpite opcional: o visitante pode escolher uma resposta ou experimentar diretamente.
 * Links diretos com valores na URL já abrem o experimento liberado.
 */
export function initGuess(root: HTMLElement, opts: { unlocked?: boolean; onReveal?: (choice: string, right: boolean) => void } = {}): void {
  const existing = guesses.get(root);
  if (existing) { if (opts.unlocked) existing(false); return; }
  const box = root.querySelector<HTMLElement>('[data-guess]');
  if (!box) return;
  const name = root.dataset.station ?? 'lab';
  const gated = qa<HTMLElement>(root, '.obs-grid, .obs-epoch, .obs-tension');
  let remembered = false;
  try { remembered = sessionStorage.getItem(`cosmos-palpite-${name}`) === '1'; } catch { /* sem armazenamento */ }
  const unlock = (focus: boolean) => {
    root.classList.add('is-unlocked');
    root.classList.remove('is-gated');
    gated.forEach((g) => root.dataset.stationReady === 'true' ? g.removeAttribute('inert') : g.setAttribute('inert', ''));
    try { sessionStorage.setItem(`cosmos-palpite-${name}`, '1'); } catch { /* sem armazenamento */ }
    root.dispatchEvent(new CustomEvent('cosmos:unlock', { bubbles: true, detail: { station: name } }));
    if (focus) root.querySelector<HTMLElement>('.obs-grid input, .obs-grid button')?.focus({ preventScroll: true });
  };
  guesses.set(root, unlock);
  if (opts.unlocked || remembered) unlock(false);
  else { root.classList.add('is-gated'); }
  const right = box.dataset.guess!;
  const buttons = qa<HTMLButtonElement>(box, '[data-opt]');
  const out = q(box, '[data-guess-result]');
  const skip = box.querySelector<HTMLButtonElement>('[data-guess-skip]');
  skip?.addEventListener('click', () => { skip.hidden = true; unlock(true); });
  buttons.forEach((b) => b.addEventListener('click', () => {
    const ok = b.dataset.opt === right;
    buttons.forEach((x) => { x.disabled = true; x.dataset.state = x.dataset.opt === right ? 'right' : x === b ? 'wrong' : 'idle'; });
    out.hidden = false;
    if (skip) skip.hidden = true;
    q(out, '[data-guess-verdict]').textContent = ok ? 'Você acertou! ' : 'Boa tentativa. ';
    box.classList.add(ok ? 'is-right' : 'is-wrong');
    root.dispatchEvent(new CustomEvent('cosmos:guess', { bubbles: true, detail: { station: name, ok } }));
    unlock(false);
    opts.onReveal?.(b.dataset.opt!, ok);
  }));
}

/** Gerador pseudoaleatório determinístico (mulberry32) e normal por Box–Muller. */
export function rng(seed: number): { next(): number; gauss(): number } {
  let s = seed >>> 0;
  const next = () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return { next, gauss: () => Math.sqrt(-2 * Math.log(1 - next())) * Math.cos(2 * Math.PI * next()) };
}

/** Faz uma animação com requestAnimationFrame que para quando a aba some ou o elemento sai da tela. */
export function animator(host: Element, step: (dt: number) => boolean): { start(): void; stop(): void; running(): boolean; dispose():void } {
  let frame = 0, last = 0, on = false, visible = true;
  const stop = () => { on = false; cancelAnimationFrame(frame); last = 0; };
  const loop = (now: number) => {
    if (!on) return;
    const dt = last ? Math.min(now - last, 64) : 16; last = now;
    if (!step(dt)) { stop(); return; }
    frame = requestAnimationFrame(loop);
  };
  const pause=()=>{const wasOn=on;stop();if(wasOn)host.dispatchEvent(new CustomEvent('cosmos:autopause'));};
  const hidden=()=>{if(document.hidden)pause();};document.addEventListener('visibilitychange',hidden);window.addEventListener('pagehide',pause);
  let io:IntersectionObserver|null=null;
  if ('IntersectionObserver' in window){io=new IntersectionObserver(([e])=>{visible=e.isIntersecting;if(!visible)pause();});io.observe(host);}
  return { start() { const rect=host.getBoundingClientRect();visible=rect.width>0&&rect.height>0&&rect.bottom>0&&rect.top<innerHeight&&rect.right>0&&rect.left<innerWidth&&!host.closest('[hidden]');if (on || !visible || document.hidden) return; on = true; frame = requestAnimationFrame(loop); }, stop, running: () => on,dispose(){stop();io?.disconnect();document.removeEventListener('visibilitychange',hidden);window.removeEventListener('pagehide',pause);} };
}
