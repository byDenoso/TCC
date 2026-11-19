import { useEffect, useRef } from 'react';
import { motion, useReducedMotion } from 'motion/react';
export default function MotionBand() {
  const ref = useRef<SVGPathElement>(null),
    reduce = useReducedMotion();
  useEffect(() => {
    const el = ref.current;
    if (!el || reduce) return;
    let cleanup: () => void = () => {};
    let active = true;
    import('gsap').then(({ gsap }) => {
      if (!active) return;
      const path = el;
      const paint = () => {
        const rect = path.ownerSVGElement?.getBoundingClientRect();
        if (!rect) return;
        const k = Math.min(1, Math.max(0, (innerHeight - rect.top) / (innerHeight + rect.height)));
        gsap.set(path, {
          attr: {
            d:
              'M0 58 C100 ' +
              (90 - 80 * k) +
              ' 140 ' +
              (55 + 45 * k) +
              ' 230 51 S390 ' +
              (2 + 55 * k) +
              ' 500 45',
          },
        });
      };
      paint();
      window.addEventListener('scroll', paint, { passive: true });
      cleanup = () => window.removeEventListener('scroll', paint);
    });
    return () => {
      active = false;
      cleanup();
    };
  }, [reduce]);
  return (
    <motion.svg
      viewBox="0 0 500 110"
      className="method-art"
      aria-hidden="true"
      initial={false}
      whileInView={reduce ? {} : { opacity: [0.7, 1] }}
      viewport={{ once: true }}
    >
      <path className="faint" d="M0 82H500M0 47H500M0 12H500" />
      <path ref={ref} d="M0 58 C100 90 140 55 230 51 S390 2 500 45" />
      <motion.circle
        cx="230"
        cy="51"
        r="4"
        initial={false}
        whileInView={reduce ? {} : { scale: 1.25 }}
        transition={{ type: 'spring', stiffness: 180, damping: 15 }}
        viewport={{ once: true }}
      />
    </motion.svg>
  );
}
