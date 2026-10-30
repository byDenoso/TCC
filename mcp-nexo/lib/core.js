import { createHash } from 'node:crypto';

export const PROJECTION = 'https://bydenoso.github.io/Pantheon/tower-projection/projection.json';
const REPOSITORY = 'byDenoso/TCC';
const RECIPIENTS = new Set(['PITIA', 'LEARNER', 'EXECUTOR', 'REFUTADOR', 'REFEREE_1', 'GUARDIAO', 'ENGINEER', 'SENTINEL', 'ADVISOR', 'CONVERSA', 'DENER', 'ALL']);

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  if (value === null || typeof value === 'string' || typeof value === 'boolean' ||
      (typeof value === 'number' && Number.isFinite(value))) return value;
  throw new Error('Envelope deve conter somente valores JSON finitos.');
}

function serialize(value) { return JSON.stringify(canonical(value)); }
const hash = data => createHash('sha256').update(data).digest('hex');

export async function status() {
  const response = await fetch(PROJECTION, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error('Projeção pública indisponível: HTTP ' + response.status);
  const data = await response.json();
  if (!data || typeof data !== 'object' || !Array.isArray(data.tests)) throw new Error('Projeção pública inválida');
  return data;
}

function assertPublic(envelope) {
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) throw new Error('Envelope inválido');
  if (!['RECIPE_BIND', 'BOARD_POST'].includes(envelope.kind) || envelope.source !== 'CHATGPT' ||
      !Number.isFinite(Date.parse(envelope.created_at)) || !envelope.payload || typeof envelope.payload !== 'object') {
    throw new Error('Somente RECIPE_BIND e BOARD_POST públicos seguem pela trilha Git; privados vão ao Drive.');
  }
  if (envelope.kind === 'BOARD_POST' && (typeof envelope.payload.text !== 'string' ||
      !envelope.payload.text.startsWith('PUBLIC:'))) {
    throw new Error('BOARD_POST público exige prefixo PUBLIC:; recados privados vão ao NEXO_INBOX.');
  }
}

async function github(method, path, branch, body) {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error('GITHUB_TOKEN ausente');
  const url = 'https://api.github.com/repos/' + REPOSITORY + '/contents/' + path.split('/').map(encodeURIComponent).join('/') + '?ref=' + encodeURIComponent(branch);
  const response = await fetch(url, {
    method,
    headers: { authorization: 'Bearer ' + token, accept: 'application/vnd.github+json',
      'x-github-api-version': '2022-11-28', 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(15000),
  });
  if (response.status === 404 && method === 'GET') return null;
  if (!response.ok) throw new Error('GitHub ' + method + ': HTTP ' + response.status);
  return response.json();
}

export async function propose(envelope) {
  assertPublic(envelope);
  const branch = process.env.NEXO_BRANCH || 'nexo/dispatch-runtime';
  if (!/^nexo\/[a-z0-9-]+$/.test(branch)) throw new Error('Ramo de despacho inválido');
  const stable_id = 'nexo-' + hash(serialize(envelope)).slice(0, 32);
  const path = 'nexo_persist/requests/' + stable_id + '.json';
  const record = { stable_id, envelope };
  const bytes = Buffer.from(serialize(record) + '\n', 'utf8');
  const expected = bytes.toString('utf8');
  let current = await github('GET', path, branch);
  if (!current) {
    try {
      await github('PUT', path, branch, {
        message: 'nexo: stage ' + stable_id, branch, content: bytes.toString('base64'),
      });
    } catch (error) {
      // Reconcile a simultaneous create; never overwrite an existing request.
      current = await github('GET', path, branch);
      if (!current) throw error;
    }
  }
  const readback = await github('GET', path, branch);
  if (!readback || readback.encoding !== 'base64' ||
      Buffer.from(readback.content.replace(/\s/g, ''), 'base64').toString('utf8') !== expected) {
    throw new Error('Readback divergente: pedido não confirmado');
  }
  return { stable_id, path, branch, sha256: hash(bytes), github_blob_sha: readback.sha };
}

export function bindRecipe(test_id, recipe, params) {
  if (!test_id || !recipe || !params || typeof params !== 'object' || Array.isArray(params)) throw new Error('Binding inválido');
  return propose({ kind: 'RECIPE_BIND', source: 'CHATGPT', created_at: new Date().toISOString(),
    payload: { test_id, recipe, params } });
}

export function boardPost(to, text, refs = []) {
  if (!RECIPIENTS.has(to) || typeof text !== 'string' || !text.startsWith('PUBLIC:') ||
      !Array.isArray(refs)) throw new Error('Recado público inválido; conteúdo privado exige NEXO_INBOX');
  return propose({ kind: 'BOARD_POST', source: 'CHATGPT', created_at: new Date().toISOString(),
    payload: { to, text, refs } });
}
