import dynamic from 'next/dynamic';
import { useEffect, useMemo, useRef, useState } from 'react';
import { hasTimeEvolution, labs, orbitUnitsPerAU, simulate } from '../lib/model';
import { temWebGL } from './Laboratory';

const Scene3D = dynamic(() => import('./Scene3D'), {
  ssr: false,
  loading: () => <div className="lesson-scene-espera">Carregando a cena…</div>,
});

/**
 * Cena 3D da bancada ligada à aula, no topo da página: o fenômeno aparece antes da conta.
 * Usa os parâmetros iniciais da bancada e o mesmo modelo físico; para mudar os valores, a
 * aula leva à bancada completa.
 */
export function LessonScene({ labId }: { labId: string }) {
  const lab = labs.find((l) => l.id === labId)!;
  const valores = useMemo(() => lab.parameters.map((p) => p.initial), [lab]);
  const caixa = useRef<HTMLElement>(null);
  const [pronto, setPronto] = useState<boolean | null>(null);
  const [visivel, setVisivel] = useState(false);
  const [tempo, setTempo] = useState(0);
  const [giro, setGiro] = useState(0);
  const anima = hasTimeEvolution(labId);

  useEffect(() => setPronto(temWebGL()), []);
  useEffect(() => {
    const el = caixa.current;
    if (!el || typeof IntersectionObserver === 'undefined') {
      setVisivel(true);
      return;
    }
    const obs = new IntersectionObserver(([e]) => setVisivel(e.isIntersecting), { rootMargin: '200px' });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  useEffect(() => {
    if (!anima || !visivel || !pronto) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let raf = 0,
      antes = performance.now();
    const passo = (agora: number) => {
      if (agora - antes >= 30) {
        const dt = Math.min(0.12, (agora - antes) / 1000);
        antes = agora;
        setTempo((t) => t + dt);
      }
      raf = requestAnimationFrame(passo);
    };
    raf = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(raf);
  }, [anima, visivel, pronto]);

  const cena = useMemo(() => simulate(labId, valores, tempo), [labId, valores, tempo]);
  const orbital = labId === 'orbitas';
  const centro = orbital ? orbitUnitsPerAU * valores[0] * valores[1] : 0;

  return (
    <section id="visual" className="lesson-scene" ref={caixa} aria-label={'Cena 3D: ' + lab.title}>
      <div className="lesson-scene-palco">
        {pronto && visivel ? (
          <Scene3D
            lab={labId}
            dots={cena.dots}
            segments={cena.segments}
            referenceOrbit={[]}
            orbital={orbital}
            center={centro}
            turn={giro}
            resetView={0}
            onFail={() => setPronto(false)}
          />
        ) : (
          <div className="lesson-scene-espera">
            {pronto === false ? 'Este navegador não abriu WebGL. A bancada tem a projeção 2D.' : 'Carregando a cena…'}
          </div>
        )}
        <button type="button" className="lesson-scene-girar" onClick={() => setGiro((g) => g + 0.35)}>
          Girar
        </button>
      </div>
      <div className="lesson-scene-legenda">
        <p>
          <strong>{lab.title}.</strong> {cena.caption} Arraste para girar a cena.
        </p>
        <a className="btn dark" href={'/laboratorios/' + labId + '/'}>
          Mudar os parâmetros
        </a>
      </div>
    </section>
  );
}
