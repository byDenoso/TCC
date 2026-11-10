import { describe, expect, it } from 'vitest';
import { MAX_ZOOM, clampView, coverSize, focusOn, spotInView, zoomAbout, type ViewBox } from '../../src/lib/photo-view';

const box = (vw: number, vh: number, ratio: number): ViewBox => ({ vw, vh, ...coverSize(vw, vh, ratio) });

describe('explorador de imagens: geometria', () => {
  it('a imagem sempre cobre a janela, em panorama e em quadrado', () => {
    expect(coverSize(900, 600, 2000 / 693)).toEqual({ cw: 600 * (2000 / 693), ch: 600 });
    expect(coverSize(900, 600, 1)).toEqual({ cw: 900, ch: 900 });
    expect(coverSize(0, 600, 1.5)).toEqual({ cw: 0, ch: 0 });
  });

  it('o arraste nunca abre faixa vazia nas bordas', () => {
    const b = box(900, 600, 1.5);
    expect(clampView({ z: 1, tx: 500, ty: 500 }, b)).toEqual({ z: 1, tx: 0, ty: 0 });
    const far = clampView({ z: 2, tx: -9999, ty: -9999 }, b);
    expect(far.tx).toBe(b.vw - b.cw * 2);
    expect(far.ty).toBe(b.vh - b.ch * 2);
    expect(clampView({ z: 99, tx: 0, ty: 0 }, b).z).toBe(MAX_ZOOM);
    expect(clampView({ z: 0.2, tx: 0, ty: 0 }, b).z).toBe(1);
  });

  it('o foco leva o ponto para dentro da janela em qualquer proporção', () => {
    for (const [vw, vh, ratio] of [[900, 600, 2000 / 693], [358, 358, 2000 / 693], [900, 600, 1], [358, 358, 1.5]] as const) {
      const b = box(vw, vh, ratio);
      for (const [x, y] of [[30, 44], [85, 82], [5, 5], [98, 96]] as const) {
        const state = focusOn(x, y, 1.8, b);
        const p = spotInView(x, y, state, b);
        expect(p.x).toBeGreaterThanOrEqual(0);
        expect(p.x).toBeLessThanOrEqual(vw);
        expect(p.y).toBeGreaterThanOrEqual(0);
        expect(p.y).toBeLessThanOrEqual(vh);
      }
    }
  });

  it('o zoom mantém parado o ponto sob a âncora quando há folga', () => {
    const b = box(900, 600, 1.5);
    const start = focusOn(50, 50, 2, b);
    const before = { x: (450 - start.tx) / start.z, y: (300 - start.ty) / start.z };
    const next = zoomAbout(start, 3, 450, 300, b);
    expect((450 - next.tx) / next.z).toBeCloseTo(before.x, 6);
    expect((300 - next.ty) / next.z).toBeCloseTo(before.y, 6);
  });
});
