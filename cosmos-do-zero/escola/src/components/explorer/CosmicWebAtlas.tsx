import { Component, lazy, Suspense, useEffect, useId, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AtlasPhoto } from './AtlasPhoto';
import { atlasMedia, webPoints } from './atlas-media';
import { Credits } from './PlanetaryAtlas';
import { Background } from './OrbitDiagram';
import { formatN, initialCamera } from './explorer-data';
import type { Station } from './explorer-data';
import { carregarTeia, type TeiaDados } from '../viagem/teiaDados';

const Scene = lazy(() => import('./ExpoScene'));
const emptyOrbits: [] = [];
const noOp = () => {};
const startView = { ...initialCamera, tilt: 24 };
const views = ['Mapa DESI', 'Fatias', 'Volume 3D'] as const;
type View = (typeof views)[number];

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

function WebSlice() {
  const controlId = useId();
  const [layer, setLayer] = useState(1);
  const [dados, setDados] = useState<TeiaDados | null>(null);
  useEffect(() => {
    carregarTeia().then(setDados).catch(() => setDados(null));
  }, []);
  // três fatias de 16 Mpc ao longo da linha de visada (centradas em -36, 0 e +36 Mpc), da mesma
  // teia de Zel'dovich da viagem: finas o bastante para os filamentos não se sobreporem
  const path = useMemo(() => {
    if (!dados) return '';
    const centro = (layer - 1) * 36;
    const partes: string[] = [];
    const p = dados.posicoes;
    for (let i = 0; i < p.length; i += 3) {
      const z = p[i + 2];
      if (Math.abs(z - centro) < 8) partes.push('M' + (350 + p[i] * 2.6).toFixed(1) + ' ' + (195 - p[i + 1] * 2.6).toFixed(1) + 'h1');
    }
    return partes.join('');
  }, [dados, layer]);
  return (
    <>
      <div className="exp-map atlas-plot">
        <Background />
        <svg viewBox="0 0 700 390" role="img" aria-label={'Distribuição de galáxias na fatia ' + (layer + 1) + ' da teia simulada'}>
          <circle cx="350" cy="195" r="162" fill="#0c151799" stroke="#4f7774" strokeDasharray="3 4" />
          <path d={path} fill="none" stroke="#cfe5e1" strokeWidth="1.7" strokeLinecap="round" opacity=".85" />
          {!dados && <text x="350" y="200" textAnchor="middle" fill="#b9c6c1" fontSize="14">Carregando a teia…</text>}
        </svg>
      </div>
      <div className="atlas-model-tools">
        <label className="atlas-range" htmlFor={controlId}>
          <span>Profundidade da fatia <output>{layer + 1} de 3</output></span>
          <input id={controlId} aria-label="Profundidade da fatia" type="range" min="0" max="2" value={layer} onChange={(event) => setLayer(Number(event.target.value))} />
        </label>
      </div>
    </>
  );
}

export function CosmicWebAtlas({ station }: { station: Station }) {
  const cameraId = useId();
  const [mode, setMode] = useState<View>('Mapa DESI');
  const [point, setPoint] = useState<number | null>(null);
  const [camera, setCamera] = useState(startView);
  const arrasto = useRef<{ x: number; y: number } | null>(null);
  const [reduced, setReduced] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const fail = () => {
    setFailed(true);
    setMode('Fatias');
  };
  const changeView = (view: View) => {
    if (view === 'Volume 3D') {
      try {
        const probe = document.createElement('canvas').getContext('webgl2');
        if (!probe) return fail();
        probe.getExtension('WEBGL_lose_context')?.loseContext();
      } catch {
        return fail();
      }
    }
    setFailed(false);
    setMode(view);
  };
  const detail = point === null ? undefined : webPoints[point];

  return (
    <div className="atlas-spread">
      <figure className="atlas-figure">
        <div className="atlas-modes" role="group" aria-label="Vistas da teia cósmica">
          {views.map((view) => (
            <button type="button" key={view} aria-pressed={mode === view} onClick={() => changeView(view)}>{view}</button>
          ))}
        </div>
        {mode === 'Mapa DESI' && (
          <>
            <AtlasPhoto
              photo={{ file: atlasMedia.teia.file, width: 1549, height: 599, alt: 'Recorte do levantamento DESI com galáxias distribuídas em regiões de densidade diferente' }}
              points={webPoints} selected={point} onSelect={setPoint}
            />
            <Credits id="teia" />
          </>
        )}
        {mode === 'Fatias' && <WebSlice />}
        {mode === 'Volume 3D' && (
          <>
            <div className="exp-map atlas-volume">
              <Background />
              <SceneGuard onError={fail}>
                <Suspense fallback={<p className="atlas-loading">Carregando volume…</p>}>
                  <div
                    className="atlas-volume-canvas"
                    style={{ touchAction: 'pan-y' }}
                    onPointerDown={(e) => {
                      arrasto.current = { x: e.clientX, y: e.clientY };
                    }}
                    onPointerMove={(e) => {
                      const a = arrasto.current;
                      if (!a) return;
                      const dx = e.clientX - a.x;
                      const dy = e.clientY - a.y;
                      arrasto.current = { x: e.clientX, y: e.clientY };
                      setCamera((c) => ({
                        ...c,
                        azimuth: Math.round((((c.azimuth + dx * 0.5) % 360) + 360) % 360),
                        tilt: e.pointerType === 'mouse' ? Math.round(Math.min(85, Math.max(5, c.tilt + dy * 0.4))) : c.tilt,
                      }));
                    }}
                    onPointerUp={() => (arrasto.current = null)}
                    onPointerCancel={() => (arrasto.current = null)}
                    onPointerLeave={() => (arrasto.current = null)}
                  >
                    <Scene station="teia" cameraView={camera} orbits={emptyOrbits} selected={-1} day={0} linear reduced={reduced} onSelect={noOp} onFailure={fail} onReady={noOp} />
                  </div>
                </Suspense>
              </SceneGuard>
            </div>
            <div className="atlas-model-tools atlas-camera">
              <label className="atlas-range" htmlFor={cameraId + '-rotation'}>
                <span>Giro <output>{formatN(camera.azimuth, 0)}°</output></span>
                <input id={cameraId + '-rotation'} aria-label="Giro do volume" type="range" min="0" max="359" value={camera.azimuth} onChange={(event) => setCamera({ ...camera, azimuth: Number(event.target.value) })} />
              </label>
              <label className="atlas-range" htmlFor={cameraId + '-tilt'}>
                <span>Inclinação <output>{formatN(camera.tilt, 0)}°</output></span>
                <input id={cameraId + '-tilt'} aria-label="Inclinação do volume" type="range" min="5" max="85" value={camera.tilt} onChange={(event) => setCamera({ ...camera, tilt: Number(event.target.value) })} />
              </label>
            </div>
          </>
        )}
        {failed && <p className="atlas-status" role="status">O volume 3D está indisponível neste navegador. As fatias estão abertas.</p>}
        {mode !== 'Mapa DESI' && (
          <figcaption className="atlas-credit">Modelo sintético · caixa de referência com lado de {station.value}</figcaption>
        )}
      </figure>
      <div className="atlas-dossier">
        <p className="atlas-measure">
          <span>{mode === 'Mapa DESI' ? 'Faixa observada no céu' : station.measure}</span>
          <strong>{mode === 'Mapa DESI' ? '80° × 5°' : station.value}</strong>
        </p>
        {mode === 'Mapa DESI' && detail && <div className="atlas-reading" aria-live="polite"><h3>{detail.name}</h3><p>{detail.detail}</p></div>}
        <p>{mode === 'Mapa DESI' ? 'O DESI mede espectros. O desvio para o vermelho ajuda a colocar os objetos em profundidade no mapa.' : station.convention}</p>
        <p>{station.text}</p>
        <a className="atlas-source" href={mode === 'Mapa DESI' ? atlasMedia.teia.source : station.url}>
          {mode === 'Mapa DESI' ? 'DESI · Dados e documentação' : station.source}
        </a>
      </div>
    </div>
  );
}
