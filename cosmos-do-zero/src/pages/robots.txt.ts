import type { APIRoute } from 'astro';
import { u } from '../lib/url';

export const GET: APIRoute = ({ site }) => {
  const publicSite = import.meta.env.PUBLIC_SITE_INDEXING === 'true';
  const body = publicSite
    ? `User-agent: *\nAllow: ${u('/')}\nSitemap: ${new URL(u('/sitemap.xml'), site).href}\n`
    : 'User-agent: *\nDisallow: /\n';
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
