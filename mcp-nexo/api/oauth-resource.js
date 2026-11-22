import { oauthResourceMetadata } from '../lib/oauth.js';

export default function handler(req, res) {
  res.setHeader('Cache-Control', 'public, max-age=60');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).end();
  try {
    return res.status(200).json(oauthResourceMetadata());
  } catch {
    return res.status(503).json({ error: 'oauth_not_configured' });
  }
}
