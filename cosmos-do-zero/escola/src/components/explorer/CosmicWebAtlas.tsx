import { Component, lazy, Suspense, useEffect, useId, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { AtlasPhoto } from './AtlasPhoto';
import { atlasMedia, webPoints } from './atlas-media';
import { Credits } from './PlanetaryAtlas';
import { Background } from './OrbitDiagram';
import { formatN, initialCamera } from './explorer-data';
import type { Station } from './explorer-data';
import { makeField, webBoxSide } from './explorer-geometry';

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
  const path = useMemo(() => {
    const min = webBoxSide * (layer / 3 - 0.5);
    return makeField('teia').grains
      .filter(({ p }) => p[2] >= min && p[2] < min + webBoxSide / 3)
      .map(({ p }) => 'M' + (350 + p[0] * 81).toFixed(1) + ' ' + (195 - p[1] * 81).toFixed(1) + 'h1')
      .join('');
  }, [layer]);
  return (
    <>
      <div className="exp-map atlas-plot">
        <Background />
        <svg viewBox="0 0 700 390" role="img" aria-label={'Distribuição de traçadores na fatia ' + (layer + 1) + ' da teia simulada'}>
          <rect x="188" y="33" width="324" height="324" fill="#080e2066" stroke="#7798bd" strokeDasharray="3 4" />
          <path d={path} fill="none" stroke="#a8ccff" strokeWidth="2.4" strokeLinecap="round" opacity=".86" />
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
                  <div className="atlas-volume-canvas">
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
