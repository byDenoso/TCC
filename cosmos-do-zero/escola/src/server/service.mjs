import { Pool } from 'pg';
import {
  randomBytes,
  randomUUID,
  scrypt as scryptCallback,
  timingSafeEqual,
  createHash,
} from 'node:crypto';
import { promisify } from 'node:util';
import bank from './answer-bank.json' with { type: 'json' };
import labBank from './lab-bank.json' with { type: 'json' };
const scrypt = promisify(scryptCallback);
const hash = (s) => createHash('sha256').update(s).digest('hex');
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
const fail = (status, message) => {
  throw new ApiError(status, message);
};
let pool, schema;
const ddl = [
  "CREATE TABLE IF NOT EXISTS cosmos_school_users (id uuid PRIMARY KEY, name text UNIQUE NOT NULL, pass text NOT NULL, role text NOT NULL DEFAULT 'student' CHECK(role IN ('student','editor')))",
  'CREATE TABLE IF NOT EXISTS cosmos_school_sessions (token text PRIMARY KEY,user_id uuid NOT NULL REFERENCES cosmos_school_users(id) ON DELETE CASCADE,expires timestamptz NOT NULL)',
  'CREATE TABLE IF NOT EXISTS cosmos_school_activity (sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id uuid NOT NULL REFERENCES cosmos_school_users(id) ON DELETE CASCADE, event_id uuid NOT NULL, data jsonb NOT NULL, UNIQUE(user_id,event_id))',
  "CREATE TABLE IF NOT EXISTS cosmos_school_revisions (key text NOT NULL, version integer NOT NULL, status text NOT NULL CHECK(status IN ('rascunho','revisao','publicado')), payload jsonb NOT NULL, editor uuid NOT NULL REFERENCES cosmos_school_users(id), created timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(key,version))",
  'CREATE TABLE IF NOT EXISTS cosmos_school_rates (bucket text PRIMARY KEY, window_start timestamptz NOT NULL, count integer NOT NULL)',
  'CREATE TABLE IF NOT EXISTS cosmos_school_certificates (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES cosmos_school_users(id), level integer NOT NULL, issued timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,level))',
];
export function configured() {
  return !!(process.env.DATABASE_URL || process.env.POSTGRES_URL);
}
export async function database() {
  if (!configured()) fail(503, 'O banco de contas ainda não está conectado.');
  pool ??= new Pool({
    connectionString: process.env.DATABASE_URL || process.env.POSTGRES_URL,
    max: 4,
    connectionTimeoutMillis: 7000,
    idleTimeoutMillis: 10000,
  });
  if (!schema)
    schema = (async () => {
      const c = await pool.connect();
      try {
        await c.query('BEGIN');
        await c.query('SELECT pg_advisory_xact_lock(733602011)');
        for (const sql of ddl) await c.query(sql);
        await c.query('COMMIT');
      } catch (e) {
        await c.query('ROLLBACK');
        throw e;
      } finally {
        c.release();
      }
    })().catch((e) => {
      schema = undefined;
      throw e;
    });
  await schema;
  return pool;
}
export async function closePool() {
  if (pool) await pool.end();
  pool = undefined;
  schema = undefined;
}
async function limited(db, bucket, max) {
  const q = await db.query(
    "INSERT INTO cosmos_school_rates VALUES ($1,now(),1) ON CONFLICT(bucket) DO UPDATE SET count=CASE WHEN cosmos_school_rates.window_start < now()-interval '15 minutes' THEN 1 ELSE cosmos_school_rates.count+1 END,window_start=CASE WHEN cosmos_school_rates.window_start < now()-interval '15 minutes' THEN now() ELSE cosmos_school_rates.window_start END RETURNING count",
    [bucket]
  );
  if (q.rows[0].count > max) fail(429, 'Limite de tentativas atingido. Tente após 15 minutos.');
}
const passwordHash = async (p, salt) =>
  Buffer.from(await scrypt(p, salt, 32, { N: 32768, r: 8, p: 3, maxmem: 64 * 1024 * 1024 })).toString(
    'hex'
  );
const idPattern = /^[a-z0-9][a-z0-9-]{0,119}$/;
const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
async function identify(db, token) {
  if (!token || !/^[a-f0-9]{64}$/.test(token)) return null;
  return (
    (
      await db.query(
        'SELECT u.id,u.name,u.role FROM cosmos_school_sessions s JOIN cosmos_school_users u ON s.user_id=u.id WHERE s.token=$1 AND s.expires>now()',
        [hash(token)]
      )
    ).rows[0] ?? null
  );
}
async function history(db, u) {
  return (
    await db.query('SELECT data FROM cosmos_school_activity WHERE user_id=$1 ORDER BY sequence', [u])
  ).rows.map((r) => r.data);
}
function correct(q, v) {
  if (typeof v !== 'string' && typeof v !== 'number') return false;
  const s = String(v).trim().replace(',', '.');
  return (
    /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(s) &&
    Number.isFinite(+s) &&
    Math.abs(+s - q.answer) <= q.tolerance + 4 * Number.EPSILON * Math.max(1, Math.abs(q.answer))
  );
}
function keysFor(level, order) {
  return Object.entries(bank).filter(([, v]) => v.level === level && (!order || v.order === order));
}
async function sanitizeEvent(db, e, allowPast) {
  if (
    !e ||
    !uuid.test(e.id) ||
    typeof e.lesson !== 'string' ||
    !idPattern.test(e.lesson) ||
    typeof e.value !== 'string' ||
    e.value.length > 12000
  )
    fail(400, 'Registro de estudo inválido.');
  const now = Date.now(),
    at = allowPast && Number.isFinite(e.at) ? Math.min(now, Math.max(0, e.at)) : now;
  const v = { id: e.id, at, kind: e.kind, lesson: e.lesson, value: e.value };
  if (e.kind === 'lab') {
    const target = Object.hasOwn(labBank, e.lesson) ? labBank[e.lesson] : null;
    let sample;
    try {
      sample = JSON.parse(e.value);
    } catch {
      fail(400, 'Medida inválida.');
    }
    if (
      !target ||
      !sample ||
      !Array.isArray(sample.values) ||
      sample.values.length !== target.values.length
    )
      fail(400, 'Configuração inválida.');
    return {
      ...v,
      correct:
        sample.values.every((n, i) => typeof n === 'number' && Math.abs(n - target.values[i]) < 1e-6) &&
        correct(
          { answer: target.metric, tolerance: Math.max(Math.abs(target.metric) * 0.01, 1e-12) },
          sample.answer
        ),
    };
  }
  if (e.kind === 'assessment') {
    const m = /^(avaliacao|diagnostico)-([1-6])$/.exec(e.lesson);
    if (!m) fail(400, 'Nível inválido.');
    let answers;
    try {
      answers = JSON.parse(e.value);
    } catch {
      fail(400, 'Respostas inválidas.');
    }
    const items = keysFor(+m[2], m[1] === 'diagnostico' ? 1 : 2);
    if (
      !answers ||
      Array.isArray(answers) ||
      items.some(([k]) => typeof answers[k] !== 'string' || !answers[k].trim())
    )
      fail(400, 'Responda todas as questões.');
    return {
      ...v,
      score: items.filter(([k, l]) => correct(l.exercise, answers[k])).length,
      total: items.length,
    };
  }
  let exercise = Object.hasOwn(bank, e.lesson) ? bank[e.lesson].exercise : null;
  if (!exercise) {
    const revisionKey = e.lesson.startsWith('edicao-') ? e.lesson.slice(7) : e.lesson;
    const p = (
      await db.query(
        "SELECT payload FROM cosmos_school_revisions WHERE key=$1 AND status='publicado' ORDER BY version DESC LIMIT 1",
        [revisionKey]
      )
    ).rows[0]?.payload;
    if (!p) fail(400, 'Aula desconhecida.');
    if (p.question) exercise = { answer: Number(p.answer), tolerance: p.tolerance };
  }
  if (e.kind === 'attempt') {
    if (!exercise || !v.value.trim() || v.value.length > 100) fail(400, 'Resposta inválida.');
    return { ...v, correct: correct(exercise, v.value) };
  }
  if (e.kind === 'open') return { ...v, value: '' };
  if (
    (e.kind === 'note' && e.value.length <= 2400) ||
    (e.kind === 'favorite' && ['yes', 'no'].includes(e.value))
  )
    return v;
  fail(400, 'Atividade inválida.');
}
async function storeEvents(db, u, raw, importing) {
  const client = await db.connect();
  const saved = [];
  try {
    await client.query('BEGIN');
    for (const e of raw) {
      const event = await sanitizeEvent(client, e, importing);
      const q = await client.query(
        'INSERT INTO cosmos_school_activity(user_id,event_id,data) VALUES($1,$2,$3) ON CONFLICT(user_id,event_id) DO NOTHING RETURNING data',
        [u, event.id, event]
      );
      saved.push(
        q.rows[0]?.data ??
          (
            await client.query(
              'SELECT data FROM cosmos_school_activity WHERE user_id=$1 AND event_id=$2',
              [u, event.id]
            )
          ).rows[0].data
      );
    }
    await client.query('COMMIT');
    return saved;
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}
const readOps = new Set(['session', 'published', 'admin', 'certificate-view']);
export const isReadOp = (op) => readOps.has(op);
const officialLabs = new Set([
  'orbitas',
  'gravitacao',
  'n-corpos',
  'ondas',
  'campos',
  'relatividade',
  'curvatura',
  'lentes',
  'buracos-negros',
  'expansao',
  'estruturas',
  'rotacao',
  'fator-de-escala',
  'energia-escura',
  'cmb',
]);
function validatePayload(p) {
  if (
    !p ||
    !['Disciplina', 'Módulo', 'Aula', 'Exercício', 'Experimento', 'Referência'].includes(p.type) ||
    !Number.isInteger(p.level) ||
    p.level < 1 ||
    p.level > 6
  )
    fail(400, 'Tipo ou nível inválido.');
  for (const k of ['title', 'body', 'subject', 'lab', 'reference', 'question', 'answer', 'unit'])
    if (
      typeof p[k] !== 'string' ||
      p[k].length > (k === 'body' ? 18000 : k === 'reference' ? 1500 : k === 'question' ? 1600 : 200)
    )
      fail(400, 'Campo editorial inválido.');
  if (
    !p.title.trim() ||
    !p.subject.trim() ||
    !p.body.trim() ||
    (p.lab && !officialLabs.has(p.lab)) ||
    (p.reference && !/^https:\/\/[^\s/]+[^\s]*$/.test(p.reference))
  )
    fail(400, 'Revise título, disciplina, texto, laboratório e fonte HTTPS.');
  if (
    !Number.isFinite(p.tolerance) ||
    p.tolerance < 0 ||
    (p.question && (!p.answer.trim() || !Number.isFinite(Number(p.answer))))
  )
    fail(400, 'Gabarito ou tolerância inválida.');
  const options = p.options ?? [];
  if (
    !Array.isArray(options) ||
    options.length > 12 ||
    options.some((o) => typeof o !== 'string' || !o.trim() || o.length > 320)
  )
    fail(400, 'Opções de resposta inválidas.');
  if (
    options.length &&
    (options.length < 2 ||
      !Number.isInteger(+p.answer) ||
      +p.answer < 0 ||
      +p.answer >= options.length ||
      p.tolerance !== 0)
  )
    fail(400, 'Selecione a alternativa correta e use tolerância zero.');
  const fields = [
    'type',
    'level',
    'title',
    'body',
    'subject',
    'lab',
    'reference',
    'question',
    'answer',
    'unit',
    'tolerance',
  ];
  return { ...Object.fromEntries(fields.map((k) => [k, p[k]])), options };
}
export async function dispatch({ op, token, body = {}, ip = '', id = '' }) {
  if (!configured() && op === 'session')
    return { data: { available: false, account: null, entries: [], certificates: false } };
  if (!configured() && op === 'published') return { data: { items: [] } };
  const db = await database();
  if (op === 'register' || op === 'login') {
    if (typeof body.name !== 'string' || typeof body.password !== 'string')
      fail(400, 'Informe usuário e senha.');
    const name = body.name.toLowerCase().trim(),
      pass = body.password;
    if (
      !/^[a-z0-9_.-]{3,40}$/.test(name) ||
      pass.length > 128 ||
      pass.length < (op === 'register' ? 12 : 1)
    )
      fail(400, 'Use um nome de 3 a 40 caracteres e uma senha válida.');
    await limited(db, 'ip:' + hash(ip), 35);
    await limited(db, 'user:' + hash(name), 15);
    let uid;
    if (op === 'register') {
      const salt = randomBytes(16).toString('hex'),
        stored = salt + ':' + (await passwordHash(pass, salt));
      uid = randomUUID();
      try {
        await db.query('INSERT INTO cosmos_school_users(id,name,pass) VALUES($1,$2,$3)', [
          uid,
          name,
          stored,
        ]);
      } catch (e) {
        if (e.code === '23505') fail(409, 'Esse nome de usuário já está em uso.');
        throw e;
      }
    } else {
      const row = (await db.query('SELECT id,pass FROM cosmos_school_users WHERE name=$1', [name]))
        .rows[0];
      const [salt, want] = (row?.pass ?? '00000000000000000000000000000000:' + '00'.repeat(32)).split(
        ':'
      );
      const got = await passwordHash(pass, salt);
      if (!row || !timingSafeEqual(Buffer.from(got, 'hex'), Buffer.from(want, 'hex')))
        fail(401, 'Usuário ou senha inválidos.');
      uid = row.id;
    }
    const fresh = randomBytes(32).toString('hex');
    await db.query("INSERT INTO cosmos_school_sessions VALUES($1,$2,now()+interval '7 days')", [
      hash(fresh),
      uid,
    ]);
    return { data: { ok: true }, session: fresh };
  }
  if (op === 'published')
    return {
      data: {
        items: (
          await db.query(
            "SELECT DISTINCT ON (key) key,version,status,payload FROM cosmos_school_revisions WHERE status='publicado' ORDER BY key,version DESC"
          )
        ).rows,
      },
    };
  if (op === 'certificate-view') {
    if (!uuid.test(id)) fail(404, 'Certificado não encontrado.');
    const row = (
      await db.query(
        'SELECT c.id,c.level,c.issued,u.name FROM cosmos_school_certificates c JOIN cosmos_school_users u ON u.id=c.user_id WHERE c.id=$1',
        [id]
      )
    ).rows[0];
    if (!row) fail(404, 'Certificado não encontrado.');
    return { data: row };
  }
  const account = await identify(db, token);
  if (op === 'session')
    return {
      data: {
        available: true,
        account: account ? { name: account.name, role: account.role } : null,
        entries: account ? await history(db, account.id) : [],
        certificates: process.env.COSMOS_CERTIFICATES === '1',
      },
    };
  if (!account) fail(401, 'Entre na sua conta para continuar.');
  if (op === 'logout') {
    await db.query('DELETE FROM cosmos_school_sessions WHERE token=$1', [hash(token)]);
    return { data: { ok: true }, session: '' };
  }
  if (op === 'record' || op === 'import') {
    const events = op === 'record' ? [body.event] : body.events;
    if (!Array.isArray(events) || events.length > 50) fail(400, 'Lote de atividades inválido.');
    const saved = await storeEvents(db, account.id, events, op === 'import');
    return { data: op === 'record' ? { event: saved[0] } : { count: saved.length } };
  }
  if (op === 'certificate') {
    if (process.env.COSMOS_CERTIFICATES !== '1')
      fail(403, 'A emissão de certificados está desabilitada.');
    const level = body.level;
    if (!Number.isInteger(level) || level < 1 || level > 6) fail(400, 'Nível inválido.');
    const entries = await history(db, account.id);
    const done = new Set(entries.filter((e) => e.kind === 'attempt' && e.correct).map((e) => e.lesson));
    if (
      !keysFor(level).every(([key]) => done.has(key)) ||
      !entries.some(
        (e) => e.kind === 'assessment' && e.lesson === 'avaliacao-' + level && e.score / e.total >= 0.7
      )
    )
      fail(409, 'Resolva os exercícios e obtenha 70% na avaliação do nível.');
    const q = await db.query(
      'INSERT INTO cosmos_school_certificates VALUES($1,$2,$3,now()) ON CONFLICT(user_id,level) DO UPDATE SET level=EXCLUDED.level RETURNING id',
      [randomUUID(), account.id, level]
    );
    return { data: q.rows[0] };
  }
  if (!['admin', 'revision'].includes(op)) fail(404, 'Operação desconhecida.');
  if (account.role !== 'editor') fail(403, 'Esta área exige uma conta editorial.');
  if (op === 'admin') {
    const revisions = (
      await db.query(
        'SELECT key,version,status,payload,created FROM cosmos_school_revisions ORDER BY created DESC'
      )
    ).rows;
    const counts = (
      await db.query(
        "SELECT (SELECT count(*)::int FROM cosmos_school_users) AS students,count(*) FILTER(WHERE data->>'kind'='attempt')::int AS attempts,count(*) FILTER(WHERE data->>'kind'='attempt' AND data->>'correct'='true')::int AS correct FROM cosmos_school_activity"
      )
    ).rows[0];
    const progress = (
      await db.query(
        "SELECT data->>'lesson' AS lesson,count(DISTINCT user_id)::int AS students FROM cosmos_school_activity WHERE data->>'kind'='attempt' AND data->>'correct'='true' GROUP BY data->>'lesson' ORDER BY students DESC"
      )
    ).rows;
    return { data: { revisions, counts, progress } };
  }
  if (
    !idPattern.test(body.key) ||
    !Number.isInteger(body.expected) ||
    body.expected < 0 ||
    !['rascunho', 'revisao', 'publicado'].includes(body.status)
  )
    fail(400, 'Identificador ou versão inválida.');
  const p = validatePayload(body.payload);
  const c = await db.connect();
  try {
    await c.query('BEGIN');
    await c.query('SELECT pg_advisory_xact_lock(hashtext($1))', ['cosmos-edit:' + body.key]);
    const last = (
      await c.query(
        'SELECT version,status,payload FROM cosmos_school_revisions WHERE key=$1 ORDER BY version DESC LIMIT 1',
        [body.key]
      )
    ).rows[0];
    if ((last?.version ?? 0) !== body.expected)
      fail(409, 'O conteúdo mudou. Recarregue a versão atual.');
    if (
      body.status === 'publicado' &&
      (!last ||
        last.status !== 'revisao' ||
        Object.keys(p).some(
          (k) =>
            JSON.stringify(last.payload[k] ?? (k === 'options' ? [] : null)) !== JSON.stringify(p[k])
        ) ||
        !p.reference)
    )
      fail(409, 'Envie o texto e a fonte para revisão antes de publicar a mesma versão.');
    await c.query(
      'INSERT INTO cosmos_school_revisions(key,version,status,payload,editor) VALUES($1,$2,$3,$4,$5)',
      [body.key, body.expected + 1, body.status, p, account.id]
    );
    await c.query('COMMIT');
    return { data: { version: body.expected + 1 } };
  } catch (e) {
    await c.query('ROLLBACK');
    throw e;
  } finally {
    c.release();
  }
}
