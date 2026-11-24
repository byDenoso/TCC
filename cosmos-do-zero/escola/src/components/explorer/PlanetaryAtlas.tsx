import { useEffect, useId, useState } from 'react';
import { AtlasPhoto } from './AtlasPhoto';
import { atlasMedia, solarPortraits } from './atlas-media';
import { Background, Diagram } from './OrbitDiagram';
import { formatN, initialCamera, solar, trappist } from './explorer-data';
import type { Station } from './explorer-data';

const rockyPlanets = solar.slice(0, 4);
const trappistPoints = trappist.map((planet, index) => ({
  name: planet.name, x: [20.2, 32.5, 45, 57.1, 69.6, 81.9, 94.2][index], y: 50,
  detail: planet.note,
}));

// Agol et al. (2021), via NASA Exoplanet Archive. The light curve uses a
// central circular transit, a uniform stellar disk and these nominal radii.
const trappistRadii = [1.116, 1.097, 0.788, 0.920, 1.045, 1.129, 0.755];
const starRadiusEarth = 0.1192 * 109.2;
const starRadiusAu = 0.1192 * 0.00465047;
const solarMissionMaps = new Set(['mercurio', 'terra', 'marte', 'jupiter']);
const orbitalView = { ...initialCamera, azimuth: 0, tilt: 65 };
type Mode = 'Sistema' | 'Órbitas' | 'Trânsito';

function blockedFraction(separation: number, radius: number) {
  if (separation >= 1 + radius) return 0;
  if (separation <= 1 - radius) return radius * radius;
  const s2 = separation * separation;
  const r2 = radius * radius;
  const area = r2 * Math.acos((s2 + r2 - 1) / (2 * separation * radius))
    + Math.acos((s2 + 1 - r2) / (2 * separation))
    - 0.5 * Math.sqrt((-separation + radius + 1) * (separation + radius - 1)
      * (separation - radius + 1) * (separation + radius + 1));
  return area / Math.PI;
}

function Transit({ planet }: { planet: number }) {
  const [minute, setMinute] = useState(0);
  const id = useId();
  const orbit = trappist[planet];
  const radius = trappistRadii[planet] / starRadiusEarth;
  const minutesPeriod = orbit.days * 1440;
  const limit = 75;
  const separation = (t: number) => orbit.a / starRadiusAu * Math.sin(2 * Math.PI * t / minutesPeriod);
  const x = (t: number) => 66 + (t + limit) / (2 * limit) * 396;
  const y = (t: number) => 154 + blockedFraction(Math.abs(separation(t)), radius) * 9600;
  const trace = Array.from({ length: 151 }, (_, i) => {
    const t = i - limit;
    return x(t).toFixed(2) + ',' + y(t).toFixed(2);
  }).join(' ');
  const depth = 100 * radius * radius;
  return (
    <>
      <div className="exp-map atlas-plot">
        <svg viewBox="0 0 500 292" role="img" aria-label={'Simulação de trânsito de ' + orbit.name}>
          <defs>
            <radialGradient id={id + '-star'}>
              <stop stopColor="#ffdd99" />
              <stop offset="1" stopColor="#ed835d" />
            </radialGradient>
          </defs>
          <circle cx="250" cy="69" r="42" fill={'url(#' + id + '-star)'} />
          <circle cx={250 + separation(minute) * 42} cy="69" r={42 * radius} fill="#0a1426" stroke="#e7eefa" strokeWidth=".7" />
          <path d="M66 144v110h396 M66 154h396 M66 250h396" stroke="#6c839c" opacity=".58" fill="none" />
          <polyline points={trace} fill="none" stroke="#aad8ff" strokeWidth="2.4" />
          <path d={'M' + x(minute) + ' 140v112'} stroke="#d3e9fa" strokeDasharray="3 4" opacity=".64" />
          <circle cx={x(minute)} cy={y(minute)} r="4.2" fill="#f6c99a" />
          <g fill="#d2e5f5" fontSize="12">
            <text x="14" y="159">100%</text>
            <text x="21" y="254">99%</text>
            <text x="66" y="276">−75 min</text>
            <text x="250" y="276" textAnchor="middle">0</text>
            <text x="462" y="276" textAnchor="end">+75 min</text>
          </g>
        </svg>
      </div>
      <div className="atlas-model-tools">
        <label className="atlas-range" htmlFor={id + '-time'}>
          <span>Tempo em relação ao meio do trânsito <output>{minute > 0 ? '+' : ''}{minute} min</output></span>
          <input id={id + '-time'} aria-label="Tempo do trânsito em minutos" type="range" min={-limit} max={limit} value={minute} onChange={(event) => setMinute(Number(event.target.value))} />
        </label>
        <p>Queda máxima de {formatN(depth, 2)}% neste modelo de disco uniforme e passagem central.</p>
      </div>
    </>
  );
}

export function Credits({ id }: { id: keyof typeof atlasMedia }) {
  const media = atlasMedia[id];
  return (
    <figcaption className="atlas-credit">
      <strong>{media.kind}</strong>
      <a href={media.source}>{media.credit}</a>
    </figcaption>
  );
}

export function PlanetaryAtlas({ station, guided }: { station: Station; guided: boolean }) {
  const clockId = useId();
  const isSolar = station.id === 'solar';
  const planets = isSolar ? solar : trappist;
  const modes: Mode[] = isSolar ? ['Sistema', 'Órbitas'] : ['Sistema', 'Órbitas', 'Trânsito'];
  const [mode, setMode] = useState<Mode>('Sistema');
  const [selected, setSelected] = useState(isSolar ? 2 : 3);
  const [day, setDay] = useState(0);
  const [linear, setLinear] = useState(!isSolar);
  const [inner, setInner] = useState(false);
  const planet = planets[selected];
  const shown = isSolar && linear && inner ? rockyPlanets : planets;

  useEffect(() => {
    if (guided) setMode('Órbitas');
  }, [guided]);

  const select = (next: number) => {
    if (next >= rockyPlanets.length) setInner(false);
    setSelected(next);
  };

  const planetChoices = (
    <div className="atlas-choices atlas-planets" role="group" aria-label="Escolher planeta">
      {planets.map((body, index) => (
        <button type="button" key={body.name} aria-pressed={selected === index} onClick={() => select(index)}>
          {isSolar ? body.name : body.name.slice(-1)}
          {!isSolar && <span className="atlas-sr"> · {body.name}</span>}
        </button>
      ))}
    </div>
  );

  return (
    <div className="atlas-spread">
      <figure className="atlas-figure">
        <div className="atlas-modes" role="group" aria-label={'Vistas de ' + station.short}>
          {modes.map((view) => (
            <button type="button" key={view} aria-pressed={mode === view} onClick={() => setMode(view)}>{view}</button>
          ))}
        </div>
        {mode === 'Sistema' && (
          <>
            {isSolar ? (
              <>
                <div className="atlas-portrait">
                  <img src={'/atlas/' + solarPortraits[selected] + '.webp'} alt={'Retrato de ' + planet.name} width="640" height="640" loading="lazy" decoding="async" />
                </div>
                {planetChoices}
              </>
            ) : (
              <AtlasPhoto
                photo={{ file: 'trappist.webp', width: 1600, height: 800, alt: 'Ilustração da estrela e dos sete planetas TRAPPIST-1, identificados de b a h' }}
                points={trappistPoints} selected={selected} onSelect={select} planetary
              />
            )}
            {isSolar && <p className="atlas-model-tools">{solarMissionMaps.has(solarPortraits[selected]) ? 'Modelo com textura baseada em observações. Iluminação ilustrativa.' : 'Modelo com aparência e iluminação ilustrativas.'}</p>}
            <Credits id={isSolar ? 'solar' : 'trappist'} />
          </>
        )}
        {mode === 'Órbitas' && (
          <>
            <div className="exp-map atlas-plot">
              <Background />
              <Diagram id={station.id} view={orbitalView} orbits={shown} linear={linear} day={day} selected={selected} onSelect={select} />
            </div>
            {planetChoices}
            <div className="atlas-model-tools">
              <label className="atlas-range" htmlFor={clockId}>
                <span>Tempo transcorrido <output>{formatN(day, isSolar ? 0 : 1)} dias</output></span>
                <input id={clockId} aria-label="Tempo transcorrido em dias" type="range" min={0} max={isSolar ? 365 : 20} step={isSolar ? 1 : 0.1} value={day} onChange={(e) => setDay(Number(e.target.value))} />
              </label>
              <label className="exp-check">
                <input type="checkbox" checked={linear} onChange={(e) => { setLinear(e.target.checked); setInner(false); }} />
                Distâncias orbitais lineares
              </label>
              {isSolar && linear && (
                <label className="exp-check">
                  <input type="checkbox" checked={inner} onChange={(e) => {
                    setInner(e.target.checked);
                    if (e.target.checked && selected >= rockyPlanets.length) setSelected(2);
                  }} />
                  Enquadrar os quatro planetas rochosos
                </label>
              )}
              <p>{station.convention} {linear ? 'Escala radial proporcional aos semieixos.' : 'Escala radial logarítmica.'}</p>
            </div>
          </>
        )}
        {mode === 'Trânsito' && (
          <>
            <Transit planet={selected} />
            {planetChoices}
            <figcaption className="atlas-credit">Simulação didática · parâmetros orbitais e raios de Agol et al. (2021)</figcaption>
          </>
        )}
      </figure>
      <div className="atlas-dossier">
        <p className="atlas-measure"><span>{station.measure}</span><strong>{station.value}</strong></p>
        <div aria-live="polite" className="atlas-reading">
          <h3>{planet.name}</h3>
          <dl className="atlas-values">
            <div><dt>Semieixo orbital</dt><dd>{formatN(planet.a, isSolar ? 3 : 5)} au</dd></div>
            <div><dt>Período</dt><dd>{formatN(planet.days, isSolar ? 1 : 3)} dias</dd></div>
          </dl>
          <p>{planet.note}</p>
        </div>
        <p>{station.text}</p>
        <a className="atlas-source" href={station.url}>{station.source}</a>
      </div>
    </div>
  );
}
