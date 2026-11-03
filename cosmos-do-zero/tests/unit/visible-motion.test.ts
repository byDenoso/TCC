import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

it('retoma após movimento reduzido mesmo se o renderizador já tiver parado', async () => {
  const media = Object.assign(new EventTarget(), { matches: false });
  const doc = Object.assign(new EventTarget(), { hidden: false, documentElement: { dataset: {} } });
  let intersect: (entries: { isIntersecting: boolean }[]) => void = () => {};
  class Observer {
    constructor(callback: typeof intersect) { intersect = callback; }
    observe() {} disconnect() {}
  }
  vi.stubGlobal('matchMedia', () => media);
  vi.stubGlobal('localStorage', { getItem: () => null });
  vi.stubGlobal('document', doc);
  vi.stubGlobal('window', { IntersectionObserver: Observer });
  vi.stubGlobal('IntersectionObserver', Observer);
  const { motionPreference } = await import('../../src/scripts/motion-preference');
  const { visibleMotion } = await import('../../src/scripts/visible-motion');
  let running = false, starts = 0;
  // A cena também finaliza sua transição ao receber a preferência reduzida.
  motionPreference.addEventListener('change', () => { if (motionPreference.matches) running = false; });
  const control = visibleMotion({} as Element, {
    start: () => { running = true; starts++; }, stop: () => { running = false; }, running: () => running
  });
  intersect([{ isIntersecting: true }]);
  expect(starts).toBe(1);
  media.matches = true; media.dispatchEvent(new Event('change'));
  expect(running).toBe(false);
  media.matches = false; media.dispatchEvent(new Event('change'));
  expect(starts).toBe(2);
  expect(running).toBe(true);
  control.manual(); running = false;
  intersect([{ isIntersecting: false }]); intersect([{ isIntersecting: true }]);
  expect(starts).toBe(2);
  control.automatic();
  expect(starts).toBe(3);
  control.dispose();
});
