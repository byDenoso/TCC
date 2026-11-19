import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { openExtraExperiments } from './lib/reader-navigation.mjs';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
let checks = 0;
const expect = (value, message) => { assert.ok(value, message); checks++; };
const pressed = locator => locator.getAttribute('aria-pressed');

try {
  for (const width of [390, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'no-preference' });
    await page.goto(`${base}/observatorio/?lab=expansao`, { waitUntil: 'domcontentloaded' });
    const panel = page.locator('[data-station="expansao"]');
    const stage = panel.locator('[data-e-volume]');
    const play = panel.locator('[data-e-play]');
    const range = panel.locator('[data-e-range]');
    await page.waitForFunction(() => document.querySelector('[data-station="expansao"]')?.dataset.stationReady === 'true');
    await page.waitForTimeout(250);
    expect(await pressed(play) === 'false' && Number(await range.inputValue()) === 1, `${width}: expansão espera entrar na tela`);
    await stage.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => document.querySelector('[data-e-play]')?.getAttribute('aria-pressed') === 'true', null, { timeout: 5000 });
    const first = Number(await range.inputValue());
    await page.waitForFunction(first => Number(document.querySelector('[data-e-range]')?.value) > first, first, { timeout: 5000 });
    expect(Number(await range.inputValue()) > first, `${width}: expansão começa ao ficar visível`);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForFunction(() => document.querySelector('[data-e-play]')?.getAttribute('aria-pressed') === 'false');
    const stopped = await range.inputValue(); await page.waitForTimeout(250);
    expect(await range.inputValue() === stopped, `${width}: expansão pausa fora da tela`);
    await stage.scrollIntoViewIfNeeded();
    // Em 390 px o botão fica abaixo da dobra: o clique rolaria a página, a cena sairia
    // de vista e a pausa automática disputaria com o clique. Cena e botão ficam juntos na tela.
    await page.evaluate(() => window.scrollBy({ top: document.querySelector('[data-e-volume]').getBoundingClientRect().top - 16, behavior: 'instant' }));
    await page.waitForFunction(() => document.querySelector('[data-e-play]')?.getAttribute('aria-pressed') === 'true');
    expect(await play.evaluate(node => { const box = node.getBoundingClientRect(); return box.top >= 0 && box.bottom <= innerHeight; }), `${width}: cena e botão de pausa cabem juntos na tela`);
    await play.click();
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await stage.scrollIntoViewIfNeeded(); await page.waitForTimeout(250);
    expect(await pressed(play) === 'false', `${width}: pausa manual permanece ao voltar`);
    await range.fill('1.5'); await page.waitForTimeout(150);
    expect(await pressed(play) === 'false' && Number(await range.inputValue()) === 1.5, `${width}: controle manual não é sobrescrito`);
    await page.close();
  }

  const reduced = await browser.newPage({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
  await reduced.goto(`${base}/observatorio/?lab=expansao`, { waitUntil: 'domcontentloaded' });
  const reducedStage = reduced.locator('[data-e-volume]'); await reducedStage.scrollIntoViewIfNeeded();
  await reduced.waitForFunction(() => document.querySelector('[data-station="expansao"]')?.dataset.stationReady === 'true');
  await reduced.waitForTimeout(350);
  expect(await pressed(reduced.locator('[data-e-play]')) === 'false' && Number(await reduced.locator('[data-e-range]').inputValue()) === 1, 'movimento reduzido não inicia sozinho');
  await reduced.close();

  const lesson = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: 'no-preference' });
  await lesson.goto(`${base}/capitulos/origem-do-universo/#origem-do-universo-o-universo`, { waitUntil: 'domcontentloaded' });
  const micro = lesson.locator('[data-mx="origem-do-universo-o-universo"]');
  await micro.locator('.mx-stage').first().scrollIntoViewIfNeeded();
  expect(await pressed(micro.locator('[data-mx-play]')) === 'false', 'primeira interação aguarda o aluno');
  await micro.locator('[data-mx-play]').click();
  await lesson.waitForFunction(() => document.querySelector('[data-mx="origem-do-universo-o-universo"] [data-mx-play]')?.getAttribute('aria-pressed') === 'true');
  expect(await micro.locator('[data-mx-verdict]').isHidden(), 'animação automática não responde ao palpite');
  await lesson.locator('footer').scrollIntoViewIfNeeded();
  await lesson.waitForFunction(() => document.querySelector('[data-mx="origem-do-universo-o-universo"] [data-mx-play]')?.getAttribute('aria-pressed') === 'false');
  await lesson.waitForTimeout(450);
  expect((await micro.locator('[data-mx-live]').textContent()).trim() === '', 'pausa automática não anuncia conteúdo fora da tela');
  await micro.locator('.mx-stage').first().scrollIntoViewIfNeeded();
  await lesson.waitForFunction(() => document.querySelector('[data-mx="origem-do-universo-o-universo"] [data-mx-play]')?.getAttribute('aria-pressed') === 'true');
  await micro.locator('[data-mx-play]').click();
  await lesson.locator('footer').scrollIntoViewIfNeeded();
  await micro.locator('.mx-stage').first().scrollIntoViewIfNeeded(); await lesson.waitForTimeout(250);
  expect(await pressed(micro.locator('[data-mx-play]')) === 'false', 'microexperiência mantém a pausa escolhida');
  await micro.locator('[data-mx-play]').click();
  await micro.locator('[data-mx-range]').fill('1.5');
  expect(Number(await micro.locator('[data-mx-range]').inputValue()) === 1.5 && await pressed(micro.locator('[data-mx-play]')) === 'false', 'controle manual mantém o valor escolhido durante a animação');
  await lesson.close();

  const sky = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: 'no-preference' });
  await sky.goto(`${base}/capitulos/origem-do-universo/#origem-do-universo-primeira-luz`, { waitUntil: 'domcontentloaded' });
  await openExtraExperiments(sky);
  await sky.locator('[data-cmbj-stage]').scrollIntoViewIfNeeded();
  await sky.waitForFunction(() => document.querySelector('[data-cmbj-play]')?.getAttribute('aria-pressed') === 'true');
  expect(await pressed(sky.locator('[data-cmbj-play]')) === 'true', 'luz antiga começa quando a cena aparece');
  await sky.locator('[data-cmbj-play]').click();
  await sky.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await sky.locator('[data-cmbj-stage]').scrollIntoViewIfNeeded(); await sky.waitForTimeout(250);
  expect(await pressed(sky.locator('[data-cmbj-play]')) === 'false', 'pausa manual da luz antiga é respeitada');
  await sky.close();

  const stars = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: 'no-preference' });
  await stars.goto(`${base}/laboratorio/#estrelas`, { waitUntil: 'domcontentloaded' });
  await stars.locator('[data-star-svg]').scrollIntoViewIfNeeded();
  await stars.waitForFunction(() => document.querySelector('[data-star-play]')?.getAttribute('aria-pressed') === 'true');
  expect(await pressed(stars.locator('[data-star-play]')) === 'true', 'ciclo estelar começa ao aparecer');
  await stars.locator('[data-star-mass]').fill('2'); await stars.waitForTimeout(200);
  expect(await pressed(stars.locator('[data-star-play]')) === 'false', 'ajustar a estrela interrompe a animação automática');
  await stars.close();

  const solar = await browser.newPage({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
  await solar.goto(`${base}/capitulos/sistema-solar/#sistema-solar-sol-e-planetas`, { waitUntil: 'domcontentloaded' });
  await openExtraExperiments(solar);
  const studio = solar.locator('[data-solar-studio]');
  const image = studio.locator('[data-solar-poster]');
  const play = studio.locator('[data-solar-play]');
  await image.scrollIntoViewIfNeeded();
  const waitFrame = file => solar.waitForFunction(file => {
    const poster = document.querySelector('[data-solar-poster]');
    return poster instanceof HTMLImageElement && poster.complete && poster.naturalWidth > 0 && poster.currentSrc.endsWith(file);
  }, '/solar-turntable/terra/' + file);
  await waitFrame('00.webp');
  expect(await pressed(play) === 'false', 'a Terra espera o comando com movimento reduzido');
  await play.click();
  await waitFrame('01.webp');
  expect(await pressed(play) === 'false', 'Avançar troca um quadro e mantém a pausa');
  await studio.locator('[data-solar-reset]').click();
  await waitFrame('00.webp');
  expect(await studio.locator('[data-world-angle]').inputValue() === '0', 'reiniciar restaura o ângulo e a imagem');
  await solar.close();

  console.log(`${checks} verificações de animação por visibilidade OK.`);
} finally { await browser.close(); }
