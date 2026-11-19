import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium } from 'playwright';
import {
  openExtraExperiments,
  openLessonStory,
} from './lib/reader-navigation.mjs';

const base = (process.env.BASE_URL || 'http://127.0.0.1:4321').replace(
  /\/$/,
  '',
);
const out = process.env.SHOTS || 'test-results/lesson-depth';
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
});
const errors = [],
  gl = [],
  checks = [],
  requests = new Set();
const context = await browser.newContext({
  viewport: { width: Number(process.env.WIDTH || 1024), height: 820 },
  reducedMotion: 'reduce',
});
await context.route('**/*', (route) => {
  const url = new URL(route.request().url());
  if (/^https?:$/.test(url.protocol) && url.origin !== new URL(base).origin) {
    errors.push(url.href);
    return route.abort();
  }
  requests.add(url.pathname);
  return route.continue();
});
await context.exposeBinding('glAttempt', (_, kind) => gl.push(kind));
await context.addInitScript(() => {
  const original = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
    if (/webgl/i.test(kind)) {
      Reflect.get(window, 'glAttempt')(kind);
      return null;
    }
    return original.call(this, kind, ...args);
  };
});
const page = await context.newPage();
page.on('pageerror', (err) => errors.push(err.message));
page.on('response', (r) => {
  if (r.status() >= 400) errors.push(r.status() + ' ' + r.url());
});
const go = (path) => page.goto(base + path);
const canvas = (s) => page.locator(s);
async function painted(selector) {
  await canvas(selector).scrollIntoViewIfNeeded();
  await page.waitForFunction((selector) => {
    const node = document.querySelector(selector),
      ctx = node?.getContext('2d');
    return ctx
      ?.getImageData(0, 0, node.width, node.height)
      .data.some((v, i) => i % 4 === 3 && v > 0);
  }, selector);
}
async function snap(name, selector) {
  await page.locator(selector).screenshot({ path: join(out, name + '.png') });
  checks.push(name);
  console.log(name);
}
try {
  await go('/');
  await page.locator('[data-journey-step="6"]').scrollIntoViewIfNeeded();
  await painted('[data-journey-canvas]');
  const select = page.locator('[data-journey-select]');
  await select.selectOption('9');
  await page.waitForFunction(() =>
    document
      .querySelector('[data-journey-step="9"]')
      .classList.contains('is-active'),
  );
  await snap('jornada', '.journey-stage');
  const frame = await canvas('[data-journey-canvas]').evaluate((c) =>
    c.toDataURL(),
  );
  await page.waitForTimeout(150);
  assert.equal(
    await canvas('[data-journey-canvas]').evaluate((c) => c.toDataURL()),
    frame,
  );
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  const pause = page.locator('[data-journey-pause]');
  await pause.click();
  const snapshot = () =>
    canvas('[data-journey-canvas]').evaluate((c) => c.toDataURL());
  await page.waitForTimeout(80);
  const paused = await snapshot();
  await page.waitForTimeout(160);
  assert.equal(await snapshot(), paused);
  await pause.click();
  await page.waitForFunction(
    (before) =>
      document.querySelector('[data-journey-canvas]').toDataURL() !== before,
    paused,
  );
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForFunction(
    () => document.querySelector('.journey').dataset.journeyVisible === 'false',
  );
  const outside = await snapshot();
  await page.waitForTimeout(140);
  assert.equal(await snapshot(), outside);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await go('/laboratorio/');
  const era = page.locator('[data-era-index="8"]');
  await era.click();
  await painted('[data-era-depth]');
  await snap('timeline', '[data-timeline-visual]');
  await page.locator('[data-mass="15"]').click();
  await page.locator('[data-star-step="2"]').click();
  await painted('[data-stellar-depth]');
  await snap('estrelas', '[data-star-svg]');
  await page.locator('[data-star-step="4"]').click();
  assert.match(
    await page.locator('[data-star-caption]').innerText(),
    /buraco negro/,
  );
  await go('/ceu/');
  await page.locator('[data-cmb-frame]').focus();
  await painted('[data-cmb-sphere]');
  const globe = await canvas('[data-cmb-sphere]').evaluate((c) =>
    c.toDataURL(),
  );
  await page.locator('[data-cmb-frame]').press('Shift+ArrowRight');
  await page.waitForFunction(
    (before) =>
      document.querySelector('[data-cmb-sphere]').toDataURL() !== before,
    globe,
  );
  assert.match(
    await page.locator('[data-cmb-read]').innerText(),
    /mapa simulado/i,
  );
  await snap('ceu', '.cmb-pair');
  await go('/luz/');
  await page.locator('[data-light-go="2"]').click();
  await page.locator('#light-redshift').press('End');
  await painted('[data-spectrum-depth]');
  assert.equal(
    await page.locator('[data-light-readout]').innerText(),
    '1.050,1 nm',
  );
  await snap('luz', '[data-light-view="spectrum"]');
  await go(
    '/capitulos/galaxias-e-nebulosas/#galaxias-e-nebulosas-centros-galacticos',
  );
  for (const kind of ['orbitas', 'acrecao', 'horizonte']) {
    const plate = '[data-bh-stage="' + kind + '"]';
    await painted(plate + ' canvas');
    const slider = page.locator(plate + ' input');
    await slider.press('Home');
    await slider.press('ArrowRight');
    assert.ok(Number(await slider.inputValue()) > 0);
    await snap('buraco-' + kind, plate);
  }
  const bh = page.locator('[data-bh-stage="orbitas"]');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await bh.locator('button').click();
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-bh-stage="orbitas"] button')
        .getAttribute('aria-pressed') === 'true',
  );
  await page.locator('footer').scrollIntoViewIfNeeded();
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-bh-stage="orbitas"] button')
        .getAttribute('aria-pressed') === 'false',
  );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openExtraExperiments(page);
  await page.locator('[data-scale-step="4"]').click();
  assert.ok(await page.locator('[data-scale-panel="4"]').isVisible());
  await page.locator('[data-light-play]').click();
  assert.equal(
    await page.locator('[data-light-pulse]').getAttribute('cx'),
    '450',
  );
  await painted('[data-flight-depth]');
  await snap('endereco', '.light-lab');
  await go('/capitulos/origem-do-universo/#origem-do-universo-primeira-luz');
  await page.locator('[data-cmbj-goto="1"]').click();
  await painted('[data-cmbj-canvas]');
  await snap('recombinacao', '[data-cmbj-stage]');
  await page.locator('[data-cmbj-goto="2"]').click();
  assert.match(await page.locator('[data-cmbj-temp]').innerText(), /2[,.]7/);
  await openLessonStory(page);
  await page.locator('[data-story-phase="2"]').click();
  await painted('[data-wave-depth]');
  await snap('resumo', '[data-story-viewport]');
  await page.locator('[data-story-mode="film"]').click();
  await page.waitForFunction(
    () => document.querySelector('[data-story-film]').currentTime > 10,
  );
  const fallback = await context.newPage();
  await fallback.addInitScript(() => {
    HTMLCanvasElement.prototype.getContext = () => null;
  });
  await fallback.goto(
    base + '/capitulos/origem-do-universo/#origem-do-universo-primeira-luz',
  );
  await fallback.locator('[data-cmbj-goto="2"]').click();
  assert.match(
    await fallback.locator('[data-cmbj-temp]').innerText(),
    /2[,.]7/,
  );
  assert.ok(await fallback.locator('[data-cmbj-still]').isVisible());
  await fallback.goto(base + '/laboratorio/');
  await fallback.locator('[data-era-index="9"]').click();
  assert.ok(await fallback.locator('[data-era-render]').isVisible());
  await fallback.locator('[data-mass="1"]').click();
  await fallback.locator('[data-star-step="4"]').click();
  assert.match(
    await fallback.locator('[data-star-caption]').innerText(),
    /Anã branca/,
  );
  await fallback.close();
  assert.equal(gl.length, 0);
  assert.deepEqual(errors, []);
  for (const name of [
    'star',
    'helium',
    'proton',
    'electron',
    'disk',
    'stars-far',
  ]) {
    assert.ok(
      [...requests].some((url) =>
        url.endsWith('/lesson-depth/' + name + '.webp'),
      ),
      name,
    );
  }
  await writeFile(
    join(out, 'acceptance.json'),
    JSON.stringify(
      {
        base,
        viewport: page.viewportSize(),
        checks,
        gl,
        errors,
        assets: [...requests].filter((p) => p.includes('/lesson-depth/')),
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
