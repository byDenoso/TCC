// Exercita os shaders de produção em WebGL (ANGLE/SwiftShader), incluindo emulação de viewport390; não é celular físico.
import assert from 'node:assert/strict';
import {openExtraExperiments, selectLessonStep} from './lib/reader-navigation.mjs';
import { mkdirSync } from 'node:fs';
import {installGpuProbe} from './lib/gpu-probe.mjs';
import { chromium } from 'playwright';
import sharp from 'sharp';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const tempoOnly = process.env.COSMOS_GRAPHICS_TEMPO_ONLY === '1';
const cpuRate = Number(process.env.COSMOS_GRAPHICS_CPU_RATE ?? '1');
assert.ok(Number.isFinite(cpuRate) && cpuRate >= 1, 'CPU throttling rate must be at least 1');
const widths = process.env.COSMOS_GRAPHICS_WIDTH ? [Number(process.env.COSMOS_GRAPHICS_WIDTH)] : [390, 1440];
assert.ok(widths.every(width => [390, 1440].includes(width)), 'graphics test width must be 390 or 1440');
const browser = await chromium.launch({ executablePath:process.env.CHROMIUM||undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
let checked = 0;
const still = async (canvas, label) => {
  console.log('GRAPHICS_CASE',label); 
  await canvas.page().waitForTimeout(100);
  const a = await canvas.screenshot();
  await canvas.page().waitForTimeout(450);
  const b = await canvas.screenshot();
  const rawA=await sharp(a).raw().toBuffer(),rawB=await sharp(b).raw().toBuffer();assert.ok(rawA.equals(rawB),`${label}: pausa congela todos os pixels`);
  const { channels } = await sharp(a).stats();
  assert.ok(channels.slice(0, 3).some(c => c.stdev > 4), `${label}: cena tem conteúdo gráfico`);
  checked += 2;
};
try {
  for (const width of widths) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'no-preference', colorScheme: 'dark' });
    if(cpuRate>1){const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setCPUThrottlingRate',{rate:cpuRate});}
    await page.addInitScript(installGpuProbe);
    await page.addInitScript(() => localStorage.setItem('cosmos-theme', 'dark'));
    const errors = [];
    const warnings = [];
    const failedResources = [];
    page.on('pageerror', e => { if (!/Transition was aborted/.test(String(e))) errors.push(String(e)); });
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('console', m => { if (m.type() === 'warning') warnings.push(m.text()); });
    page.on('requestfailed', request => failedResources.push({ url: request.url(), error: request.failure()?.errorText }));
    await page.goto(`${base}/?lab=tempo&z=0.5#observatorio`, { waitUntil: 'networkidle' });
    const tempo = page.locator('[data-t-3d]');
    const canvas = tempo.locator('canvas');
    await page.locator('[data-station="tempo"] .obs-viz').scrollIntoViewIfNeeded();
    await canvas.waitFor({ state: 'visible' });
    await tempo.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    // Isolate pause from the separate automatic quality calibration: the latter
    // may legitimately replace textures after the animation has been stopped.
    const options=page.locator('[data-station="tempo"] .cosmos-view-options').first();
    await options.locator('summary').click();
    await options.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('standard');
    await tempo.scrollIntoViewIfNeeded();
    await page.waitForFunction(()=>{
      const stage=document.querySelector('[data-t-3d]');if(!stage)return false;
      const expected=stage.clientWidth<600?'768':'1536';
      return stage.dataset.cosmosQuality==='standard'&&stage.dataset.calibrationStatus==='manual'&&stage.dataset.qualityPending==='false'&&stage.dataset.textureQuality===expected;
    },null,{timeout:30000});
    if(await tempo.locator('[data-3d-play]').getAttribute('aria-pressed')==='true')await tempo.locator('[data-3d-play]').click();
    assert.equal(await tempo.locator('[data-3d-play]').getAttribute('aria-pressed'),'false','Tempo realmente pausado antes de verificar pixels');
    await still(canvas, `tempo ${width}`);
    const before = await canvas.screenshot();
    await tempo.locator('[data-3d-play]').click();
    await page.waitForTimeout(300);
    assert.ok(!(await canvas.screenshot()).equals(before), 'continuar retoma a viagem'); checked++;
    await tempo.locator('[data-3d-play]').click();
    mkdirSync('docs/screenshots', { recursive: true });
    await tempo.screenshot({ path: `docs/screenshots/render-tempo-${width}.png` });
    await canvas.evaluate(c => c.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await page.waitForFunction(() => document.querySelector('[data-t-3d]').hidden);
    assert.equal(await page.locator('[data-t-svg]').getAttribute('viewBox'), '0 0 640 420'); checked++;
    if(tempoOnly){assert.deepEqual(errors,[],`Tempo sem erros de shader ${width}`);await page.context().close();continue;}

    await page.goto(`${base}/capitulos/galaxias-e-nebulosas/`, { waitUntil: 'networkidle' });
    const root = page.locator('[data-mx="galaxias-e-nebulosas-teia-cosmica"]');
    // Seleciona o passo que contém a teia a partir da estrutura da própria aula.
    const dot = await root.evaluate(r => [...document.querySelectorAll('.lesson-section')].indexOf(r.closest('.lesson-section')));
    await selectLessonStep(page,dot);
    await root.locator('.mx-stage').first().scrollIntoViewIfNeeded();
    const web = root.locator('.mx-gl');
    try { await web.waitFor({ state: 'visible' }); }
    catch (error) {
      const state = await root.evaluate(root => ({
        root: { ...root.dataset },
        viewport: { height: innerHeight, width: innerWidth, scrollY },
        parentHidden: !!root.closest('[hidden]'),
        stages: [...root.querySelectorAll('.mx-stage')].map(stage => {
          const rect = stage.getBoundingClientRect();
          return { class: stage.className, data: { ...stage.dataset }, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height, canvas: !!stage.querySelector('canvas') };
        }),
        visualNotice: root.querySelector('[data-mx-visual-state]')?.textContent,
        activeContexts: document.documentElement.dataset.cosmosContexts,
        currentStep: document.querySelector('[data-step-select]')?.value,
      }));
      console.error('GRAPHICS_DIAGNOSTIC', JSON.stringify({ id: 'teia', width, state, errors, warnings, failedResources }));
      throw error;
    }
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
    assert.equal(await page.evaluate(()=>__GPU_PROBE.maxActive()),1,'máximo1WebGL real incluindo todos os caminhos');checked++;
    for (const [route, step, id] of [['vida-das-estrelas',2,'vida-das-estrelas-sol'],['terra-e-atmosfera',0,'terra-e-atmosfera-formacao-da-terra'],['sistema-solar',2,'sistema-solar-gigantes'],['origem-do-universo',2,'origem-do-universo-fase-quente']]) {
      await page.goto(`${base}/capitulos/${route}/`); await selectLessonStep(page, step);
      const module = page.locator(`[data-mx="${id}"]`), stage = module.locator('.mx-stage').first();
      await stage.scrollIntoViewIfNeeded();
      try { await stage.locator('.cosmos-volume').waitFor(); }
      catch (error) {
        const state = await module.evaluate(root => ({ booted:root.dataset.mxBooted, fallback:root.dataset.visualFallback, stages:[...root.querySelectorAll('.mx-stage')].map(el => ({ class:el.className, hidden:el.hidden, fallback:el.dataset.visualFallback, top:Math.round(el.getBoundingClientRect().top), bottom:Math.round(el.getBoundingClientRect().bottom), canvas:!!el.querySelector('.cosmos-volume') })) }));
        console.error('GRAPHICS_DIAGNOSTIC', JSON.stringify({ id, width, state, errors }));
        throw error;
      }
      await module.locator('[data-mx-reset]').click();
      await stage.scrollIntoViewIfNeeded();
      await still(stage.locator('.cosmos-volume'), `${id} ${width}`);
      assert.equal(await page.evaluate(() => __GPU_PROBE.active()), 1); checked++;
    }
    await page.goto(`${base}/capitulos/sistema-solar/#sistema-solar-sol-e-planetas`);await openExtraExperiments(page);const solar=page.locator('[data-solar-stage]');await solar.scrollIntoViewIfNeeded();await solar.locator('.cosmos-volume').waitFor();await page.locator('[data-solar-reset]').click();await solar.scrollIntoViewIfNeeded();await still(solar.locator('.cosmos-volume'),`Solar ${width}`);assert.equal(await page.evaluate(()=>__GPU_PROBE.maxActive()),1);checked++;
    assert.deepEqual(errors,[],`novas famílias sem erros de shader${width}`);checked++;
    await page.context().close();
  }
  console.log(tempoOnly?`${checked} verificações WebGL de Tempo: pausa, retomada e perda de contexto; ${widths.join(' e ')} px.`:`${checked} verificações WebGL: shaders, pausa completa, retomada, cor, saturação e perda de contexto; ${widths.join(' e ')} px.`);
} finally { await browser.close(); }
