// Quando WebGL falha, o visitante deve receber uma explicação e manter o diagrama utilizável.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      if (kind === 'webgl' || kind === 'webgl2' || kind === 'experimental-webgl') return null;
      return original.call(this, kind, ...args);
    };
  });
  await page.goto(`${base}/capitulos/sistema-solar/#sistema-solar-gigantes`, { waitUntil: 'load' });
  const root = page.locator('[data-mx="sistema-solar-gigantes"]');
  await root.locator('.mx-stage').first().scrollIntoViewIfNeeded();
  const notice = root.locator('[data-mx-visual-state]');
  await notice.waitFor({ state: 'visible', timeout: 20000 });
  assert.match(await notice.innerText(), /3D.*indisponível/i);
  assert.equal(await root.locator('[data-mx-svg]').isVisible(), true);
  assert.equal(await root.locator('[data-mx-range]').isEnabled(), true);
  console.log('Sem WebGL: aviso claro, diagrama e controle disponíveis.');
} finally { await browser.close(); }
