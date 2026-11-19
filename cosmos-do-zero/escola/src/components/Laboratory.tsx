import dynamic from 'next/dynamic';
import LabChallenge from './LabChallenge';
import { Component, useCallback, useEffect, useMemo, useState } from 'react';
import { labs, simulate } from '../lib/model';
import { compact } from '../lib/school';
import { Plot } from './Plot';
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
  const initial = lab.parameters.map((p) => p.initial);
  const [values, setValues] = useState(initial),
    [base, setBase] = useState<number[] | null>(null),
    [view, setView] = useState(false),
    [error, setError] = useState(''),
    [playing, setPlay] = useState(false),
    [time, setTime] = useState(0),
    [turn, setTurn] = useState(0);
  useEffect(() => {
    if (!playing) return;
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
  }, [playing, view]);
  const scene = useMemo(() => simulate(id, values, time), [id, values, time]);
  const baseline = useMemo(() => (base ? simulate(id, base, 0) : null), [base, id]);
  const fail = useCallback(() => {
    setView(false);
    setError('O navegador abriu a projeção 2D. Os cálculos continuam disponíveis.');
  }, []);
  function enable() {
    if (view) {
      setView(false);
      return;
    }
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl2');
      if (!gl && !('gpu' in navigator && navigator.gpu)) {
        fail();
        return;
      }
      gl?.getExtension('WEBGL_lose_context')?.loseContext();
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
  }
  function proj(x: number, y: number, z: number) {
    const a = x * Math.cos(turn) - z * Math.sin(turn),
      b = x * Math.sin(turn) + z * Math.cos(turn);
    return [270 + 93 * a + 17 * b, 145 - 78 * y + 35 * b].map((n) => +n.toFixed(4));
  }
  const points = scene.dots,
    lines = scene.segments;
  return (
    <div className={'laboratory ' + (mini ? 'mini' : '')}>
      <div className="lab-body">
        <div className="lab-visual">
          <div className="scene-toolbar">
            <span>{view ? 'Cena 3D' : 'Projeção 2D'}</span>
            <button onClick={enable}>{view ? 'Usar 2D' : 'Abrir 3D'}</button>
          </div>
          {view ? (
            <SceneBoundary onFail={fail}>
              <Scene3D {...scene} turn={turn} onFail={fail} />
            </SceneBoundary>
          ) : (
            <svg
              className="lab-svg"
              viewBox="0 0 540 290"
              role="img"
              aria-label={lab.title + '. ' + scene.caption}
            >
              <defs>
                <pattern id={'grid-' + id} width="34" height="34" patternUnits="userSpaceOnUse">
                  <path d="M34 0H0V34" fill="none" stroke="#29405a" strokeWidth=".6" />
                </pattern>
              </defs>
              <rect width="540" height="290" fill={'url(#grid-' + id + ')'} />
              {lines.map(([x, y, z, a, b, c], i) => {
                const p = proj(x, y, z),
                  q = proj(a, b, c);
                return (
                  <line
                    key={i}
                    x1={p[0]}
                    y1={p[1]}
                    x2={q[0]}
                    y2={q[1]}
                    stroke="#9cd9f2"
                    strokeWidth="1.15"
                  />
                );
              })}
              {points.map(([x, y, z], i) => {
                const p = proj(x, y, z);
                return (
                  <circle
                    key={i}
                    cx={p[0]}
                    cy={p[1]}
                    r={points.length < 12 ? (i === 0 ? 6 : 4.5) : 1.8}
                    fill={i % 3 === 0 ? '#ffd9a2' : '#b5e4ff'}
                  />
                );
              })}
            </svg>
          )}
          <div className="scene-bottom">
            <button onClick={() => setPlay(!playing)}>{playing ? 'Pausar' : 'Animar'}</button>
            <button onClick={() => setTurn(turn + 0.25)}>Girar vista</button>
            <output>{compact(time)} s de animação</output>
          </div>
          {error && <p role="status">{error}</p>}
        </div>
        <div className="controls">
          <span className="kicker">Parâmetros físicos</span>
          {lab.parameters.map((p, i) => (
            <label key={p.label}>
              <span>
                {p.label}
                <output>
                  {compact(values[i])} {p.unit}
                </output>
              </span>
              <input
                type="range"
                aria-label={p.label}
                min={p.min}
                max={p.max}
                step={p.step}
                value={values[i]}
                onChange={(e) =>
                  setValues((old) => old.map((v, j) => (j === i ? Number(e.target.value) : v)))
                }
              />
            </label>
          ))}
          <div className="metric">
            <span>{scene.metric.label}</span>
            <strong>
              {compact(scene.metric.value)} <small>{scene.metric.unit}</small>
            </strong>
          </div>
          <label className="preset">
            Cenário
            <select
              aria-label="Cenário físico"
              value={lab.presets.findIndex((p) =>
                p.values.every((v, j) => Math.abs(v - values[j]) < 1e-8)
              )}
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
              {lab.parameters
                .map((p, i) => p.label + ' ' + compact(base![i]) + ' ' + p.unit)
                .join(' e ')}
              . {baseline.metric.label} = {compact(baseline.metric.value)} {baseline.metric.unit}.
            </p>
          )}
          <Plot
            points={scene.points}
            reference={baseline?.points}
            xLabel={lab.xLabel}
            yLabel={lab.yLabel}
          />
          <LabChallenge
            lab={lab}
            values={values}
            onMeasure={() => {
              setPlay(false);
              setTime(0);
            }}
          />
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
