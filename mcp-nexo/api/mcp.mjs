import { timingSafeEqual } from 'node:crypto';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { z } from 'zod';
import { createTools } from '../core.mjs';

export function createHandler(options = {}) {
  const tools = createTools(options);
  return async function handler(req, res) {
    const secret = options.sharedSecret ?? process.env.MCP_SHARED_SECRET;
    if (!secret) { res.writeHead(503); res.end('MCP_SHARED_SECRET não configurado.'); return; }
    const supplied = Buffer.from(String(req.headers.authorization || ''));
    const expected = Buffer.from(`Bearer ${secret}`);
    if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
      res.writeHead(401, { 'WWW-Authenticate': 'Bearer' }); res.end('Não autorizado.'); return;
    }
    if (req.method !== 'POST') {
      res.writeHead(405, { Allow: 'POST' }); res.end(); return;
    }
    const server = new McpServer({ name: 'nexo', version: '0.1.0' });
    const result = value => ({ content: [{ type: 'text', text: JSON.stringify(value) }], structuredContent: value });
    const call = fn => async args => {
      try { return result(await fn(args)); }
      catch (error) { return { isError: true, content: [{ type: 'text', text: error.message }] }; }
    };
    const annotations = { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true };
    server.registerTool('status', { description: 'Lê a projeção pública do NEXO.', inputSchema: {},
      annotations: { ...annotations, readOnlyHint: true } }, call(() => tools.status()));
    server.registerTool('propose', { description: 'Grava envelope público no staging e confere a leitura de volta.',
      inputSchema: { envelope: z.record(z.unknown()) }, annotations }, call(({ envelope }) => tools.propose(envelope)));
    server.registerTool('bind_recipe', { description: 'Liga receita congelada a um teste existente.',
      inputSchema: { test_id: z.string().min(1), recipe: z.string().regex(/^[a-z][a-z0-9_]*$/), params: z.record(z.unknown()) },
      annotations }, call(({ test_id, recipe, params }) => tools.bind_recipe(test_id, recipe, params)));
    server.registerTool('board_post', { description: 'Publica um recado público de coordenação no mural.',
      inputSchema: { to: z.enum(['PITIA', 'LEARNER', 'EXECUTOR', 'REFUTADOR', 'GUARDIAO', 'CONVERSA', 'DENER', 'ALL', 'ENGINEER']),
        text: z.string().min(1), refs: z.array(z.string()).default([]) }, annotations },
      call(({ to, text, refs }) => tools.board_post(to, text, refs)));
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    res.on('close', () => { void transport.close(); void server.close(); });
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  };
}

export default createHandler();
