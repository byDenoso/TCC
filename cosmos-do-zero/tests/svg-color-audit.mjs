// Procura desenhos SVG pintados com o preto padrão do navegador (classe sem CSS, cor faltando).
// Uso: BASE=http://localhost:4321 node tests/svg-color-audit.mjs
import { chromium } from 'playwright';
const BASE = process.env.BASE ?? 'http://localhost:4321';
const PAGES = ['/', '/capitulos/origem-do-universo/', '/capitulos/galaxias-e-nebulosas/', '/capitulos/misterios-do-cosmos/', '/capitulos/vida-das-estrelas/', '/capitulos/sistema-solar/', '/capitulos/terra-e-atmosfera/', '/laboratorio/', '/glossario/', '/fontes/'];
const browser = await chromium.launch();
let total = 0;
for (const scheme of ['dark', 'light']) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
  for (const path of PAGES) {
    const p = await ctx.newPage();
    await p.goto(BASE + path, { waitUntil: 'load' });
    // passa por toda a página para carregar cenas preguiçosas e revela passos ocultos
    await p.evaluate(async () => { document.documentElement.style.scrollBehavior = 'auto'; for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); } });
    await p.waitForTimeout(800);
    const hits = await p.evaluate(() => {
      const out = [];
      for (const el of document.querySelectorAll('svg circle, svg ellipse, svg path, svg rect, svg polygon, svg polyline, svg text, svg line')) {
        if (el.closest('defs, clipPath, mask, pattern, symbol, marker')) continue;
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
        const r = el.getBoundingClientRect(); if (!r.width && !r.height) continue;
        const own = el.getAttribute('fill') ?? el.style.fill;
        const black = (v) => v === 'rgb(0, 0, 0)' || v === '#000' || v === 'black';
        const fillBad = cs.fill === 'rgb(0, 0, 0)' && !(own && black(own)) && +cs.fillOpacity > 0;
        if (fillBad && el.tagName !== 'line') {
          const host = el.closest('[data-mx],[data-scene],[data-station],section[id],figure')?.getAttribute('data-mx') ?? el.closest('[data-scene]')?.getAttribute('data-scene') ?? el.closest('[data-station]')?.getAttribute('data-station') ?? el.closest('section[id]')?.id ?? '?';
          out.push(`${host} <${el.tagName} class="${el.getAttribute('class') ?? ''}">`);
        }
      }
      const agg = {}; for (const h of out) agg[h] = (agg[h] ?? 0) + 1;
      return agg;
    });
    const keys = Object.entries(hits);
    total += keys.length;
    if (keys.length) console.log(`${scheme} ${path}\n` + keys.map(([k, n]) => `   ${n}× ${k}`).join('\n'));
    await p.close();
  }
  await ctx.close();
}
await browser.close();
console.log(`\n${total} grupos com preto padrão`);
process.exit(total ? 1 : 0);
