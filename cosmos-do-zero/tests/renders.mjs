import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { openExtraExperiments } from './lib/reader-navigation.mjs';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  headless: true
});
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const problems = [];
let checked = 0;
page.on('response', response => {
  if (/\/(renders|posters|models)\//.test(response.url()) && ![200, 304].includes(response.status())) {
    problems.push(`HTTP ${response.status()} ${response.url()}`);
  }
});
const loaded = async selector => {
  await page.locator(selector).scrollIntoViewIfNeeded();
  await page.locator(selector).evaluate(image => image.decode());
  assert.ok(await page.locator(selector).evaluate(image => image.complete && image.naturalWidth > 0), selector);
  checked++;
};
try {
  const home = await page.goto(`${base}/`, { waitUntil: 'networkidle' });
  assert.ok(home?.ok(), `home retornou HTTP ${home?.status()}`);
  await page.goto(`${base}/capitulos/galaxias-e-nebulosas/`, { waitUntil: 'networkidle' });
  await openExtraExperiments(page);
  for (let i = 0; i < 5; i++) {
    await page.locator(`[data-scale-step="${i}"]`).click();
    await page.waitForFunction(() => document.querySelectorAll('[data-scale-visual][data-hidden="false"]').length === 1);
    assert.equal(await page.locator('[data-scale-visual][data-hidden="false"]').count(), 1, `um estado visual ativo na escala ${i}`);
    const selected = page.locator(`[data-scale-visual="${i}"]`);
    assert.ok(await selected.isVisible());
    const images = await selected.locator('image').all();
    assert.ok(images.length > 0);
    for (const node of images) {
      await node.evaluate(async node => {
        const image = new Image();
        image.src = node.href.baseVal;
        if (new URL(image.src).origin !== location.origin) throw Error(image.src);
        await image.decode();
      });
      checked++;
    }
  }
  await page.goto(`${base}/capitulos/misterios-do-cosmos/`, { waitUntil: 'networkidle' });
  await openExtraExperiments(page);
  for (let i = 0; i < 4; i++) {
    await page.locator(`[data-evidence-select="${i}"]`).click();
    await loaded(`[data-evidence-panel="${i}"] img`);
  }
  await page.goto(`${base}/laboratorio/#tempo`, { waitUntil: 'networkidle' });
  const eraCount = await page.locator('[data-era-index]').count();
  for (let i = 0; i < eraCount; i++) {
    await page.locator(`[data-era-index="${i}"]`).click();
    await loaded('[data-era-render]');
    const state = await page.locator('[data-era-render]').evaluate(image => ({ src: image.src, srcset: image.srcset, current: image.currentSrc }));
    const file = state.src.slice(state.src.lastIndexOf('/') + 1);
    assert.ok(state.srcset.includes(file.replace('.webp', '-small.webp')), `srcset da era ${i}`);
    assert.ok(state.current.includes(file.replace('.webp', '')), `imagem exibida da era ${i}`);
  }
  assert.ok(await page.locator('[data-star-svg] circle').count() > 0, 'cena estelar desenhada');
  assert.deepEqual(problems, []);
  console.log(`${checked} imagens raster carregadas e decodificadas; srcsets da linha do tempo consistentes; zero erro HTTP de imagem.`);
} finally {
  await browser.close();
}
