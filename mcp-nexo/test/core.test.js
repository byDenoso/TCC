import assert from 'node:assert/strict';
import { test } from 'node:test';
import { status, propose, boardPost, bindRecipe } from '../lib/core.js';

process.env.GITHUB_TOKEN = 'test-token-not-real';
process.env.NEXO_BRANCH = 'nexo/mcp-smoke-disposable';
const store = new Map();
const calls = [];
globalThis.fetch = async (url, options = {}) => {
  if (url.startsWith('https://bydenoso.github.io/')) {
    return Response.json({ tests: [], evolution: {} });
  }
  const path = decodeURIComponent(url.split('/contents/')[1].split('?')[0]);
  const branch = new URL(url).searchParams.get('ref');
  assert.equal(branch, 'nexo/mcp-smoke-disposable');
  calls.push({ method: options.method, branch, path });
  if (options.method === 'GET') {
    return store.has(path) ? Response.json(store.get(path)) : new Response('{}', { status: 404 });
  }
  assert.equal(options.method, 'PUT');
  const body = JSON.parse(options.body);
  assert.equal(body.branch, 'nexo/mcp-smoke-disposable');
  store.set(path, { encoding: 'base64', content: body.content, sha: 'mock-git-blob-sha' });
  return Response.json({ content: { sha: 'mock-git-blob-sha' } }, { status: 201 });
};

test('status returns public JSON without Git writes', async () => {
  assert.deepEqual(await status(), { tests: [], evolution: {} });
  assert.equal(store.size, 0);
});
test('BOARD_POST uses a disposable branch and verified readback', async () => {
  const result = await boardPost('ENGINEER', 'PUBLIC: teste de integração sem dados privados', ['https://github.com/byDenoso/TCC']);
  assert.match(result.stable_id, /^nexo-[a-f0-9]{32}$/);
  assert.match(result.sha256, /^[a-f0-9]{64}$/);
  assert.equal(result.branch, 'nexo/mcp-smoke-disposable');
  assert.equal(result.github_blob_sha, 'mock-git-blob-sha');
  const request = JSON.parse(Buffer.from(store.get(result.path).content, 'base64').toString());
  assert.equal(request.envelope.kind, 'BOARD_POST');
  assert.equal(request.stable_id, result.stable_id);
  assert.equal(calls.filter(x => x.method === 'PUT').length, 1);
});
test('exact replay is idempotent and does not overwrite', async () => {
  const envelope = { kind: 'RECIPE_BIND', source: 'CHATGPT', created_at: '2026-10-30T12:00:00Z',
    payload: { test_id: 'TEST-PUBLIC', recipe: 'seed_bounds', params: { n: 100 } } };
  const first = await propose(envelope), second = await propose(envelope);
  assert.deepEqual(first, second);
  assert.equal(calls.filter(x => x.method === 'PUT' && x.path === first.path).length, 1);
});
test('private board message is rejected before GitHub', async () => {
  assert.throws(() => boardPost('ENGINEER', 'assunto privado', []), /privado/i);
});
test('bindRecipe stages valid public envelope', async () => {
  const value = await bindRecipe('TEST-PUBLIC', 'seed_bounds', { n: 200 });
  assert.equal(value.branch, 'nexo/mcp-smoke-disposable');
});
