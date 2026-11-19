import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import katex from 'katex';
import { levels, grade, canon, type Lesson } from '../src/lib/school.ts';
import { summarize, scoreExam, type Entry } from '../src/lib/records.ts';
import { labs } from '../src/lib/model.ts';
import { chapters } from '../src/lib/legacy.ts';
const lessons = fs
  .readdirSync('content')
  .filter((f) => f.endsWith('.mdx'))
  .map((f) => {
    const [a, b] = fs
      .readFileSync('content/' + f, 'utf8')
      .replace(/\r/g, '')
      .split('\n---\n');
    return { m: JSON.parse(a.slice(3)) as Lesson, body: b };
  });
for (let i = 0; i < levels.length; i++)
  test('Sequência e contrato das aulas · ' + levels[i].name, () => {
    const content = lessons.filter((l) => l.m.level === i + 1);
    assert.equal(content.length, levels[i].subjects.length * 2);
    for (const subject of levels[i].subjects) {
      const pair = content.filter((l) => l.m.subject === subject);
      assert.deepEqual(pair.map((l) => l.m.order).sort(), [1, 2]);
      for (const { m, body } of pair) {
        assert(body.length > 420);
        assert(m.reference.url.startsWith('https://'));
        assert(labs.some((l) => l.id === m.lab));
        assert(m.graph.points.length >= 3);
        assert(m.graph.points.every((p) => p.every(Number.isFinite)));
        assert(grade(m.exercise, m.exercise.answer));
        assert(!grade(m.exercise, m.exercise.answer + m.exercise.tolerance + 3));
        assert(!grade(m.exercise, ''));
        const formulas = body.match(/\$\$[\s\S]*?\$\$|\$(?!\$)[^\n$]+\$/g) ?? [];
        assert(formulas.length > 0);
        for (const tex of formulas)
          katex.renderToString(tex.replace(/^\$\$?|\$\$?$/g, ''), {
            throwOnError: true,
            strict: 'ignore',
            trust: false,
          });
      }
    }
  });
test('As 82 aulas possuem identificadores únicos e os capítulos antigos mantêm destino', () => {
  assert.equal(lessons.length, 82);
  assert.equal(new Set(lessons.map((l) => l.m.slug)).size, 82);
  for (const dest of Object.values(chapters)) assert(lessons.some((l) => l.m.slug === dest));
  assert.equal(canon('Gravitação'), canon('gravitacao'));
});
test('Correção com vírgula, tolerância absoluta, escolha zero e nota do módulo', () => {
  const q = {
    kind: 'numeric' as const,
    prompt: 'Teste',
    answer: 2,
    tolerance: 0.1,
    feedback: '',
    unit: 'm',
  };
  assert(grade(q, '2,1'));
  assert(!grade(q, '2,11'));
  assert(!grade(q, null));
  assert(!grade(q, 'Infinity'));
  assert(grade({ ...q, kind: 'choice', answer: 0, tolerance: 0 }, '0'));
  assert.equal(scoreExam([{ slug: 'q', exercise: q }], { q: '1,9' }), 1);
});
test('Atividades geram progresso, agenda, favoritos e histórico verificáveis', () => {
  const item = (kind: Entry['kind'], at: number, value = '', correct?: boolean): Entry => ({
    id: String(at),
    lesson: 'a',
    kind,
    at,
    value,
    correct,
  });
  const list = [
    item('open', 1),
    item('favorite', 2, 'yes'),
    item('note', 3, 'lembrete'),
    item('attempt', 4, '2', false),
  ];
  let s = summarize(list, 5);
  assert.deepEqual(s.reviews, ['a']);
  assert(s.favorites.has('a'));
  assert.equal(s.notes.a, 'lembrete');
  assert.equal(s.latest, 'a');
  s = summarize([...list, item('attempt', 6, '4', true), item('favorite', 7, 'no')], 8);
  assert(s.done.has('a'));
  assert(!s.reviews.length);
  assert(!s.favorites.has('a'));
  assert.equal(s.due.a, 86400006);
});
