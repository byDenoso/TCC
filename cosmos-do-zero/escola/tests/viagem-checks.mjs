import assert from 'node:assert/strict';

/** Viagem guiada da página inicial: estações, modelos sob demanda, navegação livre e alternativas. */
export async function verifyViagem(browser, base) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
  try {
    const page = await context.newPage();
    const modelos = [];
    page.on('request', (r) => {
      const path = new URL(r.url()).pathname;
      if (path.startsWith('/viagem/') && path.endsWith('.glb')) modelos.push(path.split('/').pop());
    });
    await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.documentElement.dataset.ready === 'true');
    assert.equal(await page.locator('.viagem-estacao').count(), 9);
    assert.equal(modelos.length, 0, 'Nenhum modelo 3D é pedido antes de a viagem entrar na tela');

    // modo guiado: começar, ver o modelo substituir o pôster, mexer no controle e seguir
    await page.getByRole('link', { name: 'Começar a viagem', exact: true }).click();
    await page.waitForFunction(() => location.hash === '#luz');
    await page.waitForFunction(() => document.querySelector('.viagem-palco canvas'));
    await page.waitForFunction(() => !document.querySelector('.viagem-poster[data-visivel="sim"]'), null, { timeout: 60000 });
    assert(modelos.includes('luz.glb'));
    const tempo = page.getByRole('slider', { name: 'Tempo desde o disparo' });
    await tempo.focus();
    await tempo.press('End');
    await page.locator('#luz .viagem-leituras').getByText('383.734').waitFor();
    await page.getByRole('link', { name: 'Próxima estação: Sistema Solar', exact: true }).click();
    await page.waitForFunction(() => location.hash === '#sistema-solar');
    await page.locator('.viagem-trilho > ol a[aria-current]').filter({ hasText: 'Sistema Solar' }).waitFor();

    // navegação livre pelo índice e por link direto
    await page.getByText('Escolher por onde seguir', { exact: true }).click();
    await page.locator('.viagem-indice').getByRole('link', { name: /A luz mais antiga/ }).click();
    await page.waitForFunction(() => location.hash === '#luz-fossil');
    await page.goto(base + '/#galaxias', { waitUntil: 'domcontentloaded' });
    await page.locator('.viagem-trilho > ol a[aria-current]').filter({ hasText: 'Galáxias' }).waitFor();
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 844 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Largura ' + width);
    }
  } finally {
    await context.close();
  }

  // sem WebGL: o pôster renderizado no Blender continua no palco
  const semGL = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'no-preference' });
  try {
    await semGL.addInitScript(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (type, ...args) {
        return String(type).startsWith('webgl') ? null : original.call(this, type, ...args);
      };
    });
    const page = await semGL.newPage();
    await page.goto(base + '/#saturno', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.documentElement.dataset.ready === 'true');
    await page.waitForFunction(() => document.querySelector('.viagem-poster[data-visivel="sim"]')?.getAttribute('src')?.endsWith('/saturno.webp'));
    assert.equal(await page.locator('.viagem-palco canvas').count(), 0);
    // o link direto termina de rolar depois da hidratação; só então a estação está na linha de leitura
    await page.waitForFunction(() => {
      const r = document.getElementById('saturno')?.getBoundingClientRect();
      return r && Math.abs(r.top - innerHeight * 0.56) < 40;
    });
    await page.getByRole('button', { name: 'Próxima estação' }).click();
    await page.waitForFunction(() => location.hash === '#estrelas');
  } finally {
    await semGL.close();
  }

  // sem JavaScript: texto completo das estações e menu funcional
  const estatico = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 320, height: 740 } });
  try {
    const page = await estatico.newPage();
    await page.goto(base + '/');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.equal(await page.locator('.viagem-estacao h3').count(), 9);
    await page.getByRole('button', { name: 'Abrir menu' }).click();
    await page.locator('#mobile-menu').getByRole('link', { name: 'Trilhas' }).click();
    assert.equal(new URL(page.url()).pathname, '/trilhas/');
  } finally {
    await estatico.close();
  }
}
