import type { Planet } from '../types';
import { format, mass } from './format';

export function comparison(a: Planet, b: Planet) {
  const max = Math.max(a.radius, b.radius);
  return { ratio: b.radius / a.radius, diameters: [(a.radius / max) * 100, (b.radius / max) * 100] as [number, number] };
}

export function compareInsight(left: Planet, right: Planet): string {
  if (left.id === right.id) return 'O mesmo planeta nos dois lados: todas as razões são iguais a 1.';
  const [larger, smaller] = left.radius >= right.radius ? [left, right] : [right, left];
  return `${larger.name} tem um raio ${format(larger.radius / smaller.radius, 2)} vezes o ${smaller.id === 'terra' ? 'da' : 'de'} ${smaller.name}. A gravidade não cresce na mesma proporção.`;
}

export const rotationLabel = (p: Planet, long = false): string =>
  `${format(p.rotation)} h${p.rotation < 0 ? (long ? ' (retrógrada)' : ' · retrógrada') : ''}`;

/** Linhas da tabela comparativa: mesma definição para ambos os planetas. */
export const compareRows: { label: string; value: (p: Planet) => string }[] = [
  { label: 'Raio equatorial', value: (p) => `${format(p.radius)} km` },
  { label: 'Massa', value: (p) => mass(p.mass) },
  { label: 'Gravidade equatorial', value: (p) => `${format(p.gravity)} m/s²` },
  { label: 'Temperatura de referência', value: (p) => `${format(p.temperature)} °C` },
  { label: 'Onde é medida', value: (p) => (p.type === 'Rochoso' ? 'Superfície (média)' : 'Atmosfera (1 bar)') },
  { label: 'Tamanho da órbita (semieixo)', value: (p) => `${format(p.distance, 3)} UA` },
  { label: 'Período orbital tropical', value: (p) => `${format(p.orbit)} dias` },
  { label: 'Rotação sideral', value: (p) => rotationLabel(p, true) },
  { label: 'Composição principal', value: (p) => p.composition },
  { label: 'Atmosfera', value: (p) => p.atmosphere }
];

/** Campos do painel do catálogo, na ordem de exibição. */
export const catalogFacts: { label: string; value: (p: Planet) => string }[] = [
  { label: 'Raio equatorial', value: (p) => `${format(p.radius)} km` },
  { label: 'Massa', value: (p) => mass(p.mass) },
  { label: 'Gravidade equatorial', value: (p) => `${format(p.gravity)} m/s²` },
  { label: 'Temperatura de referência', value: (p) => `${format(p.temperature)} °C` },
  { label: 'Tamanho da órbita (semieixo)', value: (p) => `${format(p.distance, 3)} UA` },
  { label: 'Período orbital', value: (p) => `${format(p.orbit)} dias` },
  { label: 'Rotação sideral', value: (p) => rotationLabel(p) },
  { label: 'Tipo', value: (p) => p.type }
];
