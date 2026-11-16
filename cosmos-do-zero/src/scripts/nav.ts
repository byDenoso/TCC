import { motionPreference } from './motion-preference';
import { $, $$ } from './dom';
import { u } from '../lib/url';

/** Endereços antigos da página inicial que mudaram para páginas próprias. */
const MOVED: Record<string, string> = { tempo: '/laboratorio/#tempo', planetas: '/laboratorio/#planetas', laboratorio: '/laboratorio/#laboratorio', comparador: '/laboratorio/#comparador', estrelas: '/laboratorio/#estrelas', extras: '/laboratorio/', glossario: '/glossario/', fontes: '/fontes/', explorar: '/#observatorio' };

const hashId = (hash = location.hash): string => { try { return decodeURIComponent(hash.slice(1)); } catch { return ''; } };

export function initNav(): void {
  const isHome = location.pathname === u('/') || location.pathname === u('/').replace(/\/$/, '');
  const movedTo = isHome && location.hash ? MOVED[hashId()] : undefined;
  if (movedTo && !document.getElementById(hashId())) { location.replace(u(movedTo)); return; }
  if (isHome) addEventListener('hashchange', () => { const to = MOVED[hashId()]; if (to && !document.getElementById(hashId())) location.replace(u(to)); });
  // Old deep links still reveal content inside the complementary explorer.
  const revealHash = () => {
    let target: HTMLElement | null = null;
    try { target = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch { return; }
    if (!target) return;
    if (target instanceof HTMLDetailsElement) target.open = true;
    for (let node = target.parentElement; node; node = node.parentElement) {
      if (node instanceof HTMLDetailsElement) node.open = true;
    }
    requestAnimationFrame(() => target?.scrollIntoView({ behavior: 'instant', block: 'start' }));
  };
  if (location.hash) revealHash();
  window.addEventListener('hashchange', revealHash);
  document.addEventListener('click', (event) => {
    const a = (event.target as Element).closest<HTMLAnchorElement>('a[href]');
    if (!a) return;
    const url = new URL(a.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname) return;
    // Âncora na mesma página: nunca apagar o estado dos experimentos guardado na URL.
    if (!event.defaultPrevented && url.hash && !url.search && location.search && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey && a.target !== '_blank') {
      const id = hashId(url.hash);
      const target = document.getElementById(id);
      if (target) {
        event.preventDefault();
        const oldURL = location.href;
        if (location.hash !== url.hash) { history.pushState(history.state, '', location.search + url.hash); dispatchEvent(new HashChangeEvent('hashchange', { oldURL, newURL: location.href })); }
        else revealHash();
        const smooth = !motionPreference.matches;
        target.scrollIntoView({ behavior: smooth ? 'smooth' : 'instant', block: 'start' });
        if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
        target.focus({ preventScroll: true });
        return;
      }
    }
    if (url.hash === location.hash) revealHash();
  });
  addEventListener('popstate', () => { if (location.hash) revealHash(); });
  const mobileMenu = $<HTMLDetailsElement>('[data-mobile-menu]');
  const headerMenus = $$<HTMLDetailsElement>('[data-mobile-menu], [data-motion-menu]');
  const close = (menu: HTMLDetailsElement, returnFocus = false) => {
    if (!menu.open) return;
    menu.open = false;
    if (returnFocus) $('summary', menu)?.focus();
  };
  if (mobileMenu) {
    $$('a', mobileMenu).forEach((link) => link.addEventListener('click', () => close(mobileMenu)));
    matchMedia('(min-width: 961px)').addEventListener('change', (e) => {
      if (e.matches) close(mobileMenu);
    });
  }
  for (const menu of headerMenus) {
    menu.addEventListener('toggle', () => {
      if (menu.open) headerMenus.filter((other) => other !== menu).forEach((other) => close(other));
    });
    menu.addEventListener('focusout', (event) => {
      if (event.relatedTarget instanceof Node && !menu.contains(event.relatedTarget)) close(menu);
    });
  }
  document.addEventListener('click', (event) => {
    for (const menu of headerMenus) {
      if (event.target instanceof Node && !menu.contains(event.target)) close(menu);
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || event.defaultPrevented) return;
    for (const menu of headerMenus) close(menu, menu.contains(document.activeElement));
  });

  if (!isHome || !('IntersectionObserver' in window)) return;
  const links = $$<HTMLAnchorElement>('.main-nav a[data-spy]');
  const targets = ['capitulos', 'planetario', 'interativos', 'observatorio', 'prologo', 'imagens', 'escala-cosmica', 'viagem', 'movimento'];
  const mark = (id?: string) => {
    for (const link of links) {
      if (link.dataset.spy === id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }
  };
  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) mark(entry.target.id === 'capitulos' ? 'capitulos' : 'planetario');
    }
  }, { rootMargin: '-40% 0px -55% 0px' });
  for (const id of targets) {
    const target = document.getElementById(id);
    if (target) io.observe(target);
  }
  const cover = $('.editorial-cover--home');
  if (cover) new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting) mark();
  }, { rootMargin: '-40% 0px -55% 0px' }).observe(cover);
}
