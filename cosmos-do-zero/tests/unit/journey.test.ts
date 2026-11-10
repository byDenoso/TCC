import { describe, expect, it } from 'vitest';
import eras from '../../src/data/eras.json';
import { JOURNEY_ERAS, buildJourney, journeyPoint, journeyProgress, seeded, smooth } from '../../src/lib/journey';

describe('viagem pelo tempo', () => {
  it('usa exatamente os marcos de eras.json, na mesma ordem', () => {
    expect([...JOURNEY_ERAS]).toEqual(eras.map((era) => era.id));
  });
  it('gera um estado por marco, com o mesmo número de partículas e valores finitos', () => {
    const layouts = buildJourney(300);
    expect(layouts.map((layout) => layout.id)).toEqual([...JOURNEY_ERAS]);
    const point: [number, number] = [0, 0];
    for (const layout of layouts) {
      expect(layout.gx.length).toBe(300);
      for (let i = 0; i < 300; i += 7) {
        journeyPoint(layout, i, 12.5, point);
        expect(Number.isFinite(point[0]) && Number.isFinite(point[1])).toBe(true);
        expect(layout.a[i]).toBeGreaterThan(0);
        expect(layout.c[i]).toBeLessThan(3);
      }
    }
  });
  it('é determinística: a mesma semente produz a mesma cena', () => {
    const a = buildJourney(120), b = buildJourney(120);
    expect(Array.from(a[4].th)).toEqual(Array.from(b[4].th));
    const r1 = seeded(7), r2 = seeded(7);
    expect([r1(), r1(), r1()]).toEqual([r2(), r2(), r2()]);
  });
  it('agrupa cerca de um quarto das partículas em núcleos de quatro', () => {
    const n = 400, nuclei = buildJourney(n)[1];
    let grouped = 0;
    for (let i = 0; i + 3 < n; i += 4) {
      const spread = Math.hypot(nuclei.gx[i] - nuclei.gx[i + 3], nuclei.gy[i] - nuclei.gy[i + 3]);
      if (spread < 0.05) grouped += 4;
    }
    expect(grouped / n).toBeGreaterThan(0.2);
    expect(grouped / n).toBeLessThan(0.32);
  });
  it('no Sistema Solar ilustrado, órbitas internas giram mais rápido', () => {
    const solar = buildJourney(600)[6];
    const inner: number[] = [], outer: number[] = [];
    for (let i = 0; i < 600; i++) { if (solar.r[i] > 0.14 && solar.r[i] < 0.2) inner.push(solar.w[i]); if (solar.r[i] > 0.7) outer.push(solar.w[i]); }
    const mean = (v: number[]) => v.reduce((s, x) => s + x, 0) / v.length;
    expect(mean(inner)).toBeGreaterThan(mean(outer) * 4);
  });
  it('as galáxias ficam mais afastadas no marco da aceleração', () => {
    const [grow, apart] = [buildJourney(200)[4], buildJourney(200)[5]];
    const reach = (layout: typeof grow) => Math.max(...layout.marks.map((m) => Math.hypot(m.x, m.y)));
    expect(reach(apart)).toBeGreaterThan(reach(grow) * 1.3);
  });
  it('converte a posição de leitura em progresso contínuo e limitado', () => {
    const centers = [100, 300, 500];
    expect(journeyProgress(centers, 0)).toBe(0);
    expect(journeyProgress(centers, 200)).toBeCloseTo(0.5);
    expect(journeyProgress(centers, 500)).toBe(2);
    expect(journeyProgress(centers, 9000)).toBe(2);
    expect(journeyProgress([], 10)).toBe(0);
    expect(smooth(-1)).toBe(0); expect(smooth(2)).toBe(1); expect(smooth(0.5)).toBeCloseTo(0.5);
  });
});
