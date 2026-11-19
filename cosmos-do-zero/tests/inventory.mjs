import assert from 'node:assert/strict';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { MICRO } from '../src/data/micro.ts';

const project = new URL('../', import.meta.url);
const read = path => readFile(new URL(path, project), 'utf8');
const chapters = JSON.parse(await read('src/data/chapters.json'));
const references = JSON.parse(await read('src/data/micro-frames.json'));
const sections = [];
const ids = new Set();

for (const chapter of chapters) {
  const route = `/capitulos/${chapter.id}/`;
  const html = await read(`dist${route}index.html`);
  for (const { id, title } of chapter.sections) {
    assert.ok(!ids.has(id), `ID repetido: ${id}`);
    ids.add(id);
    assert.ok(html.includes(`id="${id}"`), `Âncora ausente: ${route}#${id}`);
    const isCmb = html.includes(`data-cmbj data-section="${id}"`);
    assert.ok(isCmb || html.includes(`data-mx="${id}"`), `Instrumento ausente: ${id}`);
    const images = references[id]?.paths ?? [];
    for (const image of images) {
      assert.ok(image.startsWith('/') && !image.startsWith('//'), `Imagem não local: ${image}`);
      assert.ok((await stat(new URL('dist' + image, project))).isFile(), `Imagem ausente: ${image}`);
    }
    sections.push({ route: route + '#' + id, id, title, render: isCmb ? 'Jornada CMB' : 'Diagrama SVG',
      control: isCmb ? 'Etapas da recombinação' : MICRO[id].control.label, images });
  }
}
for (const id of Object.keys(references)) assert.ok(ids.has(id), `Referência sem seção: ${id}`);
const counts = { chapters: chapters.length, sections: sections.length,
  withImages: sections.filter(section => section.images.length > 0).length };
const out = new URL('test-results/inventory/', project);
await mkdir(out, { recursive: true });
await writeFile(new URL('inventario.json', out), JSON.stringify({ counts, sections }, null, 2) + '\n');
const rows = sections.map(s => `| ${s.route} | ${s.render} | ${s.control} | ${s.images.length} |`);
await writeFile(new URL('inventario.md', out),
  ['# Instrumentos das aulas', '', '| Seção | Instrumento | Controle | Imagens locais |', '| --- | --- | --- | ---: |', ...rows, ''].join('\n'));
console.log(counts);
