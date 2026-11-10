// Capturas e verificações do explorador de imagens (desktop, celular, escuro, sem JS).
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:4321';
const PATH = process.env.PHOTO_PATH ?? '/imagens/';
const OUT = process.env.SHOTS ?? 'tests/_px';
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM, args: ['--no-sandbox'] });
const errors = [], report = [];
const ok = (name, pass, extra = '') => report.push(`${pass ? 'ok  ' : 'FALHA'} ${name} ${extra}`);
async function open(opts, theme) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  if (theme) await page.addInitScript(t => localStorage.setItem('cosmos-theme', t), theme);
  await page.goto(BASE + PATH, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-px][data-px-ready]');
  await page.locator('#imagens').evaluate(e => e.scrollIntoView({ behavior: 'instant', block: 'start' }));
  await page.waitForTimeout(500);
  return page;
}
const inView = (page, key) => page.evaluate((key) => {
  const p = document.querySelector(`[data-px-panel="${key}"]`), v = p.querySelector('[data-px-view]').getBoundingClientRect();
  const a = p.querySelector('.px-spot.is-active').getBoundingClientRect(), c = p.querySelector('[data-px-canvas]').getBoundingClientRect();
  const cx = a.left + a.width / 2, cy = a.top + a.height / 2;
  const traces = [...p.querySelectorAll('[data-px-annotation]')].filter((path) => getComputedStyle(path).display !== 'none');
  const trace = traces[0];
  const bbox = trace?.getBoundingClientRect();
  return {
    spotInside: cx > v.left && cx < v.right && cy > v.top && cy < v.bottom,
    covers: c.left <= v.left + 1 && c.top <= v.top + 1 && c.right >= v.right - 1 && c.bottom >= v.bottom - 1,
    annotation: traces.length === 1 && trace.dataset.pxAnnotation === p.querySelector('.px-spot.is-active').dataset.pxSpot &&
      bbox.left < v.right && bbox.right > v.left && bbox.top < v.bottom && bbox.bottom > v.top,
    title: p.querySelector('[data-px-reading-title]').textContent,
    overflow: document.documentElement.scrollWidth - innerWidth
  };
}, key);

for (const [name, opts] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['mobile', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }]]) {
  const page = await open(opts);
  for (const key of ['carina-cosmic-cliffs', 'andromeda-wise', 'iss-sunrise']) {
    await page.locator(`[data-px-tab="${key}"]`).click(); await page.waitForTimeout(300);
    const spots = await page.locator(`[data-px-panel="${key}"] [data-px-spot]`).count();
    let s = await inView(page, key);
    ok(`${name}/${key}: abre com a primeira anotação sobre a imagem`, s.spotInside && s.covers && s.annotation && s.overflow <= 0, JSON.stringify(s));
    await page.locator(`[data-px-panel="${key}"]`).scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${OUT}/${name}-${key}-a.png` });
    for (let k = 1; k < spots; k++) {
      await page.locator(`[data-px-panel="${key}"] [data-px-step="1"]`).click(); await page.waitForTimeout(850);
      s = await inView(page, key);
      ok(`${name}/${key}: anotação ${k + 1} visível após avançar`, s.spotInside && s.covers && s.annotation, s.title);
    }
    await page.screenshot({ path: `${OUT}/${name}-${key}-b.png` });
    await page.locator(`[data-px-panel="${key}"] [data-px-zoom="reset"]`).click(); await page.waitForTimeout(800);
    const z = await page.locator(`[data-px-panel="${key}"] [data-px-view]`).getAttribute('data-px-zoomed');
    ok(`${name}/${key}: "Ver inteira" volta ao zoom inicial`, z === 'false');
  }
  // arraste com o mouse move a imagem
  if (name === 'desktop') {
    await page.locator('[data-px-tab="carina-cosmic-cliffs"]').click(); await page.waitForTimeout(300);
    const view = page.locator('[data-px-panel="carina-cosmic-cliffs"] [data-px-view]');
    const before = await page.locator('[data-px-panel="carina-cosmic-cliffs"] [data-px-canvas]').evaluate(e => e.style.transform);
    const box = await view.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.8); await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 - 180, box.y + box.height * 0.8, { steps: 6 }); await page.mouse.up();
    const after = await page.locator('[data-px-panel="carina-cosmic-cliffs"] [data-px-canvas]').evaluate(e => e.style.transform);
    ok('desktop: arrastar move a imagem', before !== after, `${before} -> ${after}`);
    await view.focus(); await page.keyboard.press('+'); await page.waitForTimeout(800);
    ok('desktop: tecla + aproxima', await view.getAttribute('data-px-zoomed') === 'true');
  }
  await page.context().close();
}
const dark = await open({ viewport: { width: 1440, height: 900 } }, 'dark');
await dark.locator('[data-px-tab="andromeda-wise"]').click(); await dark.waitForTimeout(400);
const reading = dark.locator('[data-px-panel="andromeda-wise"]');
await reading.locator('[data-px-view]').scrollIntoViewIfNeeded();
await dark.screenshot({ path: `${OUT}/dark-andromeda.png` });
const drawing = await reading.evaluate((panel) => {
  panel.querySelector('[data-px-step="1"]').click();
  const trace = panel.querySelector('[data-px-annotation="1"]');
  if (!trace) return false;
  const style = getComputedStyle(trace);
  return style.animationName !== 'none' && Number.parseFloat(style.strokeDashoffset) > 0;
});
ok('anima o traço ao avançar com a imagem na tela', drawing);
await dark.setViewportSize({ width: 1440, height: 320 });
await dark.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
await dark.waitForTimeout(100);
const offscreen = await reading.locator('[data-px-annotation="1"]').evaluate((node) => {
  const style = getComputedStyle(node);
  return style.animationName === 'none' && Number.parseFloat(style.strokeDashoffset) === 0;
}, null, { timeout: 1000 }).catch(() => false);
ok('fora da tela o traço está completo e sem animação', offscreen);
await dark.context().close();

const reduced = await open({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' }, 'dark');
const carina = reduced.locator('[data-px-panel="carina-cosmic-cliffs"]');
await carina.locator('[data-px-view]').scrollIntoViewIfNeeded();
await carina.locator('[data-px-step="1"]').dispatchEvent('click');
const reducedTrace = await carina.locator('[data-px-annotation="1"]').evaluate((node) => {
  const style = getComputedStyle(node);
  return style.animationName === 'none' && Number.parseFloat(style.strokeDashoffset) === 0;
}, null, { timeout: 1000 }).catch(() => false);
ok('movimento reduzido mostra o traço completo ao avançar', reducedTrace);
await reduced.screenshot({ path: `${OUT}/reduced-mobile-carina.png` });
await reduced.context().close();

const n = await browser.newContext({ viewport: { width: 1280, height: 800 }, javaScriptEnabled: false }); const np = await n.newPage();
await np.goto(BASE + PATH, { waitUntil: 'load' });
ok('sem JS: três imagens, 13 anotações completas, créditos e listas legíveis', await np.locator('.px-panel:visible').count() === 3 && await np.locator('.px-list:visible li').count() === 13 && await np.locator('[data-px-annotation]:visible').count() === 13 && await np.locator('.px-credit a:visible').count() === 3 && !(await np.locator('.px-tabs').isVisible()));
await np.locator('#imagens').scrollIntoViewIfNeeded(); await np.screenshot({ path: `${OUT}/nojs.png` });
await n.close();
await browser.close();
for (const line of report) console.log(line);
console.log('erros de console:', errors.length, errors.slice(0, 3));
if (report.some(l => l.startsWith('FALHA')) || errors.length) process.exitCode = 1;
