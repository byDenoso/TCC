// Pós-build: relatório de tamanho do bundle (sem alterar saída).
import { readdirSync, statSync, existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';
const walk = (d) => readdirSync(d).flatMap((f) => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
// Source PNGs and superseded texture iterations stay editable in the repository.
// Only browser-used WebP/materials are copied to the private deployment artifact.
for(const name of ['galaxies','galaxies-v3']){const dir=join('dist','models',name);if(existsSync(dir))rmSync(dir,{recursive:true});}
const originals=join('dist','models','galaxies-v4');if(existsSync(originals))for(const name of readdirSync(originals)){if(name.endsWith('.png'))rmSync(join(originals,name));}
const files = walk('dist');
const sum = (re) => files.filter((f) => re.test(f)).reduce((a, f) => a + statSync(f).size, 0);
const kb = (n) => (n / 1024).toFixed(1) + ' kB';
console.log(`[postbuild] HTML ${kb(sum(/\.html$/))} · JS ${kb(sum(/\.js$/))} · CSS ${kb(sum(/\.css$/))} · imagens ${kb(sum(/\.(webp|png|jpg|svg)$/))} · fontes ${kb(sum(/\.woff2$/))}`);
