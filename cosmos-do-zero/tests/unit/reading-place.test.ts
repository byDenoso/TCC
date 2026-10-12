import { describe, expect, it } from 'vitest';
import { parsePlaces } from '../../src/lib/reading-place';

const place = { chapter: 'galaxias-e-nebulosas', step: 3, total: 6, section: 'galaxias-e-nebulosas-nebulosas', title: 'Nebulosas', at: 100 };
describe('retomar a leitura sem depender de armazenamento válido', () => {
  it.each(['null', '[]', 'false', '1', '{', '{"galaxias-e-nebulosas":null}'])('ignora estado inválido %s', (raw) => {
    expect(parsePlaces(raw)).toEqual({});
  });
  it('preserva a posição válida e ignora entradas corrompidas no mesmo objeto', () => {
    expect(parsePlaces(JSON.stringify({ [place.chapter]: place, desconhecido: place, 'sistema-solar': { ...place, chapter: 'sistema-solar', step: -1 } }))).toEqual({ [place.chapter]: place });
  });
  it('rejeita posições fora da aula e âncoras de outro capítulo', () => {
    for (const bad of [{ ...place, step: 6 }, { ...place, step: 0.5 }, { ...place, section: 'sistema-solar-disco' }]) {
      expect(parsePlaces(JSON.stringify({ [place.chapter]: bad }))).toEqual({});
    }
  });
});
