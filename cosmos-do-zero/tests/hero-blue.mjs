import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import sharp from 'sharp';

const base = (process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
try {
  for (const width of [390, 1440]) {
    const page = await browser.newPage({viewport:{width,height:900}, reducedMotion:'reduce'});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/ceu/');
    const plate = page.locator('[data-nebula-plate]');
    const button = page.getByRole('button', { name: 'Mostrar nebulosa ilustrativa' });
    assert.equal(await plate.getAttribute('src'), null);
    await button.focus();
    await button.press('Enter');
    await plate.waitFor();
    await plate.evaluate(img => img.decode());
    const url = await plate.evaluate(img => img.currentSrc);
    const stats = await sharp(await (await page.request.get(url)).body()).stats();
    assert.ok(stats.channels[2].stdev > 2, 'A nebulosa deve apresentar estrutura no canal azul');
    await page.getByRole('button',{name:'Ocultar nebulosa ilustrativa'}).click();
    assert.ok(await plate.isHidden());
    assert.equal(await button.getAttribute('aria-pressed'),'false');
    assert.deepEqual(errors, []);
    await page.close();
  }
} finally {
  await browser.close();
}
