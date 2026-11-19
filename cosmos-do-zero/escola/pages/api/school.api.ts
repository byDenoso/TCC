import type { NextApiRequest, NextApiResponse } from 'next';
import { dispatch, isReadOp, ApiError } from '../../src/server/service.mjs';
export const config = { api: { bodyParser: { sizeLimit: '768kb' } } };
export default async function school(req: NextApiRequest, res: NextApiResponse) {
  const op = typeof req.query.op === 'string' ? req.query.op : '',
    host = req.headers.host ?? '',
    origin = req.headers.origin;
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  if (
    (op === 'published' || op === 'certificate-view') &&
    origin === 'https://cosmos.denerpereira.com.br'
  ) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
  }
  if ((isReadOp(op) ? 'GET' : 'POST') !== req.method) {
    res.status(405).json({ message: 'Método inválido.' });
    return;
  }
  if (req.method === 'POST') {
    let safeOrigin = false;
    try {
      const o = new URL(origin ?? '');
      safeOrigin =
        o.host === host &&
        (o.protocol === 'https:' ||
          (o.protocol === 'http:' && /^(localhost|127\.0\.0\.1)(:|$)/.test(host)));
    } catch {}
    if (!safeOrigin || req.headers['sec-fetch-site'] === 'cross-site') {
      res.status(403).json({ message: 'Origem inválida.' });
      return;
    }
    if (!req.headers['content-type']?.startsWith('application/json')) {
      res.status(415).json({ message: 'Use JSON.' });
      return;
    }
  }
  try {
    const result = await dispatch({
      op,
      body: req.body ?? {},
      token: req.cookies.cosmos_session ?? '',
      ip: String(req.headers['x-vercel-forwarded-for'] ?? req.socket.remoteAddress ?? '').split(',')[0],
      id: String(req.query.id ?? ''),
    });
    if ('session' in result) {
      const secure = !/^(localhost|127\.0\.0\.1)(:|$)/.test(host);
      res.setHeader(
        'Set-Cookie',
        'cosmos_session=' +
          result.session +
          '; Path=/; HttpOnly; SameSite=Lax; Max-Age=' +
          (result.session ? 604800 : 0) +
          (secure ? '; Secure' : '')
      );
    }
    res.status(200).json(result.data);
  } catch (error) {
    res
      .status(error instanceof ApiError ? error.status : 503)
      .json({
        message: error instanceof ApiError ? error.message : 'Serviço temporariamente indisponível.',
      });
  }
}
