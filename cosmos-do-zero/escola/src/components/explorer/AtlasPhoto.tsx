import { useState } from 'react';
import type { AtlasPoint } from './atlas-media';

type Photo = { file: string; width: number; height: number; alt: string };

export function AtlasPhoto({
  photo, points, selected, onSelect, planetary = false,
}: {
  photo: Photo;
  points: AtlasPoint[];
  selected: number | null;
  onSelect: (index: number) => void;
  planetary?: boolean;
}) {
  const [zoom, setZoom] = useState(false);
  const point = selected === null ? undefined : points[selected];
  const select = (index: number) => {
    setZoom(false);
    onSelect(index);
  };

  return (
    <>
      <div className="atlas-photo" data-zoom={zoom}>
        <img
          className="atlas-photo-image"
          src={'/atlas/' + photo.file}
          alt={photo.alt}
          width={photo.width}
          height={photo.height}
          loading="lazy"
          decoding="async"
          style={{ transformOrigin: point ? point.x + '% ' + point.y + '%' : '50% 50%' }}
        />
        {!zoom && points.map((p, i) => (
          <button
            type="button"
            className="atlas-pin"
            key={p.name}
            aria-label={p.name + ' na imagem'}
            aria-pressed={selected === i}
            onClick={() => select(i)}
            style={{ left: p.x + '%', top: p.y + '%' }}
          >
            <span aria-hidden="true">{planetary ? p.name.slice(-1) : i + 1}</span>
          </button>
        ))}
      </div>
      <div className="atlas-photo-controls">
        <div className="atlas-choices" role="group" aria-label="Pontos da imagem">
          {points.map((p, i) => (
            <button key={p.name} type="button" aria-pressed={selected === i} onClick={() => select(i)}>
              {planetary ? p.name.slice(-1) : p.name}
              {planetary && <span className="atlas-sr"> · {p.name}</span>}
            </button>
          ))}
        </div>
        {!planetary && (
          <button type="button" className="atlas-action" aria-pressed={zoom} onClick={() => setZoom(!zoom)}>
            {zoom ? 'Ver imagem inteira' : point ? 'Ampliar ponto' : 'Ampliar imagem'}
          </button>
        )}
      </div>
    </>
  );
}
