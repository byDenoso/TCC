import { useEffect } from 'react';

const cards = '.level-card, .feature, .index-card';
const reveals = '.section-title, .level-card, .feature, .index-card, .research-grid';

/** Progressive enhancement: no hidden content, no polling, no new animation bundle. */
export function usePremiumMotion(path: string) {
  useEffect(() => {
    const main = document.querySelector('main');
    if (!main) return;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const fine = matchMedia('(hover: hover) and (pointer: fine)');
    const nodes = Array.from(main.querySelectorAll<HTMLElement>(reveals));
    let observer: IntersectionObserver | undefined;
    let active: HTMLElement | null = null;
    let frame = 0;
    let x = 0, y = 0;

    const clearSpot = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      if (!active) return;
      active.style.removeProperty('--cosmos-spot-x');
      active.style.removeProperty('--cosmos-spot-y');
      delete active.dataset.cosmosSpotlight;
      active = null;
    };
    const paint = () => {
      frame = 0;
      if (!active || reduced.matches || !fine.matches) return;
      const rect = active.getBoundingClientRect();
      active.style.setProperty('--cosmos-spot-x', (x - rect.left) + 'px');
      active.style.setProperty('--cosmos-spot-y', (y - rect.top) + 'px');
      active.dataset.cosmosSpotlight = 'active';
    };
    const pointer = (event: PointerEvent) => {
      if (reduced.matches || !fine.matches || event.pointerType !== 'mouse') return;
      const next = event.target instanceof Element ? event.target.closest<HTMLElement>(cards) : null;
      if (active !== next) {
        clearSpot();
        active = next;
      }
      if (!active) return;
      x = event.clientX;
      y = event.clientY;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const sync = () => {
      observer?.disconnect();
      clearSpot();
      for (const el of nodes) {
        delete el.dataset.cosmosEnter;
        el.style.removeProperty('--cosmos-stagger');
      }
      if (reduced.matches || !('IntersectionObserver' in window)) return;
      observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const el = entry.target as HTMLElement;
          const siblings = el.parentElement ? Array.from(el.parentElement.children).filter(child => child.matches(cards)) : [];
          const index = Math.max(0, siblings.indexOf(el));
          el.style.setProperty('--cosmos-stagger', Math.min(index % 3, 2) * 65 + 'ms');
          el.dataset.cosmosEnter = 'shown';
          observer?.unobserve(el);
        }
      }, { threshold: .12 });
      nodes.forEach(el => observer?.observe(el));
    };
    sync();
    reduced.addEventListener('change', sync);
    fine.addEventListener('change', clearSpot);
    main.addEventListener('pointermove', pointer, { passive: true });
    main.addEventListener('pointerleave', clearSpot);
    return () => {
      observer?.disconnect();
      clearSpot();
      reduced.removeEventListener('change', sync);
      fine.removeEventListener('change', clearSpot);
      main.removeEventListener('pointermove', pointer);
      main.removeEventListener('pointerleave', clearSpot);
      nodes.forEach(el => {
        delete el.dataset.cosmosEnter;
        el.style.removeProperty('--cosmos-stagger');
      });
    };
  }, [path]);
}
