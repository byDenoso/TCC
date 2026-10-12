// Valida o build público para GitHub Pages sem depender de navegador ou rede.
// Executar após npm run build, com SITE_URL/SITE_BASE/SITE_PUBLIC do workflow.
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, relative, resolve, sep } from 'node:path';

const dist = resolve('dist');
const origin = (process.env.SITE_URL ?? '').replace(/\/$/, '');
const base = (process.env.SITE_BASE ?? '').replace(/^\/+|\/+$/g, '');
const prefix = base ? `/${base}` : '';
assert.ok((origin === 'https://bydenoso.github.io' && prefix === '/TCC/cosmos-do-zero') ||
  (origin === 'https://cosmos.denerpereira.com.br' && prefix === ''), 'Destino/base não autorizado');
assert.equal(process.env.SITE_PUBLIC, 'true', 'Build público precisa ter SITE_PUBLIC=true');
assert.ok(existsSync(join(dist, 'index.html')), 'dist/index.html ausente');
const expectedRoot = `${origin}${prefix}/`;
const expectedMap = `${expectedRoot}sitemap.xml`;
let checks = 0;
const assertExists = (asset) => {
  const pathname = new URL(asset, origin).pathname;
  assert.ok(pathname === prefix || pathname.startsWith(`${prefix}/`), `Caminho escapou do base: ${asset}`);
  const rel = decodeURIComponent(pathname.slice(prefix.length)).replace(/^\//, '');
  const file = rel ? resolve(dist, rel) : resolve(dist, 'index.html');
  const contained = relative(dist, file);
  assert.ok(contained && !contained.startsWith(`..${sep}`) && contained !== '..', `Fora de dist: ${asset}`);
  const target = pathname.endsWith('/') && rel ? join(file, 'index.html') : file;
  assert.ok(existsSync(target), `Recurso interno inexistente: ${asset} (${target})`);
  checks++;
};
const html = [];
function walk(dir) {
  for (const name of readdirSync(dir)) {
    const f = join(dir, name);
    if (statSync(f).isDirectory()) walk(f);
    else if (f.endsWith('.html')) html.push(f);
  }
}
walk(dist);
assert.equal(html.length, 8, 'Esperadas home, seis capítulos e 404');

for (const file of html) {
  const text = readFileSync(file, 'utf8');
  const slug = relative(dist, file).split(sep).join('/');
  const pagePath = slug === 'index.html' ? '' : slug === '404.html' ? '404/' : slug.replace(/index\.html$/, '');
  const pageUrl = `${expectedRoot}${pagePath}`;
  assert.ok(text.includes(`<link rel="canonical" href="${pageUrl}"`), `Canônica incorreta: ${slug}`);
  assert.ok(text.includes(`property="og:url" content="${pageUrl}"`), `og:url incorreto: ${slug}`);
  assert.ok(text.includes(`property="og:image" content="${expectedRoot}social-card.png"`), `og:image incorreto: ${slug}`);
  assert.ok(text.includes(`href="${prefix}/favicon.svg"`), `favicon sem base: ${slug}`);
  assert.ok(!text.includes('http://localhost:4321'), `URL local em ${slug}`);
  if (slug === '404.html') assert.match(text, /name="robots" content="noindex, nofollow"/);
  else assert.doesNotMatch(text, /name="robots" content="noindex/i, `Página pública com noindex: ${slug}`);

  const attrs = /(?:^|\s)(href|src|srcset|data-render-src)\s*=\s*(["'])(.*?)\2/g;
  for (const match of text.matchAll(attrs)) {
    const [, attr,, value] = match;
    const candidates = attr === 'srcset' ? value.split(',').map((v) => v.trim().split(/\s+/)[0]) : [value];
    for (const raw of candidates) {
      const u = raw.replace(/&amp;/g, '&');
      if (!u || u.startsWith('#') || /^(mailto:|tel:|data:)/i.test(u)) continue;
      // A página 404 usa uma canônica sem arquivo index.html correspondente.
      if (slug === '404.html' && u === pageUrl) continue;
      assert.ok(!/^javascript:/i.test(u), `Link JavaScript proibido: ${slug}`);
      if (u.startsWith('/')) assertExists(u);
      else if (/^https?:\/\//i.test(u) && new URL(u).origin === origin) assertExists(u);
      // URLs externas de fontes não são validadas por este teste offline.
    }
  }
  checks++;
}

const robots = readFileSync(join(dist, 'robots.txt'), 'utf8');
assert.match(robots, new RegExp(`Allow: ${prefix}/`));
assert.ok(robots.includes(`Sitemap: ${expectedMap}`), 'robots.txt aponta para sitemap incorreto');
assert.ok(!robots.includes('Disallow: /'), 'Produção com robots Disallow');
const xml = readFileSync(join(dist, 'sitemap.xml'), 'utf8');
for (const slug of ['', 'galaxias-e-nebulosas/', 'origem-do-universo/', 'misterios-do-cosmos/', 'vida-das-estrelas/', 'sistema-solar/', 'terra-e-atmosfera/']) {
  const path = slug ? `capitulos/${slug}` : '';
  assert.ok(xml.includes(`<loc>${expectedRoot}${path}</loc>`), `Sitemap sem ${path || '/'}`);
}
assert.equal((xml.match(/<loc>/g) ?? []).length, 7, 'Sitemap deve conter sete URLs públicas');
checks += 9;

// A compilação de estilos pode incorporar fontes com url() relativo ou com o base.
function checkCss(directory) {
  for (const name of readdirSync(directory)) {
    const file = join(directory, name);
    if (statSync(file).isDirectory()) { checkCss(file); continue; }
    if (extname(file) !== '.css') continue;
    const css = readFileSync(file, 'utf8');
    for (const [, raw] of css.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
      if (/^(data:|https?:)/i.test(raw)) continue;
      if (raw.startsWith('/')) assertExists(raw);
      else {
        const candidate = resolve(join(file, '..'), raw.split(/[?#]/)[0]);
        assert.ok(existsSync(candidate), `Fonte/recurso CSS inexistente: ${file} -> ${raw}`);
        checks++;
      }
    }
  }
}
checkCss(dist);
console.log(`GitHub Pages: ${html.length} páginas, SEO/sitemap, ${checks} URLs e assets verificados no base ${prefix}/.`);
