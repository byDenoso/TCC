import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const site = new URL(process.env.BASE_URL || 'http://localhost:3000');
const explorer = new URL((site.pathname.replace(/\/$/, '') || '') + '/explorador/', site);
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_EXECUTABLE || undefined,
  args: ['--no-zygote', '--disable-dev-shm-usage', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});

const ids = ['solar', 'trappist', 'orion', 'm31', 'virgo', 'teia'];

try {
  const desktop = await browser.newPage({ viewport: { width: 1350, height: 900 } });
  const errors = [];
  desktop.on('pageerror', (error) => errors.push(error.message));
  desktop.on('console', (message) => {
    if (message.type() === 'error' && /shader|WebGLProgram|hydration/i.test(message.text())) errors.push(message.text());
  });

  await desktop.goto(explorer.href + '#trappist');
  await desktop.waitForFunction(() => document.documentElement.dataset.ready === 'true');
  const trappist = desktop.locator('#trappist');
  const orbitHeading = trappist.getByRole('heading', { name: 'TRAPPIST-1', exact: true });
  assert.equal(await desktop.locator('.atlas-chapter').count(), 6);
  assert.equal(await desktop.locator('.atlas-chapter canvas').count(), 0);
  await orbitHeading.scrollIntoViewIfNeeded();
  const start = await desktop.evaluate(() => ({
    y: scrollY,
    h: document.documentElement.scrollHeight,
    view: innerHeight,
  }));
  assert(start.y > 0 && start.h / start.view > 4, 'Link direto abre um capítulo de um atlas longo');
  await trappist.getByRole('button', { name: 'TRAPPIST-1 h na imagem' }).click();
  assert.match(await trappist.locator('.atlas-values').innerText(), /0,06189 au/);
  await trappist.getByRole('button', { name: 'Trânsito', exact: true }).click();
  const marker = trappist.locator('svg[aria-label^="Simulação de trânsito"] circle').last();
  const before = await marker.getAttribute('cx');
  await trappist.getByRole('slider', { name: 'Tempo do trânsito em minutos' }).press('End');
  assert.notEqual(await marker.getAttribute('cx'), before);
  assert.match(await trappist.locator('output').innerText(), /\+75 min/);
  await trappist.getByRole('button', { name: 'Órbitas', exact: true }).click();
  await trappist.getByRole('slider', { name: 'Tempo transcorrido em dias' }).press('End');
  assert.match(await trappist.locator('output').innerText(), /20 dias/);

  const solar = desktop.locator('#solar');
  await solar.getByRole('button', { name: 'Órbitas', exact: true }).click();
  await solar.getByRole('button', { name: 'Netuno', exact: true }).click();
  assert.match(await solar.locator('.atlas-values').innerText(), /30,07 au/);
  await solar.getByRole('slider', { name: 'Tempo transcorrido em dias' }).press('End');
  assert.match(await solar.locator('output').innerText(), /365 dias/);
  await solar.getByLabel('Distâncias orbitais lineares').check();
  const rocky = solar.getByLabel('Enquadrar os quatro planetas rochosos');
  await rocky.check();
  assert.equal(await solar.locator('.exp-diagram polyline').count(), 4);
  await solar.getByRole('button', { name: 'Netuno', exact: true }).click();
  assert.equal(await solar.locator('.exp-diagram polyline').count(), 8);
  assert.equal(await rocky.isChecked(), false);

  const orion = desktop.locator('#orion');
  await orion.getByRole('button', { name: 'Infravermelho longo' }).click();
  assert.match(await orion.locator('img').getAttribute('src'), /orion-long\.webp/);
  await orion.getByRole('button', { name: 'Trapézio na imagem' }).click();
  await orion.getByRole('button', { name: 'Ampliar ponto' }).click();
  assert.equal(await orion.locator('.atlas-photo').getAttribute('data-zoom'), 'true');
  assert.match(await orion.locator('.atlas-reading').innerText(), /Trapézio/);

  const web = desktop.locator('#teia');
  await web.getByRole('button', { name: 'Fatias', exact: true }).click();
  await web.getByRole('slider', { name: 'Profundidade da fatia' }).press('End');
  assert.match(await web.locator('output').innerText(), /3 de 3/);
  await web.getByRole('button', { name: 'Volume 3D', exact: true }).click();
  await web.locator('canvas').waitFor();
  assert.equal(await desktop.locator('.atlas-chapter canvas').count(), 1);

  const guide = desktop.getByRole('region', { name: 'Viagem guiada', exact: true });
  const startGuide = desktop.getByRole('button', { name: 'Iniciar viagem guiada' });
  await startGuide.click();
  for (const id of ids) {
    assert.equal(new URL(desktop.url()).hash, '#' + id);
    assert.equal(await desktop.locator('#' + id).getByRole('region', { name: 'Viagem guiada', exact: true }).count(), 1);
    await guide.getByRole('button', { name: id === 'teia' ? 'Concluir viagem' : 'Próxima parada' }).click();
  }
  assert.match(await web.locator('.atlas-status').innerText(), /concluída/);
  assert.deepEqual(errors, []);

  const mobile = await browser.newPage({
    viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce',
  });
  await mobile.addInitScript(() => {
    const native = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      return kind.startsWith('webgl') ? null : native.call(this, kind, ...args);
    };
  });
  await mobile.goto(explorer.href + '#m31');
  await mobile.waitForFunction(() => document.documentElement.dataset.ready === 'true');
  await mobile.locator('#m31').getByRole('button', { name: 'Faixas de poeira', exact: true }).tap();
  await mobile.locator('#m31').getByRole('button', { name: 'Ampliar ponto' }).tap();
  assert.equal(await mobile.locator('#m31 .atlas-photo').getAttribute('data-zoom'), 'true');
  const mobileWeb = mobile.locator('#teia');
  await mobileWeb.getByRole('button', { name: 'Volume 3D', exact: true }).tap();
  assert.match(await mobileWeb.locator('.atlas-status').innerText(), /As fatias estão abertas/);
  assert.equal(await mobile.locator('canvas').count(), 0);
  for (const width of [320, 360, 721, 768]) {
    await mobile.setViewportSize({ width, height: 740 });
    const layout = await mobile.evaluate(() => ({
      content: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth,
    }));
    assert(layout.content <= layout.viewport, `Largura ${width} px: conteúdo ${layout.content} px, viewport ${layout.viewport} px`);
  }
  for (const id of ids) {
    await desktop.locator('#' + id).scrollIntoViewIfNeeded();
    for (const image of await desktop.locator('#' + id + ' img').all()) {
      await image.evaluate((img) => img.decode());
      assert(await image.evaluate((img) => img.naturalWidth > 0));
    }
  }
  await desktop.goto(site.href);
  assert.equal(await desktop.locator('.home-atlas-card').count(), 6);
  await desktop.locator('.home-atlas-orion').click();
  assert.equal(new URL(desktop.url()).hash, '#orion');
  console.log('Atlas verificado em seis capítulos, com fotos, órbitas, trânsitos, viagem, 3D opcional e fallback móvel.');
} finally {
  await browser.close();
}
