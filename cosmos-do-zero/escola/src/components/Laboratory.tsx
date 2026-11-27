import dynamic from 'next/dynamic';
import LabChallenge from './LabChallenge';
import { Component, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { hasTimeEvolution, labs, orbitGuide, orbitUnitsPerAU, simulate } from '../lib/model';
import { compact } from '../lib/school';
import { ExpansionDiagram } from './ExpansionDiagram';
import { Plot } from './Plot';
let verifiedWebGL = false;
/** WebGL2 disponível e não desativado: a cena 3D vira a vista padrão. */
export function temWebGL() {
  if (verifiedWebGL) return true;
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2');
    if (!gl) return false;
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    verifiedWebGL = true;
    return true;
  } catch {
    return false;
  }
}
const Scene3D = dynamic(() => import('./Scene3D'), {
  ssr: false,
  loading: () => <p className="pad">Carregando o motor 3D…</p>,
});
class SceneBoundary extends Component<
  { onFail: () => void; children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFail();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
export function LabView({ id, mini = false }: { id: string; mini?: boolean }) {
  const lab = labs.find((l) => l.id === id)!;
  const initial = useMemo(() => lab.parameters.map((p) => p.initial), [lab]);
  const stage = useRef<HTMLDivElement>(null);
  const orbital = id === 'orbitas';
  const expansion = id === 'expansao';
  const timeEvolution = hasTimeEvolution(id);
  const motionHint = useId();
  const sweepDistance = useRef(initial[1]);
  const [values, setValues] = useState(initial),
    [base, setBase] = useState<number[] | null>(null),
    [view, setView] = useState(false),
    [error, setError] = useState(''),
    [playing, setPlay] = useState(false),
    [time, setTime] = useState(0),
    [turn, setTurn] = useState(0),
    [resetView, setResetView] = useState(0),
    [visible, setVisible] = useState(true),
    [reveal, setReveal] = useState(65),
    [reducedMotion, setReducedMotion] = useState(false);
  // a explicação visual vem primeiro: com WebGL, a bancada abre direto na cena 3D
  useEffect(() => {
    if (temWebGL()) setView(true);
  }, []);
  useEffect(() => {
    if (!stage.current || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting));
    observer.observe(stage.current);
    return () => observer.disconnect();
  }, []);
  const center = orbital ? orbitUnitsPerAU * values[0] * values[1] : 0;
  const measure = useCallback(() => {
    setPlay(false);
    setTime(0);
  }, []);
  useEffect(() => {
    if (!expansion) return;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    function sync() {
      setReducedMotion(preference.matches);
      if (preference.matches) setPlay(false);
    }
    sync();
    preference.addEventListener('change', sync);
    return () => preference.removeEventListener('change', sync);
  }, [expansion]);
  useEffect(() => {
    if (!playing || !visible || !timeEvolution) return;
    let raf = 0,
      last = performance.now();
    function step(now: number) {
      if (now - last >= (view ? 15 : 30)) {
        const dt = Math.min(0.12, (now - last) / 1000);
        last = now;
        setTime((t) => t + dt);
      }
      raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, timeEvolution, view, visible]);
  useEffect(() => {
    if (!expansion || !playing || !visible || reducedMotion) return;
    const { max, step } = lab.parameters[1];
    const from = sweepDistance.current;
    const start = performance.now();
    let frame = requestAnimationFrame(sweep);
    function sweep(now: number) {
      const next = Math.min(max, from + Math.floor((now - start) / 48) * step);
      if (next !== sweepDistance.current) {
        sweepDistance.current = next;
        setValues(([h0]) => [h0, next]);
      }
      if (next < max) frame = requestAnimationFrame(sweep);
      else setPlay(false);
    }
    return () => cancelAnimationFrame(frame);
  }, [expansion, lab, playing, reducedMotion, visible]);
  const scene = useMemo(() => simulate(id, values, time), [id, values, time]);
  const baseline = useMemo(() => (base ? simulate(id, base, 0) : null), [base, id]);
  const referenceOrbit = useMemo(
    () => (orbital && baseline ? baseline.segments.slice(0, -1).filter((_, i) => i % 2 === 0) : []),
    [baseline, orbital]
  );
  const fail = useCallback(() => {
    verifiedWebGL = false;
    setView(false);
    setError('O navegador abriu a projeção 2D. Os cálculos continuam disponíveis.');
  }, []);
  function enable() {
    if (view) {
      setView(false);
      return;
    }
    try {
      if (!verifiedWebGL) {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl2');
        if (!gl && !('gpu' in navigator && navigator.gpu)) {
          fail();
          return;
        }
        verifiedWebGL = !!gl;
        gl?.getExtension('WEBGL_lose_context')?.loseContext();
      }
      setError('');
      setView(true);
    } catch {
      fail();
    }
  }
  function reset() {
    setValues(initial);
    setBase(null);
    setTime(0);
    setPlay(false);
    setTurn(0);
    setResetView((n) => n + 1);
  }
  function togglePlayback() {
    if (playing) {
      setPlay(false);
      return;
    }
    if (expansion) {
      const { min, max } = lab.parameters[1];
      sweepDistance.current = values[1] === max ? min : values[1];
      setValues([values[0], sweepDistance.current]);
    }
    setPlay(true);
  }
  function proj(x: number, y: number, z: number) {
    if (orbital) {
      const u = x + center,
        v = y / 0.54;
      return [
        270 + 87 * (u * Math.cos(turn) - v * Math.sin(turn)),
        145 - 49 * (u * Math.sin(turn) + v * Math.cos(turn)),
      ].map((n) => +n.toFixed(4));
    }
    const a = x * Math.cos(turn) - z * Math.sin(turn),
      b = x * Math.sin(turn) + z * Math.cos(turn);
    return [270 + 93 * a + 17 * b, 145 - 78 * y + 35 * b].map((n) => +n.toFixed(4));
  }
  const points = scene.dots,
    lines = scene.segments;
  const plot = (
    <Plot
      points={scene.points}
      reference={baseline?.points}
      selection={
        expansion
          ? {
              point: [values[1], scene.metric.value],
              label: 'Galáxia selecionada · ' + compact(values[1]) + ' Mpc · ' + compact(scene.metric.value) + ' km/s',
              referencePoint: base && baseline ? [base[1], baseline.metric.value] : undefined,
            }
          : undefined
      }
      yDomain={expansion ? [0, lab.parameters[0].max * lab.parameters[1].max] : undefined}
      xLabel={lab.xLabel}
      yLabel={lab.yLabel}
    />
  );
  const caption = <p className="caption">{scene.caption}</p>;
  return (
    <div className={'laboratory' + (mini ? ' mini' : '') + (expansion ? ' laboratory--expansion' : '')}>
      <div className="lab-body">
        <div className="lab-visual" ref={stage}>
          <div className="scene-toolbar">
            <span>{view ? 'Cena 3D' : expansion ? 'Campo de recessão' : 'Projeção 2D'}</span>
            <button onClick={enable}>{view ? 'Usar 2D' : 'Abrir 3D'}</button>
          </div>
          {view ? (
            <SceneBoundary onFail={fail}>
              <Scene3D
                lab={id}
                dots={points}
                segments={lines}
                referenceOrbit={referenceOrbit}
                orbital={orbital}
                center={center}
                turn={turn}
                resetView={resetView}
                onFail={fail}
              />
            </SceneBoundary>
          ) : expansion ? (
            <ExpansionDiagram scene={scene} reference={baseline} reveal={reveal} project={proj} />
          ) : (
            <svg
              className="lab-svg"
              viewBox="0 0 540 290"
              role="img"
              aria-label={lab.title + '. ' + scene.caption}
            >
              <defs>
                {orbital && (
                  <>
                    <radialGradient id="orbit-star" cx=".36" cy=".28" r=".8">
                      <stop stopColor="#fff8ce" />
                      <stop offset=".55" stopColor="#ffd36b" />
                      <stop offset="1" stopColor="#ee8a35" />
                    </radialGradient>
                    <radialGradient id="orbit-planet" cx=".28" cy=".28" r=".82">
                      <stop stopColor="#e3f8ff" />
                      <stop offset=".45" stopColor="#58bdef" />
                      <stop offset="1" stopColor="#205477" />
                    </radialGradient>
                  </>
                )}
                <pattern id={'grid-' + id} width="34" height="34" patternUnits="userSpaceOnUse">
                  <path d="M34 0H0V34" fill="none" stroke="#24393a" strokeWidth=".6" />
                </pattern>
              </defs>
              <rect width="540" height="290" fill={'url(#grid-' + id + ')'} />
              {orbital && (
                <path
                  fill="none"
                  stroke="#3d5b59"
                  d={orbitGuide
                    .map(
                      ([x, y, z, a, b, c]) => 'M' + proj(x, y, z).join(' ') + 'L' + proj(a, b, c).join(' ')
                    )
                    .join(' ')}
                />
              )}
              {referenceOrbit.length > 0 && (
                <path
                  fill="none"
                  stroke="#ffbb79"
                  strokeWidth="1.4"
                  d={referenceOrbit
                    .map(
                      ([x, y, z, a, b, c]) => 'M' + proj(x, y, z).join(' ') + 'L' + proj(a, b, c).join(' ')
                    )
                    .join(' ')}
                />
              )}
              <path
                fill="none"
                stroke="#8fd0c6"
                strokeWidth="1.2"
                d={lines
                  .map(
                    ([x, y, z, a, b, c]) => 'M' + proj(x, y, z).join(' ') + 'L' + proj(a, b, c).join(' ')
                  )
                  .join(' ')}
              />
              {points.map(([x, y, z], i) => {
                const p = proj(x, y, z);
                return (
                  <circle
                    key={i}
                    cx={p[0]}
                    cy={p[1]}
                    r={orbital ? (i === 0 ? 8 : 5.5) : points.length < 12 ? (i === 0 ? 6 : 4.5) : 1.8}
                    fill={
                      orbital
                        ? i === 0
                          ? 'url(#orbit-star)'
                          : 'url(#orbit-planet)'
                        : i % 3 === 0
                          ? '#ffd9a2'
                          : '#b5e4ff'
                    }
                  />
                );
              })}
            </svg>
          )}
          {orbital && (
            <div className="orbit-key">
              <span>Sol</span>
              <span>Planeta</span>
              <span className="orbit-guide">1 UA</span>
              {base && <span className="orbit-reference">Referência</span>}
              <small>Diâmetros ilustrativos</small>
            </div>
          )}
          {expansion && !view && (
            <div className="expansion-legend">
              <span className="expansion-observer">Observador comóvel</span>
              <span className="expansion-galaxy">Galáxia selecionada</span>
              <span className="expansion-arrow">Vetor de recessão</span>
            </div>
          )}
          {expansion && !view && baseline && (
            <label className="expansion-compare">
              <span>Referência</span>
              <input
                type="range"
                aria-label="Comparar referência e cenário atual"
                aria-valuetext={reveal + '% de referência'}
                min="0"
                max="100"
                value={reveal}
                onChange={(event) => setReveal(event.currentTarget.valueAsNumber)}
              />
              <span>Atual</span>
            </label>
          )}
          <div className="scene-bottom">
            {(timeEvolution || expansion) && (
              <button
                onClick={togglePlayback}
                disabled={expansion && reducedMotion}
                aria-describedby={expansion ? motionHint : undefined}
              >
                {playing ? 'Pausar' : 'Animar'}
              </button>
            )}
            <button onClick={() => setTurn(turn + 0.25)}>Girar vista</button>
            {timeEvolution && (
              <span className="scene-clock">
                {orbital ? compact(time * 30) + ' dias simulados' : compact(time) + ' s de animação'}
              </span>
            )}
            {expansion && (
              <span className="scene-clock expansion-motion-hint" id={motionHint}>
                {reducedMotion ? 'Movimento reduzido. Ajuste a distância manualmente.' : 'Percorre distâncias com H₀ fixo.'}
              </span>
            )}
          </div>
          {error && <p role="status">{error}</p>}
        </div>
        <div className="controls">
          <span className="kicker">Parâmetros físicos</span>
          {lab.parameters.map((p, i) => (
            <label key={p.label}>
              <span>
                {p.label}
                <output aria-live="off">
                  {compact(values[i])} {p.unit === 'adimensional' ? '' : p.unit}
                </output>
              </span>
              <input
                type="range"
                aria-label={p.label}
                aria-valuetext={compact(values[i]) + ' ' + p.unit}
                min={p.min}
                max={p.max}
                step={p.step}
                value={values[i]}
                onChange={(e) => {
                  const value = e.currentTarget.valueAsNumber;
                  if (expansion) setPlay(false);
                  setValues((old) => old.map((v, j) => (j === i ? value : v)));
                }}
              />
            </label>
          ))}
          {expansion && (
            <p className="expansion-equation">
              <span aria-hidden="true">v = H₀ × D</span>
              <span className="screen-reader-only">Velocidade igual à constante de Hubble vezes a distância.</span>
            </p>
          )}
          <div className="metric" aria-live={expansion ? (playing ? 'off' : 'polite') : undefined} aria-atomic={expansion || undefined}>
            <span>{scene.metric.label}</span>
            <strong>
              {compact(scene.metric.value)} <small>{scene.metric.unit}</small>
            </strong>
            {scene.secondaryMetric && (
              <span className="expansion-redshift">
                {scene.secondaryMetric.label} <b>{compact(scene.secondaryMetric.value)}</b>
              </span>
            )}
          </div>
          {orbital && (
            <dl className="orbit-distances">
              <div>
                <dt>Periélio</dt>
                <dd>{compact(values[0] * (1 - values[1]))} UA</dd>
              </div>
              <div>
                <dt>Afélio</dt>
                <dd>{compact(values[0] * (1 + values[1]))} UA</dd>
              </div>
            </dl>
          )}
          <label className="preset">
            Cenário
            <select
              aria-label="Cenário físico"
              value={lab.presets.findIndex((p) => p.values.every((v, j) => Math.abs(v - values[j]) < 1e-8))}
              onChange={(e) => {
                const i = +e.target.value;
                if (i >= 0) setValues([...lab.presets[i].values]);
                if (expansion) setPlay(false);
                setTime(0);
              }}
            >
              <option value="-1">Personalizado</option>
              {lab.presets.map((p, i) => (
                <option key={p.name} value={i}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <div className="row-actions">
            <button
              onClick={() => {
                setBase(base ? null : [...values]);
                if (expansion) setReveal(65);
              }}
            >
              {base ? 'Remover referência' : 'Fixar referência'}
            </button>
            <button onClick={reset}>Reiniciar</button>
          </div>
        </div>
      </div>
      {!mini && (
        <>
          {expansion ? plot : caption}
          {baseline && (
            <p className="compare-key">
              Curva tracejada · referência fixa com{' '}
              {lab.parameters.map((p, i) => p.label + ' ' + compact(base![i]) + ' ' + p.unit).join(' e ')}.{' '}
              {baseline.metric.label} = {compact(baseline.metric.value)} {baseline.metric.unit}.
            </p>
          )}
          {expansion ? caption : plot}
          <LabChallenge lab={lab} values={values} onMeasure={measure} />
          <aside className="method">
            <h3>Hipóteses e limites</h3>
            <p>{lab.assumptions}</p>
            {expansion && (
              <p>
                Os valores da bancada vêm do modelo didático. Em 1929, Edwin Hubble estimou a relação a partir de medidas de distância e velocidade.
              </p>
            )}
            <a href={lab.reference.url}>{lab.reference.name} ↗</a>
            {expansion && <a href="https://doi.org/10.1073/pnas.15.3.168">Edwin Hubble · Artigo de 1929 ↗</a>}
          </aside>
        </>
      )}
      {mini && base && (
        <p className="caption">
          Referência fixa · {baseline?.metric.label} {compact(baseline!.metric.value)}{' '}
          {baseline!.metric.unit}
        </p>
      )}
    </div>
  );
}
