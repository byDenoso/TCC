import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { openExtraExperiments } from './lib/reader-navigation.mjs';
import { installSceneQa,assertPausedScene,useStandardQuality } from './lib/scene-capture.mjs';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
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
    // Compilar o primeiro shader no SwiftShader pode bloquear mais de um quadro.
    await page.waitForFunction(first => Number(document.querySelector('[data-e-range]')?.value) > first, first, { timeout: 5000 });
    expect(Number(await range.inputValue()) > first, `${width}: expansão começa ao ficar visível`);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForFunction(() => document.querySelector('[data-e-play]')?.getAttribute('aria-pressed') === 'false');
    const stopped = await range.inputValue(); await page.waitForTimeout(250);
    expect(await range.inputValue() === stopped, `${width}: expansão pausa fora da tela`);
    await stage.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => document.querySelector('[data-e-play]')?.getAttribute('aria-pressed') === 'true');
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
  await lesson.waitForFunction(() => document.querySelector('[data-mx="origem-do-universo-o-universo"] [data-mx-play]')?.getAttribute('aria-pressed') === 'true');
  expect(await micro.locator('[data-mx-verdict]').isHidden(), 'animação automática não responde ao palpite');
  await lesson.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await lesson.waitForFunction(() => document.querySelector('[data-mx="origem-do-universo-o-universo"] [data-mx-play]')?.getAttribute('aria-pressed') === 'false');
  await lesson.waitForTimeout(450);
  expect((await micro.locator('[data-mx-live]').textContent()).trim() === '', 'pausa automática não anuncia conteúdo fora da tela');
  await micro.locator('.mx-stage').first().scrollIntoViewIfNeeded();
  await lesson.waitForFunction(() => document.querySelector('[data-mx="origem-do-universo-o-universo"] [data-mx-play]')?.getAttribute('aria-pressed') === 'true');
  await micro.locator('[data-mx-play]').click();
  await lesson.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await micro.locator('.mx-stage').first().scrollIntoViewIfNeeded(); await lesson.waitForTimeout(250);
  expect(await pressed(micro.locator('[data-mx-play]')) === 'false', 'microexperiência mantém a pausa escolhida');
  await micro.locator('[data-mx-play]').click();
  await micro.locator('[data-mx-range]').fill('1.5');
  expect(Number(await micro.locator('[data-mx-range]').inputValue()) === 1.5 && await pressed(micro.locator('[data-mx-play]')) === 'false', 'controle manual mantém o valor escolhido durante a animação');
  await lesson.close();

  const sky = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: 'no-preference' });
  await sky.goto(`${base}/capitulos/origem-do-universo/#origem-do-universo-primeira-luz`, { waitUntil: 'domcontentloaded' });
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

  const solar = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: 'no-preference' });
  await installSceneQa(solar);
  const errors = []; solar.on('pageerror', error => errors.push(String(error)));
  await solar.goto(`${base}/capitulos/sistema-solar/#sistema-solar-sol-e-planetas`, { waitUntil: 'domcontentloaded' });
  await openExtraExperiments(solar);
  const earthStage = solar.locator('[data-solar-stage]'); await earthStage.scrollIntoViewIfNeeded();
  await earthStage.locator('.cosmos-volume').waitFor();
  const earthPlay = solar.locator('[data-solar-play]');
  await solar.waitForFunction(() => document.querySelector('[data-solar-play]')?.getAttribute('aria-pressed') === 'true');
  expect(await pressed(earthPlay) === 'true', 'rotação da Terra inicia com a cena 3D visível');
  assert.equal(await earthStage.getAttribute('data-cosmos-quality'),'auto','a cena inicia em qualidade automática');
  await earthPlay.click(); await earthStage.scrollIntoViewIfNeeded();
  assert.equal(await pressed(earthPlay),'false','a pausa manual interrompe a rotação');
  await useStandardQuality(earthStage,solar.locator('[data-solar-studio]'),'Autoplay Solar 1280','world');
  assert.equal(await pressed(earthPlay),'false','a cena permanece pausada após selecionar a qualidade');
  if (process.env.EARTH_CAPTURE) await earthStage.screenshot({ path: process.env.EARTH_CAPTURE });
  await assertPausedScene(earthStage.locator('canvas'),'Autoplay Solar 1280',250); checks++;
  expect(errors.length === 0, `a cena 3D não produz erros: ${errors.join('; ')}`);
  await solar.close();

  const stillEarth = await browser.newPage({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce' });
  await stillEarth.goto(`${base}/capitulos/sistema-solar/#sistema-solar-sol-e-planetas`, { waitUntil: 'domcontentloaded' });
  await openExtraExperiments(stillEarth);
  await stillEarth.locator('[data-solar-stage]').scrollIntoViewIfNeeded();
  await stillEarth.locator('[data-solar-stage] .cosmos-volume').waitFor(); await stillEarth.waitForTimeout(300);
  expect(await pressed(stillEarth.locator('[data-solar-play]')) === 'false', 'a Terra não gira sozinha com movimento reduzido');
  await stillEarth.close();

  const fallback = await browser.newPage({ viewport: { width: 390, height: 900 } });
  await fallback.route('**/models/mundos.glb', route => route.abort());
  await fallback.goto(`${base}/capitulos/sistema-solar/#sistema-solar-sol-e-planetas`, { waitUntil: 'domcontentloaded' });
  await openExtraExperiments(fallback);
  await fallback.locator('[data-solar-stage]').scrollIntoViewIfNeeded();
  await fallback.waitForFunction(() => document.querySelector('[data-solar-play]')?.disabled === true);
  expect(await fallback.locator('[data-solar-poster]').isVisible(), 'imagem da Terra continua visível quando o modelo 3D falha');
  expect(/indisponível/.test(await fallback.locator('[data-solar-play]').innerText()), 'controle explica quando não há rotação 3D');
  expect(await fallback.locator('[data-solar-reset]').isDisabled(), 'reiniciar rotação também fica indisponível sem 3D');
  await fallback.close();

  console.log(`${checks} verificações de animação por visibilidade OK.`);
} finally { await browser.close(); }
