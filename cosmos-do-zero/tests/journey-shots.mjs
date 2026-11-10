// Capturas da viagem pelo tempo (home): dez marcos em desktop, amostras em celular, tema escuro e movimento reduzido.
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:4321';
const OUT = process.env.SHOTS ?? 'tests/_journey';
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const errors = [];
async function open(opts, theme) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  if (theme) await page.addInitScript(t => localStorage.setItem('cosmos-theme', t), theme);
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-journey][data-journey-ready]');
  return page;
}
async function go(page, i) {
  return page.evaluate(async (i) => {
    const st = [...document.querySelectorAll('[data-journey-step]')];
    const r = st[i].getBoundingClientRect();
    window.scrollTo(0, scrollY + r.top + r.height / 2 - innerHeight * 0.58);
    await new Promise(r => setTimeout(r, 700));
    return { active: st.findIndex(s => s.classList.contains('is-active')), when: document.querySelector('[data-journey-when]').textContent, overflow: document.documentElement.scrollWidth - innerWidth };
  }, i);
}
const report = [];
const d = await open({ viewport: { width: 1440, height: 900 } });
for (let i = 0; i < 10; i++) { const s = await go(d, i); report.push(['desktop', i, s.active, s.when, s.overflow]); await d.screenshot({ path: `${OUT}/desktop-${String(i + 1).padStart(2, '0')}.png` }); }
await d.evaluate(() => document.querySelector('#viagem').scrollIntoView()); await d.waitForTimeout(500); await d.screenshot({ path: `${OUT}/desktop-00-intro.png` });
await d.context().close();
const m = await open({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
for (const i of [0, 2, 4, 6, 9]) { const s = await go(m, i); report.push(['mobile', i, s.active, s.when, s.overflow]); await m.screenshot({ path: `${OUT}/mobile-${String(i + 1).padStart(2, '0')}.png` }); }
await m.context().close();
const k = await open({ viewport: { width: 1440, height: 900 } }, 'dark');
for (const i of [0, 3, 6]) { const s = await go(k, i); report.push(['dark', i, s.active, s.when, s.overflow]); await k.screenshot({ path: `${OUT}/dark-${String(i + 1).padStart(2, '0')}.png` }); }
await k.context().close();
const r = await open({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
await go(r, 4);
const a = await r.locator('[data-journey-canvas]').screenshot(); await r.waitForTimeout(900); const b = await r.locator('[data-journey-canvas]').screenshot();
report.push(['reduced: canvas parado', 4, Buffer.compare(a, b) === 0]);
await r.context().close();
const n = await browser.newContext({ viewport: { width: 1280, height: 800 }, javaScriptEnabled: false }); const np = await n.newPage();
await np.goto(BASE + '/', { waitUntil: 'load' });
report.push(['sem JS: passos legíveis', await np.locator('.journey-step h3').count(), await np.locator('.journey-stage').isVisible()]);
await np.locator('#viagem').scrollIntoViewIfNeeded(); await np.screenshot({ path: `${OUT}/nojs.png` });
await n.close();
await browser.close();
for (const line of report) console.log(line.join(' | '));
console.log('erros:', errors.length, errors.slice(0, 3));
