import { useId } from 'react';
import type { Simulation } from '../lib/model';

type Props = {
  scene: Simulation;
  reference: Simulation | null;
  reveal: number;
  project: (x: number, y: number, z: number) => number[];
};

export function ExpansionDiagram({ scene, reference, reveal, project }: Props) {
  const id = useId();
  const split = (540 * reveal) / 100;
  function field({ segments, dots }: Simulation, fixed = false) {
    return (
      <g className={fixed ? 'expansion-field expansion-field--reference' : 'expansion-field'}>
        <path
          className="expansion-vectors"
          d={segments
            .map(([x, y, z, a, b, c]) => 'M' + project(x, y, z).join(' ') + 'L' + project(a, b, c).join(' '))
            .join(' ')}
        />
        {dots.map(([x, y, z], i) => {
          const [cx, cy] = project(x, y, z);
          return i < 2 ? (
            <g key={i} className={i === 0 ? 'expansion-observer' : 'expansion-galaxy'}>
              <circle cx={cx} cy={cy} r="10" fill="none" />
              <circle cx={cx} cy={cy} r="4.5" stroke="none" />
            </g>
          ) : (
            <circle key={i} cx={cx} cy={cy} r="2.8" fill="#a6bcca" />
          );
        })}
      </g>
    );
  }

  return (
    <svg
      className="lab-svg expansion-diagram"
      viewBox="0 0 540 290"
      role="img"
      aria-labelledby={id + '-title'}
      aria-describedby={id + '-description'}
    >
      <title id={id + '-title'}>Campo de recessão cosmológica</title>
      <desc id={id + '-description'}>{scene.caption}</desc>
      <defs>
        <pattern id={id + '-grid'} width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0V24" fill="none" stroke="#2f4a49" strokeWidth="0.55" />
        </pattern>
        {reference && (
          <>
            <clipPath id={id + '-reference'}>
              <rect width={split} height="290" />
            </clipPath>
            <clipPath id={id + '-current'}>
              <rect x={split} width={540 - split} height="290" />
            </clipPath>
          </>
        )}
      </defs>
      <rect width="540" height="290" fill={'url(#' + id + '-grid)'} />
      {reference ? (
        <>
          <g clipPath={'url(#' + id + '-reference)'}>{field(reference, true)}</g>
          <g clipPath={'url(#' + id + '-current)'}>{field(scene)}</g>
          <line className="expansion-divider" x1={split} x2={split} y1="0" y2="290" />
        </>
      ) : field(scene)}
    </svg>
  );
}
