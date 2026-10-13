// Exercita os shaders de produção em WebGL (ANGLE/SwiftShader), inclusive no celular.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright';
import sharp from 'sharp';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
let checked = 0;
const still = async (canvas, label) => {
  await canvas.page().waitForTimeout(100);
  const a = await canvas.screenshot();
  await canvas.page().waitForTimeout(450);
  const b = await canvas.screenshot();
  assert.deepEqual(await sharp(a).raw().toBuffer(), await sharp(b).raw().toBuffer(), `${label}: pausa congela todos os pixels`);
  const { channels } = await sharp(a).stats();
  assert.ok(channels.slice(0, 3).some(c => c.stdev > 4), `${label}: cena tem conteúdo gráfico`);
  checked += 2;
};
try {
  for (const width of [390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'no-preference', colorScheme: 'dark' });
    const errors = [];
    page.on('pageerror', e => { if (!/Transition was aborted/.test(String(e))) errors.push(String(e)); });
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(`${base}/?lab=tempo&z=0.5#observatorio`, { waitUntil: 'networkidle' });
    const tempo = page.locator('[data-t-3d]');
    const canvas = tempo.locator('canvas');
    await canvas.waitFor({ state: 'visible' });
    await tempo.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    await tempo.locator('[data-3d-play]').click();
    await still(canvas, `tempo ${width}`);
    const before = await canvas.screenshot();
    await tempo.locator('[data-3d-play]').click();
    await page.waitForTimeout(300);
    assert.notDeepEqual(await canvas.screenshot(), before, 'continuar retoma a viagem'); checked++;
    await tempo.locator('[data-3d-play]').click();
    mkdirSync('docs/screenshots', { recursive: true });
    await tempo.screenshot({ path: `docs/screenshots/render-tempo-${width}.png` });
    await canvas.evaluate(c => c.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await page.waitForFunction(() => document.querySelector('[data-t-3d]').hidden);
    assert.equal(await page.locator('[data-t-svg]').getAttribute('viewBox'), '0 0 640 420'); checked++;

    await page.goto(`${base}/capitulos/galaxias-e-nebulosas/`, { waitUntil: 'networkidle' });
    const root = page.locator('[data-mx="galaxias-e-nebulosas-teia-cosmica"]');
    // Seleciona o passo que contém a teia a partir da estrutura da própria aula.
    const dot = await root.evaluate(r => [...document.querySelectorAll('.lesson-section')].indexOf(r.closest('.lesson-section')));
    await page.locator(`[data-step-dot="${dot}"]`).click();
    await root.scrollIntoViewIfNeeded();
    const web = root.locator('.mx-gl');
    await web.waitFor({ state: 'visible' });
    await root.locator('[data-mx-range]').focus(); await page.keyboard.press('End');
    for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowLeft');
    await root.locator('[data-mx-play]').click();
    await page.waitForTimeout(350);
    await root.locator('[data-mx-play]').click();
    await still(web, `teia ${width}`);
    await root.locator('[data-mx-range]').focus(); await page.keyboard.press('End');
    const { data, info } = await sharp(await web.screenshot()).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    let clipped = 0, colored = 0;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      if (Math.min(r, g, b) > 245) clipped++;
      if (Math.max(r, g, b) > 25 && Math.max(r, g, b) - Math.min(r, g, b) > 15) colored++;
    }
    assert.ok(clipped / (info.width * info.height) < 0.01, 'aglomerados preservam textura sem áreas brancas estouradas'); checked++;
    assert.ok(colored > 100, 'cores dos filamentos e aglomerados permanecem visíveis'); checked++;
    await root.locator('.mx-stage').screenshot({ path: `docs/screenshots/render-teia-${width}.png` });
    await web.evaluate(c => c.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await page.waitForFunction(() => !document.querySelector('[data-mx="galaxias-e-nebulosas-teia-cosmica"] .mx-stage').classList.contains('mx-stage--gl'));
    assert.ok(await root.locator('.mx-flat circle').first().isVisible()); checked++;
    assert.deepEqual(errors, [], `sem erros de shader ${width}`); checked++;
    await page.context().close();
  }
  console.log(`${checked} verificações WebGL: shaders, pausa completa, retomada, cor, saturação e perda de contexto; 390 e 1440 px.`);
} finally { await browser.close(); }
