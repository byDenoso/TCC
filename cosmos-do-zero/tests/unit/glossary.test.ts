import { describe, expect, it } from 'vitest';
import terms from '../../src/data/terms.json';
import { filterTerms, searchNormalize, suggestTerms } from '../../src/lib/glossary';
import type { Term } from '../../src/types';

const T = terms as Term[];
const names = (q: string) => filterTerms(T, q).map((i) => T[i].term);

describe('busca tolerante do glossário', () => {
  it('normaliza hífen, travessão e espaços', () => {
    expect(searchNormalize('Ano–Luz')).toBe('ano luz');
    for (const q of ['ano luz', 'ano-luz', 'ano–luz', 'anoluz', '  ANO   LUZ ']) expect(names(q)).toContain('Ano-luz');
  });
  it('acha sinônimos', () => {
    expect(names('desvio para o vermelho')).toContain('Redshift');
    expect(names('fundo cósmico')).toContain('Radiação cósmica de fundo (CMB)');
  });
  it('tolera um erro de digitação', () => {
    expect(names('nebuloza')).toContain('Nebulosa');
    expect(names('supernva')).toContain('Supernova');
  });
  it('lixo não casa e sugere quando dá', () => {
    expect(names('zzzzqq')).toEqual([]);
    expect(suggestTerms(T, 'galaxa').map((i) => T[i].term)).toContain('Galáxia');
  });
});
