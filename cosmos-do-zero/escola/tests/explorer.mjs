import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const site = new URL(process.env.BASE_URL || 'http://localhost:3000');
const explorer = new URL((site.pathname.replace(/\/$/, '') || '') + '/explorador/', site);
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_EXECUTABLE || undefined,
  args: [
    '--no-zygote',
    '--disable-dev-shm-usage',
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
  ],
});

try {
  const desktop = await browser.newPage({ viewport: { width: 1350, height: 900 } });
  const errors = [];
  await desktop.addInitScript(() => {
    window.explorerDraws = 0;
    for (const method of [
      'drawArrays',
      'drawElements',
      'drawArraysInstanced',
      'drawElementsInstanced',
    ]) {
      const native = WebGL2RenderingContext.prototype[method];
      WebGL2RenderingContext.prototype[method] = function (...args) {
        window.explorerDraws++;
        return native.apply(this, args);
      };
    }
  });
  desktop.on('pageerror', (error) => errors.push(error.message));
  desktop.on('console', (message) => {
    if (message.type() === 'error' && /shader|WebGLProgram|hydration/i.test(message.text()))
      errors.push(message.text());
  });
  await desktop.goto(explorer.href);
  await desktop.getByRole('heading', { name: 'Explorador do Universo' }).waitFor();
  await desktop.getByRole('combobox', { name: 'Planeta' }).selectOption({ label: 'Netuno' });
  assert.match(await desktop.locator('.exp-body-values').innerText(), /30,07 au/);
  await desktop.getByRole('slider', { name: 'Tempo transcorrido em dias' }).press('End');
  assert.match(await desktop.locator('.exp-orbits output').innerText(), /365 dias/);
  await desktop.getByRole('button', { name: 'Aproximar', exact: true }).click();
  assert.match(await desktop.locator('.exp-map-footer').innerText(), /1,2×/);
  await desktop.getByRole('button', { name: 'Restaurar câmera' }).click();
  await desktop.getByLabel('Distâncias orbitais lineares').check();
  const rocky = desktop.getByLabel('Enquadrar os quatro planetas rochosos');
  await rocky.check();
  assert.equal(await desktop.locator('.exp-diagram polyline').count(), 4);
  assert.equal(await desktop.getByRole('combobox', { name: 'Planeta' }).inputValue(), '2');
  await desktop.getByRole('combobox', { name: 'Planeta' }).selectOption({ label: 'Netuno' });
  assert.equal(await desktop.locator('.exp-diagram polyline').count(), 8);
  assert.equal(await rocky.isChecked(), false);
  await desktop.getByRole('button', { name: 'Iniciar viagem' }).click();
  await desktop.getByRole('button', { name: 'Teia cósmica', exact: true }).click();
  assert.equal(await desktop.getByRole('button', { name: 'Concluir viagem' }).count(), 0);
  await desktop.getByRole('button', { name: 'Iniciar viagem' }).click();
  for (const name of [
    'TRAPPIST-1',
    'Nebulosa de Órion',
    'Galáxia de Andrômeda',
    'Aglomerado de Virgem',
    'Teia cósmica',
  ]) {
    await desktop.getByRole('button', { name: 'Próxima parada' }).click();
    assert.equal(await desktop.locator('.exp-dossier h2').innerText(), name);
  }
  await desktop.getByRole('button', { name: 'Concluir viagem' }).click();
  assert.match(await desktop.locator('.exp-status').innerText(), /concluída/);
  await desktop.getByRole('button', { name: 'Iniciar viagem' }).click();
  assert.equal(await desktop.locator('.exp-status').count(), 0);
  await desktop.getByRole('button', { name: 'Órion', exact: true }).click();
  await desktop.getByRole('button', { name: 'Cena 3D' }).click();
  await desktop.locator('.exp-surface canvas').waitFor();
  for (const name of ['Sistema Solar', 'TRAPPIST-1', 'Andrômeda', 'Virgem', 'Teia cósmica']) {
    await desktop.getByRole('button', { name, exact: true }).click();
    await desktop.locator('.exp-surface canvas').waitFor();
    await desktop.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    );
  }
  await desktop.waitForFunction(() => window.explorerDraws > 0);
  await desktop.waitForTimeout(1200);
  const draws = await desktop.evaluate(() => window.explorerDraws);
  await desktop.waitForTimeout(300);
  assert.equal(await desktop.evaluate(() => window.explorerDraws), draws);
  await desktop
    .locator('.exp-surface canvas')
    .evaluate((canvas) => canvas.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
  await desktop.locator('.exp-diagram').waitFor();
  const open3D = desktop.getByRole('button', { name: 'Cena 3D' });
  assert(await open3D.isEnabled());
  await open3D.click();
  await desktop.locator('.exp-surface canvas').waitFor();
  assert.deepEqual(errors, []);

  const mobile = await browser.newPage({
    viewport: { width: 360, height: 740 },
    isMobile: true,
    hasTouch: true,
    reducedMotion: 'reduce',
  });
  await mobile.addInitScript(() => {
    const native = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      return kind.startsWith('webgl') ? null : native.call(this, kind, ...args);
    };
  });
  explorer.hash = 'm31';
  await mobile.goto(explorer.href);
  await mobile.getByRole('heading', { name: 'Galáxia de Andrômeda', exact: true }).waitFor();
  await mobile.getByRole('button', { name: 'Cena 3D' }).click();
  await mobile.locator('.exp-diagram').waitFor();
  assert.match(await mobile.locator('.exp-status').innerText(), /mapa 2D/);
  assert(await mobile.getByRole('button', { name: 'Cena 3D' }).isDisabled());
  await mobile.locator('.exp-surface').focus();
  await mobile.keyboard.press('ArrowUp');
  assert.equal(await mobile.getByRole('slider', { name: 'Inclinação da câmera' }).inputValue(), '35');
  for (const name of ['Órion', 'Teia cósmica', 'TRAPPIST-1', 'Virgem', 'Sistema Solar']) {
    await mobile.getByRole('button', { name, exact: true }).click();
    assert(
      await mobile.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth
      )
    );
  }
  for (const width of [320, 721, 768]) {
    await mobile.setViewportSize({ width, height: 740 });
    await mobile.getByRole('button', { name: 'Teia cósmica', exact: true }).click();
    assert(
      await mobile.evaluate(() => {
        const label = document.querySelector('.exp-map-caption').getBoundingClientRect();
        const mode = document.querySelector('.exp-mode').getBoundingClientRect();
        return (
          label.right <= mode.left &&
          document.documentElement.scrollWidth <= document.documentElement.clientWidth
        );
      })
    );
  }
  await mobile.setViewportSize({ width: 320, height: 650 });
  await mobile.getByRole('button', { name: 'Iniciar viagem' }).tap();
  await mobile.getByRole('button', { name: 'Próxima parada' }).tap();
  assert(
    await mobile.evaluate(() => {
      const map = document.querySelector('.exp-map').getBoundingClientRect();
      return map.bottom > 0 && map.top < document.documentElement.clientHeight;
    })
  );
  console.log(
    'Explorador verificado em seis destinos, com WebGL 2, mapa 2D, teclado, viagem e largura móvel de 360 px.'
  );
} finally {
  await browser.close();
}
