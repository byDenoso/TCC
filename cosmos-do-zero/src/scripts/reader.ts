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
}
