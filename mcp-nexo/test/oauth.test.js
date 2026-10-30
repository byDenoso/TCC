import assert from 'node:assert/strict';
import { createSign, generateKeyPairSync } from 'node:crypto';
import { test } from 'node:test';
import { verifyAccessToken, isWriteRequest, oauthResourceMetadata } from '../lib/oauth.js';

const pair = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = pair.publicKey.export({ format: 'jwk' });
Object.assign(jwk, { kid: 'test-key', use: 'sig', alg: 'RS256' });
globalThis.fetch = async url => {
  assert.equal(url, 'https://auth.example.test/jwks');
  return Response.json({ keys: [jwk] });
};
Object.assign(process.env, {
  OAUTH_ISSUER: 'https://auth.example.test',
  OAUTH_AUDIENCE: 'https://nexo.example.test/api/mcp',
  OAUTH_JWKS_URI: 'https://auth.example.test/jwks',
  OAUTH_OWNER_SUB: 'owner-sub',
});
const now = Math.floor(Date.now() / 1000);
function token(patch = {}, signedBy = pair.privateKey) {
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'test-key' })).toString('base64url');
  const body = Buffer.from(JSON.stringify({
    iss: process.env.OAUTH_ISSUER, aud: process.env.OAUTH_AUDIENCE,
    sub: 'owner-sub', iat: now - 100, exp: now + 3600, scope: 'nexo:read nexo:write',
    ...patch,
  })).toString('base64url');
  const input = header + '.' + body;
  const signature = createSign('RSA-SHA256').update(input).end().sign(signedBy).toString('base64url');
  return input + '.' + signature;
}

test('accept owner access token signed by configured JWKS with audience and scopes', async () => {
  const info = await verifyAccessToken(token());
  assert.equal(info.extra.subject, 'owner-sub');
  assert.deepEqual(info.scopes, ['nexo:read', 'nexo:write']);
});
test('reject missing token, forged signature, wrong issuer, owner, audience, expiry and nbf', async () => {
  assert.equal(await verifyAccessToken(''), undefined);
  const forged = generateKeyPairSync('rsa', { modulusLength: 2048 });
  for (const value of [token({}, forged.privateKey), token({ iss: 'https://evil.test' }),
    token({ sub: 'other' }), token({ aud: 'https://elsewhere.test' }),
    token({ exp: now - 1 }), token({ nbf: now + 100 })]) {
    assert.equal(await verifyAccessToken(value), undefined);
  }
});
test('reject token without read scope and ID token', async () => {
  assert.equal(await verifyAccessToken(token({ scope: 'nexo:write' })), undefined);
  assert.equal(await verifyAccessToken(token({ token_use: 'id' })), undefined);
});
test('read-only token lacks write scope, HTTP middleware must deny writes', async () => {
  const info = await verifyAccessToken(token({ scope: 'nexo:read' }));
  assert.deepEqual(info.scopes, ['nexo:read']);
  assert.equal(info.scopes.includes('nexo:write'), false);
});
test('metadata advertises exact resource and issuer', () => {
  assert.deepEqual(oauthResourceMetadata(), {
    resource: 'https://nexo.example.test/api/mcp', authorization_servers: ['https://auth.example.test'],
    scopes_supported: ['nexo:read', 'nexo:write'],
  });
});
test('write request classification denies calls and batched calls except status', () => {
  assert.equal(isWriteRequest({ method: 'initialize' }), false);
  assert.equal(isWriteRequest({ method: 'tools/list' }), false);
  assert.equal(isWriteRequest({ method: 'tools/call', params: { name: 'status' } }), false);
  assert.equal(isWriteRequest({ method: 'tools/call', params: { name: 'propose' } }), true);
  assert.equal(isWriteRequest([{ method: 'tools/call', params: { name: 'status' } },
    { method: 'tools/call', params: { name: 'board_post' } }]), true);
  assert.equal(isWriteRequest({ method: 'tools/call' }), true);
});
