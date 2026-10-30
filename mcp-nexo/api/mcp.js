import { timingSafeEqual } from 'node:crypto';
import { Readable } from 'node:stream';
import { createMcpHandler } from 'mcp-handler';
import { z } from 'zod';
import { status, propose, bindRecipe, boardPost } from '../lib/core.js';

const text = value => ({ content: [{ type: 'text', text: JSON.stringify(value) }] });
const mcp = createMcpHandler(server => {
  server.registerTool('status', { description: 'Retorna a projeção pública atual do NEXO.', inputSchema: z.object({}) },
    async () => text(await status()));
  server.registerTool('propose', { description: 'Grava somente RECIPE_BIND ou BOARD_POST público, com readback Git.',
    inputSchema: z.object({ envelope: z.record(z.string(), z.unknown()) }) },
    async ({ envelope }) => text(await propose(envelope)));
  server.registerTool('bind_recipe', { description: 'Propõe um RECIPE_BIND público.',
    inputSchema: z.object({ test_id: z.string().min(1), recipe: z.string().min(1), params: z.record(z.string(), z.unknown()) }) },
    async ({ test_id, recipe, params }) => text(await bindRecipe(test_id, recipe, params)));
  server.registerTool('board_post', { description: 'Publica aviso autorizado; text deve começar com PUBLIC:. Privados vão ao Drive.',
    inputSchema: z.object({ to: z.string(), text: z.string(), refs: z.array(z.unknown()).default([]) }) },
    async ({ to, text: body, refs }) => text(await boardPost(to, body, refs)));
});

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  const secret = process.env.MCP_SHARED_SECRET || '';
  const authorization = req.headers.authorization || '';
  const supplied = authorization.startsWith('Bearer ') ? authorization.slice(7) : '';
  const valid = secret && supplied && Buffer.byteLength(secret) === Buffer.byteLength(supplied) &&
    timingSafeEqual(Buffer.from(secret), Buffer.from(supplied));
  if (!valid) return res.status(401).json({ error: 'unauthorized' });
  const origin = req.headers.origin;
  if (origin && !['https://chatgpt.com', 'https://chat.openai.com', 'https://' + req.headers.host].includes(origin)) {
    return res.status(403).json({ error: 'origin forbidden' });
  }
  const url = new URL(req.url, 'https://' + req.headers.host);
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const request = new Request(url, { method: req.method, headers: req.headers,
    body: ['GET', 'HEAD'].includes(req.method) ? undefined : Buffer.concat(chunks) });
  const response = await mcp(request);
  res.statusCode = response.status;
  for (const [key, value] of response.headers) res.setHeader(key, value);
  if (!response.body) return res.end();
  Readable.fromWeb(response.body).pipe(res);
}
