import { memo, useId, useState } from 'react';
import { scaleLinear } from 'd3-scale';
import { line } from 'd3-shape';
import { compact } from '../lib/school';
export type XY = [number, number];
function extent(values: number[]): [number, number] {
  const lo = Math.min(...values),
    hi = Math.max(...values);
  return hi === lo ? [lo - 1, hi + 1] : [lo, hi];
}
export const Plot = memo(function Plot({
  points,
  xLabel,
  yLabel,
  caption,
  reference,
  inspect = true,
}: {
  points: XY[];
  xLabel: string;
  yLabel: string;
  caption?: string;
  reference?: XY[];
  inspect?: boolean;
}) {
  const id = useId(),
    [fraction, setFraction] = useState(0.5),
    [tableOpen, setTableOpen] = useState(false);
  const valid = points.filter((p) => p.every(Number.isFinite)),
    other = (reference || []).filter((p) => p.every(Number.isFinite));
  if (!valid.length) return <p>Esta configuração está fora do domínio do gráfico.</p>;
  const both = valid.concat(other),
    X = scaleLinear()
      .domain(extent(both.map((p) => p[0])))
      .range([79, 542]),
    Y = scaleLinear()
      .domain(extent(both.map((p) => p[1])))
      .nice(4)
      .range([190, 25]);
  const curve = line<XY>()
    .x((p) => X(p[0]))
    .y((p) => Y(p[1]));
  const index = Math.round(fraction * (valid.length - 1)),
    current = valid[index];
  return (
    <figure className="plot">
      <svg viewBox="0 0 560 235" role="img" aria-labelledby={id}>
        <title id={id}>{yLabel + ' em função de ' + xLabel + (caption ? '. ' + caption : '')}</title>
        <text x="14" y="14">
          {yLabel}
        </text>
        {Y.ticks(4).map((t) => (
          <g key={t}>
            <path d={'M79 ' + Y(t) + ' H542'} className="gridline" />
            <text x="73" y={Y(t) + 4} textAnchor="end">
              {compact(t)}
            </text>
          </g>
        ))}
        {X.ticks(5).map((t) => (
          <g key={t}>
            <path d={'M' + X(t) + ' 25 V190'} className="gridline" />
            <text x={X(t)} y="209" textAnchor="middle">
              {compact(t)}
            </text>
          </g>
        ))}
        <text x="540" y="230" textAnchor="end">
          {xLabel}
        </text>
        {other.length > 0 && <path d={curve(other) ?? ''} className="baseline" />}
        <path d={curve(valid) ?? ''} className="plotline" />
        {inspect && (
          <>
            <path d={'M' + X(current[0]) + ' 25 V190'} className="cursorline" />
            <circle cx={X(current[0])} cy={Y(current[1])} r="5" className="cursorpoint" />
          </>
        )}
      </svg>
      {inspect && (
        <label className="plot-reader">
          Ler ponto{' '}
          <input
            aria-label="Selecionar ponto no gráfico"
            type="range"
            min="0"
            max={Math.max(1, valid.length - 1)}
            value={index}
            onChange={(e) => setFraction(+e.target.value / Math.max(1, valid.length - 1))}
          />
          <output>
            {compact(current[0])} · {compact(current[1])}
          </output>
        </label>
      )}
      {caption && <figcaption>{caption}</figcaption>}
      {inspect && (
        <details onToggle={(e) => setTableOpen(e.currentTarget.open)}>
          <summary>Valores em tabela</summary>
          {tableOpen && (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{xLabel}</th>
                    <th>{yLabel}</th>
                  </tr>
                </thead>
                <tbody>
                  {valid.map(([x, y], i) => (
                    <tr key={i}>
                      <td>{compact(x)}</td>
                      <td>{compact(y)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </details>
      )}
    </figure>
  );
});
