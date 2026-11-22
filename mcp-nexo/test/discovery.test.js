import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

test('MCP resource path has RFC 9728 path-specific discovery route', async () => {
  const config = JSON.parse(await readFile(new URL('../vercel.json', import.meta.url)));
  assert.ok(config.rewrites.some(route => route.source === '/.well-known/oauth-protected-resource/api/mcp' && route.destination === '/api/oauth-resource'));
});
