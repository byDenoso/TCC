import assert from 'node:assert/strict';
import { createSign, generateKeyPairSync } from 'node:crypto';
import { createServer } from 'node:http';
import { after, before, test } from 'node:test';
import handler from '../api/mcp.js';

const keys = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = { ...keys.publicKey.export({ format: 'jwk' }), kid: 'local', alg: 'RS256', use: 'sig' };
const originalFetch = globalThis.fetch;
let base;
let server;
const writes = new Map();
Object.assign(process.env, {
  OAUTH_ISSUER: 'https://issuer.invalid/', OAUTH_AUDIENCE: 'https://nexo.example.test/api/mcp',
  OAUTH_JWKS_URI: 'https://issuer.invalid/jwks', OAUTH_OWNER_SUB: 'only-owner',
  GITHUB_TOKEN: 'mock-only', NEXO_BRANCH: 'nexo/mcp-smoke-disposable',
});

function token(scope) {
  const now = Math.floor(Date.now() / 1000);
  const part = x => Buffer.from(JSON.stringify(x)).toString('base64url');
  const signed = part({ alg: 'RS256', kid: 'local' }) + '.' + part({
    iss: process.env.OAUTH_ISSUER, aud: process.env.OAUTH_AUDIENCE, sub: 'only-owner',
    iat: now, exp: now + 600, scope,
  });
  return signed + '.' + createSign('RSA-SHA256').update(signed).end().sign(keys.privateKey).toString('base64url');
}

before(async () => {
  globalThis.fetch = async (input, options = {}) => {
    const url = String(input);
    if (url === process.env.OAUTH_JWKS_URI) return Response.json({ keys: [jwk] });
    if (url.includes('bydenoso.github.io')) return Response.json({ tests: [], evolution: {} });
    if (url.includes('/contents/nexo_persist/requests/')) {
      const path = decodeURIComponent(url.split('/contents/')[1].split('?')[0]);
      if (options.method === 'GET') return writes.has(path) ? Response.json(writes.get(path)) : new Response('', { status: 404 });
      if (options.method === 'PUT') {
        const body = JSON.parse(options.body);
        assert.equal(body.branch, 'nexo/mcp-smoke-disposable');
        writes.set(path, { encoding: 'base64', content: body.content, sha: 'local-blob' });
        return Response.json({});
      }
    }
    throw new Error('Chamada externa inesperada: ' + url);
  };
  server = createServer((req, res) => {
    res.status = code => { res.statusCode = code; return res; };
    res.json = data => { res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(data)); return res; };
    Promise.resolve(handler(req, res)).catch(() => { if (!res.headersSent) res.writeHead(500); res.end(); });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = 'http://127.0.0.1:' + server.address().port + '/api/mcp';
});
after(async () => {
  globalThis.fetch = originalFetch;
  if (server) await new Promise(resolve => server.close(resolve));
});

async function rpc(body, auth) {
  return originalFetch(base, { method: 'POST', headers: {
    accept: 'application/json, text/event-stream', 'content-type': 'application/json',
    'mcp-protocol-version': '2025-03-26', ...(auth ? { authorization: 'Bearer ' + auth } : {}),
  }, body: JSON.stringify(body) });
}
const message = (method, params = {}) => ({ jsonrpc: '2.0', id: 1, method, params });

test('HTTP missing bearer is 401 with OAuth discovery challenge', async () => {
  const r = await rpc(message('initialize'));
  assert.equal(r.status, 401);
  assert.match(r.headers.get('www-authenticate') || '', /oauth-protected-resource/);
});
test('HTTP authorized initialize and tools/list', async () => {
  const access = token('nexo:read');
  const init = await rpc(message('initialize', {
    protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'local', version: '1' },
  }), access);
  assert.equal(init.status, 200, await init.text());
  const listed = await rpc(message('tools/list'), access);
  const body = await listed.text();
  assert.equal(listed.status, 200, body);
  assert.match(body, /status/);
});
test('HTTP read-only authorization cannot call write tool', async () => {
  const r = await rpc(message('tools/call', { name: 'board_post', arguments: {
    to: 'ENGINEER', text: 'PUBLIC: teste', refs: [],
  } }), token('nexo:read'));
  assert.equal(r.status, 403);
  assert.equal(writes.size, 0);
});
test('HTTP status tool returns public projection for authorized reader', async () => {
  const r = await rpc(message('tools/call', { name: 'status', arguments: {} }), token('nexo:read'));
  const body = await r.text();
  assert.equal(r.status, 200, body);
  assert.match(body, /tests/);
});
test('HTTP authenticated write stages BOARD_POST only on disposable branch', async () => {
  const r = await rpc(message('tools/call', { name: 'board_post', arguments: {
    to: 'ENGINEER', text: 'PUBLIC: teste isolado', refs: [],
  } }), token('nexo:read nexo:write'));
  assert.equal(r.status, 200, await r.text());
  assert.equal(writes.size, 1);
  const payload = JSON.parse(Buffer.from([...writes.values()][0].content, 'base64').toString());
  assert.equal(payload.envelope.kind, 'BOARD_POST');
});
