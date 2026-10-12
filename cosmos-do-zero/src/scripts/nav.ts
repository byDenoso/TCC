import { $, $$ } from './dom';
import { u } from '../lib/url';

/** Endereços antigos da página inicial que mudaram para páginas próprias. */
const MOVED: Record<string, string> = { tempo: '/laboratorio/#tempo', planetas: '/laboratorio/#planetas', laboratorio: '/laboratorio/#laboratorio', comparador: '/laboratorio/#comparador', estrelas: '/laboratorio/#estrelas', extras: '/laboratorio/', glossario: '/glossario/', fontes: '/fontes/', explorar: '/#observatorio' };

export function initNav(): void {
  const isHome = location.pathname === u('/') || location.pathname === u('/').replace(/\/$/, '');
  const movedTo = isHome && location.hash ? MOVED[decodeURIComponent(location.hash.slice(1))] : undefined;
  if (movedTo && !document.getElementById(location.hash.slice(1))) { location.replace(u(movedTo)); return; }
  if (isHome) addEventListener('hashchange', () => { const to = MOVED[decodeURIComponent(location.hash.slice(1))]; if (to && !document.getElementById(location.hash.slice(1))) location.replace(u(to)); });
  // Old deep links still reveal content inside the complementary explorer.
  const revealHash = () => {
    let target: HTMLElement | null = null;
    try { target = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch { return; }
    if (!target) return;
    for (let node = target.parentElement; node; node = node.parentElement) {
      if (node instanceof HTMLDetailsElement) node.open = true;
    }
    requestAnimationFrame(() => target?.scrollIntoView({ behavior: 'instant', block: 'start' }));
  };
  if (location.hash) revealHash();
  window.addEventListener('hashchange', revealHash);
  document.addEventListener('click', (event) => {
    const a = (event.target as Element).closest<HTMLAnchorElement>('a[href]');
    if (a && new URL(a.href).pathname === location.pathname && new URL(a.href).hash === location.hash) revealHash();
  });
  const menu = $<HTMLDetailsElement>('[data-mobile-menu]');
  if (menu) {
    const close = (returnFocus = false) => { if (menu.open) { menu.open = false; if (returnFocus) $('summary', menu)?.focus(); } };
    $$('a', menu).forEach((a) => a.addEventListener('click', () => close()));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(true); });
    document.addEventListener('click', (e) => { if (menu.open && !menu.contains(e.target as Node)) close(); });
    matchMedia('(min-width: 761px)').addEventListener('change', (e) => e.matches && close());
  }
  // Destaque da seção atual no menu principal
  const links = new Map($$<HTMLAnchorElement>('.main-nav a[data-spy]').map((a) => [a.dataset.spy!, a]));
  if (!links.size) return;
  const targets = ['observatorio', 'capitulos'].map((id) => document.getElementById(id)).filter((n): n is HTMLElement => !!n);
  if (!targets.length || !('IntersectionObserver' in window)) return;
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      links.forEach((a, id) => (id === e.target.id ? a.setAttribute('aria-current', 'location') : a.removeAttribute('aria-current')));
    }
  }, { rootMargin: '-40% 0px -55% 0px' });
  targets.forEach((t) => io.observe(t));
  const hero = $('.hero-shell');
  if (hero) new IntersectionObserver(([e]) => e.isIntersecting && links.forEach((a) => a.removeAttribute('aria-current')), { rootMargin: '-60% 0px 0px 0px' }).observe(hero);
}
