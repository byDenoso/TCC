// Exercise the rendered exhibits against a running site.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const lightPath = process.env.LIGHT_PATH ?? '/luz/';
const shots = process.env.SHOTS;
if (shots) await mkdir(shots, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM, args: ['--no-sandbox'] });

async function open(path, options) {
  const page = await browser.newPage(options);
  await page.addInitScript((scheme) => localStorage.setItem('cosmos-theme', scheme ?? 'light'), options?.colorScheme);
  page.on('pageerror', (error) => { throw error; });
  assert.equal((await page.goto(base + path)).status(), 200);
  return page;
}

function showStep(page, step, offset) {
  return page.locator(`[data-light-step="${step}"]`).evaluate((node, pixels) => {
    const line = innerHeight * (innerWidth <= 720 ? 0.62 : 0.78);
    window.scrollBy({ top: node.getBoundingClientRect().top - line + pixels, behavior: 'instant' });
  }, offset);
}

async function spectrum(page) {
  return page.locator('.light-shifts path').evaluateAll((lines) => lines.map((line) => line.transform.baseVal.getItem(0).matrix.e));
}

async function expansion(page) {
  return page.locator('[data-sci-panel="expansao"] svg ellipse').evaluateAll((dots) =>
    dots.map((dot) => ({ distance: Math.hypot(dot.cx.baseVal.value - 240, dot.cy.baseVal.value - 150), shown: dot.style.display !== 'none' })));
}

try {
  const light = await open(lightPath, { viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
  await light.locator('[data-light-nav]').waitFor();
  await showStep(light, 1, 15);
  await light.locator('[data-light-view="spectrum"]').waitFor();
  const initial = await spectrum(light);
  await showStep(light, 1, 230);
  await light.waitForFunction((previous) => document.querySelector('.light-shifts path').transform.baseVal.getItem(0).matrix.e > previous + 10, initial[0], { timeout: 2500 });
  const shifted = await spectrum(light);
  assert.ok(shifted.every((position, i) => position > initial[i]));
  const changes = shifted.map((position, i) => position - initial[i]);
  assert.ok(Math.abs(changes[2] / changes[0] - 656.3 / 486.1) < 0.001, 'λobs scales by 1 + z');
  assert.ok(await light.getByRole('link', { name: 'Fonte e gráfico em resolução integral' }).isVisible());
  if (shots) {
    await showStep(light, 1, 490);
    await light.screenshot({ path: `${shots}/espectro-desktop.png` });
  }
  await showStep(light, 2, 50);
  const slider = light.getByRole('slider', { name: 'Redshift', exact: true });
  await slider.press('End');
  assert.equal(await light.locator('[data-light-readout]').innerText(), '1.050,1 nm');
  const manual = await spectrum(light);
  await showStep(light, 2, 120);
  await light.waitForTimeout(120);
  assert.deepEqual(await spectrum(light), manual);
  await light.close();

  const mobile = await open(lightPath, { viewport: { width: 390, height: 844 }, colorScheme: 'dark', reducedMotion: 'reduce' });
  await mobile.locator('[data-light-nav]').waitFor();
  await showStep(mobile, 1, 15);
  await mobile.locator('[data-light-view="spectrum"]').waitFor();
  const still = await spectrum(mobile);
  await showStep(mobile, 1, 180);
  await mobile.waitForTimeout(120);
  assert.deepEqual(await spectrum(mobile), still);
  assert.ok(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  if (shots) {
    await showStep(mobile, 1, 390);
    await mobile.screenshot({ path: `${shots}/espectro-celular-escuro-reduzido.png` });
  }
  await mobile.close();

  const staticLight = await open(lightPath, { javaScriptEnabled: false });
  assert.ok(await staticLight.locator('[data-light-view="photo"]').isVisible());
  assert.ok(await staticLight.locator('[data-light-view="spectrum"]').isVisible());
  assert.ok(await staticLight.getByRole('link', { name: 'Fonte e gráfico em resolução integral' }).isVisible());
  await staticLight.close();

  const staticHome = await open('/', { javaScriptEnabled: false });
  assert.ok(await staticHome.locator('[data-sci-static-expansion]').isVisible());
  assert.ok(await staticHome.locator('[data-sci-static-expansion] line').count() > 3);
  await staticHome.close();

  for (const reducedMotion of ['no-preference', 'reduce']) {
    const page = await open('/', { viewport: { width: 1280, height: 800 }, reducedMotion });
    await page.getByRole('tab', { name: 'Espaço crescendo', exact: true }).click();
    const panel = page.locator('[data-sci-panel="expansao"]');
    const stage = panel.locator('[data-sci-stage]');
    const positionStage = (fraction) => stage.evaluate((element, at) => {
      window.scrollBy({ top: element.getBoundingClientRect().top - innerHeight * at, behavior: 'instant' });
    }, fraction);
    await positionStage(0.8);
    await page.waitForTimeout(160);
    const before = await expansion(page);
    await positionStage(0.42);
    await page.waitForTimeout(160);
    const after = await expansion(page);
    if (reducedMotion === 'reduce') {
      assert.deepEqual(after, before);
    } else {
      const ratios = after.flatMap((dot, i) => dot.shown && before[i].shown && before[i].distance > 10 ? [dot.distance / before[i].distance] : []);
      assert.ok(ratios.length > 3 && ratios.every((ratio) => ratio > 1.2 && Math.abs(ratio - ratios[0]) < 0.001), 'scroll multiplies the visible separations by the same factor');
      if (shots) await page.screenshot({ path: `${shots}/expansao-desktop.png` });
    }
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForTimeout(120);
    assert.deepEqual(await expansion(page), after, 'the grid stays still offscreen');
    await panel.getByRole('slider').press('Home');
    const manual = await expansion(page);
    await positionStage(0.45);
    await page.waitForTimeout(120);
    assert.deepEqual(await expansion(page), manual);
    await page.close();
  }
  console.log('Espectro e expansão: rolagem, escala, controles e estados estáticos verificados.');
} finally {
  await browser.close();
}
