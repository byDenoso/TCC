/**
 * Motion graphics com GSAP: abertura coreografada, órbitas em SVG desenhadas e percorridas,
 * números que contam e títulos de seção que entram palavra por palavra ao rolar.
 * Sem fixar a página nem sequestrar a rolagem. Com movimento reduzido, nada é animado.
 */
import { motionPreference, motionFactor } from './motion-preference';

/** Divide o texto em palavras/letras para animar, mantendo o nome acessível no elemento. */
function split(el: HTMLElement, mode: 'chars' | 'words'): HTMLElement[] {
  if (el.dataset.split) return [...el.querySelectorAll<HTMLElement>('.gs-unit')];
  el.dataset.split = mode;
  el.setAttribute('aria-label', el.textContent?.replace(/\s+/g, ' ').trim() ?? '');
  const units: HTMLElement[] = [];
  const walk = (node: Node) => {
    for (const child of [...node.childNodes]) {
      if (child.nodeType === Node.TEXT_NODE) {
        const frag = document.createDocumentFragment();
        for (const part of (child.textContent ?? '').split(/(\s+)/)) {
          if (!part) continue;
          if (/^\s+$/.test(part)) { frag.append(part); continue; }
          const word = document.createElement('span'); word.className = 'gs-mask'; word.setAttribute('aria-hidden', 'true');
          if (mode === 'chars') for (const ch of part) { const c = document.createElement('span'); c.className = 'gs-unit'; c.textContent = ch; word.append(c); units.push(c); }
          else { const w = document.createElement('span'); w.className = 'gs-unit'; w.textContent = part; word.append(w); units.push(w); }
          frag.append(word);
        }
        child.replaceWith(frag);
      } else if (child.nodeType === Node.ELEMENT_NODE && (child as Element).tagName !== 'BR') walk(child);
    }
  };
  walk(el);
  return units;
}

export async function initGsapMotion(): Promise<void> {
  if (motionPreference.matches) return;
  const [{ gsap }, { ScrollTrigger }] = await Promise.all([import('gsap'), import('gsap/ScrollTrigger')]);
  gsap.registerPlugin(ScrollTrigger);
  // O tempo da coreografia é o do relógio: um quadro lento não estica a abertura.
  gsap.ticker.lagSmoothing(0);
  const k = motionFactor();
  gsap.defaults({ ease: 'expo.out', duration: 1.1 * k });
  document.documentElement.classList.add('gsap-on');
  const stopAll: Array<() => void> = [];

  // ── abertura ──
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  if (hero) {
    const title = hero.querySelector<HTMLElement>('h1');
    const chars = title ? split(title, 'chars') : [];
    const tl = gsap.timeline({ defaults: { ease: 'expo.out' } });
    tl.from(hero.querySelector('.hero-overline .dash'), { scaleX: 0, transformOrigin: 'left center', duration: 0.9 * k }, 0)
      .from(hero.querySelector('.hero-overline'), { opacity: 0, x: -14, duration: 0.8 * k }, 0.1)
      .from(chars, { yPercent: 115, rotate: 8, opacity: 0, duration: 1.15 * k, stagger: 0.035 * k }, 0.15)
      .from(hero.querySelector('.hero-introduction'), { opacity: 0, y: 24, filter: 'blur(6px)', duration: 1 * k }, 0.55)
      .from(hero.querySelectorAll('.hero-actions > :not([hidden])'), { opacity: 0, y: 18, stagger: 0.08 * k, duration: 0.8 * k }, 0.75)
      .from(hero.querySelectorAll('.hero-routes a'), { opacity: 0, y: 26, rotateX: -35, transformOrigin: '50% 100%', stagger: 0.07 * k, duration: 0.9 * k }, 0.85)
      .from(hero.querySelector('.cmb-hero'), { opacity: 0, scale: 0.9, rotateY: -12, transformPerspective: 1200, duration: 1.5 * k }, 0.25)
      .from(hero.querySelectorAll('.hero-foot > *'), { opacity: 0, y: 16, stagger: 0.06 * k, duration: 0.8 * k }, 1.0);

    // Órbitas em SVG: o traço é desenhado e os pequenos corpos percorrem as elipses.
    const svg = hero.querySelector<SVGSVGElement>('.sky-orbits');
    if (svg) {
      svg.querySelectorAll<SVGEllipseElement>('ellipse').forEach((e, i) => {
        const len = Math.PI * (3 * (e.rx.baseVal.value + e.ry.baseVal.value) - Math.sqrt((3 * e.rx.baseVal.value + e.ry.baseVal.value) * (e.rx.baseVal.value + 3 * e.ry.baseVal.value)));
        gsap.fromTo(e, { strokeDasharray: len, strokeDashoffset: len }, { strokeDashoffset: 0, duration: 2.2 * k, delay: 0.4 + i * 0.25, ease: 'power3.inOut' });
      });
      const bodies = [...svg.querySelectorAll<SVGCircleElement>('circle')].map((c, i) => {
        const e = c.closest('g')!.querySelector('ellipse')!;
        const cx = e.cx.baseVal.value, cy = e.cy.baseVal.value, rx = e.rx.baseVal.value, ry = e.ry.baseVal.value;
        const a0 = Math.atan2((c.cy.baseVal.value - cy) / ry, (c.cx.baseVal.value - cx) / rx);
        return { c, cx, cy, rx, ry, a: a0, speed: (i % 2 ? -1 : 1) * (0.05 + i * 0.018) };
      });
      const tick = (_t: number, dt: number) => {
        if (hero.dataset.ambientPaused === 'true') return;
        for (const b of bodies) { b.a += b.speed * dt / 1000 * k; b.c.setAttribute('cx', (b.cx + b.rx * Math.cos(b.a)).toFixed(1)); b.c.setAttribute('cy', (b.cy + b.ry * Math.sin(b.a)).toFixed(1)); }
      };
      gsap.ticker.add(tick); stopAll.push(() => gsap.ticker.remove(tick));
      ScrollTrigger.create({ trigger: hero, start: 'top top', end: 'bottom top', onToggle: (st) => (st.isActive ? gsap.ticker.add(tick) : gsap.ticker.remove(tick)) });
    }

    // Números entram como um contador mecânico: os dígitos rolam para o lugar, o texto nunca muda.
    hero.querySelectorAll<HTMLElement>('.hero-foot .number').forEach((n, i) => {
      const digits = split(n, 'chars');
      n.removeAttribute('aria-label'); n.querySelectorAll('[aria-hidden]').forEach((m) => m.removeAttribute('aria-hidden'));
      gsap.from(digits, { yPercent: 120, opacity: 0, duration: 1.4 * k, ease: 'expo.out', stagger: 0.09 * k, delay: 1.05 + i * 0.12 });
    });

    // Ao rolar, a abertura recua em profundidade (sem fixar a página).
    gsap.to(hero.querySelector('.hero-copy'), { yPercent: -10, opacity: 0.35, ease: 'none', scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: true } });
    gsap.to(hero.querySelector('.cmb-hero'), { yPercent: -6, scale: 0.96, ease: 'none', scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: true } });
  }

  // ── revelações de uma vez: IntersectionObserver dispara tweens pausados (robusto a mudanças de layout) ──
  const once = (el: Element, tween: ReturnType<typeof gsap.from>) => {
    const io = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) { tween.play(); io.disconnect(); } }, { rootMargin: '0px 0px -10% 0px' });
    io.observe(el);
  };
  // títulos de seção: palavras sobem de dentro de uma máscara
  document.querySelectorAll<HTMLElement>('main .display').forEach((h) => {
    if (h.closest('.hero-shell')) return;
    const words = split(h, 'words');
    once(h, gsap.from(words, { yPercent: 110, opacity: 0, rotate: 4, stagger: 0.06 * k, duration: 1.1 * k, paused: true }));
  });
  // marcadores de seção: o texto é revelado da esquerda para a direita
  document.querySelectorAll<HTMLElement>('main .section-id').forEach((el) => {
    once(el, gsap.from(el, { clipPath: 'inset(0 100% 0 0)', duration: 1 * k, ease: 'power3.out', paused: true }));
  });
  // cartões entram em leque
  document.querySelectorAll<HTMLElement>('.continue-cards, .chapters, .school-catalog').forEach((group) => {
    const items = group.querySelectorAll(':scope > *');
    if (items.length) once(group, gsap.from(items, { y: 40, opacity: 0, rotateX: -18, transformPerspective: 900, transformOrigin: '50% 0%', stagger: 0.08 * k, duration: 1 * k, paused: true }));
  });
  addEventListener('load', () => ScrollTrigger.refresh(), { once: true });

  // Se o leitor pedir movimento reduzido depois, tudo vai ao estado final.
  motionPreference.addEventListener('change', () => {
    if (!motionPreference.matches) return;
    stopAll.forEach((f) => f());
    ScrollTrigger.getAll().forEach((st) => st.kill());
    gsap.globalTimeline.getChildren(true, true, true).forEach((a) => a.progress(1));
  });
}
