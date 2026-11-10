import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium, devices } from 'playwright';
import sharp from 'sharp';

const url = process.env.SCALE_URL ?? 'http://127.0.0.1:4321/escalas/';
const captures = process.env.SCALE_CAPTURES;
if (captures) await mkdir(captures, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']
});
const visual = '[data-scale-visual-stage]';
const canvas = '[data-scale-canvas] canvas';
const stationNames = ['Terra', 'Sistema Solar', 'Via Láctea', 'Grupo Local', 'Teia cósmica'];
const errors = [];

async function open(options) {
  const page = await browser.newPage(options);
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
  await desktop.waitForSelector(`${visual}[data-media="webgl"]`);
  const rect = await desktop.locator(visual).boundingBox();
  assert.deepEqual([rect.x, rect.width, rect.height], [0, 1280, 800]);
  assert.ok(Math.abs(rect.y) < 1);
  const frames = [];
  for (const progress of [0, .4, 1, 2, 3, 4, 2.6]) {
    await goToScale(desktop, progress);
    assert.equal(await desktop.locator('[data-scale-name]').textContent(), stationNames[Math.round(progress)]);
    assert.equal(await desktop.locator('.cosmic-exhibit-nav [aria-current="step"]').textContent(), `0${Math.round(progress) + 1}${stationNames[Math.round(progress)]}`);
    const image = await desktop.locator(canvas).screenshot();
    const frame = await sharp(image).resize(64, 48).removeAlpha().raw().toBuffer();
    if (frames.length) assert.ok(!frame.equals(frames.at(-1)), `changed WebGL pixels at scale ${progress}`);
    frames.push(frame);
    if (captures && [0, .4, 4].includes(progress)) await desktop.screenshot({ path: join(captures, `desktop-${progress}.png`) });
  }
  await desktop.evaluate(() => scrollTo(0, 0));
  await desktop.locator(canvas).waitFor({ state: 'detached' });
  await desktop.close();

  const ssr = await open({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  assert.deepEqual(await ssr.locator('[data-scale-station] h3').allTextContents(), stationNames);
  assert.equal(await ssr.locator('[data-scale-station] img[alt]').count(), 5);
  assert.equal(await ssr.locator('[data-scale-station] a[href^="https://"]').count(), 5);
  assert.equal(await ssr.locator(visual).isVisible(), false);
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
  await phone.waitForSelector(`${visual}[data-media="webgl"]`);
  assert.equal(await phone.locator('[data-scale-video]').getAttribute('src'), null);
  // Deliberately miss a frame under live scroll without claiming a hardware benchmark.
  await phone.evaluate(() => new Promise(resolve => {
    const travel = document.querySelector('[data-scale-lane]');
    const start = travel.getBoundingClientRect().top + scrollY;
    let step = 0;
    const move = () => {
      scrollTo(0, start + ++step * 12);
      const deadline = performance.now() + 25;
      while (performance.now() < deadline) { /* intentional CPU load */ }
      if (step < 98 && !travel.querySelector('[data-scale-video]').hasAttribute('src')) requestAnimationFrame(move);
      else resolve();
    };
    requestAnimationFrame(move);
  }));
  await phone.waitForSelector(`${visual}[data-media="video"]`, { timeout: 30000 });
  const p90 = Number(await phone.locator(visual).getAttribute('data-scale-p90'));
  assert.ok(p90 > 20, `expected p90 over 20 ms, received ${p90}`);
  assert.equal(await phone.locator(canvas).count(), 0);
  for (const progress of [3, 1, 4]) {
    await goToScale(phone, progress);
    await phone.waitForFunction(value => {
      const video = document.querySelector('[data-scale-video]');
      return !video.seeking && video.paused && Math.abs(video.currentTime - value) < .025;
    }, progress);
  }
  if (captures) await phone.screenshot({ path: join(captures, 'mobile-video.png') });
  await phone.emulateMedia({ reducedMotion: 'reduce' });
  await phone.locator('[data-scale-enhanced]').waitFor({ state: 'detached' });
  assert.equal(await phone.locator(visual).isVisible(), false);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ desktop: 'five WebGL views plus intermediate frames', ssr: true, reducedMotion: true, mobile: { mode: 'Pixel 7 emulated, SwiftShader, 25 ms injected CPU load', p90Ms: p90, videoSeek: 'forward, backward, final' } }));
} finally {
  await browser.close();
}
