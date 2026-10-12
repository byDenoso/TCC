/** Movimento: revelação ao rolar e estrelas que acompanham o ponteiro. */
const SELECTORS = [
  '.section-id', 'main .display', '.intro-head > p', '.obs-head > p', '.obs-tabs', '.chapter-row', '.journey-status', '.course-map', '.badges',
  '.continue-card', '.quiz-card', '.quiz-copy > p', '.quiz-filter-label', '.subpage-head > *', '.subpage-jump',
  '.lesson-section', '.reader-opening > *', '.chapter-photo', '.chapter-concept', '.chapter-check', '.reader-finish',
  '.time-nav', '.timeline-detail', '.planet-tabs', '.planet-stage', '.planet-info', '.experience-heading', '.compare-controls',
  '.glossary-search', '.glossary-chips', '.evidence-key > div', '.image-credits figure', '.extra-reading-links a', '.cosmos-scene',
  '.observatory.is-chapter .obs-head', '.lesson-step'
];

export function initMotion(): void {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  const nodes = [...document.querySelectorAll<HTMLElement>(SELECTORS.join(','))].filter((n) => !n.closest('.hero-shell, [hidden], .obs-station'));
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  const seen = new Map<Element, number>();
  for (const n of nodes) {
    const parent = n.parentElement!;
    const i = seen.get(parent) ?? 0; seen.set(parent, i + 1);
    n.style.setProperty('--rv-delay', `${Math.min(i, 5) * 0.07}s`);
    n.classList.add('rv');
    if (n.matches('.continue-card, .quiz-card, .chapter-photo, .chapter-concept, .image-credits figure, .cosmos-scene')) n.classList.add('rv-scale');
    io.observe(n);
  }

  // Estrelas acompanham o ponteiro (profundidade)
  const field = document.querySelector<HTMLElement>('.starfield');
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  if (field && hero && matchMedia('(pointer: fine)').matches) {
    hero.addEventListener('pointermove', (e) => {
      const r = hero.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      field.style.transform = `translate(${(-x * 18).toFixed(1)}px, ${(-y * 12).toFixed(1)}px)`;
    });
  }
}
