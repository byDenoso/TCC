'use client';
import {
  Component,
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { KeyboardEvent, PointerEvent, ReactNode } from 'react';
import {
  bound,
  facing,
  formatN,
  initialCamera,
  orbitPoint,
  orbitRadius,
  solar,
  stations,
  trappist,
} from './explorer-data';
import type { CameraView, Orbit, Vec } from './explorer-data';
import { ink, makeField, sky } from './explorer-geometry';

const Scene = lazy(() => import('./ExpoScene'));
const labels = [
  'Sistema planetário',
  'Sistema planetário',
  'Nebulosa',
  'Galáxia',
  'Aglomerado',
  'Estrutura em grande escala',
];
const cameraStart = (i: number) => ({ ...initialCamera, tilt: [32, 32, 15, 30, 18, 24][i] });

class SceneGuard extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function Icon({ name }: { name: 'cross' | 'path' | 'minus' | 'plus' | 'reset' | 'turn' | 'box' }) {
  const paths = {
    cross: 'M12 2v5m0 10v5M2 12h5m10 0h5 M15.5 12a3.5 3.5 0 1 0-7 0 3.5 3.5 0 0 0 7 0Z',
    path: 'M3 19c3.5 0 4-2 5-7s7-7 13-7m-4 5 4-5-5-3',
    minus: 'M5 12h14',
    plus: 'M5 12h14m-7-7v14',
    reset: 'M4 9a8 8 0 1 1 1 9M4 4v5h5',
    turn: 'M2 12c0-3 4.5-5 10-5s10 2 10 5-4.5 5-10 5c-2 0-4-.3-5.5-.8m1.5 3.3-3.3-4.5L10 14',
    box: 'm12 2 8.6 5v10L12 22l-8.6-5V7Zm-8 5.4 8 4.7 8-4.7M12 12v10',
  };
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.45"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  );
}
function Background() {
  return (
    <svg
      className="exp-sky"
      aria-hidden="true"
      viewBox="0 0 700 390"
      preserveAspectRatio="xMidYMid slice"
    >
      {sky.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#c9d9ed" opacity={s.o} />
      ))}
    </svg>
  );
}
const plot = (p: Vec, view: CameraView): Vec => {
  const [x, y, z] = facing(p, view);
  return [350 + x * 91 * view.zoom, 195 - y * 91 * view.zoom, z];
};
const lineCoords = (v: number) => v.toFixed(1);

function Diagram({
  id,
  view,
  orbits,
  linear,
  day,
  selected,
  onSelect,
}: {
  id: string;
  view: CameraView;
  orbits: Orbit[];
  linear: boolean;
  day: number;
  selected: number;
  onSelect: (i: number) => void;
}) {
  const prefix = useId().replace(/[^a-zA-Z0-9-]/g, '');
  const base = useMemo(() => makeField(id), [id]);
  const cloud = useMemo(() => {
    const paths = Array.from({ length: ink.length * 2 }, () => '');
    const stride = Math.max(1, Math.ceil(base.grains.length / 1500));
    for (let i = 0; i < base.grains.length; i += stride) {
      const g = base.grains[i],
        [x, y] = plot(g.p, view);
      const r = Math.max(0.5, Math.min(3.8, g.width * 0.48 * view.zoom));
      const k = g.tone + (g.width > 3.1 ? ink.length : 0);
      paths[k] += `M${lineCoords(x)} ${lineCoords(y)}h${lineCoords(r)}`;
    }
    return paths;
  }, [base, view]);
  const size = orbits.length ? orbits[orbits.length - 1].a : 1;
  const starTint = id === 'trappist' ? '#ff9976' : '#ffd283';
  const body = orbits
    .map((o, i) => ({ p: plot(orbitPoint(o, size, linear, day), view), o, i }))
    .sort((a, b) => a.p[2] - b.p[2]);
  const renderPlanet = ({ p, o, i }: (typeof body)[number]) => {
    const r = o.symbolSize * 93 * view.zoom,
      chosen = i === selected;
    return (
      <g
        key={o.name}
        transform={`translate(${p[0]},${p[1]})`}
        onClick={() => onSelect(i)}
        style={{ cursor: 'pointer' }}
      >
        <circle r={Math.max(13, r * 1.8)} fill="transparent" />
        {chosen && (
          <circle r={r + 5} stroke={o.color} strokeDasharray="3 2" strokeOpacity=".85" fill="none" />
        )}
        <circle r={r} fill={`url(#${prefix}-body-${i})`} />
        {o.name === 'Saturno' && (
          <ellipse
            rx={r * 1.75}
            ry={r * 0.36}
            transform="rotate(-18)"
            fill="none"
            stroke="#d2b787"
            strokeWidth={r * 0.22}
          />
        )}
      </g>
    );
  };
  return (
    <svg
      className="exp-diagram"
      role="img"
      aria-label={`${stations.find((s) => s.id === id)?.name}. Projeção do esquema espacial.`}
      viewBox="0 0 700 390"
    >
      <defs>
        <radialGradient id={prefix + '-star'}>
          <stop stopColor="#fff8dd" />
          <stop offset=".16" stopColor={starTint} stopOpacity=".94" />
          <stop offset=".34" stopColor="#eaa56e" stopOpacity=".3" />
          <stop offset="1" stopColor="#d77839" stopOpacity="0" />
        </radialGradient>
        <filter id={prefix + '-blur'} x="-10%" y="-20%" width="120%" height="140%">
          <feGaussianBlur stdDeviation={id === 'orion' ? '7' : '3.2'} />
        </filter>
        {orbits.map((o, i) => (
          <radialGradient key={o.name} id={prefix + '-body-' + i} cx="30%" cy="23%" r="76%">
            <stop stopColor="#fff5de" />
            <stop offset=".26" stopColor={o.color} />
            <stop offset=".65" stopColor={o.color} />
            <stop offset="1" stopColor="#202d47" />
          </radialGradient>
        ))}
      </defs>
      {orbits.length > 0 ? (
        <>
          {orbits.map((o, i) => {
            const r = orbitRadius(o.a, size, linear);
            const pts = Array.from({ length: 97 }, (_, j) => {
              const a = (j * Math.PI) / 48;
              const q = plot([r * Math.cos(a), 0, r * Math.sin(a)], view);
              return lineCoords(q[0]) + ',' + lineCoords(q[1]);
            }).join(' ');
            return (
              <polyline
                key={o.name}
                points={pts}
                fill="none"
                stroke={i === selected ? o.color : '#7798bd'}
                opacity={i === selected ? 0.85 : 0.43}
                strokeWidth={i === selected ? 1.4 : 0.8}
              />
            );
          })}
          {body.filter((b) => b.p[2] < 0).map(renderPlanet)}
          <circle cx="350" cy="195" r={37 * view.zoom} fill={`url(#${prefix}-star)`} />
          <circle cx="350" cy="195" r={7.5 * view.zoom} fill={starTint} />
          {body.filter((b) => b.p[2] >= 0).map(renderPlanet)}
        </>
      ) : (
        <>
          {base.wires.length > 0 && (
            <g stroke="#739bcc" opacity=".30" strokeWidth=".8">
              {base.wires.map((w, i) => {
                const [x, y] = plot(w.a, view),
                  [x2, y2] = plot(w.b, view);
                return <line key={i} x1={x} y1={y} x2={x2} y2={y2} />;
              })}
            </g>
          )}
          <g filter={`url(#${prefix}-blur)`}>
            {cloud.map(
              (p, i) =>
                p && (
                  <path
                    key={i}
                    d={p}
                    stroke={ink[i % ink.length]}
                    fill="none"
                    strokeWidth={id === 'orion' ? 11 : 4.5}
                    opacity={id === 'orion' ? 0.3 : 0.27}
                    strokeLinecap="round"
                  />
                )
            )}
          </g>
          {cloud.map(
            (p, i) =>
              p && (
                <path
                  key={i}
                  d={p}
                  stroke={ink[i % ink.length]}
                  fill="none"
                  opacity={i >= ink.length ? 0.85 : 0.69}
                  strokeWidth={i >= ink.length ? 1.9 : 1.25}
                  strokeLinecap="round"
                />
              )
          )}
        </>
      )}
    </svg>
  );
}

export default function Expo() {
  const [index, setIndex] = useState(0),
    [selection, setSelection] = useState(2),
    [day, setDay] = useState(0),
    [linear, setLinear] = useState(false);
  const [view, setView] = useState<CameraView>(initialCamera),
    [mode, setMode] = useState<'2d' | '3d'>('2d'),
    [has3D, setHas3D] = useState(true);
  const [reduced, setReduced] = useState(true),
    [guided, setGuided] = useState(false),
    [readings, setReadings] = useState(true),
    [status, setStatus] = useState('');
  const drag = useRef<{ x: number; y: number; a: number; t: number; moved: boolean } | null>(null);
  const navigation = useRef<HTMLElement>(null);
  const baseId = useId();
  const station = stations[index];
  const orbits = index === 0 ? solar : index === 1 ? trappist : [];
  const body = orbits[selection];
  const select = useCallback((i: number) => {
    if (!drag.current?.moved) setSelection(i);
  }, []);
  const go = useCallback((i: number, write = true) => {
    const n = bound(i, 0, stations.length - 1);
    setIndex(n);
    setSelection(n === 1 ? 3 : 2);
    setDay(0);
    setLinear(n === 1);
    setView(cameraStart(n));
    if (write && typeof window !== 'undefined') {
      window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${window.location.search}#${stations[n].id}`
      );
    }
  }, []);
  useEffect(() => {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const syncMotion = () => setReduced(motion.matches);
    syncMotion();
    motion.addEventListener('change', syncMotion);
    const syncHash = () => {
      const i = stations.findIndex((s) => '#' + s.id === window.location.hash);
      if (i !== -1) go(i, false);
    };
    syncHash();
    window.addEventListener('hashchange', syncHash);
    return () => {
      motion.removeEventListener('change', syncMotion);
      window.removeEventListener('hashchange', syncHash);
    };
  }, [go]);
  useEffect(() => {
    const nav = navigation.current,
      current = nav?.querySelector<HTMLElement>('[aria-current="step"]');
    if (!nav || !current || nav.scrollWidth <= nav.clientWidth) return;
    const frame = nav.getBoundingClientRect(),
      selected = current.getBoundingClientRect();
    if (selected.left < frame.left || selected.right > frame.right) {
      nav.scrollTo({
        left: nav.scrollLeft + selected.left - frame.left - (nav.clientWidth - selected.width) / 2,
        behavior: reduced ? 'auto' : 'smooth',
      });
    }
  }, [index, reduced]);
  const fail = useCallback(() => {
    setMode('2d');
    setHas3D(false);
    setStatus('O mapa 2D está ativo. Este navegador não conseguiu abrir a cena 3D.');
  }, []);
  function show3D() {
    if (mode === '3d') return;
    if (!has3D) return;
    try {
      const c = document.createElement('canvas');
      const g = c.getContext('webgl2', { powerPreference: 'low-power' });
      if (!g) {
        fail();
        return;
      }
      g.getExtension('WEBGL_lose_context')?.loseContext();
      setMode('3d');
      setStatus('');
    } catch {
      fail();
    }
  }
  function pointerDown(e: PointerEvent<HTMLDivElement>) {
    if (!e.isPrimary || e.button !== 0) return;
    drag.current = { x: e.clientX, y: e.clientY, a: view.azimuth, t: view.tilt, moved: false };
  }
  function pointerMove(e: PointerEvent<HTMLDivElement>) {
    const t = drag.current;
    if (!t || !e.isPrimary || e.buttons === 0) return;
    const dx = e.clientX - t.x,
      dy = e.clientY - t.y;
    if (!t.moved && Math.hypot(dx, dy) < 5) return;
    t.moved = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    setView((v) => ({
      ...v,
      azimuth: (((t.a + dx * 0.45) % 360) + 360) % 360,
      tilt: bound(t.t + dy * 0.28, 5, 85),
    }));
  }
  function pointerEnd(e: PointerEvent<HTMLDivElement>) {
    const moved = drag.current?.moved;
    if (e.currentTarget.hasPointerCapture(e.pointerId))
      e.currentTarget.releasePointerCapture(e.pointerId);
    if (moved) {
      window.setTimeout(() => {
        drag.current = null;
      }, 0);
    } else {
      drag.current = null;
    }
  }
  function keys(e: KeyboardEvent<HTMLDivElement>) {
    const map: Record<string, [number, number, number]> = {
      ArrowLeft: [-10, 0, 0],
      ArrowRight: [10, 0, 0],
      ArrowUp: [0, 5, 0],
      ArrowDown: [0, -5, 0],
      '+': [0, 0, 0.1],
      '=': [0, 0, 0.1],
      '-': [0, 0, -0.1],
    };
    if (e.key === 'Home') {
      e.preventDefault();
      setView(cameraStart(index));
      return;
    }
    const d = map[e.key];
    if (!d) return;
    e.preventDefault();
    setView((v) => ({
      azimuth: (v.azimuth + d[0] + 360) % 360,
      tilt: bound(v.tilt + d[1], 5, 85),
      zoom: bound(v.zoom + d[2], 0.65, 2.4),
    }));
  }
  const stepJourney = () => {
    if (!guided) {
      go(0);
      setGuided(true);
      setReadings(true);
    } else if (index < stations.length - 1) go(index + 1);
    else {
      setGuided(false);
      setStatus('Viagem guiada concluída. As seis escalas estão disponíveis para nova exploração.');
    }
  };
  return (
    <article className="cosmos-explorer">
      <header className="exp-heading">
        <div>
          <p className="exp-kicker">Atlas interativo</p>
          <h1>Explorador do Universo</h1>
        </div>
        <p>
          Parta da órbita da Terra e atravesse seis escalas até a teia cósmica. Escolha um destino ou
          siga a viagem guiada.
        </p>
      </header>
      <nav ref={navigation} className="exp-stations" aria-label="Destinos do explorador">
        {stations.map((s, i) => (
          <button
            key={s.id}
            type="button"
            className={index === i ? 'active' : ''}
            aria-current={index === i ? 'step' : undefined}
            onClick={() => go(i)}
          >
            <span className="exp-station-dot" aria-hidden="true" />
            {s.short}
          </button>
        ))}
      </nav>
      <div className="exp-console">
        <div className="exp-map-column">
          <div className="exp-map">
            <Background />
            <div className="exp-map-caption">
              <span className="exp-sight" />
              <span>
                {mode === '3d' ? 'Cena 3D' : 'Mapa 2D'}
                <b>{station.family}</b>
              </span>
            </div>
            <div className="exp-mode">
              <button
                type="button"
                aria-pressed={mode === '2d'}
                onClick={() => {
                  setMode('2d');
                  setStatus('');
                }}
              >
                Mapa 2D
              </button>
              <button type="button" aria-pressed={mode === '3d'} disabled={!has3D} onClick={show3D}>
                <Icon name="box" />
                Cena 3D
              </button>
            </div>
            <div
              className="exp-surface"
              tabIndex={0}
              role="group"
              aria-label={'Câmera de ' + station.name}
              aria-describedby={baseId + '-keys'}
              onKeyDown={keys}
              onPointerDown={pointerDown}
              onPointerMove={pointerMove}
              onPointerUp={pointerEnd}
              onPointerCancel={() => {
                drag.current = null;
              }}
            >
              {mode === '3d' ? (
                <SceneGuard onError={fail}>
                  <Suspense
                    fallback={
                      <Diagram
                        id={station.id}
                        view={view}
                        orbits={orbits}
                        linear={linear}
                        day={day}
                        selected={selection}
                        onSelect={select}
                      />
                    }
                  >
                    <Scene
                      station={station.id}
                      cameraView={view}
                      orbits={orbits}
                      selected={selection}
                      day={day}
                      linear={linear}
                      reduced={reduced}
                      onSelect={select}
                      onFailure={fail}
                    />
                  </Suspense>
                </SceneGuard>
              ) : (
                <Diagram
                  id={station.id}
                  view={view}
                  orbits={orbits}
                  linear={linear}
                  day={day}
                  selected={selection}
                  onSelect={select}
                />
              )}
            </div>
            <div className="exp-map-footer">
              <span>Ilustração · {station.frame}</span>
              <span>{formatN(view.zoom, 1)}×</span>
            </div>
          </div>
          <div className="exp-tools">
            <label htmlFor={baseId + '-tilt'}>
              <span>
                Inclinação <output>{formatN(view.tilt, 0)}°</output>
              </span>
              <input
                id={baseId + '-tilt'}
                aria-label="Inclinação da câmera"
                type="range"
                min="5"
                max="85"
                step="1"
                value={Math.round(view.tilt)}
                onChange={(e) => setView((v) => ({ ...v, tilt: Number(e.target.value) }))}
              />
            </label>
            <label htmlFor={baseId + '-yaw'}>
              <span>
                Giro <output>{formatN(view.azimuth, 0)}°</output>
              </span>
              <input
                id={baseId + '-yaw'}
                aria-label="Giro da câmera"
                type="range"
                min="0"
                max="359"
                step="1"
                value={Math.round(view.azimuth) % 360}
                onChange={(e) => setView((v) => ({ ...v, azimuth: Number(e.target.value) }))}
              />
            </label>
            <div className="exp-zoom">
              <button
                type="button"
                title="Afastar"
                aria-label="Afastar"
                disabled={view.zoom <= 0.65}
                onClick={() => setView((v) => ({ ...v, zoom: Math.max(0.65, v.zoom - 0.2) }))}
              >
                <Icon name="minus" />
              </button>
              <button
                type="button"
                aria-label="Aproximar"
                title="Aproximar"
                disabled={view.zoom >= 2.4}
                onClick={() => setView((v) => ({ ...v, zoom: Math.min(2.4, v.zoom + 0.2) }))}
              >
                <Icon name="plus" />
              </button>
              <button
                type="button"
                aria-label="Restaurar câmera"
                title="Restaurar câmera"
                onClick={() => setView(cameraStart(index))}
              >
                <Icon name="reset" />
              </button>
            </div>
          </div>
          <p className="exp-key-help" id={baseId + '-keys'}>
            Arraste para girar. Com o foco no mapa, use as setas para orientar a câmera e + ou − para
            ajustar o zoom.
          </p>
        </div>
        <section className="exp-dossier" aria-labelledby={baseId + '-target'}>
          <p className="exp-kicker">Destino {String(index + 1).padStart(2, '0')} de 06</p>
          <h2 id={baseId + '-target'}>{station.name}</h2>
          <div className="exp-distance">
            <span>{station.measure}</span>
            <strong>{station.value}</strong>
          </div>
          {orbits.length > 0 && (
            <div className="exp-orbits">
              <label>
                Planeta
                <select
                  aria-label="Planeta"
                  value={selection}
                  onChange={(e) => setSelection(Number(e.target.value))}
                >
                  {orbits.map((o, i) => (
                    <option key={o.name} value={i}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </label>
              {body && (
                <div className="exp-body-values">
                  <div>
                    <span>Semieixo orbital</span>
                    <strong>{formatN(body.a, index === 1 ? 5 : 3)} au</strong>
                  </div>
                  <div>
                    <span>Período</span>
                    <strong>{formatN(body.days, index === 1 ? 3 : 1)} dias</strong>
                  </div>
                </div>
              )}
              <label htmlFor={baseId + '-time'}>
                <span>
                  Tempo transcorrido <output>{formatN(day, index === 1 ? 1 : 0)} dias</output>
                </span>
                <input
                  id={baseId + '-time'}
                  aria-label="Tempo transcorrido em dias"
                  type="range"
                  min="0"
                  max={index === 0 ? 365 : 20}
                  step={index === 0 ? 1 : 0.1}
                  value={day}
                  onChange={(e) => setDay(Number(e.target.value))}
                />
              </label>
              <label className="exp-check">
                <input type="checkbox" checked={linear} onChange={(e) => setLinear(e.target.checked)} />
                Distâncias orbitais lineares
              </label>
              <small>
                {linear
                  ? 'Escala radial proporcional aos semieixos.'
                  : 'Escala radial logarítmica para distinguir as órbitas internas.'}
              </small>
            </div>
          )}
          <label className="exp-check exp-reading">
            <input type="checkbox" checked={readings} onChange={(e) => setReadings(e.target.checked)} />
            Modo educacional
          </label>
          {readings && (
            <div className="exp-prose">
              <p>{station.text}</p>
              {body && <p>{body.note}</p>}
            </div>
          )}
          <div className="exp-source">
            <span>Fonte científica</span>
            <a href={station.url} target="_blank" rel="noreferrer">
              {station.source}
            </a>
          </div>
        </section>
      </div>
      {status && (
        <p role="status" className="exp-status">
          {status}
        </p>
      )}
      <section className="exp-guide" aria-label="Viagem guiada">
        <div className="exp-guide-symbol">
          <Icon name="path" />
        </div>
        <div>
          <p className="exp-kicker">
            {guided ? 'Viagem guiada · ' + (index + 1) + ' de 6' : 'Viagem guiada'}
          </p>
          <h3>{guided ? station.guide : 'Uma pergunta em cada escala'}</h3>
        </div>
        <div className="exp-guide-actions">
          {guided && (
            <button type="button" className="exp-secondary" onClick={() => setGuided(false)}>
              Sair da viagem
            </button>
          )}
          <button type="button" className="exp-primary" onClick={stepJourney}>
            {!guided ? 'Iniciar viagem' : index === 5 ? 'Concluir viagem' : 'Próxima parada'}
          </button>
        </div>
      </section>
      <details className="exp-notes" open>
        <summary>Como interpretar a cena</summary>
        <p>{station.convention}</p>
        {index === 0 && (
          <p>
            O período adotado é o de uma revolução sideral, medido em dias terrestres.{' '}
            <a href="https://ssd.jpl.nasa.gov/planets/phys_par.html" target="_blank" rel="noreferrer">
              Parâmetros físicos dos planetas, JPL
            </a>
            .
          </p>
        )}
      </details>
      <details className="exp-notes">
        <summary>Consultar as seis escalas em texto</summary>
        <ol>
          {stations.map((s, i) => (
            <li key={s.id}>
              <strong>{s.name}</strong>
              <span>
                {labels[i]} · {s.measure} — {s.value}.
              </span>
              <p>{s.text}</p>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.source}
              </a>
            </li>
          ))}
        </ol>
      </details>
    </article>
  );
}
