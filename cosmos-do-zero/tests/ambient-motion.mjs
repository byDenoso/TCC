// Confere o controle de movimento decorativo com mouse, teclado e preferência do sistema.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage({ reducedMotion: 'no-preference', viewport: { width: 1280, height: 900 } });
  await page.goto(`${base}/`, { waitUntil: 'load' });
  const control = page.getByRole('button', { name: 'Pausar o céu animado' });
  await control.waitFor({ state: 'visible', timeout: 10000 });
  const orbit = page.locator('.sky-orbit--outer');
  const star = page.locator('.star').first();
  assert.equal(await orbit.evaluate(el => getComputedStyle(el).animationPlayState), 'running');
  await control.focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.getByRole('button', { name: 'Retomar o céu animado' }).isVisible(), true);
  assert.equal(await orbit.evaluate(el => getComputedStyle(el).animationPlayState), 'paused');
  assert.equal(await star.evaluate(el => getComputedStyle(el).animationPlayState), 'paused');
  await page.keyboard.press('Enter');
  assert.equal(await page.getByRole('button', { name: 'Pausar o céu animado' }).isVisible(), true);
  assert.equal(await orbit.evaluate(el => getComputedStyle(el).animationPlayState), 'running');
  assert.equal(await star.evaluate(el => getComputedStyle(el).animationPlayState), 'running');
  const compact = await browser.newPage({ viewport: { width: 320, height: 760 } });
  await compact.goto(`${base}/`, { waitUntil: 'load' });
  for (const link of await compact.locator('.hero-routes a').all()) {
    assert.ok(await link.evaluate(el => {
      const label=el.querySelector('strong').getBoundingClientRect(), box=el.getBoundingClientRect();
      const text=el.querySelector('strong');
      return label.left >= box.left && label.right <= box.right && text.scrollWidth <= text.clientWidth;
    }), 'atalhos da abertura não cortam palavras em tela estreita');
  }
  const reduced = await browser.newPage({ reducedMotion: 'reduce', viewport: { width: 390, height: 844 } });
  await reduced.goto(`${base}/`, { waitUntil: 'load' });
  assert.equal(await reduced.getByRole('button', { name: /céu animado/i }).count(), 0);
  assert.equal(await reduced.locator('.sky-orbit--outer').evaluate(el => getComputedStyle(el).animationName), 'none');
  const noJs = await browser.newPage({ javaScriptEnabled: false });
  await noJs.goto(`${base}/`, { waitUntil: 'load' });
  assert.equal(await noJs.getByRole('button', { name: /céu animado/i }).count(), 0);
  assert.equal(await noJs.getByRole('heading', { name: /Cosmos do Zero/i }).count(), 1);
  console.log('Controle de efeitos: teclado, pausa, retomada, movimento reduzido e ausência de JavaScript OK.');
} finally { await browser.close(); }
