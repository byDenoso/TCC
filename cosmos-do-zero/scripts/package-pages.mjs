// Empacotamento offline; nunca altera DNS, Pages ou GitHub.
import assert from 'node:assert/strict';
import { cpSync, mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
const site = process.env.SITE_URL;
const base = process.env.SITE_BASE;
const custom = site === 'https://cosmos.denerpereira.com.br' && base === '/';
const github = site === 'https://bydenoso.github.io' && base === '/TCC/cosmos-do-zero';
assert.ok(custom || github, 'Destino/base inválido; empacotamento recusado');
rmSync('pages-root', { recursive: true, force: true });
mkdirSync('pages-root', { recursive: true });
if (custom) {
  cpSync('dist', 'pages-root', { recursive: true });
  writeFileSync('pages-root/CNAME', 'cosmos.denerpereira.com.br\n');
  // Preserve URLs shared while the site lived under /TCC/cosmos-do-zero/.
  const paths = ['', ...readdirSync('dist/capitulos', { withFileTypes: true }).filter(x => x.isDirectory()).map(x => `capitulos/${x.name}`)];
  for (const path of paths) {
    const target = `/${path}${path ? '/' : ''}`;
    const folder = `pages-root/cosmos-do-zero/${path}`;
    mkdirSync(folder, { recursive: true });
    writeFileSync(`${folder}/index.html`, `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Cosmos do Zero</title><meta http-equiv="refresh" content="0; url=${target}"><link rel="canonical" href="${site}${target}"></head><body><a href="${target}">Continuar no Cosmos do Zero</a></body></html>`);
  }
} else {
  cpSync('dist', 'pages-root/cosmos-do-zero', { recursive: true });
  writeFileSync('pages-root/index.html', `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Cosmos do Zero</title><meta http-equiv="refresh" content="0; url=${base}/"><link rel="canonical" href="${site}${base}/"></head><body><a href="${base}/">Acessar Cosmos do Zero</a></body></html>`);
}
writeFileSync('pages-root/.nojekyll', '');
console.log(`Artefato pronto: ${site}${base === '/' ? '/' : base + '/'}`);
