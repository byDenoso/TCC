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
  console.log(
    'Explorador verificado em seis destinos, com WebGL 2, mapa 2D, teclado, viagem e largura móvel de 360 px.'
  );
} finally {
  await browser.close();
}
