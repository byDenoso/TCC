import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const base = (process.env.BASE_URL || 'http://127.0.0.1:4378').replace(/\/$/, '');
const out = process.env.SHOTS;
if (out) await mkdir(out, { recursive: true });
const browser = await chromium.launch();
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: width === 390 ? 844 : 900 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/#viagem-galaxies');
    const stage = page.locator('[data-journey-canvas]');
    const choice = page.locator('[data-journey-select]');
    const urls = new Set();
    const check = async i => {
      await page.waitForFunction(index => {
        const current = document.querySelector('[data-journey-step="' + index + '"].is-active');
        if (!current) return false;
        const plate = document.querySelector('[data-journey-canvas]').dataset.plate;
        return [current.dataset.journeyLarge, current.querySelector('img').getAttribute('src')].includes(plate);
      }, i);
      const url = await stage.getAttribute('data-plate');
      assert.ok(url.endsWith('.webp'));
      const decoded = await page.locator('[data-journey-step="' + i + '"]').getAttribute('data-journey-large');
      const size = await page.evaluate(async src => {
        const image = new Image(); image.src = src; await image.decode();
        return [image.naturalWidth, image.naturalHeight];
      }, decoded);
      assert.ok(size[0] >= 1600, decoded + ' HD');
      return url;
    };
    await check(6);
    assert.equal(await choice.inputValue(), '6');
    if (out) await page.screenshot({path:out + '/galaxias-' + width + '.png'});
    const actual = await stage.getAttribute('data-plate');
    assert.match(actual, /jades-/);
    for (let i = 0; i < 12; i++) {
      await choice.selectOption(String(i));
      urls.add(await check(i));
    }
    assert.equal(urls.size, 12);
    assert.deepEqual(errors, []);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.close();
    console.log(width + ' px: 12 distinct HD plates, direct link and controls verified');
  }
  const fail = await browser.newPage({viewport:{width:1280,height:850},reducedMotion:'reduce'});
  await fail.route('**/jades-2211.webp', route=>route.abort());
  await fail.goto(base + '/#viagem-galaxies');
  await fail.waitForFunction(()=>document.querySelector('[data-journey-canvas]')?.dataset.plate?.endsWith('jades-880.webp'));
  await fail.close();
  const offline = await browser.newPage({reducedMotion:'reduce'});
  await offline.route('**/jades-*.webp', route => route.abort());
  await offline.goto(base + '/#viagem-galaxies');
  await offline.locator('[data-journey-missing]').waitFor({state:'visible'});
  assert.ok(await offline.locator('#viagem-galaxies h3').isVisible());
  await offline.locator('[data-journey-select]').selectOption('7');
  await offline.locator('[data-journey-missing]').waitFor({state:'hidden'});
  await offline.close();
  const staticPage = await browser.newPage({javaScriptEnabled:false});
  await staticPage.goto(base + '/#viagem-galaxies');
  const photo = staticPage.locator('#viagem-galaxies img');
  await photo.scrollIntoViewIfNeeded(); await photo.evaluate(image => image.decode());
  assert.ok(await photo.isVisible());
  assert.equal(await staticPage.locator('.journey-step img').count(), 12);
  console.log('HD unavailable: compact image works. JavaScript disabled: all 12 illustrated chapters are present.');
} finally { await browser.close(); }
