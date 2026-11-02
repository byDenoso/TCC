// Após o primeiro palpite, o próximo controle precisa estar visível e com foco.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--no-sandbox'] });
try {
  for (const width of [390, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 850 }, reducedMotion: 'reduce' });
    await page.goto(`${base}/capitulos/galaxias-e-nebulosas/#galaxias-e-nebulosas-via-lactea`, { waitUntil: 'load' });
    const module = page.locator('[data-mx="galaxias-e-nebulosas-via-lactea"]');
    await module.locator('[data-mx-guess="0"]').click();
    const next = module.locator('[data-mx-opt="1"]');
    await next.waitFor({ state: 'visible' });
    assert.equal(await next.evaluate(el => document.activeElement === el), true, `foco no controle em ${width}px`);
    const rect = await next.evaluate(el => { const r=el.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,height:innerHeight}; });
    assert.ok(rect.top >= 64 && rect.bottom <= rect.height - 125, `controle visível e acima da barra em ${width}px: ${JSON.stringify(rect)}`);
    await next.click();
    const feedback = module.locator('[data-mx-inline-feedback]');
    assert.equal(await feedback.isVisible(), true, `explicação junto aos controles em ${width}px`);
    assert.match(await feedback.innerText(), /O que sabemos:/, `resultado compreensível em ${width}px`);
    await page.close();
  }
  console.log('Palpite → controle visível → explicação: celular e desktop OK.');
} finally { await browser.close(); }
