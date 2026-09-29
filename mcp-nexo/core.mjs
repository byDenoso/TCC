import { createHash } from 'node:crypto';

export const PROJECTION_URL = 'https://bydenoso.github.io/Pantheon/tower-projection/projection.json';
export const DISPATCH_BRANCH = 'nexo/dispatch-runtime';
const REPOSITORY = 'byDenoso/TCC';

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

// A retry keeps its identity when only the transport timestamp changes.
function identity(envelope) {
  const { created_at, ...rest } = envelope;
  if (rest.kind === 'BATCH') rest.payload = { ...rest.payload, items: rest.payload.items.map(identity) };
  return rest;
}

export function validateEnvelope(envelope) {
  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)
      || typeof envelope.kind !== 'string' || !envelope.kind
      || typeof envelope.source !== 'string' || !envelope.source
      || typeof envelope.created_at !== 'string' || !Number.isFinite(Date.parse(envelope.created_at))
      || !envelope.payload || typeof envelope.payload !== 'object' || Array.isArray(envelope.payload)) {
    throw new Error('Envelope exige kind, source, created_at e payload, conforme gpt/PROPOSAL_SCHEMA.md.');
  }
  if (['HANDOFF', 'HANDOFF_TRANSITION'].includes(envelope.kind)) {
    throw new Error('Handoff exige inbox privado do Drive; o staging GitHub é público.');
  }
  if (envelope.kind === 'BATCH') {
    const items = envelope.payload.items;
    if (!Array.isArray(items) || !items.length || items.length > 10) throw new Error('BATCH exige de 1 a 10 itens.');
    for (const item of items) {
      if (item.kind === 'BATCH') throw new Error('Use lotes planos com até 10 itens.');
      validateEnvelope(item);
    }
  }
}

export function stableId(envelope) {
  validateEnvelope(envelope);
  return `nexo-${createHash('sha256').update(canonical(identity(envelope))).digest('hex')}`;
}

export function createTools({ branch = DISPATCH_BRANCH, fetchImpl = fetch, githubToken = process.env.GITHUB_TOKEN } = {}) {
  async function github(path, options = {}) {
    if (!githubToken) throw new Error('GITHUB_TOKEN não configurado.');
    return fetchImpl(`https://api.github.com/repos/${REPOSITORY}/${path}`, {
      ...options,
      headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${githubToken}`,
        'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(30_000),
    });
  }

  async function propose(envelope) {
    const stable_id = stableId(envelope);
    const path = `nexo_persist/requests/${stable_id}.json`;
    const target = `contents/${path}`;
    const read = () => github(`${target}?ref=${encodeURIComponent(branch)}`);
    let response = await read();
    if (response.status === 404) {
      const record = { stable_id, envelope };
      response = await github(target, { method: 'PUT', body: JSON.stringify({
        message: `NEXO: proposta ${stable_id}`,
        branch,
        content: Buffer.from(canonical(record) + '\n').toString('base64'),
      }) });
      // Concurrent identical proposals may race; the read-back decides success.
      if (!response.ok && ![409, 422].includes(response.status)) throw new Error(`GitHub gravação: HTTP ${response.status}.`);
      response = await read();
    }
    if (!response.ok) throw new Error(`GitHub leitura: HTTP ${response.status}.`);
    const file = await response.json();
    const stored = JSON.parse(Buffer.from(file.content, 'base64').toString('utf8'));
    if (stored.stable_id !== stable_id || canonical(identity(stored.envelope)) !== canonical(identity(envelope))) {
      throw new Error('Leitura de volta divergiu da proposta.');
    }
    return { stable_id, repository: REPOSITORY, branch, path, sha: file.sha };
  }

  function envelope(kind, payload) {
    return { kind, source: 'CHATGPT', producer: 'GPT', created_at: new Date().toISOString(), payload };
  }

  return {
    async status() {
      const response = await fetchImpl(PROJECTION_URL, { signal: AbortSignal.timeout(30_000) });
      if (!response.ok) throw new Error(`Projeção pública: HTTP ${response.status}.`);
      return response.json();
    },
    propose,
    bind_recipe: (test_id, recipe, params) => propose(envelope('RECIPE_BIND', { test_id, recipe, params })),
    board_post: (to, text, refs = []) => propose(envelope('BOARD_POST', { entries: [{ to, text, refs }] })),
  };
}
