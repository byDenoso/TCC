import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { dispatch, database, closePool } from '../src/server/service.mjs';
import bank from '../src/server/answer-bank.json' with { type: 'json' };
if (!process.env.COSMOS_TEST_DATABASE_URL)
  throw Error('Informe COSMOS_TEST_DATABASE_URL apontando a um PostgreSQL isolado de teste.');
process.env.DATABASE_URL = process.env.COSMOS_TEST_DATABASE_URL;
process.env.COSMOS_CERTIFICATES = '1';
const suffix = randomUUID().slice(0, 8),
  name = 'qa_' + suffix,
  password = 'Cosmos test ' + suffix,
  other = 'qa2_' + suffix,
  key = 'edital-' + suffix,
  ip = 'qa-' + suffix;
let token = '',
  tokenOther = '',
  issued = '',
  checks = 0;
const run = (op, body = {}, t = token, id = '') => dispatch({ op, token: t, body, ip, id });
const eq = (a, b) => {
  assert.deepEqual(a, b);
  checks++;
};
const rejected = async (fn, status) => {
  await assert.rejects(fn, (e) => e.status === status);
  checks++;
};
const event = (kind, lesson, value) => ({ kind, lesson, value, id: randomUUID(), at: Date.now() });
const slug = Object.keys(bank)[0],
  q = bank[slug].exercise;
try {
  const reg = await run('register', { name, password });
  token = reg.session;
  eq(token.length, 64);
  await rejected(() => run('register', { name, password }), 409);
  await rejected(() => run('login', { name, password: 'invalid-pass-test' }), 401);
  const info = await run('session');
  eq(info.data.account, { name, role: 'student' });
  tokenOther = (await run('register', { name: other, password }, '')).session;
  const attempt = event('attempt', slug, String(q.answer));
  const wrong = { ...event('attempt', slug, String(q.answer + 100000)), correct: true };
  eq((await run('record', { event: wrong })).data.event.correct, false);
  const both = await Promise.all([run('record', { event: attempt }), run('record', { event: attempt })]);
  eq(
    both.map((r) => r.data.event.id),
    [attempt.id, attempt.id]
  );
  eq((await run('session')).data.entries.length, 2);
  eq((await run('session', {}, tokenOther)).data.entries.length, 0);
  await run('record', { event: event('note', slug, 'Anotação da sessão') });
  await run('record', { event: event('favorite', slug, 'yes') });
  await run('import', { events: [attempt, attempt] });
  eq((await run('session')).data.entries.length, 4);
  await rejected(() => run('admin'), 403);
  await rejected(() => run('certificate', { level: 1 }), 409);
  const db = await database();
  await db.query("UPDATE cosmos_school_users SET role='editor' WHERE name=$1", [name]);
  const payload = {
    type: 'Aula',
    title: 'Revisão QA',
    body: 'Uma edição de teste.',
    level: 1,
    subject: 'Matemática básica',
    lab: 'orbitas',
    reference: 'https://openstax.org',
    question: 'Quanto vale 3 × 3?',
    answer: '9',
    unit: '',
    tolerance: 0,
  };
  const edit = (expected, status, p = payload) => run('revision', { key, expected, status, payload: p });
  eq((await edit(0, 'rascunho')).data.version, 1);
  await rejected(() => edit(0, 'revisao'), 409);
  await rejected(() => edit(1, 'publicado'), 409);
  eq((await edit(1, 'revisao')).data.version, 2);
  await rejected(() => edit(2, 'publicado', { ...payload, title: 'Outra revisão' }), 409);
  eq((await edit(2, 'publicado')).data.version, 3);
  eq((await run('published')).data.items.find((r) => r.key === key).payload.title, payload.title);
  eq((await run('record', { event: event('attempt', 'edicao-' + key, '9') })).data.event.correct, true);
  const meta = (await run('admin')).data;
  assert(meta.counts.students >= 2);
  assert(meta.progress.length > 0);
  checks += 2;
  const lvl = Object.entries(bank).filter(([, m]) => m.level === 1);
  for (const [s, b] of lvl)
    await run('record', { event: event('attempt', s, String(b.exercise.answer)) });
  const answers = Object.fromEntries(
    lvl.filter(([, m]) => m.order === 2).map(([s, b]) => [s, String(b.exercise.answer)])
  );
  const exam = (
    await run('record', { event: event('assessment', 'avaliacao-1', JSON.stringify(answers)) })
  ).data.event;
  eq(exam.score, 5);
  eq(exam.total, 5);
  issued = (await run('certificate', { level: 1 })).data.id;
  eq((await run('certificate', { level: 1 })).data.id, issued);
  eq((await run('certificate-view', {}, '', issued)).data.name, name);
  await run('logout');
  eq((await run('session')).data.account, null);
  token = (await run('login', { name, password })).session;
  assert((await run('session')).data.entries.some((e) => e.value === 'Anotação da sessão'));
  checks++;
  console.log(
    checks +
      ' verificações PostgreSQL aprovadas (contas, idempotência, isolamento, edição, avaliação, emissão e nova sessão).'
  );
} finally {
  const db = await database();
  await db.query('DELETE FROM cosmos_school_revisions WHERE key=$1', [key]);
  await db.query('DELETE FROM cosmos_school_certificates WHERE id::text=$1', [issued]);
  await db.query('DELETE FROM cosmos_school_users WHERE name=ANY($1)', [[name, other]]);
  await closePool();
}
