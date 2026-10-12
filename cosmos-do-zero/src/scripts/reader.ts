import { $, $$ } from './dom';
import { getParam, setParams } from '../lib/url-state';
import type { DepthLevel } from '../types';

const KEY = 'cosmos-v4-depth';
const LEVELS: DepthLevel[] = ['essential', 'more', 'deep'];
const URL_NAME: Record<DepthLevel, string | null> = { essential: null, more: 'entender', deep: 'profundo' };
const FROM_URL: Record<string, DepthLevel> = { essencial: 'essential', entender: 'more', profundo: 'deep' };

export function initReader(): void {
  const root = $('.chapter-reader');
  if (!root) return;
  const buttons = $$<HTMLButtonElement>('[data-depth]', root);
  const layers = $$<HTMLDetailsElement>('[data-layer]', root);
  const apply = (level: DepthLevel, persist = true) => {
    buttons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.depth === level)));
    layers.forEach((d) => { d.open = level === 'deep' || (level === 'more' && d.dataset.layer === 'more'); });
    root.dataset.depth = level;
    if (persist) {
      setParams({ nivel: URL_NAME[level] });
      try { localStorage.setItem(KEY, level); } catch { /* sem armazenamento */ }
    }
  };
  buttons.forEach((b) => b.addEventListener('click', () => apply(b.dataset.depth as DepthLevel)));
  let initial: DepthLevel = 'essential';
  try { const s = localStorage.getItem(KEY) as DepthLevel | null; if (s && LEVELS.includes(s)) initial = s; } catch { /* ignora */ }
  const q = getParam('nivel'); if (q && FROM_URL[q]) initial = FROM_URL[q];
  apply(initial, false);

  // Barra de leitura
  const bar = $('[data-reading-bar]');
  if (bar) {
    let ticking = false;
    const update = () => {
      const doc = document.documentElement;
      const total = doc.scrollHeight - doc.clientHeight;
      bar.style.transform = `scaleX(${total > 0 ? Math.min(1, Math.max(0, doc.scrollTop / total)) : 0})`;
      ticking = false;
    };
    addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  // Seção atual no índice
  const links = new Map($$<HTMLAnchorElement>('[data-toc] a', root).map((a) => [a.hash.slice(1), a]));
  const sections = $$('.lesson-section', root);
  if ('IntersectionObserver' in window && sections.length) {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        links.forEach((a, id) => (id === e.target.id ? a.setAttribute('aria-current', 'location') : a.removeAttribute('aria-current')));
      }
    }, { rootMargin: '-25% 0px -65% 0px' });
    sections.forEach((s) => io.observe(s));
  }
  // Âncora que aponta para dentro de um bloco recolhido
  const open = () => { const t = location.hash && document.getElementById(location.hash.slice(1)); const d = t && t.closest('details'); if (d) d.open = true; };
  open(); addEventListener('hashchange', open);

  initSteps(root, links);
}

/** Modo aula: um passo por vez, com progresso, anterior/próximo e opção de ver tudo. */
const WHOLE_KEY = 'cosmos-v5-aula-inteira';
function initSteps(root: HTMLElement, links: Map<string, HTMLAnchorElement>): void {
  const content = $('.reader-content', root);
  const sections = $$<HTMLElement>('.lesson-section', root);
  if (!content || sections.length < 2) return;
  const after = $$<HTMLElement>('.chapter-check, .reader-references, .reader-finish', root);
  const chapter = root.dataset.reader ?? '';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  const bar = document.createElement('div');
  bar.className = 'lesson-stepper';
  bar.setAttribute('role', 'group');
  bar.setAttribute('aria-label', 'Passos da aula');
  bar.innerHTML = `<button type="button" class="step-prev" data-step-prev>← Anterior</button>
    <div class="step-dots">${sections.map((s, i) => `<button type="button" class="step-dot" data-step-dot="${i}" aria-label="Passo ${i + 1}: ${s.querySelector('h2')?.textContent ?? ''}"></button>`).join('')}</div>
    <span class="step-count" data-step-count aria-live="polite"></span>
    <button type="button" class="step-next" data-step-next>Próximo passo →</button>`;
  sections[sections.length - 1].after(bar);
  const toggle = document.createElement('button');
  toggle.type = 'button'; toggle.className = 'step-toggle'; toggle.dataset.stepToggle = '';
  $('.reader-aside', root)?.append(toggle);

  const prev = $<HTMLButtonElement>('[data-step-prev]', bar)!, next = $<HTMLButtonElement>('[data-step-next]', bar)!;
  const dots = $$<HTMLButtonElement>('[data-step-dot]', bar), count = $('[data-step-count]', bar)!;
  let whole = false, current = 0, reachedEnd = false;
  try { whole = localStorage.getItem(WHOLE_KEY) === '1'; } catch { /* ignora */ }

  const show = (i: number, focus = false) => {
    current = Math.max(0, Math.min(sections.length - 1, i));
    if (current === sections.length - 1 && !reachedEnd) { reachedEnd = true; root.dispatchEvent(new CustomEvent('cosmos:lesson-end', { bubbles: true, detail: { chapter } })); }
    sections.forEach((s, k) => {
      const on = whole || k === current;
      s.hidden = !on;
      s.classList.toggle('step-in', !whole && k === current && !reduced);
    });
    after.forEach((a) => (a.hidden = !whole && !reachedEnd));
    bar.hidden = whole;
    dots.forEach((d, k) => { d.setAttribute('aria-current', String(k === current)); d.dataset.done = String(k < current || (reachedEnd && k <= current)); });
    count.textContent = `Passo ${current + 1} de ${sections.length}`;
    prev.disabled = current === 0;
    next.textContent = current === sections.length - 1 ? 'Ir para o desafio da aula ↓' : 'Próximo passo →';
    links.forEach((a, id) => (id === sections[current].id ? a.setAttribute('aria-current', 'step') : a.removeAttribute('aria-current')));
    toggle.textContent = whole ? 'Ver em passos' : 'Ver a aula inteira';
    root.classList.toggle('is-stepped', !whole);
    if (focus && !whole) {
      const h = sections[current].querySelector<HTMLElement>('h2');
      if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
      const top = sections[current].getBoundingClientRect().top;
      if (top < 80 || top > innerHeight * 0.6) sections[current].scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
    }
  };
  prev.addEventListener('click', () => show(current - 1, true));
  next.addEventListener('click', () => {
    if (current === sections.length - 1) { $('.chapter-check', root)?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' }); return; }
    show(current + 1, true);
  });
  dots.forEach((d, k) => d.addEventListener('click', () => show(k, true)));
  toggle.addEventListener('click', () => { whole = !whole; try { localStorage.setItem(WHOLE_KEY, whole ? '1' : '0'); } catch { /* ignora */ } show(current, !whole); });
  links.forEach((a, id) => a.addEventListener('click', (e) => {
    if (whole) return;
    e.preventDefault();
    const k = sections.findIndex((s) => s.id === id);
    if (location.hash !== `#${id}`) history.pushState(history.state, '', `#${id}`);
    show(k, true);
  }));
  // Voltar/avançar do navegador percorre os passos visitados
  addEventListener('popstate', () => {
    if (whole) return;
    const k = sections.findIndex((s) => `#${s.id}` === location.hash);
    show(k >= 0 ? k : 0, true);
  });
  const fromHash = sections.findIndex((s) => `#${s.id}` === location.hash);
  if (fromHash > 0) { for (let k = 0; k <= fromHash; k++) show(k); } else show(0);
  document.addEventListener('keydown', (e) => {
    if (whole || (e.target as Element).closest('input, textarea, select, [contenteditable]')) return;
    if (e.key === 'ArrowRight' && (e.altKey || e.target === document.body)) show(current + 1, true);
    if (e.key === 'ArrowLeft' && (e.altKey || e.target === document.body)) show(current - 1, true);
  });
}
