import { describe, expect, it } from 'vitest';
import { chapters, planets, questions, terms, eras, CHAPTER_IDS, PRIMARY_CHAPTER_IDS, EXTRA_CHAPTER_IDS, chapterOrder, primaryChapters, extraChapters, primaryRows, extraRows, chapterTrack, trackChapterIds, chapterNumber, adjacentChapters } from '../../src/data';
import { format, mass, normalize } from '../../src/lib/format';
import { compareInsight, comparison, compareRows } from '../../src/lib/planets';
import { stellarPath, clampMass } from '../../src/lib/stars';
import { filterTerms } from '../../src/lib/glossary';
import { advance, answer, createQuiz, missed, poolFor, score } from '../../src/lib/quiz';
import { createLocalStore, mainCompletedCount, nextUnfinished, progressLabel, sanitize } from '../../src/lib/progress';

const byId = (id: string) => planets.find((p) => p.id === id)!;

describe('dados', () => {
  it('mantém as contagens aprovadas', () => {
    expect(chapters).toHaveLength(6);
    expect(eras).toHaveLength(10);
    expect(planets).toHaveLength(8);
    expect(questions).toHaveLength(15);
    expect(terms).toHaveLength(26);
    expect(chapters.every((c) => c.sections.length === 6)).toBe(true);
  });
  it('perguntas têm gabarito válido, 3 por capítulo principal e 2 por extra', () => {
    for (const q of questions) expect(q.correct).toBeGreaterThanOrEqual(0), expect(q.correct).toBeLessThan(q.answers.length);
    for (const id of PRIMARY_CHAPTER_IDS) expect(questions.filter((q) => q.chapter === id)).toHaveLength(3);
    for (const id of EXTRA_CHAPTER_IDS) expect(questions.filter((q) => q.chapter === id)).toHaveLength(2);
  });
  it('todo marco, termo e pergunta aponta para um capítulo existente', () => {
    const ok = new Set<string>(chapterOrder);
    for (const x of [...eras, ...terms, ...questions]) expect(ok.has(x.chapter)).toBe(true);
  });
  it('navegação entre capítulos', () => {
    expect(adjacentChapters('galaxias-e-nebulosas').prev).toBeUndefined();
    expect(adjacentChapters('galaxias-e-nebulosas').next?.id).toBe('origem-do-universo');
    expect(adjacentChapters('origem-do-universo').next?.id).toBe('misterios-do-cosmos');
    expect(adjacentChapters('misterios-do-cosmos').next).toBeUndefined();
    expect(adjacentChapters('vida-das-estrelas').prev).toBeUndefined();
    expect(adjacentChapters('vida-das-estrelas').next?.id).toBe('sistema-solar');
    expect(adjacentChapters('terra-e-atmosfera').next).toBeUndefined();
  });
  it('preserva os IDs legados e separa as duas trilhas na ordem definida', () => {
    expect(CHAPTER_IDS).toEqual([
      'origem-do-universo', 'galaxias-e-nebulosas', 'vida-das-estrelas',
      'sistema-solar', 'terra-e-atmosfera', 'misterios-do-cosmos'
    ]);
    expect(PRIMARY_CHAPTER_IDS).toEqual(['galaxias-e-nebulosas', 'origem-do-universo', 'misterios-do-cosmos']);
    expect(EXTRA_CHAPTER_IDS).toEqual(['vida-das-estrelas', 'sistema-solar', 'terra-e-atmosfera']);
    expect(chapterOrder).toEqual([...PRIMARY_CHAPTER_IDS, ...EXTRA_CHAPTER_IDS]);
    expect(primaryChapters.map((chapter) => chapter.id)).toEqual(PRIMARY_CHAPTER_IDS);
    expect(extraChapters.map((chapter) => chapter.id)).toEqual(EXTRA_CHAPTER_IDS);
    expect(primaryRows.map((row) => row.id)).toEqual(PRIMARY_CHAPTER_IDS);
    expect(extraRows.map((row) => row.id)).toEqual(EXTRA_CHAPTER_IDS);
    expect(chapterTrack('origem-do-universo')).toBe('primary');
    expect(chapterTrack('sistema-solar')).toBe('extra');
    expect(trackChapterIds('misterios-do-cosmos')).toBe(PRIMARY_CHAPTER_IDS);
    expect(trackChapterIds('terra-e-atmosfera')).toBe(EXTRA_CHAPTER_IDS);
    expect(chapterNumber('origem-do-universo')).toBe(2);
    expect(chapterNumber('vida-das-estrelas')).toBe(1);
    expect(chapterNumber('terra-e-atmosfera')).toBe(3);
  });
  it('links externos são https', () => {
    for (const c of chapters) for (const s of c.sections) for (const l of s.sources) expect(l.href.startsWith('https://')).toBe(true);
  });
});

describe('formatação', () => {
  it('pt-BR', () => {
    expect(format(6378)).toBe('6.378');
    expect(format(0.387, 3)).toBe('0,387');
    expect(mass(5.97e24)).toBe('5,97 × 10²⁴ kg');
    expect(mass(1.898e27)).toBe('1,898 × 10²⁷ kg');
  });
  it('normaliza acentos', () => expect(normalize('Radiação Cósmica')).toBe('radiacao cosmica'));
});

describe('comparador', () => {
  it('razão de raios Júpiter/Terra ≈ 11,2', () => {
    expect(compareInsight(byId('terra'), byId('jupiter'))).toContain('11,21 vezes');
    const c = comparison(byId('terra'), byId('jupiter'));
    expect(c.diameters[1]).toBe(100);
    expect(c.diameters[0]).toBeCloseTo((6378 / 71492) * 100, 5);
  });
  it('mesmo planeta nos dois lados', () => expect(compareInsight(byId('marte'), byId('marte'))).toMatch(/mesmo planeta/));
  it('troca de lados mantém a razão', () => {
    expect(compareInsight(byId('jupiter'), byId('terra'))).toContain('11,21 vezes');
  });
  it('tabela define onde cada temperatura é medida', () => {
    const row = compareRows.find((r) => r.label === 'Onde é medida')!;
    expect(row.value(byId('venus'))).toBe('Superfície (média)');
    expect(row.value(byId('netuno'))).toBe('Atmosfera (1 bar)');
    const rot = compareRows.find((r) => r.label === 'Rotação sideral')!;
    expect(rot.value(byId('venus'))).toContain('retrógrada');
  });
});

describe('evolução estelar', () => {
  it('três regimes e limiares', () => {
    expect(stellarPath(0.3).orb).toBe('low');
    expect(stellarPath(0.59).orb).toBe('low');
    expect(stellarPath(0.6).orb).toBe('medium');
    expect(stellarPath(1).category).toBe('SEMELHANTE AO SOL');
    expect(stellarPath(1.5).category).toBe('MASSA INTERMEDIÁRIA');
    expect(stellarPath(7.9).orb).toBe('medium');
    expect(stellarPath(8).orb).toBe('high');
    expect(stellarPath(30).steps.at(-1)).toMatch(/buraco negro/);
  });
  it('sanitiza a massa vinda da URL', () => {
    expect(clampMass(NaN)).toBe(1);
    expect(clampMass(500)).toBe(30);
    expect(clampMass(-3)).toBe(0.2);
    expect(clampMass(5.04)).toBe(5);
  });
});

describe('glossário', () => {
  it('busca com e sem acento', () => {
    expect(filterTerms(terms, 'radiacao').map((i) => terms[i].term)).toContain('Radiação cósmica de fundo (CMB)');
    expect(filterTerms(terms, 'RADIAÇÃO').length).toBe(filterTerms(terms, 'radiacao').length);
  });
  it('sem resultados e recuperação da lista', () => {
    expect(filterTerms(terms, 'zzzzqq')).toHaveLength(0);
    expect(filterTerms(terms, '')).toHaveLength(26);
  });
  it('filtra por capítulo', () => expect(filterTerms(terms, '', 'vida-das-estrelas').length).toBe(terms.filter((t) => t.chapter === 'vida-das-estrelas').length));
});

describe('quiz', () => {
  it('fluxo completo, resultado e reinício', () => {
    let s = createQuiz(poolFor(questions, 'origem-do-universo'));
    expect(s.pool).toHaveLength(3);
    s = answer(s, s.pool[0].correct);
    expect(score(s)).toBe(1);
    s = answer(s, 0); // segunda resposta na mesma pergunta é ignorada
    expect(s.history).toHaveLength(1);
    s = advance(s);
    s = answer(s, (s.pool[1].correct + 1) % s.pool[1].answers.length);
    expect(score(s)).toBe(1);
    expect(s.history).toHaveLength(2);
    s = advance(s);
    s = answer(s, s.pool[2].correct);
    expect(score(s)).toBe(2);
    s = advance(s);
    expect(s.finished).toBe(true);
    expect(score(s)).toBe(2);
    expect(missed(s).map((q) => q.id)).toEqual([s.pool[1].id]);
    s = advance(s);
    expect(s.finished).toBe(false);
    expect(s.history).toHaveLength(0);
    expect(s.position).toBe(0);
    expect(s.pool).toHaveLength(3);
  });
  it('não avança sem responder', () => {
    const s = createQuiz(questions);
    expect(advance(s)).toBe(s);
  });
  it('rejeita alternativa inexistente', () => {
    const s = createQuiz(questions);
    expect(answer(s, 9)).toBe(s);
  });
});

describe('progresso', () => {
  it('sanitiza lixo e duplicatas', () => expect(sanitize(['sistema-solar', 'x', 'sistema-solar', 3])).toEqual(['sistema-solar']));
  it('persiste e lê', () => {
    const mem = new Map<string, string>();
    const st = { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v) } as unknown as Storage;
    const store = createLocalStore(() => st);
    expect(store.write(['origem-do-universo'])).toBe(true);
    expect(store.read()).toEqual(['origem-do-universo']);
  });
  it('funciona sem armazenamento (bloqueado)', () => {
    const blocked = () => {
      throw new Error('SecurityError');
    };
    const store = createLocalStore(blocked as unknown as () => Storage);
    expect(store.write(['terra-e-atmosfera'])).toBe(false);
    expect(store.read()).toEqual(['terra-e-atmosfera']);
  });
  it('prioriza o progresso pendente quando getItem ainda devolve o valor antigo', () => {
    const mem = new Map<string, string>([['cosmos-v3-progress', '["origem-do-universo"]']]);
    const storage = {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: () => { throw new Error('QuotaExceededError'); }
    } as unknown as Storage;
    const store = createLocalStore(() => storage);

    expect(store.read()).toEqual(['origem-do-universo']);
    expect(store.write(['galaxias-e-nebulosas', 'sistema-solar'])).toBe(false);
    expect(store.read()).toEqual(['galaxias-e-nebulosas', 'sistema-solar']);
    expect(store.read()).toEqual(['galaxias-e-nebulosas', 'sistema-solar']);
  });
  it('mantém desmarcação e reinício na sessão enquanto a gravação falha', () => {
    const mem = new Map<string, string>([['cosmos-v3-progress', '["origem-do-universo","galaxias-e-nebulosas"]']]);
    const storage = {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: () => { throw new Error('SecurityError'); }
    } as unknown as Storage;
    const store = createLocalStore(() => storage);

    expect(store.read()).toEqual(['origem-do-universo', 'galaxias-e-nebulosas']);
    expect(store.write(['galaxias-e-nebulosas'])).toBe(false);
    expect(store.read()).toEqual(['galaxias-e-nebulosas']);
    expect(store.write([])).toBe(false);
    expect(store.read()).toEqual([]);
  });
  it('retoma a persistência depois que setItem volta a funcionar', () => {
    const mem = new Map<string, string>([['cosmos-v3-progress', '["origem-do-universo"]']]);
    let writable = false;
    const storage = {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => {
        if (!writable) throw new Error('QuotaExceededError');
        mem.set(key, value);
      }
    } as unknown as Storage;
    const store = createLocalStore(() => storage);

    expect(store.write(['misterios-do-cosmos', 'terra-e-atmosfera'])).toBe(false);
    expect(store.read()).toEqual(['misterios-do-cosmos', 'terra-e-atmosfera']);
    writable = true;
    expect(store.write(['misterios-do-cosmos', 'terra-e-atmosfera'])).toBe(true);
    expect(store.read()).toEqual(['misterios-do-cosmos', 'terra-e-atmosfera']);
    expect(mem.get('cosmos-v3-progress')).toBe('["misterios-do-cosmos","terra-e-atmosfera"]');
  });
  it('atualiza progresso vindo de outra aba quando não há escrita pendente', () => {
    const mem = new Map<string, string>([['cosmos-v3-progress', '[]']]);
    const storage = {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => mem.set(key, value)
    } as unknown as Storage;
    const store = createLocalStore(() => storage);
    expect(store.read()).toEqual([]);
    mem.set('cosmos-v3-progress', '["sistema-solar"]');
    expect(store.read()).toEqual(['sistema-solar']);
  });
  it('conta apenas a jornada principal e escolhe o próximo capítulo principal', () => {
    const done = ['vida-das-estrelas', 'origem-do-universo'] as const;
    expect(mainCompletedCount([...done])).toBe(1);
    expect(progressLabel(mainCompletedCount([...done]))).toContain('1 de 3');
    expect(nextUnfinished([...done])).toBe('galaxias-e-nebulosas');
    expect(nextUnfinished(['galaxias-e-nebulosas', 'origem-do-universo', 'misterios-do-cosmos', 'vida-das-estrelas'])).toBeUndefined();
    expect(mainCompletedCount(['vida-das-estrelas', 'sistema-solar', 'terra-e-atmosfera'])).toBe(0);
    expect(nextUnfinished(['vida-das-estrelas', 'sistema-solar', 'terra-e-atmosfera'])).toBe('galaxias-e-nebulosas');
  });
  it('JSON corrompido é ignorado', () => {
    const st = { getItem: () => '{oops', setItem: () => {} } as unknown as Storage;
    expect(createLocalStore(() => st).read()).toEqual([]);
  });
});
