import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium, devices } from 'playwright';
import sharp from 'sharp';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const url = base + '/capitulos/sistema-solar/#saturno-aneis';
const out = resolve(process.env.SATURN_OUTPUT ?? 'test-results/saturn');
const media = new URL('../public/models/saturn/', import.meta.url);
const manifest = JSON.parse(await readFile(new URL('frames.json', media), 'utf8'));
const hash = data => createHash('sha256').update(data).digest('hex');
const records = manifest.frames;
assert.deepEqual(records.map(frame => frame.degree), Array.from({ length: 91 }, (_, i) => i));
assert.equal(new Set(records.map(frame => frame.sha256)).size, 91);
assert.equal(hash(await readFile(new URL('../assets/source/saturn/saturn.blend', import.meta.url))), manifest.sourceSha256);
for (const entry of [...records, manifest.poster]) {
  const bytes = await readFile(new URL(entry.file, media));
  assert.equal(bytes.toString('ascii', 8, 12), 'WEBP');
  assert.equal(hash(bytes), entry.sha256, entry.file);
}
assert.equal(manifest.poster.sha256, records[30].sha256);
// Compare the silhouette in the actual pixels with the orthographic ring projection.
const silhouettes = [];
for (const degree of [0, 30, 45, 60, 90]) {
  const { data, info } = await sharp(await readFile(new URL(records[degree].file, media)))
    .greyscale().raw().toBuffer({ resolveWithObject: true });
  let left = info.width, right = -1, top = info.height, bottom = -1;
  for (let y = 0; y < info.height; y++) {
    for (let x = 0; x < info.width; x++) {
      if (Math.abs(data[y * info.width + x] - data[0]) <= 12) continue;
      left = Math.min(left, x);
      right = Math.max(right, x);
      top = Math.min(top, y);
      bottom = Math.max(bottom, y);
    }
  }
  const width = right - left + 1, height = bottom - top + 1;
  assert.ok(left > 0 && top > 0 && right < info.width - 1 && bottom < info.height - 1);
  if (degree === 0) {
    // The edge-on ring has zero projected area. The remaining silhouette is the oblate globe.
    assert.ok(Math.abs(height / width - 0.904) < 0.025 && width < info.width / 3);
  } else {
    assert.ok(Math.abs(height / width - Math.sin(degree * Math.PI / 180)) < 0.015, String(degree));
  }
  silhouettes.push({ degree, width, height });
}
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--disable-webgl'] });
try {
  const context = await browser.newContext({ ...devices['Pixel 7'], viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
  await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin ? route.continue() : route.abort());
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  await page.addInitScript(() => {
    window.saturnGl = [];
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...options) {
      if (/webgl/i.test(type)) window.saturnGl.push(new Error().stack);
      return original.call(this, type, ...options);
    };
  });
  const requests = [];
  page.on('request', request => {
    if (/\/models\/saturn\/.*\.(webp|glb)$/.test(request.url())) requests.push(new URL(request.url()).pathname);
  });
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  const root = page.locator('[data-saturn]');
  const slider = root.locator('input:enabled');
  await slider.waitFor();
  await root.scrollIntoViewIfNeeded();
  async function visible(degree) {
    await page.waitForFunction(degree => {
      const img = document.querySelector('[data-saturn-frame]');
      const suffix = degree === 30 ? '/poster.webp' : '/frames/' + String(degree).padStart(2, '0') + '.webp';
      return !img.hidden && img.complete && img.naturalWidth === 704 && img.naturalHeight === 512 && img.currentSrc.endsWith(suffix);
    }, degree);
    assert.equal(await slider.inputValue(), String(degree));
    assert.equal(await root.locator('output').textContent(), degree + '°');
  }
  await visible(30);
  assert.equal(requests.length, 1, JSON.stringify(requests));
  assert.ok(requests[0].endsWith('/poster.webp'));
  await context.setOffline(true);
  const failed = page.waitForEvent('requestfailed', request => request.url().endsWith('/frames/31.webp'));
  await slider.press('ArrowRight');
  await failed;
  await page.waitForFunction(() => document.querySelector('[data-saturn-frame]').hidden);
  assert.equal(await slider.inputValue(), '31');
  assert.equal(await root.locator('output').textContent(), '31°');
  assert.ok((await root.locator('[data-saturn-rings]').first().getAttribute('transform')).includes(String(Math.sin(31 * Math.PI / 180))));
  await slider.press('Home');
  assert.equal(await root.locator('[data-saturn-edge]').getAttribute('visibility'), 'visible');
  await page.waitForFunction(() => document.querySelector('[data-saturn-frame]').getAttribute('src').endsWith('/00.webp'));
  await root.screenshot({ path: resolve(out, 'mobile-offline-edge.png') });
  await context.setOffline(false);
  await root.getByRole('button', { name: 'Vista polar' }).tap();
  await visible(90);
  // Change the selection while the previous image request is still in flight.
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/frames/89.webp', async route => {
    await gate;
    await route.continue();
  }, { times: 1 });
  const previous = page.waitForRequest('**/frames/89.webp');
  await slider.press('ArrowLeft');
  await previous;
  try {
    await slider.press('ArrowLeft');
    await visible(88);
  } finally {
    release();
  }
  await root.getByRole('button', { name: 'De perfil' }).tap();
  await visible(0);
  for (let degree = 1; degree <= 90; degree++) {
    await slider.press('ArrowRight');
    await visible(degree);
  }
  await root.getByRole('button', { name: 'Vista aberta' }).tap();
  await visible(30);
  await root.screenshot({ path: resolve(out, 'mobile-open.png') });

  assert.equal(await root.locator('canvas').count(), 0);
  assert.ok(requests.every(path => !path.endsWith('.glb')));
  const attempts = await page.evaluate(() => window.saturnGl);
  assert.ok(attempts.every(stack => !/saturn-exhibit|saturn-view/i.test(stack)), JSON.stringify(attempts));
  const staticPage = await browser.newPage({ javaScriptEnabled: false });
  await staticPage.goto(url, { waitUntil: 'domcontentloaded' });
  const staticImage = staticPage.locator('[data-saturn-frame]');
  await staticImage.scrollIntoViewIfNeeded();
  await staticImage.evaluate(img => img.decode());
  assert.equal(await staticImage.evaluate(img => img.naturalWidth), 704);
  assert.equal(await staticPage.locator('[data-saturn-controls]').isVisible(), false);
  await staticPage.close();
  const report = { browser: browser.version(), renderedDegrees: records.length, verifiedHashes: 93,
    displayedDegrees: 91, resolution: manifest.resolution, silhouettes, firstRequest: requests[0],
    input: ['touch presets', 'keyboard 0–90'], offlineFallbackDegrees: [31, 0],
    recoveredDegree: 90, changedWhileLoading: [89, 88], noScriptPoster: true, saturnGlCalls: 0, chapterGlAttempts: attempts.length };
  await writeFile(resolve(out, 'saturn-results.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(report);
} finally {
  await browser.close();
}
