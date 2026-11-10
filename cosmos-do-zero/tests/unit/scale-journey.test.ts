import { describe, expect, it } from 'vitest';
import { journeyLayers, journeyPosition, journeyVideoTime } from '../../src/lib/scale-journey';
import { FrameBudget } from '../../src/scripts/visual/render-policy';

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

  it('switches mobile to video only after measured frames miss the 50 fps budget', () => {
    const fast = new FrameBudget();
    const slow = new FrameBudget();
    for (let frame = 0; frame < 44; frame++) { fast.record(20); slow.record(24); }
    expect(slow.decide(45, 20)).toBeNull();
    fast.record(20);
    slow.record(24);
    expect(fast.decide(45, 20)).toBe('standard');
    expect(slow.decide(45, 20)).toBe('low');
  });
});
