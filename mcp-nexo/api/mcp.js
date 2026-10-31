import { configuredCatalog } from '../lib/drive-catalog.js';
import { CATEGORIES } from '../lib/catalog.js';
import { Readable } from 'node:stream';
import { createMcpHandler, withMcpAuth } from 'mcp-handler';
import { z } from 'zod';
import { status, propose, bindRecipe, boardPost } from '../lib/core.js';
import { verifyAccessToken, isWriteRequest, SCOPES } from '../lib/oauth.js';

const text = value => ({ content: [{ type: 'text', text: JSON.stringify(value) }] });
const requireWrite = ctx => {
  if (!ctx.http?.authInfo?.scopes?.includes(SCOPES.WRITE)) throw new Error('Permissão de escrita necessária');
};
const mcp = createMcpHandler(server => {
  server.registerTool('catalog_status', { description: 'Read configured private catalog sources and report freshness, hashes and blocked connections. Does not execute science.',
    inputSchema: z.object({}), annotations: { readOnlyHint: true, destructiveHint: false } },
    async () => text(await configuredCatalog().status()));
  server.registerTool('catalog_search', { description: 'Search typed capabilities, solvers, adapters, datasets, recipes, skills, contracts and Tower/Writer references. Paginated metadata only; recorded readiness is not execution authorization.',
    inputSchema: z.object({ q: z.string().max(200).default(''), category: z.enum(CATEGORIES).optional(), limit: z.number().int().min(1).max(100).default(25), cursor: z.string().max(1024).optional() }),
    annotations: { readOnlyHint: true, destructiveHint: false } },
    async args => text(await configuredCatalog().search(args)));
  server.registerTool('catalog_get', { description: 'Read one discovered catalog record with provenance and readiness boundaries. Does not fetch arbitrary files, run solvers or write Tower.',
    inputSchema: z.object({ id: z.string().min(1).max(1024) }), annotations: { readOnlyHint: true, destructiveHint: false } },
    async args => text(await configuredCatalog().get(args)));

  server.registerTool('status', { description: 'Retorna a projeção pública atual do NEXO.',
    inputSchema: z.object({}), annotations: { readOnlyHint: true } },
    async () => text(await status()));
  server.registerTool('propose', { description: 'Grava somente RECIPE_BIND ou BOARD_POST público, com readback Git.',
    inputSchema: z.object({ envelope: z.record(z.string(), z.unknown()) }) },
    async ({ envelope }, ctx) => { requireWrite(ctx); return text(await propose(envelope)); });
  server.registerTool('bind_recipe', { description: 'Propõe um RECIPE_BIND público.',
    inputSchema: z.object({ test_id: z.string().min(1), recipe: z.string().min(1), params: z.record(z.string(), z.unknown()) }) },
    async ({ test_id, recipe, params }, ctx) => { requireWrite(ctx); return text(await bindRecipe(test_id, recipe, params)); });
  server.registerTool('board_post', { description: 'Publica aviso autorizado; text deve começar com PUBLIC:. Privados vão ao Drive.',
    inputSchema: z.object({ to: z.string(), text: z.string(), refs: z.array(z.unknown()).default([]) }) },
    async ({ to, text: body, refs }, ctx) => { requireWrite(ctx); return text(await boardPost(to, body, refs)); });
});
const verify = async (_request, token) => verifyAccessToken(token);
const options = { required: true, resourceMetadataPath: '/.well-known/oauth-protected-resource' };
const readHandler = withMcpAuth(mcp, verify, { ...options, requiredScopes: [SCOPES.READ] });
const writeHandler = withMcpAuth(mcp, verify, { ...options, requiredScopes: [SCOPES.READ, SCOPES.WRITE] });

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  let content;
  try {
    const chunks = [];
    let size = 0;
    for await (const chunk of req) {
      size += chunk.length;
      if (size > 1024 * 1024) return res.status(413).json({ error: 'request_too_large' });
      chunks.push(chunk);
    }
    content = Buffer.concat(chunks);
  } catch {
    return res.status(400).json({ error: 'invalid_body' });
  }
  let write = false;
  if (content.length) {
    try { write = isWriteRequest(JSON.parse(content.toString('utf8'))); }
    catch { return res.status(400).json({ error: 'invalid_json' }); }
  }
  try {
    const request = new Request(new URL(req.url, process.env.OAUTH_AUDIENCE || 'https://localhost'), {
      method: req.method, headers: req.headers,
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : content,
    });
    const response = await (write ? writeHandler : readHandler)(request);
    res.statusCode = response.status;
    for (const [key, value] of response.headers) res.setHeader(key, value);
    if (!response.body) return res.end();
    Readable.fromWeb(response.body).pipe(res);
  } catch {
    if (!res.headersSent) return res.status(503).json({ error: 'mcp_unavailable' });
    res.destroy();
  }
}
