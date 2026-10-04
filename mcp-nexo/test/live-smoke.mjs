import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { createHandler } from '../api/mcp.mjs';

// Create this disposable branch first. Never send smoke proposals to the relay branch.
const branch = process.argv[2];
assert.match(branch || '', /^nexo\/mcp-smoke-[a-z0-9-]+$/);
assert.ok(process.env.GITHUB_TOKEN && process.env.MCP_SHARED_SECRET, 'Configure as duas variáveis no ambiente, sem gravá-las em arquivos.');
const server = createServer(createHandler({ branch }));
server.listen(0, '127.0.0.1');
await new Promise(resolve => server.once('listening', resolve));
const client = new Client({ name: 'nexo-live-smoke', version: '1.0.0' });
try {
  await client.connect(new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${server.address().port}/api/mcp`), {
    requestInit: { headers: { Authorization: `Bearer ${process.env.MCP_SHARED_SECRET}` } },
  }));
  const args = { to: 'ALL', text: 'Teste isolado do servidor MCP; esta branch não é consumida pelo relay.', refs: [] };
  const first = await client.callTool({ name: 'board_post', arguments: args });
  assert.ok(!first.isError, first.content[0].text);
  const retry = await client.callTool({ name: 'board_post', arguments: args });
  assert.equal(retry.structuredContent.sha, first.structuredContent.sha);
  assert.equal(retry.structuredContent.stable_id, first.structuredContent.stable_id);
  console.log(JSON.stringify(first.structuredContent));
} finally { await client.close(); server.close(); }
