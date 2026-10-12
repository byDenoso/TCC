// Capturas dos 5 degraus da cena "Afastar a câmera" (galaxias-e-nebulosas-via-lactea).
import { chromium } from 'playwright';
import { existsSync, mkdirSync } from 'node:fs';
const BASE = process.env.BASE ?? 'http://localhost:4321';
const OUT = 'docs/screenshots/zoom'; mkdirSync(OUT, { recursive: true });
const exe = [process.env.CHROMIUM].find((p) => p && existsSync(p));
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
let fail = 0;
for (const vp of [{ n: 'desktop', width: 1280, height: 800, dpr: 1 }, { n: 'mobile', width: 390, height: 844, dpr: 2, m: true }]) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.dpr, isMobile: !!vp.m, hasTouch: !!vp.m });
  const page = await ctx.newPage(); const errs = [];
  page.on('pageerror', (e) => errs.push(String(e))); page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await page.goto(`${BASE}/capitulos/galaxias-e-nebulosas/#galaxias-e-nebulosas-via-lactea`, { waitUntil: 'load' });
  const root = '[data-mx="galaxias-e-nebulosas-via-lactea"]';
  await page.evaluate((r) => { document.documentElement.style.scrollBehavior = 'auto'; const e = document.querySelector(r); scrollTo(0, e.getBoundingClientRect().top + scrollY - 60); }, root);
  await page.waitForSelector(`${root} [data-mx-svg] image`, { timeout: 10000 });
  const opts = await page.$$(`${root} [data-mx-opt]`);
  for (let i = 0; i < opts.length; i++) {
    await opts[i].click(); await page.waitForTimeout(2200);
    const svg = await page.$(`${root} [data-mx-svg]`);
    await svg.screenshot({ path: `${OUT}/${vp.n}-${i + 1}.png` });
  }
  const loaded = await page.evaluate((r) => Promise.all([...document.querySelectorAll(`${r} image`)].map((im) => new Promise((res) => { const x = new Image(); x.onload = () => res(x.naturalWidth); x.onerror = () => res(0); x.src = im.getAttribute('href'); }))), root);
  const ok = loaded.every((w) => w > 0) && errs.length === 0;
  if (!ok) fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'} ${vp.n}: ${opts.length} degraus, imagens ${loaded.join(',')}, erros ${errs.length} ${errs.join(' | ')}`);
  await ctx.close();
}
await browser.close(); process.exit(fail ? 1 : 0);
