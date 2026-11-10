import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const readPage = (path) => readFile(new URL(`../dist/${path}index.html`, import.meta.url), 'utf8');
const home = await readPage('');
const labels = [...home.matchAll(/data-home-section="(\d+)"/g)].map((match) => match[1]);
assert.deepEqual(labels, ['01', '02', '03', '04'], 'a home tem quatro seções com numeração única');
assert.equal((home.match(/<section(?=[\s>])/g) ?? []).length, 4, 'só quatro seções no HTML inicial');
assert.match(home, /id="movimento"/);
assert.equal((home.match(/data-school-course=/g) ?? []).length, 6, 'as seis aulas permanecem no HTML');
assert.match(home, /id="viagem"/);
assert.equal((home.match(/class="school-cover-source"><a href="https:\/\//g) ?? []).length, 6, 'as seis capas indicam a fonte junto à imagem');
for (const [page, id] of Object.entries({ luz: 'prologo', escalas: 'escala-cosmica', imagens: 'imagens', observatorio: 'observatorio', desafio: 'desafio', explorar: 'interativos', ceu: 'ceu' })) {
  assert.doesNotMatch(home, new RegExp(`id="${id}"`));
  assert.match(home, new RegExp(`href="[^"#]*\/${page}\/`), `link visível no HTML para /${page}/`);
  assert.match(await readPage(`${page}/`), new RegExp(`id="${id}"`), `conteúdo de ${page} no HTML`);
}
console.log('Saguão SSR: quatro seções, seis aulas e sete destinos preservados.');
