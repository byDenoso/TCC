import { useEffect, useState } from 'react';
import { AtlasPhoto } from './AtlasPhoto';
import {
  andromedaPoints,
  atlasMedia,
  orionPoints,
  virgoPoints,
} from './atlas-media';
import { CosmicWebAtlas } from './CosmicWebAtlas';
import { Credits, PlanetaryAtlas } from './PlanetaryAtlas';
import { stations } from './explorer-data';
import type { Station } from './explorer-data';

const photoStops = {
  orion: {
    points: orionPoints,
    width: 1920,
    height: 1303,
    alt: 'Nebulosa de Órion e região do Trapézio em uma composição de imagens do Webb',
  },
  m31: {
    points: andromedaPoints,
    width: 3900,
    height: 911,
    alt: 'Panorama de Andrômeda com o bojo luminoso e as faixas escuras de poeira no disco',
  },
  virgo: {
    points: virgoPoints,
    width: 1200,
    height: 900,
    alt: 'Campo óptico do aglomerado de Virgem com M87, M49 e várias galáxias da Cadeia de Markarian',
  },
};

function Observation({ id, station }: { id: keyof typeof photoStops; station: Station }) {
  const [layer, setLayer] = useState<'short' | 'long'>('short');
  const [selected, setSelected] = useState<number | null>(null);
  const { points, ...photo } = photoStops[id];
  const file = id === 'orion' && layer === 'long' ? 'orion-long.webp' : atlasMedia[id].file;
  const selectedPoint = selected === null ? undefined : points[selected];

  return (
    <div className="atlas-spread">
      <figure className="atlas-figure">
        {id === 'orion' && (
          <div className="atlas-modes" role="group" aria-label="Faixas do infravermelho">
            <button type="button" aria-pressed={layer === 'short'} onClick={() => setLayer('short')}>Infravermelho curto</button>
            <button type="button" aria-pressed={layer === 'long'} onClick={() => setLayer('long')}>Infravermelho longo</button>
          </div>
        )}
        <AtlasPhoto photo={{ ...photo, file }} points={points} selected={selected} onSelect={setSelected} />
        <Credits id={id} />
      </figure>
      <div className="atlas-dossier">
        <p className="atlas-measure"><span>{station.measure}</span><strong>{station.value}</strong></p>
        <div aria-live="polite" className="atlas-reading">
          {selectedPoint && <><h3>{selectedPoint.name}</h3><p>{selectedPoint.detail}</p></>}
          {id === 'orion' && <p>{layer === 'short' ? 'O canal curto destaca mais estrelas e pequenos discos ao redor delas.' : 'O canal longo destaca gás, poeira e moléculas na mesma região do céu.'}</p>}
        </div>
        <p>{station.text}</p>
        <p className="atlas-note">{station.convention}</p>
        <a className="atlas-source" href={station.url}>{station.source}</a>
      </div>
    </div>
  );
}

export default function Expo() {
  const [active, setActive] = useState(0);
  const [guided, setGuided] = useState<number | null>(null);
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    const sections = stations.map(({ id }) => document.getElementById(id));
    let frame = 0;
    const sync = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const boundary = Math.min(250, innerHeight * 0.35);
        let current = 0;
        for (const [index, section] of sections.entries()) {
          if (section && section.getBoundingClientRect().top <= boundary) current = index;
        }
        setActive(current);
      });
    };
    sync();
    addEventListener('scroll', sync, { passive: true });
    addEventListener('resize', sync);
    return () => {
      cancelAnimationFrame(frame);
      removeEventListener('scroll', sync);
      removeEventListener('resize', sync);
    };
  }, []);

  const go = (index: number) => {
    const id = stations[index].id;
    if (window.location.hash !== '#' + id) window.history.pushState(window.history.state, '', '#' + id);
    document.getElementById(id)?.scrollIntoView({ block: 'start' });
    document.getElementById(id + '-title')?.focus({ preventScroll: true });
    setActive(index);
  };

  const startJourney = () => {
    setFinished(false);
    setGuided(0);
    go(0);
  };

  const advance = (index: number) => {
    if (index === stations.length - 1) {
      setGuided(null);
      setFinished(true);
      return;
    }
    setGuided(index + 1);
    go(index + 1);
  };

  return (
    <article className="cosmos-explorer atlas">
      <header className="exp-heading atlas-heading">
        <div>
          <p className="exp-kicker">Atlas interativo</p>
          <h1>Explorador do Universo</h1>
        </div>
        <p>Seis escalas, da órbita da Terra à distribuição das galáxias. Os mapas, as imagens e os modelos de cada destino revelam uma parte da história.</p>
      </header>
      <div className="atlas-nav">
        <nav aria-label="Destinos do explorador">
          {stations.map((station, index) => (
            <a
              key={station.id}
              href={'#' + station.id}
              aria-current={active === index ? 'location' : undefined}
              onClick={() => { if (guided !== index) setGuided(null); }}
            >{station.short}</a>
          ))}
        </nav>
        <button type="button" className="atlas-guide-start" onClick={startJourney}>Iniciar viagem guiada</button>
      </div>
      {stations.map((station, index) => (
        <section className="atlas-chapter" id={station.id} key={station.id} aria-labelledby={station.id + '-title'}>
          <div className="atlas-chapter-heading">
            <p className="exp-kicker">{station.family}</p>
            <h2 id={station.id + '-title'} tabIndex={-1}>{station.name}</h2>
          </div>
          {guided === index && (
            <section className="atlas-guide" aria-label="Viagem guiada">
              <div>
                <p className="exp-kicker">Viagem guiada · {index + 1} de {stations.length}</p>
                <p>{station.guide}</p>
              </div>
              <div className="atlas-guide-actions">
                <button type="button" className="exp-secondary" onClick={() => setGuided(null)}>Sair da viagem</button>
                <button type="button" className="exp-primary" onClick={() => advance(index)}>{index === stations.length - 1 ? 'Concluir viagem' : 'Próxima parada'}</button>
              </div>
            </section>
          )}
          {station.id === 'solar' || station.id === 'trappist' ? (
            <PlanetaryAtlas station={station} guided={guided === index} />
          ) : station.id === 'teia' ? (
            <CosmicWebAtlas station={station} />
          ) : (
            <Observation station={station} id={station.id as keyof typeof photoStops} />
          )}
          {station.id === 'teia' && finished && <p className="atlas-status" role="status">Viagem guiada concluída.</p>}
        </section>
      ))}
      <section className="atlas-next" aria-labelledby="atlas-next-title">
        <div>
          <h2 id="atlas-next-title">Continue a investigação</h2>
          <p>Calcule o período de uma órbita, veja como medimos a expansão ou siga uma trilha de estudo.</p>
        </div>
        <div className="atlas-next-links">
          <a href="/laboratorios/orbitas/">Laboratório de órbitas</a>
          <a href="/laboratorios/expansao/">Laboratório de expansão</a>
          <a href="/trilhas/">Trilhas de estudo</a>
        </div>
      </section>
    </article>
  );
}
