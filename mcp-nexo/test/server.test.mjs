import assert from 'node:assert/strict';
import { randomUUID, createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { test } from 'node:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { createHandler } from '../api/mcp.mjs';
import { createTools, stableId, validateEnvelope, PROJECTION_URL } from '../core.mjs';

const branch = 'nexo/mcp-smoke-fixture';
const envelope = () => ({ kind: 'BOARD_POST', source: 'CHATGPT', created_at: '2026-09-29T00:00:00Z',
  payload: { entries: [{ to: 'ALL', text: 'Teste isolado do MCP; nenhuma proposta ao runtime.', refs: [] }] } });

function githubFixture() {
  let content;
  const requests = [];
  return { requests, async fetchImpl(url, options = {}) {
    requests.push({ url, options });
    if (url === PROJECTION_URL) return Response.json({ tests: [], evolution: null });
    if (options.method === 'PUT') {
      const body = JSON.parse(options.body);
      assert.equal(body.branch, branch);
      content = body.content;
      return Response.json({}, { status: 201 });
    }
    assert.equal(new URL(url).searchParams.get('ref'), branch);
    if (!content) return Response.json({}, { status: 404 });
    const bytes = Buffer.from(content, 'base64');
    const sha = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');
    return Response.json({ content, sha });
  } };
}

test('MCP HTTP: initialize, list, BOARD_POST, retry, RECIPE_BIND and public status', async t => {
  const fixture = githubFixture();
  const secret = randomUUID();
  const handler = createHandler({ ...fixture, branch, githubToken: randomUUID(), sharedSecret: secret });
  const server = createServer(handler);
  server.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  t.after(() => server.close());
  const url = new URL(`http://127.0.0.1:${server.address().port}/api/mcp`);
  assert.equal((await fetch(url, { method: 'POST' })).status, 401);
  const client = new Client({ name: 'nexo-local-test', version: '1.0.0' });
  await client.connect(new StreamableHTTPClientTransport(url, { requestInit: { headers: { Authorization: `Bearer ${secret}` } } }));
  t.after(() => client.close());
  assert.deepEqual((await client.listTools()).tools.map(x => x.name).sort(), ['bind_recipe', 'board_post', 'propose', 'status']);
  const args = { to: 'ALL', text: 'Teste isolado do MCP.', refs: [] };
  const first = await client.callTool({ name: 'board_post', arguments: args });
  assert.equal(first.isError, undefined);
  assert.equal(first.structuredContent.branch, branch);
  assert.match(first.structuredContent.stable_id, /^[a-z0-9-]+$/);
  assert.match(first.structuredContent.sha, /^[a-f0-9]{40}$/);
  const retry = await client.callTool({ name: 'board_post', arguments: args });
  assert.equal(retry.structuredContent.stable_id, first.structuredContent.stable_id);
  assert.equal(fixture.requests.filter(x => x.options.method === 'PUT').length, 1);
  const status = await client.callTool({ name: 'status', arguments: {} });
  assert.deepEqual(status.structuredContent, { tests: [], evolution: null });
  const bad = await client.callTool({ name: 'propose', arguments: { envelope: { kind: 'BOARD_POST' } } });
  assert.equal(bad.isError, true);
  // A fresh fixture represents the next immutable request path.
  const binding = await createTools({ ...githubFixture(), branch, githubToken: randomUUID() }).bind_recipe('TEST-1', 'seed_bounds', { n: 100 });
  assert.equal(binding.branch, branch);
});

test('stable ID ignores timestamps and key order; changed payload is new work', () => {
  const a = envelope();
  const b = { payload: a.payload, source: a.source, created_at: '2026-09-30T00:00:00Z', kind: a.kind };
  assert.equal(stableId(a), stableId(b));
  assert.notEqual(stableId(a), stableId({ ...a, payload: { entries: [{ to: 'ALL', text: 'Outro pedido.' }] } }));
});

test('private handoff and oversized batches are refused before writing', () => {
  assert.throws(() => validateEnvelope({ ...envelope(), kind: 'HANDOFF' }), /privado/);
  assert.throws(() => validateEnvelope({ ...envelope(), kind: 'BATCH', payload: { items: Array(11).fill(envelope()) } }), /10 itens/);
});

test('read-back mismatch and missing GitHub credentials fail explicitly', async () => {
  const tools = createTools({ branch, githubToken: randomUUID(), fetchImpl: async () => Response.json({
    content: Buffer.from(JSON.stringify({ stable_id: 'wrong', envelope: envelope() })).toString('base64'), sha: 'unused',
  }) });
  await assert.rejects(tools.propose(envelope()), /divergiu/);
  await assert.rejects(createTools({ githubToken: '' }).propose(envelope()), /GITHUB_TOKEN/);
});

test('concurrent create race succeeds only after matching read-back', async () => {
  const a = envelope();
  let reads = 0;
  const tools = createTools({ branch, githubToken: randomUUID(), fetchImpl: async (_url, options = {}) => {
    if (options.method === 'PUT') return Response.json({}, { status: 422 });
    if (++reads === 1) return Response.json({}, { status: 404 });
    return Response.json({ content: Buffer.from(JSON.stringify({ stable_id: stableId(a), envelope: a })).toString('base64'), sha: 'verified' });
  } });
  assert.equal((await tools.propose(a)).sha, 'verified');
});
