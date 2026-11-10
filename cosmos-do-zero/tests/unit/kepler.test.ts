import { describe, expect, it } from 'vitest';
import { orbitPeriod, orbitState, TAU } from '../../src/lib/kepler';

describe('bancada de mecânica orbital', () => {
  it('mantém distância e velocidade constantes numa órbita circular', () => {
    for (const fraction of [0, 0.1, 0.5, 0.99, 1]) {
      const { radius, speed } = orbitState(1, 0, TAU * fraction);
      expect(radius).toBeCloseTo(1, 12);
      expect(speed).toBeCloseTo(29.785, 3);
    }
  });

  it('alcança as distâncias dos apses e a velocidade maior no periélio', () => {
    const perihelion = orbitState(1.6, 0.8, 0);
    const aphelion = orbitState(1.6, 0.8, Math.PI);
    expect(perihelion.radius).toBeCloseTo(0.32, 12);
    expect(aphelion.radius).toBeCloseTo(2.88, 12);
    expect(perihelion.speed / aphelion.speed).toBeCloseTo(9, 10);
    expect(orbitPeriod(1.6)).toBeCloseTo(739.2, 1);
  });

  it('escala velocidade, energia e período com a massa total', () => {
    const base = orbitState(1, 0.55, 0.2);
    const twice = orbitState(1, 0.55, 0.2, 2);
    expect(twice.radius).toBe(base.radius);
    expect(twice.speed / base.speed).toBeCloseTo(Math.SQRT2, 12);
    expect(twice.specificEnergy / base.specificEnergy).toBeCloseTo(2, 12);
    expect(orbitPeriod(1) / orbitPeriod(1, 2)).toBeCloseTo(Math.SQRT2, 12);
  });

  it('resolve a equação de Kepler em toda a faixa do controle', () => {
    for (const e of [0, 0.55, 0.8]) {
      for (let i = -10; i <= 110; i++) {
        const mean = TAU * i / 100;
        const { eccentricAnomaly: E } = orbitState(0.6, e, mean);
        expect(E - e * Math.sin(E)).toBeCloseTo(mean, 12);
      }
    }
  });

  it('varre a mesma área em um oitavo do período nos dois apses', () => {
    const a = 1.6;
    const e = 0.8;
    const area = (center: number) => {
      const a0 = orbitState(a, e, center - TAU / 16).eccentricAnomaly;
      const a1 = orbitState(a, e, center + TAU / 16).eccentricAnomaly;
      return a * a * Math.sqrt(1 - e * e) / 2 * (a1 - a0 - e * (Math.sin(a1) - Math.sin(a0)));
    };
    expect(area(0)).toBeCloseTo(area(Math.PI), 12);
    expect(area(0)).toBeCloseTo(Math.PI * a * a * Math.sqrt(1 - e * e) / 8, 12);
  });
});
