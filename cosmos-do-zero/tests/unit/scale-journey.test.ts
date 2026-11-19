import { describe, expect, it } from 'vitest';
import { journeyLayers, journeyLog, journeyPosition, journeyVideoTime } from '../../src/lib/scale-journey';
import { scaleLogs, scaleStations } from '../../src/data/scale-stations';

describe('exposição de escalas', () => {
  it('maps measured station offsets to continuous, clamped scroll progress', () => {
    const stations = [0, 650, 1400, 2000, 3000];
    expect(journeyPosition(-100, stations)).toBe(0);
    expect(journeyPosition(325, stations)).toBe(.5);
    expect(journeyPosition(1400, stations)).toBe(2);
    expect(journeyPosition(2500, stations)).toBe(3.5);
    expect(journeyPosition(4000, stations)).toBe(4);
  });

  it('overlaps adjacent scenes continuously while preserving the five keyframes', () => {
    expect(journeyLayers(0)).toEqual({ from: 0, to: 1, blend: 0 });
    expect(journeyLayers(.5)).toEqual({ from: 0, to: 1, blend: .5 });
    expect(journeyLayers(1)).toEqual({ from: 1, to: 2, blend: 0 });
    expect(journeyLayers(4)).toEqual({ from: 3, to: 4, blend: 1 });
    expect(journeyLayers(.25).blend).toBeLessThan(.25);
    expect(journeyLayers(.999).blend).toBeGreaterThan(.999);
  });

  it('maps the same scroll keyframes onto the video in both directions', () => {
    expect([0, 1, 2, 3, 4, 3, 2, 1, 0].map(value => journeyVideoTime(value, 4.02))).toEqual([0, 1, 2, 3, 4, 3, 2, 1, 0]);
    expect(journeyVideoTime(4, 3.97)).toBeLessThan(3.97);
  });

  it('maps the whole journey onto a strictly increasing logarithmic ruler', () => {
    const end = scaleStations.length - 1;
    expect(scaleStations[0].id).toBe('proton');
    expect(scaleStations[end].id).toBe('universo-observavel');
    expect(journeyLayers(end, end)).toEqual({ from: end - 1, to: end, blend: 1 });
    scaleLogs.forEach((size, i) => {
      expect(journeyLog(i, scaleLogs)).toBeCloseTo(size, 9);
      expect(journeyPosition(size, scaleLogs)).toBe(i);
      if (i > 0) {
        expect(size).toBeGreaterThan(scaleLogs[i - 1]);
        expect(journeyPosition(journeyLog(i - .4, scaleLogs), scaleLogs)).toBeCloseTo(i - .4, 9);
      }
    });
  });
});
