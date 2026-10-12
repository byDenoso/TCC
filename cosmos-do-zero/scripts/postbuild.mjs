// Pós-build: relatório de tamanho do bundle (sem alterar saída).
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
const walk = (d) => readdirSync(d).flatMap((f) => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
const files = walk('dist');
const sum = (re) => files.filter((f) => re.test(f)).reduce((a, f) => a + statSync(f).size, 0);
const kb = (n) => (n / 1024).toFixed(1) + ' kB';
console.log(`[postbuild] HTML ${kb(sum(/\.html$/))} · JS ${kb(sum(/\.js$/))} · CSS ${kb(sum(/\.css$/))} · imagens ${kb(sum(/\.(webp|png|jpg|svg)$/))} · fontes ${kb(sum(/\.woff2$/))}`);
