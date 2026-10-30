import { createPublicKey, verify as verifySignature } from 'node:crypto';

const READ = 'nexo:read';
const WRITE = 'nexo:write';
let keys;
let keysUntil = 0;
let cachedUri;

function config() {
  const issuer = process.env.OAUTH_ISSUER;
  const audience = process.env.OAUTH_AUDIENCE;
  const jwksUri = process.env.OAUTH_JWKS_URI;
  const owner = process.env.OAUTH_OWNER_SUB;
  if (![issuer, audience, jwksUri, owner].every(Boolean)) throw new Error('OAuth não configurado');
  const provider = new URL(issuer), jwks = new URL(jwksUri), resource = new URL(audience);
  if ([provider, jwks, resource].some(url => url.protocol !== 'https:' || url.username || url.password)) {
    throw new Error('OAuth exige URLs HTTPS sem credenciais');
  }
  if (provider.search || provider.hash || jwks.hash || resource.search || resource.hash) {
    throw new Error('URLs OAuth inválidas');
  }
  return { issuer, audience, jwksUri, owner };
}

function decode(part) {
  return JSON.parse(Buffer.from(part, 'base64url').toString('utf8'));
}

async function publicKey(kid, uri) {
  if (!keys || cachedUri !== uri || Date.now() >= keysUntil) {
    const response = await fetch(uri, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error('JWKS HTTP ' + response.status);
    const body = await response.json();
    if (!Array.isArray(body.keys)) throw new Error('JWKS inválido');
    keys = body.keys;
    cachedUri = uri;
    keysUntil = Date.now() + 5 * 60_000;
  }
  const jwk = keys.find(key => key.kid === kid && key.kty === 'RSA' &&
    (key.alg === undefined || key.alg === 'RS256') &&
    (key.use === undefined || key.use === 'sig'));
  if (!jwk) return undefined;
  return createPublicKey({ key: jwk, format: 'jwk' });
}

export async function verifyAccessToken(token) {
  if (typeof token !== 'string' || token.length > 8192) return undefined;
  const parts = token.split('.');
  if (parts.length !== 3) return undefined;
  try {
    const { issuer, audience, jwksUri, owner } = config();
    const header = decode(parts[0]), claims = decode(parts[1]);
    if (header.alg !== 'RS256' || typeof header.kid !== 'string' || !header.kid ||
        typeof claims !== 'object' || claims === null) return undefined;
    const now = Math.floor(Date.now() / 1000);
    if (claims.iss !== issuer || claims.sub !== owner ||
        !(claims.aud === audience || (Array.isArray(claims.aud) && claims.aud.includes(audience))) ||
        !Number.isSafeInteger(claims.exp) || claims.exp <= now ||
        (claims.nbf !== undefined && (!Number.isSafeInteger(claims.nbf) || claims.nbf > now)) ||
        (claims.iat !== undefined && (!Number.isSafeInteger(claims.iat) || claims.iat > now + 60)) ||
        (claims.token_use !== undefined && claims.token_use !== 'access')) return undefined;
    const key = await publicKey(header.kid, jwksUri);
    if (!key || !verifySignature('RSA-SHA256', Buffer.from(parts[0] + '.' + parts[1]), key,
      Buffer.from(parts[2], 'base64url'))) return undefined;
    const scopes = typeof claims.scope === 'string' ? claims.scope.split(/\s+/).filter(Boolean) :
      (Array.isArray(claims.scp) && claims.scp.every(value => typeof value === 'string') ? claims.scp : []);
    if (!scopes.includes(READ)) return undefined;
    return { token, scopes, clientId: String(claims.azp || claims.client_id || claims.sub),
      extra: { subject: claims.sub } };
  } catch {
    return undefined;
  }
}

export function oauthResourceMetadata() {
  const { issuer, audience } = config();
  return { resource: audience, authorization_servers: [issuer], scopes_supported: [READ, WRITE] };
}

export function isWriteRequest(body) {
  if (Array.isArray(body)) return body.some(isWriteRequest);
  if (!body || typeof body !== 'object') return true;
  if (body.method !== 'tools/call') return false;
  return body.params?.name !== 'status';
}

export const SCOPES = Object.freeze({ READ, WRITE });
