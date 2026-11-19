import { useEffect, useRef } from 'react';

export default function MotionBand() {
  const figure = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const svg = figure.current;
    const path = svg?.querySelector<SVGPathElement>('.method-curve');
    const point = svg?.querySelector('circle');
    if (!svg || !path || !point || !('IntersectionObserver' in window)) return;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let visible = false,
      sequence = 0;
    let stop = () => {};
    const refresh = () => {
      const revision = ++sequence;
      stop();
      if (!visible || reduced.matches) return;
      // This diagram is the final section. Load its two engines at the figure, not at the hero.
      Promise.all([import('gsap'), import('motion')])
        .then(([{ gsap }, { animate }]) => {
          if (revision !== sequence) return;
          const spring = animate(
            point,
            { scale: [1, 1.25] },
            { type: 'spring', stiffness: 180, damping: 15 }
          );
          let frame = 0;
          const paint = () => {
            frame = 0;
            const rect = svg.getBoundingClientRect();
            const k = Math.min(1, Math.max(0, (innerHeight - rect.top) / (innerHeight + rect.height)));
            gsap.set(path, {
              attr: {
                d: `M0 58 C100 ${90 - 80 * k} 140 ${55 + 45 * k} 230 51 S390 ${2 + 55 * k} 500 45`,
              },
            });
          };
          const scroll = () => {
            if (!frame) frame = requestAnimationFrame(paint);
          };
          paint();
          window.addEventListener('scroll', scroll, { passive: true });
          stop = () => {
            spring.stop();
            cancelAnimationFrame(frame);
            window.removeEventListener('scroll', scroll);
          };
        })
        .catch(() => {
          /* The static diagram remains visible. */
        });
    };
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        refresh();
      },
      { rootMargin: '100px' }
    );
    observer.observe(svg);
    reduced.addEventListener('change', refresh);
    return () => {
      sequence++;
      stop();
      observer.disconnect();
      reduced.removeEventListener('change', refresh);
    };
  }, []);
  return (
    <svg ref={figure} viewBox="0 0 500 110" className="method-art" aria-hidden="true">
      <path className="faint" d="M0 82H500M0 47H500M0 12H500" />
      <path className="method-curve" d="M0 58 C100 90 140 55 230 51 S390 2 500 45" />
      <circle cx="230" cy="51" r="4" fill="currentColor" />
    </svg>
  );
}
