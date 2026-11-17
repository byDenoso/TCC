// Browser integration exercising the production PlayCanvas renderer and its SVG fallbacks.
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import sharp from 'sharp';
import {installGpuProbe} from './lib/gpu-probe.mjs';
import {selectLessonStep,activateMicro3D} from './lib/reader-navigation.mjs';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const browser = await chromium.launch({
  executablePath:process.env.CHROMIUM || undefined,
  args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'],
});
const rows = [];
const experiments = [
  {chapter:'origem-do-universo', id:'origem-do-universo-fase-quente', step:2},
  {chapter:'vida-das-estrelas', id:'vida-das-estrelas-sol', step:2},
  {chapter:'sistema-solar', id:'sistema-solar-orbitas', anchor:true},
];

async function open(mode) {
  const page = await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
  const errors = [];
  page.on('pageerror', error => errors.push(error.stack || error.message));
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.addInitScript(installGpuProbe);
  await page.addInitScript(mode => {
    window.__WEBGPU_REQUESTS = 0;
    Object.defineProperty(navigator,'gpu',{configurable:true,value:{requestAdapter(){
      window.__WEBGPU_REQUESTS++;
      throw new Error('PlayCanvas WebGL should not request WebGPU');
    }}});
    if (mode === 'no-webgl') {
      const getContext = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type,...args) {
        return /^(webgl2?|experimental-webgl)$/.test(type) ? null : getContext.call(this,type,...args);
      };
    }
  }, mode);
  return {page,errors};
}

async function openExperiment(page, {chapter,id,step,anchor}) {
  await page.goto(base + '/capitulos/' + chapter + '/' + (anchor ? '#' + id : ''));
  if (step !== undefined) await selectLessonStep(page,step);
  await activateMicro3D(page,id);
  const experiment = page.locator('[data-mx="' + id + '"]');
  const stage = experiment.locator('.mx-volume-stage');
  try { await stage.scrollIntoViewIfNeeded({timeout:5000}); }
  catch (error) { if (await stage.getAttribute('data-visual-fallback') !== 'true') throw error; }
  return {experiment,stage,canvas:experiment.locator('.cosmos-volume')};
}

async function assertDiagram(experiment) {
  const svg = experiment.locator('[data-mx-svg]');
  await svg.waitFor({state:'visible'});
  const before = await svg.evaluate(element => element.innerHTML);
  await experiment.locator('[data-mx-opt="1"]').click();
  assert.notEqual(await svg.evaluate(element => element.innerHTML), before,
    'the existing learner control still changes the SVG after renderer failure');
}

try {
  for (const [index,spec] of experiments.entries()) {
    const {page,errors} = await open('context-loss');
    const {experiment,stage,canvas} = await openExperiment(page,spec);
    try { await canvas.waitFor({timeout:30000}); }
    catch (error) {
      console.error(spec.id,await stage.evaluate(element => ({...element.dataset, hidden:element.hidden})),errors);
      throw error;
    }
    assert.equal(await stage.getAttribute('data-renderer-engine'),'playcanvas');
    assert.equal(await stage.getAttribute('data-renderer'),'webgl2');
    const detail = (await sharp(await canvas.screenshot()).stats()).channels.slice(0,3).map(c=>c.stdev);
    assert.ok(Math.max(...detail)>4,'the real scene contains visible detail');
    assert.equal(await page.evaluate(() => window.__GPU_PROBE.maxActive()),1);
    assert.ok(await page.evaluate(() => window.__GPU_PROBE.snapshot().some(context => context.draws>0)));
    const row = {scene:spec.id,engine:'PlayCanvas WebGL2',pixelStandardDeviation:detail.map(value=>Number(value.toFixed(2))),peakContexts:1};
    if (index === 0) {
      await canvas.evaluate(element => {
        const loss = element.getContext('webgl2').getExtension('WEBGL_lose_context');
        if (!loss) throw new Error('WEBGL_lose_context extension unavailable in test Chromium');
        loss.loseContext();
      });
      await canvas.waitFor({state:'detached'});
      assert.equal(await stage.getAttribute('data-visual-fallback'),'true');
      await assertDiagram(experiment);
      assert.equal(await page.evaluate(() => window.__GPU_PROBE.active()),0);
      row.afterContextLoss = 'interactive SVG';
    }
    assert.equal(await page.evaluate(() => window.__WEBGPU_REQUESTS),0);
    assert.deepEqual(errors,[]);
    rows.push(row);
    await page.close();
  }

  const {page,errors} = await open('no-webgl');
  const {experiment,stage,canvas} = await openExperiment(page,experiments[0]);
  await page.waitForFunction(() => document.querySelector('.mx-volume-stage[data-visual-fallback="true"]'));
  assert.equal(await stage.getAttribute('data-renderer-engine'),null);
  assert.equal(await canvas.count(),0);
  await assertDiagram(experiment);
  assert.equal(await page.evaluate(() => window.__GPU_PROBE.maxActive()),0);
  assert.equal(await page.evaluate(() => window.__WEBGPU_REQUESTS),0);
  assert.deepEqual(errors,[]);
  rows.push({scene:experiments[0].id,afterMissingWebGL2:'interactive SVG',peakContexts:0});
  await page.close();
  console.log(JSON.stringify(rows));
} finally {
  await browser.close();
}
