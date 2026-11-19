import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium, devices } from 'playwright';
import sharp from 'sharp';

const url = process.env.SCALE_URL ?? `${(process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '')}/escalas/`;
const captures = process.env.SCALE_CAPTURES;
if (captures) await mkdir(captures, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined
});
const visual = '[data-scale-visual-stage]';
const canvas = '[data-scale-canvas] canvas';
const stationNames = ['Próton', 'Átomo de hidrogênio', 'Hemácia', 'Um metro', 'Terra', 'Sistema Solar', 'Via Láctea', 'Grupo Local', 'Teia cósmica', 'Universo observável'];
const activeName = '[data-scale-active] [data-scale-name]';
const errors = [];

async function open(options) {
  const page = await browser.newPage(options);
  await page.addInitScript(() => Object.defineProperty(navigator, 'gpu', { value: undefined }));
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', entry => { if (entry.type() === 'error') errors.push(entry.text()); });
  await page.goto(url, { waitUntil: 'networkidle' });
  return page;
}

async function goToScale(page, progress) {
  await page.evaluate(value => {
    document.documentElement.style.scrollBehavior = 'auto';
    const stations = [...document.querySelectorAll('[data-scale-station]')];
    const i = Math.min(stations.length - 2, Math.floor(value));
    const a = stations[i].getBoundingClientRect().top;
    const b = stations[i + 1].getBoundingClientRect().top;
    window.scrollBy(0, a + (b - a) * (value - i));
  }, progress);
  await page.waitForFunction(({ visual, progress }) =>
    Math.abs(Number(document.querySelector(visual).dataset.scalePosition) - progress) < .003, { visual, progress });
}

try {
  const desktop = await open({ viewport: { width: 1280, height: 800 } });
  assert.equal(await desktop.locator('html').getAttribute('data-theme'), 'light');
  await goToScale(desktop, 0);
  await desktop.waitForSelector(`${visual}[data-media="posters"]`);
  assert.equal(await desktop.locator(canvas).count(), 0);
  const rect = await desktop.locator(visual).boundingBox();
  assert.ok(rect.width > 960 && rect.width <= 1280 && rect.height === 800);
  assert.ok(Math.abs(rect.y) < 1);
  const frames = [];
  for (const progress of [0, .4, 1, 2, 3, 4, 5, 6, 7, 8, 9, 7.6]) {
    await goToScale(desktop, progress);
    assert.equal(await desktop.locator(activeName).textContent(), stationNames[Math.round(progress)]);
    assert.equal(await desktop.locator('.cosmic-exhibit-nav [aria-current="step"]').textContent(), `${String(Math.round(progress) + 1).padStart(2, '0')}${stationNames[Math.round(progress)]}`);
    const image = await desktop.locator('.scale-scene-window').screenshot();
    const frame = await sharp(image).resize(64, 48).removeAlpha().raw().toBuffer();
    if (frames.length) assert.ok(!frame.equals(frames.at(-1)), `changed exhibit pixels at scale ${progress}`);
    frames.push(frame);
    if (captures && [0, .4, 6, 9].includes(progress)) await desktop.screenshot({ path: join(captures, `desktop-${progress}.png`) });
  }
  const slider = desktop.getByRole('slider');
  await slider.press('End');
  await desktop.waitForFunction(selector => document.querySelector(selector).textContent === 'Universo observável', activeName);
  await slider.press('Home');
  await desktop.waitForFunction(selector => document.querySelector(selector).textContent === 'Próton', activeName);
  const scaleSelect = desktop.getByRole('combobox', { name: 'Ir para uma escala' });
  await scaleSelect.selectOption('6');
  await desktop.waitForFunction(selector => document.querySelector(selector).textContent === 'Via Láctea', activeName);
  assert.match(desktop.url(), /#escala-via-lactea$/);
  const light = desktop.getByRole('button', { name: 'Modo leve' });
  await light.click();
  await desktop.locator(canvas).waitFor({ state: 'detached' });
  await slider.press('End');
  await desktop.waitForFunction(selector => document.querySelector(selector).textContent === 'Universo observável', activeName);
  await desktop.waitForFunction(() => [...document.querySelectorAll('.scale-journey-posters img')].at(-1).naturalWidth > 0);
  await light.click();
  assert.equal(await light.getAttribute('aria-pressed'), 'false');
  await desktop.setViewportSize({ width: 1280, height: 300 });
  await desktop.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await desktop.locator(canvas).waitFor({ state: 'detached' });
  await desktop.close();

  const ssr = await open({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  assert.deepEqual(await ssr.locator('[data-scale-station] h3').allTextContents(), stationNames);
  assert.equal(await ssr.locator('[data-scale-station] img[alt]').count(), stationNames.length);
  assert.equal(await ssr.locator('[data-scale-station] a[href^="https://"]').count(), stationNames.length);
  assert.equal(await ssr.locator(visual).isVisible(), false);
  const staticList = await ssr.locator('.cosmic-exhibit-stages').boundingBox();
  assert.ok(staticList.x > 0 && Math.abs(staticList.x * 2 + staticList.width - 390) < 2);
  await ssr.close();

  const reduced = await open({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const teia = reduced.getByRole('navigation', { name: 'Escalas da exposição' }).getByRole('link', { name: 'Teia cósmica' });
  await teia.click();
  assert.match(reduced.url(), /#escala-teia-cosmica$/);
  assert.equal(await reduced.locator('[data-scale-enhanced]').count(), 0);
  assert.equal(await reduced.locator(canvas).count(), 0);
  assert.equal(await reduced.locator('[data-scale-video]').getAttribute('src'), null);
  if (captures) await reduced.screenshot({ path: join(captures, 'mobile-reduzido.png') });
  await reduced.close();

  const phone = await open({ ...devices['Pixel 7'], deviceScaleFactor: 1 });
  await goToScale(phone, 0);
  await phone.waitForSelector(`${visual}[data-media="posters"]`);
  assert.equal(await phone.locator('[data-scale-video]').getAttribute('src'), null);
  await phone.locator('[data-theme-toggle]').first().click();
  assert.equal(await phone.locator('html').getAttribute('data-theme'), 'dark');
  const mobileSlider = await phone.getByRole('slider').boundingBox();
  await phone.touchscreen.tap(mobileSlider.x + mobileSlider.width - 4, mobileSlider.y + mobileSlider.height / 2);
  await phone.waitForFunction(selector => document.querySelector(selector).textContent === 'Universo observável', activeName);
  assert.equal(await phone.evaluate(() => document.documentElement.scrollWidth - innerWidth), 0);
  if (captures) await phone.screenshot({ path: join(captures, 'mobile-dark-9.png') });
  await goToScale(phone, 4);
  await phone.waitForSelector(`${visual}[data-media="video"]`, { timeout: 30000 });
  assert.equal(await phone.locator(canvas).count(), 0);
  for (const progress of [7, 5, 8]) {
    await goToScale(phone, progress);
    await phone.waitForFunction(value => {
      const video = document.querySelector('[data-scale-video]');
      return !video.seeking && video.paused && Math.abs(video.currentTime - (value - 4)) < .025;
    }, progress);
  }
  if (captures) await phone.screenshot({ path: join(captures, 'mobile-video.png') });
  await phone.emulateMedia({ reducedMotion: 'reduce' });
  await phone.locator('[data-scale-enhanced]').waitFor({ state: 'detached' });
  assert.equal(await phone.locator(visual).isVisible(), false);
  assert.deepEqual(errors, []);
  await phone.close();
  const failedVideo = await open({ viewport: {width: 390, height: 844} });
  await failedVideo.route('**/media/scale-journey.mp4', route => route.fulfill({status: 503,body:''}));
  await goToScale(failedVideo, 6);
  await failedVideo.waitForFunction(() => document.querySelector('[data-scale-video]').error !== null);
  assert.equal(await failedVideo.locator(visual).getAttribute('data-media'), 'posters');
  assert.equal(await failedVideo.locator(activeName).textContent(), 'Via Láctea');
  await failedVideo.close();
  console.log('Ten stations, keyboard, reduced motion, video seeking and poster fallback verified.');
} finally {
  await browser.close();
}
