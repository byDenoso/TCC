import dynamic from 'next/dynamic';
import LabChallenge from './LabChallenge';
import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { hasTimeEvolution, labs, orbitGuide, orbitUnitsPerAU, simulate } from '../lib/model';
import { compact } from '../lib/school';
import { Plot } from './Plot';
let verifiedWebGL = false;
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
  const [values, setValues] = useState(initial),
    [base, setBase] = useState<number[] | null>(null),
    [view, setView] = useState(false),
    [error, setError] = useState(''),
    [playing, setPlay] = useState(false),
    [time, setTime] = useState(0),
    [turn, setTurn] = useState(0),
    [resetView, setResetView] = useState(0),
    [visible, setVisible] = useState(true);
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
    if (!playing || !visible) return;
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
  }, [playing, view, visible]);
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
  return (
    <div className={'laboratory ' + (mini ? 'mini' : '')}>
      <div className="lab-body">
        <div className="lab-visual" ref={stage}>
          <div className="scene-toolbar">
            <span>{view ? 'Cena 3D' : 'Projeção 2D'}</span>
            <button onClick={enable}>{view ? 'Usar 2D' : 'Abrir 3D'}</button>
          </div>
          {view ? (
            <SceneBoundary onFail={fail}>
              <Scene3D
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
                  <path d="M34 0H0V34" fill="none" stroke="#29405a" strokeWidth=".6" />
                </pattern>
              </defs>
              <rect width="540" height="290" fill={'url(#grid-' + id + ')'} />
              {orbital && (
                <path
                  fill="none"
                  stroke="#425c76"
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
                stroke="#9cd9f2"
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
          <div className="scene-bottom">
            {hasTimeEvolution(id) && (
              <button onClick={() => setPlay(!playing)}>{playing ? 'Pausar' : 'Animar'}</button>
            )}
            <button onClick={() => setTurn(turn + 0.25)}>Girar vista</button>
            {hasTimeEvolution(id) && (
              <span className="scene-clock">
                {orbital ? compact(time * 30) + ' dias simulados' : compact(time) + ' s de animação'}
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
                  setValues((old) => old.map((v, j) => (j === i ? value : v)));
                }}
              />
            </label>
          ))}
          <div className="metric">
            <span>{scene.metric.label}</span>
            <strong>
              {compact(scene.metric.value)} <small>{scene.metric.unit}</small>
            </strong>
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
            <button onClick={() => setBase(base ? null : [...values])}>
              {base ? 'Remover referência' : 'Fixar referência'}
            </button>
            <button onClick={reset}>Reiniciar</button>
          </div>
        </div>
      </div>
      {!mini && (
        <>
          <p className="caption">{scene.caption}</p>
          {baseline && (
            <p className="compare-key">
              Curva tracejada · referência fixa com{' '}
              {lab.parameters.map((p, i) => p.label + ' ' + compact(base![i]) + ' ' + p.unit).join(' e ')}.{' '}
              {baseline.metric.label} = {compact(baseline.metric.value)} {baseline.metric.unit}.
            </p>
          )}
          <Plot
            points={scene.points}
            reference={baseline?.points}
            xLabel={lab.xLabel}
            yLabel={lab.yLabel}
          />
          <LabChallenge lab={lab} values={values} onMeasure={measure} />
          <aside className="method">
            <h3>Hipóteses e limites</h3>
            <p>{lab.assumptions}</p>
            <a href={lab.reference.url}>{lab.reference.name} ↗</a>
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
