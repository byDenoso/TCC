import { createServer } from 'node:http';
import handler from './api/mcp.mjs';

createServer(async (req, res) => {
  if (req.url !== '/api/mcp') { res.writeHead(404); res.end(); return; }
  await handler(req, res);
}).listen(Number(process.env.PORT || 3000), '127.0.0.1', () => console.log('NEXO MCP: http://127.0.0.1:3000/api/mcp'));
