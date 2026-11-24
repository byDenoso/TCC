import assert from 'node:assert/strict';

export async function verifyPremium(browser, base) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
  try {
    const p = await context.newPage();
    await p.goto(base + '/', { waitUntil: 'domcontentloaded' });
    await p.waitForFunction(() => document.documentElement.dataset.ready === 'true');
    const cards = p.locator('.level-card');
    assert.equal(await cards.count(), 6);
    const first = cards.first();
    assert.equal(await first.evaluate(el => getComputedStyle(el).gridColumnStart), 'span 5');
    await first.scrollIntoViewIfNeeded();
    await p.waitForFunction(() => document.querySelector('.level-card')?.dataset.cosmosEnter === 'shown');
    await first.locator('img').evaluate(img => img.decode());
    await p.waitForFunction(() => document.querySelector('.level-card img')?.dataset.imageState === 'ready');
    if (await p.evaluate(() => matchMedia('(hover: hover) and (pointer: fine)').matches)) {
      await first.hover();
      await p.waitForFunction(() => document.querySelector('.level-card')?.dataset.cosmosSpotlight === 'active');
    }
    await p.emulateMedia({ reducedMotion: 'reduce' });
    await p.waitForFunction(() => !document.querySelector('[data-cosmos-enter], [data-cosmos-spotlight]'));
    assert.equal(await first.evaluate(el => getComputedStyle(el).animationName), 'none');
    for (const width of [320, 390, 768, 1440]) {
      await p.setViewportSize({ width, height: 844 });
      assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Overflow: ' + width);
    }
    await p.screenshot({ path: 'test-results/premium-desktop.png', fullPage: true });
  } finally { await context.close(); }
}
