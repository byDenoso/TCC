import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch(process.env.CHROMIUM
  ? { executablePath: process.env.CHROMIUM, headless: true }
  : { headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const problems = [];
let checked = 0;
page.on('response', response => {
  if (response.url().includes('/renders/') && ![200, 304].includes(response.status())) {
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
  for (let i = 0; i < 5; i++) {
    await page.locator(`[data-scale-step="${i}"]`).click();
    await page.waitForTimeout(1300);
    assert.equal(await page.locator('[data-scale-visual]:visible').count(), 1, `uma ilustração visível na escala ${i}`);
  }
  await page.goto(`${base}/capitulos/misterios-do-cosmos/`, { waitUntil: 'networkidle' });
  for (let i = 0; i < 4; i++) {
    await page.locator(`[data-evidence-select="${i}"]`).click();
    await loaded(`[data-evidence-panel="${i}"] img`);
  }
  await page.goto(`${base}/laboratorio/#tempo`, { waitUntil: 'networkidle' });
  for (let i = 0; i < 10; i++) {
    await page.locator(`[data-era-index="${i}"]`).click();
    await loaded('[data-era-render]');
    const state = await page.locator('[data-era-render]').evaluate(image => ({ src: image.src, srcset: image.srcset, current: image.currentSrc }));
    const file = state.src.slice(state.src.lastIndexOf('/') + 1);
    assert.ok(state.srcset.includes(file.replace('.webp', '-small.webp')), `srcset da era ${i}`);
    assert.ok(state.current.includes(file.replace('.webp', '')), `imagem exibida da era ${i}`);
  }
  await loaded('[data-star-render]');
  assert.deepEqual(problems, []);
  console.log(`${checked} imagens raster carregadas e decodificadas; srcsets da linha do tempo consistentes; zero erro HTTP de imagem.`);
} finally {
  await browser.close();
}
