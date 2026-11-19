import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
  await page.addInitScript(() => {
    window.__glAttempts = [];
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      if (/webgl|webgpu/i.test(kind)) { window.__glAttempts.push(kind); return null; }
      return original.call(this, kind, ...args);
    };
  });
  await page.goto(`${base}/capitulos/sistema-solar/#sistema-solar-gigantes`, { waitUntil: 'load' });
  const root = page.locator('[data-mx="sistema-solar-gigantes"]');
  await root.locator('.mx-stage').first().scrollIntoViewIfNeeded();
  await page.waitForFunction(() => document.querySelector('[data-mx="sistema-solar-gigantes"]')?.dataset.mxLoad === 'ready');
  const svg = root.locator('[data-mx-svg]');
  const range = root.locator('[data-mx-range]');
  const before = await svg.innerHTML();
  await range.fill('0.75');
  assert.equal(await range.inputValue(), '0.75');
  assert.ok(await svg.isVisible());
  assert.notEqual(await svg.innerHTML(), before);
  assert.deepEqual(await page.evaluate(() => window.__glAttempts), []);
  console.log('O controle de profundidade atualiza a figura sem solicitar contexto gráfico 3D.');
} finally { await browser.close(); }
