import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const journey = '/capitulos/galaxias-e-nebulosas/';
const earth = '/capitulos/terra-e-atmosfera/';
const scene = '[data-mx="galaxias-e-nebulosas-via-lactea"]';
const chapterScript = /\/_astro\/galaxias[.-][^/]+\.js$/;
const viewport = { width: 295, height: 850 };
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });

try {
  const page = await browser.newPage({ viewport, reducedMotion: 'no-preference' });
  for (const path of ['/', journey, earth, '/laboratorio/', '/observatorio/', '/escalas/', '/ceu/']) {
    await page.goto(base + path);
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), viewport.width, path);
  }

  await page.goto(base + '/');
  const backdrop = () => page.locator('.arrival-grid').evaluate(el => getComputedStyle(el, '::before').animationName);
  assert.equal(await backdrop(), 'ambient-drift');
  const cta = page.locator('.arrival-actions .cta');
  await cta.hover();
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.arrival-actions .cta')).translate === '0px -2px');
  await page.mouse.down();
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.arrival-actions .cta')).scale === '0.975');
  await page.mouse.move(0, 0);
  await page.mouse.up();

  const settings = page.locator('.motion-settings');
  await settings.locator('summary').click();
  const panel = await settings.locator('div').boundingBox();
  assert.ok(panel && panel.x >= 0 && panel.x + panel.width <= viewport.width);
  await settings.locator('select').selectOption('reduced');
  assert.equal(await backdrop(), 'none');
  await settings.locator('select').selectOption('full');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  assert.equal(await backdrop(), 'none');
  await page.close();

  const cold = await browser.newPage({ viewport });
  const gate = Promise.withResolvers();
  await cold.route(chapterScript, async route => {
    await gate.promise;
    await route.continue();
  });
  const requested = cold.waitForRequest(chapterScript);
  await cold.goto(base + journey + '?visual=diagram', { waitUntil: 'domcontentloaded' });
  const experiment = cold.locator(scene);
  const diagram = experiment.locator('[data-mx-svg]');
  const pending = experiment.locator('.mx-stage [data-mx-pending]');
  await diagram.scrollIntoViewIfNeeded();
  await requested;
  assert.ok(await diagram.locator('[data-mx-opening] circle').first().isVisible());
  assert.ok(await pending.isVisible());
  assert.ok(await experiment.locator('[data-mx-opt="1"]').isDisabled());
  gate.resolve();
  await experiment.locator('[data-mx-opt="1"]').click();
  assert.equal(await experiment.getAttribute('data-mx-load'), 'ready');
  assert.equal(await experiment.locator('[data-mx-opt="1"]').getAttribute('aria-pressed'), 'true');
  assert.equal(await diagram.locator('[data-mx-opening]').count(), 0);
  assert.equal(await pending.isVisible(), false);
  await cold.close();

  const offline = await browser.newPage({ viewport });
  await offline.route(chapterScript, route => route.abort());
  await offline.goto(base + journey);
  const fallback = offline.locator(scene);
  await fallback.locator('.mx-stage [data-mx-error]').waitFor();
  assert.ok(await fallback.locator('[data-mx-opening] circle').first().isVisible());
  await offline.close();

  const noScript = await browser.newPage({ viewport, javaScriptEnabled: false });
  await noScript.goto(base + journey);
  assert.ok(await noScript.locator(scene + ' [data-mx-opening] circle').first().isVisible());
  assert.equal(await noScript.locator(scene + ' .mx-load-status').isVisible(), false);
  await noScript.goto(base + earth);
  assert.equal(await noScript.locator('[data-mx-opening]').count(), 6);
  assert.ok(await noScript.locator('[data-mx-opening] circle').first().isVisible());
  console.log('Abertura da Terra, carregamento atrasado/indisponível, movimento e sete rotas a 295 px verificados.');
} finally {
  await browser.close();
}
