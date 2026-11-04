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
  // A preferência pode mudar com a página aberta; o leitor e o instrumento continuam disponíveis.
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForFunction(() => document.documentElement.dataset.motion === 'reduced');
  assert.equal(await page.getByRole('button', { name: /céu animado/i }).count(), 0);
  assert.equal(await orbit.evaluate(el => getComputedStyle(el).animationName), 'none');
  assert.equal(await page.locator('#hero-title .gs-unit').count(), 0, 'o título mantém seu texto nativo');
  assert.equal(await page.locator('[data-cmb-frame]').isVisible(), true);
  const field = page.locator('.starfield');
  const stopped = await field.getAttribute('style');
  await page.locator('.hero-shell').dispatchEvent('pointermove', { clientX: 20, clientY: 20, pointerType: 'mouse' });
  assert.equal(await field.getAttribute('style'), stopped, 'a paralaxe respeita a mudança para movimento reduzido');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.getByRole('button', { name: 'Pausar o céu animado' }).waitFor();
  await page.locator('#desafio').scrollIntoViewIfNeeded();
  await page.waitForFunction(() => document.querySelector('.hero-shell')?.dataset.ambientSuspended === 'true');
  assert.equal(await orbit.evaluate(el => getComputedStyle(el).animationPlayState), 'paused', 'a moldura para fora da tela');
  await page.locator('#topo').scrollIntoViewIfNeeded();
  await page.waitForFunction(() => document.querySelector('.hero-shell')?.dataset.ambientSuspended === 'false');
  assert.equal(await orbit.evaluate(el => getComputedStyle(el).animationPlayState), 'running');
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
  assert.equal(await noJs.locator('html').getAttribute('data-theme'), 'dark');
  assert.equal(await noJs.getByRole('button', { name: /céu animado/i }).count(), 0);
  assert.equal(await noJs.getByRole('heading', { name: /Cosmos do Zero/i }).count(), 1);
  console.log('Controle de efeitos: teclado, pausa, retomada, preferência ao vivo, saída da tela e ausência de JavaScript OK.');
} finally { await browser.close(); }
