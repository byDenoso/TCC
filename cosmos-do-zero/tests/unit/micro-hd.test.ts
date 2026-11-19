import { describe, expect, test } from 'vitest';
import { drawGlobe } from '../../src/scripts/micro/hd-materials';
import type { StagePaint } from '../../src/scripts/stage-surface';

function recorder() {
  const drawn: string[] = [];
  const pending = new Set<string>();
  const stage: StagePaint = {
    ctx: {} as CanvasRenderingContext2D,
    backdrop() {},
    label() {},
    image: (path: string) => pending.has(path) ? null : {} as HTMLImageElement,
    sprite: (path: string) => { drawn.push(path); }
  };
  return { stage, drawn, pending };
}

describe('Globos das microexperiências', () => {
  test.each(['terra','lua','mercurio','venus','marte','jupiter','saturno-globo'])('%s mantém o atlas HD por uma volta completa', name => {
    const {stage, drawn} = recorder();
    for (let n = 0; n <= 36; n++) drawGlobe(stage, name, 10, 10, 100, n);
    const expected = Array.from({length:36}, (_,n) =>
      '/models/worlds-hd/' + name + '/' + String(n).padStart(2,'0') + '.webp');
    expect(drawn).toEqual([...expected,expected[0]]);
  });

  test('segura a orientação anterior enquanto a próxima imagem carrega', () => {
    const {stage, drawn, pending} = recorder();
    const next = '/models/worlds-hd/terra/13.webp';
    pending.add(next);
    drawGlobe(stage,'terra',0,0,100,12);
    drawGlobe(stage,'terra',0,0,100,13);
    pending.clear();
    drawGlobe(stage,'terra',0,0,100,13);
    expect(drawn).toEqual(['/models/worlds-hd/terra/12.webp','/models/worlds-hd/terra/12.webp',next]);
  });

  test('objetos distantes usam o quadro pequeno correspondente', () => {
    const {stage, drawn} = recorder();
    drawGlobe(stage,'marte',0,0,14,34);
    expect(drawn).toEqual(['/models/solar-turntable/marte/34.webp']);
  });
});

