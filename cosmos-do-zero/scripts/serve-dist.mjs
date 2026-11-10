// Servidor estático mínimo (sem dependências) para a pasta dist/.
// Uso: node scripts/serve-dist.mjs [porta]
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, isAbsolute, join, relative, resolve, sep } from 'node:path';

const root = resolve(process.env.DIST ?? 'dist');
const port = Number(process.argv[2] ?? process.env.PORT ?? 4321);
const types = {
  '.avif': 'image/avif',
  '.css': 'text/css; charset=utf-8',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.mp4': 'video/mp4',
  '.vtt': 'text/vtt; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.wasm': 'application/wasm',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
  '.xml': 'application/xml; charset=utf-8'
};

function withinRoot(file) {
  const rel = relative(root, file);
  return rel === '' || (rel !== '..' && !rel.startsWith(`..${sep}`) && !isAbsolute(rel));
}

function send(res, method, status, body, contentType = 'text/plain; charset=utf-8', extraHeaders = {}) {
  const buffer = Buffer.isBuffer(body) ? body : Buffer.from(body);
  res.writeHead(status, {
    'content-length': buffer.byteLength,
    'content-type': contentType,
    'cache-control': 'no-cache',
    'x-content-type-options': 'nosniff',
    ...extraHeaders
  });
  res.end(method === 'HEAD' ? undefined : buffer);
}

function sendVideo(req, res, method, body) {
  const headers = { 'accept-ranges': 'bytes' };
  const range = method === 'GET' && !req.headers['if-range'] && /^bytes=(\d*)-(\d*)$/i.exec(req.headers.range ?? '');
  if (!range || (!range[1] && !range[2])) {
    send(res, method, 200, body, 'video/mp4', headers);
    return;
  }
  const length = body.byteLength;
  const start = range[1] ? Number(range[1]) : Math.max(0, length - Number(range[2]));
  const end = range[1] && range[2] ? Math.min(length - 1, Number(range[2])) : length - 1;
  if (start > end) {
    send(res, method, 416, '', 'video/mp4', { ...headers, 'content-range': `bytes */${length}` });
    return;
  }
  send(res, method, 206, body.subarray(start, end + 1), 'video/mp4', {
    ...headers, 'content-range': `bytes ${start}-${end}/${length}`
  });
}

async function readFileIfPresent(candidate) {
  try {
    const info = await stat(candidate);
    const file = info.isDirectory() ? join(candidate, 'index.html') : candidate;
    return { file, body: await readFile(file) };
  } catch (error) {
    if (error?.code === 'ENOENT' || error?.code === 'ENOTDIR') return undefined;
    throw error;
  }
}

async function handle(req, res) {
  const method = req.method ?? 'GET';
  if (method !== 'GET' && method !== 'HEAD') {
    send(res, method, 405, 'Method not allowed', 'text/plain; charset=utf-8', { allow: 'GET, HEAD' });
    return;
  }

  let pathname;
  try {
    pathname = decodeURIComponent(new URL(req.url ?? '/', 'http://localhost').pathname);
  } catch {
    send(res, method, 400, 'Malformed URL');
    return;
  }
  if (pathname.includes('\0')) {
    send(res, method, 400, 'Malformed URL');
    return;
  }

  // Remove URL-root separators before resolving. The relative-path check below
  // catches traversal after decoding, including sibling names sharing a prefix.
  const candidate = resolve(root, pathname.replace(/^[/\\]+/, ''));
  if (!withinRoot(candidate)) {
    send(res, method, 403, 'Forbidden');
    return;
  }

  const result = await readFileIfPresent(candidate);
  if (result) {
    const type = types[extname(result.file).toLowerCase()] ?? 'application/octet-stream';
    if (type === 'video/mp4') sendVideo(req, res, method, result.body);
    else send(res, method, 200, result.body, type);
    return;
  }

  const notFound = await readFileIfPresent(join(root, '404.html'));
  if (notFound) {
    send(res, method, 404, notFound.body, types[extname(notFound.file).toLowerCase()] ?? 'application/octet-stream');
    return;
  }
  send(res, method, 404, 'Not found');
}

const server = createServer((req, res) => {
  void handle(req, res).catch(() => {
    if (!res.headersSent) send(res, req.method ?? 'GET', 500, 'Internal server error');
    else res.destroy();
  });
});

server.listen(port, '127.0.0.1', () => {
  const address = server.address();
  const listeningPort = typeof address === 'object' && address ? address.port : port;
  console.log(`Cosmos do Zero em http://127.0.0.1:${listeningPort}/`);
});
