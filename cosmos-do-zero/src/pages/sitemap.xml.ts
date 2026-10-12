import type { APIRoute } from 'astro';
import { CHAPTER_IDS } from '../types';
import { u } from '../lib/url';

export const GET: APIRoute = ({ site }) => {
  const routes = ['/', '/laboratorio/', '/glossario/', '/fontes/', ...CHAPTER_IDS.map((id) => `/capitulos/${id}/`)];
  const urls = routes.map((path) => `<url><loc>${new URL(u(path), site).href}</loc></url>`).join('');
  return new Response(`<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' }
  });
};
