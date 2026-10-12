import { describe, expect, it } from 'vitest';
import { vHalo, vLum, vTotal } from '../../src/lib/rotation';

const grid = Array.from({ length: 180 }, (_, i) => 0.5 + i * 0.5); // 0.5..90

describe('curva de rotação', () => {
  it('halo não é negativo e vTotal domina as componentes', () => {
    for (const r of grid) {
      expect(vHalo(r)).toBeGreaterThanOrEqual(0);
      expect(vTotal(r)).toBeGreaterThanOrEqual(vLum(r));
      expect(vTotal(r)).toBeGreaterThanOrEqual(vHalo(r));
    }
    expect(vHalo(0)).toBe(0);
    expect(vTotal(0)).toBe(0);
  });
  it('curva total fica plana: dentro de 15% de r=40 para r em 30..90', () => {
    const ref = vTotal(40);
    for (const r of grid.filter((x) => x >= 30)) expect(Math.abs(vTotal(r) / ref - 1)).toBeLessThanOrEqual(0.15);
  });
  it('componente visível cai depois de r=25 (Kepler)', () => {
    for (const r of grid.filter((x) => x > 25)) expect(vLum(r + 0.5)).toBeLessThan(vLum(r));
  });
});
