import assert from 'node:assert/strict';
import { chromium, webkit } from 'playwright';
import { openExtraExperiments } from './lib/reader-navigation.mjs';

const base = process.env.BASE_URL || 'http://127.0.0.1:4321';
for (const engine of [webkit, chromium]) {
  const browser = await engine.launch();
  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({ viewport: { width, height: 820 }, reducedMotion: 'reduce' });
      await page.goto(base + '/capitulos/galaxias-e-nebulosas/');
      await openExtraExperiments(page);
      const button = page.locator('[data-light-play]');
      await button.scrollIntoViewIfNeeded();
      const geometry = await button.evaluate(el => {
        const button = el.getBoundingClientRect();
        const layer = document.querySelector('[data-flight-depth]');
        const svg = layer.previousElementSibling.getBoundingClientRect();
        const canvas = layer.getBoundingClientRect();
        const x = button.left + button.width/2, y = button.top + button.height/2;
        return {
          hit: el.contains(document.elementFromPoint(x, y)),
          bounded: ['top','left','right','bottom'].every(k => Math.abs(svg[k]-canvas[k]) < 1),
          overlaps: canvas.bottom > button.top + 1,
          pointer: getComputedStyle(layer).pointerEvents,
        };
      });
      assert.deepEqual(geometry, { hit:true, bounded:true, overlaps:false, pointer:'none' });
      await button.click();
      assert.equal(await page.locator('[data-light-pulse]').getAttribute('cx'), '450');
      await button.click();
      assert.equal(await page.locator('[data-light-pulse]').getAttribute('cx'), '45');
      console.log(engine.name(), width, 'px · clique, chegada e reinício OK');
      await page.close();
    }
  } finally { await browser.close(); }
}
