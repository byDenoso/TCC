import { describe, expect, it } from 'vitest';
import { comovingMpc, E2, lookbackGyr, PLANCK } from '../../src/lib/cosmology';
import { expansionHistory, expansionPoint, EXPANSION_PRESETS } from '../../src/lib/expansion-exhibit';

describe('história de expansão FLRW/CPL', () => {
  const reference = EXPANSION_PRESETS.planck;

  it('recupera o ΛCDM de referência no limite w₀ = −1 e wₐ = 0', () => {
    for (const z of [0, 0.5, 1, 3]) {
      const point = expansionPoint(z, reference);
      expect(point.h).toBeCloseTo(PLANCK.h0 * Math.sqrt(E2(1 / (1 + z), PLANCK)), 8);
      expect(point.comoving).toBeCloseTo(comovingMpc(z, PLANCK), 3);
      expect(point.lookback).toBeCloseTo(lookbackGyr(z, PLANCK), 5);
      expect(point.luminosity).toBeCloseTo((1 + z) * point.comoving, 7);
    }
  });

  it('usa a normalização de hoje mesmo em um modelo curvo com energia escura dinâmica', () => {
    expect(expansionPoint(0, { h0: 72, om: 0.4, ode: 0.7, w0: -0.85, wa: 0.65 })).toEqual({
      z: 0, a: 1, h: 72, lookback: 0, comoving: 0, luminosity: 0,
    });
  });

  it('reproduz a solução independente de w constante com curvatura aberta', () => {
    const point = expansionPoint(2, { h0: 70, om: 0.3, ode: 0.5, w0: -2 / 3, wa: 0 });
    // Ωde ∝ a⁻¹, com integrais de quadratura independente e Sₖ hiperbólico.
    expect(point.h).toBeCloseTo(236.410863, 5);
    expect(point.lookback).toBeCloseTo(9.201004, 5);
    expect(point.comoving).toBeCloseTo(4602.634082, 3);
    expect(point.luminosity).toBeCloseTo(14345.430320, 3);
  });

  it('reproduz uma história CPL com curvatura fechada', () => {
    const point = expansionPoint(2, { h0: 70, om: 0.4, ode: 0.8, w0: -0.85, wa: 0.65 });
    // Quadratura independente de dz/E(z) e dz/[(1+z)E(z)], com Sₖ trigonométrico.
    expect(point.h).toBeCloseTo(243.004053, 5);
    expect(point.lookback).toBeCloseTo(9.465967, 5);
    expect(point.comoving).toBeCloseTo(4716.670058, 3);
    expect(point.luminosity).toBeCloseTo(13584.585130, 3);
  });

  it('ordena os pontos de uma curva pela evolução do tempo e da escala', () => {
    const history = expansionHistory(reference);
    expect(history[0]).toEqual(expansionPoint(0, reference));
    expect(history.at(-1)).toEqual(expansionPoint(3, reference));
    expect(history[1].lookback).toBeGreaterThan(0);
    expect(history[1].a).toBeLessThan(1);
  });
});
