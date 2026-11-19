import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://127.0.0.1:4339';
const shots = process.env.SHOTS;
if (shots) await mkdir(shots, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM });
const ids = ['luz', 'expansao', 'hubble', 'frio', 'giro'];
const pixels = canvas => canvas.evaluate(c => c.toDataURL());
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({
      viewport: { width, height: width === 390 ? 844 : 900 }, reducedMotion: 'reduce',
      isMobile: width === 390, hasTouch: width === 390
    });
    await page.goto(base);
    for (const id of ids) {
      await page.locator(`[data-sci-tab="${id}"]`).click();
      const panel = page.locator(`[data-sci-panel="${id}"]`);
      const canvas = panel.locator('canvas');
      await canvas.waitFor({ state: 'visible' });
      await canvas.scrollIntoViewIfNeeded();
      const toggle = panel.getByRole('button', { name: 'Ver medidas' });
      const diagram = panel.locator('[data-sci-svg]');
      assert(await diagram.isHidden());
      assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
      const canvasBounds = await canvas.boundingBox();
      assert(canvasBounds.height >= canvasBounds.width * .55);
      await toggle.press('Enter');
      assert(await diagram.isVisible());
      const close = panel.getByRole('button', { name: 'Ocultar medidas' });
      assert.equal(await close.getAttribute('aria-expanded'), 'true');
      await close.press('Space');
      assert(await diagram.isHidden());
      if (id !== 'frio') assert.equal(await panel.locator('[data-sci-credit] a').innerText(),
        'M51 · NASA, ESA, S. Beckwith (STScI), and The Hubble Heritage Team (STScI/AURA)');
      const range = panel.locator('[data-sci-range]');
      await range.press('Home');
      const before = await pixels(canvas);
      await range.press('End');
      assert.notEqual(await pixels(canvas), before, id + ': control changes projected scene');
      const ends = { luz: '1.012 nm', expansao: '2,2', hubble: 'km/s', frio: '0,97 µm', giro: '100%' };
      assert((await panel.locator('[data-sci-sky-value]').innerText()).includes(ends[id]), id);
      assert.equal(await panel.locator('[data-sci-play-label]').innerText(), 'Avançar');
      const atEnd = await pixels(canvas);
      await page.waitForTimeout(160);
      assert.equal(await pixels(canvas), atEnd, id + ': reduced motion');
      if (id === 'expansao') {
        await panel.locator('[data-sci-action]').press('Enter');
        assert.notEqual(await pixels(canvas), atEnd, 'change observer');
      }
      if (id === 'luz') await range.press('Home');
      if (shots) await panel.locator('.sci-fig').screenshot({ path: join(shots, id + '-' + width + '.png') });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      console.log(width, id, 'OK');
    }
    await page.close();
  }
  const page = await browser.newPage();
  await page.goto(base);
  const panel = page.locator('[data-sci-panel="giro"]');
  await page.locator('[data-sci-tab="giro"]').click();
  const canvas = panel.locator('canvas');
  await canvas.scrollIntoViewIfNeeded();
  await panel.locator('[data-sci-reset]').click();
  await panel.locator('[data-sci-play]').click();
  await canvas.scrollIntoViewIfNeeded();
  const moving = await pixels(canvas);
  await page.waitForFunction(snapshot => document.querySelector('[data-sci-panel="giro"] canvas').toDataURL() !== snapshot, moving);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(180);
  const paused = await pixels(canvas);
  await page.waitForTimeout(230);
  assert.equal(await pixels(canvas), paused, 'offscreen canvas stays frozen');
  await canvas.scrollIntoViewIfNeeded();
  await page.waitForFunction(snapshot => document.querySelector('[data-sci-panel="giro"] canvas').toDataURL() !== snapshot, paused);
  await page.close();
  for (const failure of ['context', 'asset']) {
    const p = await browser.newPage({ reducedMotion: 'reduce' });
    if (failure === 'context') await p.addInitScript(() => { HTMLCanvasElement.prototype.getContext = () => null; });
    else await p.route(/m51-480\.webp|planck-cmb[^/]*\.webp/, route => route.abort());
    await p.goto(base);
    for (const id of ids) {
      await p.locator(`[data-sci-tab="${id}"]`).click();
      const fallback = p.locator(`[data-sci-panel="${id}"]`);
      await fallback.locator('[data-sci-range]').press('End');
      assert(await fallback.locator('[data-sci-svg]').isVisible());
      assert(await fallback.locator('canvas').isHidden());
      assert(await fallback.locator('[data-sci-measures]').isHidden());
      if (id === 'luz') assert.equal(await fallback.locator('[data-sci-value]').innerText(), '2,2×');
    }
    await p.close();
  }
  const staticPage = await browser.newPage({ javaScriptEnabled: false });
  await staticPage.goto(base);
  for (const id of ids) {
    const panel = staticPage.locator(`[data-sci-panel="${id}"]`);
    assert(await panel.locator('[data-sci-svg]').isVisible(), id + ': static diagram');
    assert(await panel.locator('[data-sci-svg] :is(path,polyline)').count() > 0);
  }
  await staticPage.close();
  console.log('Playback, offscreen pause/resume and both SVG fallbacks OK');
} finally { await browser.close(); }

