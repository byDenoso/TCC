import assert from 'node:assert/strict';

export async function verifyHero(browser, base) {
  const context = await browser.newContext({
    viewport: { width: 665, height: 820 },
    reducedMotion: 'no-preference',
  });
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'hardwareConcurrency', { value: 8, configurable: true });
  });
  const page = await context.newPage();
  const scenes = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith('/cosmos-hero/')) scenes.push(path.split('/').pop());
  });
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  const slider = page.getByRole('slider', { name: 'Inclinação dos anéis' });
  await slider.waitFor();
  assert.deepEqual([...scenes].sort(), ['campo-estelar.webp', 'saturno-24-small.webp']);
  const bounds = await page.locator('.hero-actions').boundingBox();
  const planet = await page.locator('.cosmos-sky__world').boundingBox();
  assert(planet.y >= bounds.y + bounds.height, 'Os controles de navegação ficam acima da cena a 665 px');
  await slider.focus();
  await slider.press('ArrowRight');
  await page.locator('.cosmos-sky[data-view="28"]').waitFor();
  await page.waitForFunction(
    () =>
      document.querySelector('.cosmos-sky__canvas--live') ||
      document.querySelector('.cosmos-sky img').currentSrc.endsWith('/saturno-28.webp')
  );
  if (await page.locator('.cosmos-sky__canvas--live').count()) {
    assert(scenes.includes('saturno-mapa.webp'));
    assert(!scenes.includes('saturno-28.webp'), 'O renderizador 3D dispensa o quadro 2D alternativo');
  }
  await context.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      return type.startsWith('webgl') ? null : original.call(this, type, ...args);
    };
  });
  await page.reload({ waitUntil: 'networkidle' });
  scenes.length = 0;
  await slider.focus();
  await slider.press('ArrowRight');
  await page.waitForFunction(() => {
    const img = document.querySelector('.cosmos-sky img');
    return img.complete && img.currentSrc.endsWith('/saturno-28.webp');
  });
  assert(
    !scenes.includes('saturno-mapa.webp'),
    'Sem WebGL, o navegador pede apenas o quadro alternativo'
  );
  await page.getByRole('button', { name: 'Abrir menu' }).click();
  await page.locator('#mobile-menu').waitFor();
  await page.keyboard.press('Escape');
  assert(!(await page.locator('#mobile-menu').isVisible()));
  assert.equal(await page.evaluate(() => document.activeElement?.tagName), 'SUMMARY');
  const staticContext = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 320, height: 740 },
  });
  const staticPage = await staticContext.newPage();
  await staticPage.goto(base + '/');
  assert(await staticPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await staticPage.getByRole('button', { name: 'Abrir menu' }).click();
  await staticPage.locator('#mobile-menu').getByRole('link', { name: 'Trilhas' }).click();
  assert.equal(new URL(staticPage.url()).pathname, '/trilhas/');
  // The suite owns the browser and closes both contexts in its finally block.
}
