import { useEffect, useRef, useState } from 'react';
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
  // no celular, imagens largas ganham altura legível e se percorrem arrastando para os lados
  const larga = photo.width / photo.height > 1.2;
  const visor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = visor.current;
    if (!el || el.scrollWidth <= el.clientWidth + 1) return;
    const alvo = point ? (point.x / 100) * el.scrollWidth : el.scrollWidth / 2;
    el.scrollTo({ left: alvo - el.clientWidth / 2, behavior: point ? 'smooth' : 'instant' });
  }, [point]);
  const select = (index: number) => {
    setZoom(false);
    onSelect(index);
  };

  return (
    <>
      <div className="atlas-photo" data-zoom={zoom} data-larga={larga} ref={visor}>
        <div className="atlas-photo-quadro" style={{ aspectRatio: photo.width + ' / ' + photo.height }}>
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
      </div>
      {larga && <p className="atlas-dica">Arraste a imagem para os lados para percorrê-la.</p>}
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
