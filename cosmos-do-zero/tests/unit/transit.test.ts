import { describe, expect, it } from 'vitest';
import { circleOverlapArea, transitPlot, transitSnapshot, TRANSIT_PRESETS, TRANSIT_VIEW } from '../../src/lib/transit';

describe('trânsito com brilho uniforme', () => {
  it('dá área zero no contato externo e a área do disco menor no contato interno', () => {
    expect(circleOverlapArea(1, 0.25, 1.25)).toBe(0);
    expect(circleOverlapArea(1, 0.25, 0.75)).toBeCloseTo(0.19634954084936207, 14);
  });

  it('reproduz a área da lente de dois círculos unitários separados por um raio', () => {
    expect(circleOverlapArea(1, 1, 1)).toBeCloseTo(1.228369698608757, 14);
  });

  it('dá uma queda de cerca de 84 ppm para um raio terrestre diante de um raio solar', () => {
    const center = transitSnapshot(TRANSIT_PRESETS.earth, 0);
    expect(center.kind).toBe('full');
    expect(center.flux).toBeCloseTo(0.9999160944, 12);
  });

  it('reduz a queda central a um quarto ao dobrar o raio estelar', () => {
    const center = transitSnapshot({ planet: 10, star: 2, inclination: 90 }, 0);
    expect(center.flux).toBeCloseTo(0.99790236, 12);
  });

  it('limita o trânsito rasante a uma sobreposição parcial', () => {
    const center = transitSnapshot(TRANSIT_PRESETS.grazing, 0);
    expect(center.kind).toBe('grazing');
    expect(center.flux).toBeGreaterThan(0.99160944);
    expect(center.flux).toBeLessThan(1);
  });

  it('mantém o fluxo em 100% quando o planeta passa fora do disco', () => {
    const center = transitSnapshot(TRANSIT_PRESETS.miss, 0);
    expect(center.kind).toBe('none');
    expect(center.flux).toBe(1);
  });

  it('projeta a órbita circular com entrada e saída simétricas', () => {
    const ingress = transitSnapshot(TRANSIT_PRESETS.giant, -1.6);
    const egress = transitSnapshot(TRANSIT_PRESETS.giant, 1.6);
    expect(egress.x).toBeCloseTo(1.003617148513, 10);
    expect(ingress.x).toBe(-egress.x);
    expect(ingress.flux).toBe(egress.flux);
    expect(egress.flux).toBeGreaterThan(0.99160944);
    expect(egress.flux).toBeLessThan(1);
  });

  it('mantém o fluxo estelar quando o planeta passa atrás da estrela', () => {
    expect(transitSnapshot(TRANSIT_PRESETS.giant, 50).flux).toBe(1);
  });

  it('enquadra a curva completa e mantém o fluxo físico nos extremos dos controles', () => {
    const { top, bottom } = TRANSIT_VIEW.chart;
    for (const planet of [1, 18]) {
      for (const star of [0.65, 1.5]) {
        for (const inclination of [80, 85, 90]) {
          const model = { planet, star, inclination };
          const { curve } = transitPlot(model);
          const samples = [...curve.matchAll(/[ML][\d.]+ ([\d.]+)/g)].map((match) => Number(match[1]));
          expect(samples).toHaveLength(241);
          expect(samples[0]).toBe(top);
          expect(samples.at(-1)).toBe(top);
          expect(samples[120]).toBe(Math.max(...samples));
          expect(Math.max(...samples)).toBeLessThanOrEqual(bottom);
          expect(transitSnapshot(model, 0).flux).toBeGreaterThan(0.93);
        }
      }
    }
  });
});
