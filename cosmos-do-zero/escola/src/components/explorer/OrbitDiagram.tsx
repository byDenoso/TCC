import { useId, useMemo } from 'react';
import { facing, orbitalSymbols, orbitPoint, orbitRadius, stations } from './explorer-data';
import type { CameraView, Orbit, Vec } from './explorer-data';
import { sky } from './explorer-geometry';

export function Background() {
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

export function Diagram({
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
  const size = orbits.length ? orbits[orbits.length - 1].a : 1;
  const symbols = useMemo(() => orbitalSymbols(orbits, linear), [orbits, linear]);
  const starTint = id === 'trappist' ? '#ff9976' : '#ffd283';
  const body = orbits
    .map((o, i) => ({ p: plot(orbitPoint(o, size, linear, day), view), o, i }))
    .sort((a, b) => a.p[2] - b.p[2]);
  const renderPlanet = ({ p, o, i }: (typeof body)[number]) => {
    const r = symbols.bodies[i] * 91 * view.zoom,
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
        {orbits.map((o, i) => (
          <radialGradient key={o.name} id={prefix + '-body-' + i} cx="30%" cy="23%" r="76%">
            <stop stopColor="#fff5de" />
            <stop offset=".26" stopColor={o.color} />
            <stop offset=".65" stopColor={o.color} />
            <stop offset="1" stopColor="#202d47" />
          </radialGradient>
        ))}
      </defs>
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
      <circle cx="350" cy="195" r={symbols.star * 355 * view.zoom} fill={`url(#${prefix}-star)`} />
      <circle cx="350" cy="195" r={symbols.star * 91 * view.zoom} fill={starTint} />
      {body.filter((b) => b.p[2] >= 0).map(renderPlanet)}
    </svg>
  );
}
