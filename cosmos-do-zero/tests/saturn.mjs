import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { chromium, devices } from 'playwright';
import { installGpuProbe } from './lib/gpu-probe.mjs';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const path = '/capitulos/sistema-solar/#saturno-aneis';
const out = resolve(process.env.SATURN_OUTPUT ?? 'test-results/saturn');
await mkdir(out, { recursive: true });

const software = process.env.CI || process.env.COSMOS_SOFTWARE_GL === '1';
const launchOptions = {
  executablePath: process.env.CHROMIUM || undefined,
  headless: process.env.HEADED !== '1',
  args: ['--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
    ...(software ? ['--use-gl=angle', '--use-angle=swiftshader'] : [])]
};
const browser = await chromium.launch(launchOptions);
const report = { browser: browser.version(), checks: [], measurements: {} };

async function captureComparison() {
  const sources = await Promise.all(['open', 'edge'].map(async angle => ({
    angle,
    blender: (await readFile(new URL(`../assets/source/saturn/blender-${angle}.png`, import.meta.url))).toString('base64'),
    web: (await readFile(resolve(out, `playcanvas-${angle}.png`))).toString('base64')
  })));
  const comparison = await browser.newPage({ viewport: { width: 1600, height: 1040 } });
  await comparison.setContent(`<html lang="pt-BR">
    <style>
      body{margin:0;padding:28px 36px;background:#171c26;color:#e9e4d9;font:20px system-ui}
      h1{margin:0 0 14px;font-size:30px} h2{margin:17px 0 6px;font-size:19px;font-weight:600}
      .pair{display:grid;grid-template-columns:1fr 1fr;gap:12px} figure{margin:0}
      figcaption{font-size:15px;margin-bottom:6px;color:#d9cbaf}
      img{display:block;width:100%;aspect-ratio:16 / 9;border-radius:6px}
    </style>
    <h1>Saturno · o mesmo enquadramento nos dois motores</h1>
    ${sources.map(({ angle, blender, web }) => `<h2>${angle === 'open' ? '30° · Vista aberta' : '0° · De perfil'}</h2><div class="pair">
      <figure><figcaption>Blender 5.3</figcaption><img src="data:image/png;base64,${blender}" /></figure>
      <figure><figcaption>PlayCanvas 2.24.1</figcaption><img src="data:image/png;base64,${web}" /></figure>
    </div>`).join('')}
    </html>`);
  await comparison.screenshot({ path: resolve(out, 'blender-playcanvas.png'), fullPage: true });
  await comparison.close();
}

async function visit(page) {
  await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded' });
  const root = page.locator('[data-saturn]');
  const stage = root.locator('[data-saturn-stage]');
  const slider = root.getByRole('slider', { name: 'Ângulo de visão' });
  await root.locator('[data-saturn-slider]:enabled').waitFor();
  return { root, stage, slider };
}

try {
  const desktop = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  await desktop.addInitScript(installGpuProbe);
  const errors = [];
  desktop.on('pageerror', error => errors.push(error.message));
  desktop.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  let allowModel;
  const modelGate = new Promise(resolve => { allowModel = resolve; });
  let requestedModel;
  const modelRequested = new Promise(resolve => { requestedModel = resolve; });
  await desktop.route('**/models/saturn/saturn.glb', async route => {
    requestedModel();
    await modelGate;
    await route.continue();
  });

  const { root, stage, slider } = await visit(desktop);
  await stage.scrollIntoViewIfNeeded();
  await modelRequested;
  assert.equal(await stage.locator('[data-saturn-diagram]').isVisible(), true);
  await slider.press('End');
  assert.equal(await slider.inputValue(), '90');
  assert.equal(await stage.locator('[data-saturn-rings]').first().getAttribute('transform'), 'scale(1 1)');
  await slider.press('Home');
  assert.equal(await slider.inputValue(), '0');
  assert.equal(await stage.locator('[data-saturn-edge]').getAttribute('visibility'), 'visible');
  await root.getByRole('button', { name: 'Vista aberta' }).click();
  assert.equal(await slider.inputValue(), '30');
  report.checks.push('diagram interactive while GLB is blocked, keyboard endpoints and preset');

  allowModel();
  await desktop.locator('[data-saturn-stage][data-renderer="playcanvas-webgl2"]').waitFor({ timeout: 15000 });
  assert.deepEqual(errors, []);
  await stage.evaluate(node => { node.style.width = '960px'; });
  await stage.scrollIntoViewIfNeeded();
  await desktop.waitForFunction(() => document.querySelector('#saturn-canvas')?.width === 960);
  await stage.screenshot({ path: resolve(out, 'playcanvas-open.png'), animations: 'disabled' });
  const edgeFrame = stage.evaluate(node => new Promise(resolve => {
    node.addEventListener('saturn:frame', event => {
      if (event.detail.angle === 0) resolve(null);
    });
  }));
  await root.getByRole('button', { name: 'De perfil' }).click();
  assert.equal(await slider.inputValue(), '0');
  await edgeFrame;
  await stage.screenshot({ path: resolve(out, 'playcanvas-edge.png'), animations: 'disabled' });
  const graphics = await stage.locator('canvas').evaluate(node => {
    const gl = node.getContext('webgl2');
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    return { renderer: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), resolution: [node.width, node.height] };
  });
  const animation = await root.evaluate(async node => {
    const input = node.querySelector('[data-saturn-slider]');
    const stage = node.querySelector('[data-saturn-stage]');
    const frames = [];
    const count = event => frames.push(event.detail.time);
    stage.addEventListener('saturn:frame', count);
    const start = performance.now();
    let value = Number(input.value);
    await new Promise(resolve => {
      const step = () => {
        const elapsed = performance.now() - start;
        if (elapsed >= 5000) { resolve(); return; }
        value = (value + 1) % 91;
        input.value = String(value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
    stage.removeEventListener('saturn:frame', count);
    const gaps = frames.slice(1).map((time, index) => time - frames[index]).sort((a, b) => a - b);
    return { frames: frames.length, seconds: (performance.now() - start) / 1000, p95Milliseconds: gaps[Math.floor(.95 * (gaps.length - 1))] };
  });
  assert.ok(animation.frames > 0);
  report.measurements.continuousProgrammaticSlider = { ...graphics, ...animation, fps: animation.frames / animation.seconds };
  report.checks.push('first 3D frame, rendered frames while changing angle, matched framing screenshots');

  await root.getByRole('button', { name: 'De perfil' }).click();
  await stage.locator('canvas').evaluate(node => node.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
  await stage.locator('canvas').waitFor({ state: 'detached' });
  assert.equal(await slider.inputValue(), '0');
  assert.equal(await stage.locator('[data-saturn-diagram]').isVisible(), true);
  await slider.press('ArrowRight');
  assert.equal(await slider.inputValue(), '1');
  assert.equal(await stage.locator('canvas').count(), 0);
  assert.equal(await desktop.evaluate(() => window.__GPU_PROBE.maxActive()), 1);
  report.checks.push('real context loss preserves angle, input and no automatic retry');
  await desktop.close();

  for (const width of [360, 390]) {
    const mobile = await browser.newPage({ ...devices['Pixel 7'], viewport: { width, height: 844 }, reducedMotion: 'reduce' });
    await mobile.addInitScript(() => {
      const actual = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(type, ...args) {
        return type.includes('webgl') ? null : actual.call(this, type, ...args);
      };
    });
    const { root, slider, stage } = await visit(mobile);
    await mobile.waitForFunction(() => {
      const heading = document.querySelector('#saturn-title').getBoundingClientRect();
      const slider = document.querySelector('#saturn-angle').getBoundingClientRect();
      return heading.top >= 0 && slider.bottom <= innerHeight;
    });
    assert.ok(await root.evaluate(node => {
      const heading = node.querySelector('h3').getBoundingClientRect();
      const slider = node.querySelector('[data-saturn-slider]').getBoundingClientRect();
      return heading.top >= 0 && slider.bottom <= innerHeight && slider.height >= 44;
    }));
    await root.getByRole('button', { name: 'De perfil' }).tap();
    assert.equal(await slider.inputValue(), '0');
    assert.equal(await stage.locator('[data-saturn-diagram]').isVisible(), true);
    report.checks.push(`${width}px touch, reduced motion, visible heading and control, no WebGL`);
    if (width === 390) await root.screenshot({ path: resolve(out, 'mobile-fallback.png'), animations: 'disabled' });
    await mobile.close();
  }

  const interrupted = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await interrupted.route('**/models/saturn/saturn.glb', route => route.abort());
  const fallback = await visit(interrupted);
  await fallback.stage.scrollIntoViewIfNeeded();
  await fallback.root.getByRole('button', { name: 'De perfil' }).click();
  assert.equal(await fallback.slider.inputValue(), '0');
  assert.equal(await fallback.stage.locator('[data-saturn-diagram]').isVisible(), true);
  assert.equal(await fallback.stage.locator('canvas').count(), 0);
  report.checks.push('diagram and controls with interrupted asset');
  await interrupted.close();

  const cold = [];
  const coldBrowser = await chromium.launch(launchOptions);
  try {
    for (let trial = 0; trial < 5; trial++) {
      const page = await coldBrowser.newPage({ viewport: { width: 1440, height: 900 } });
      const { stage } = await visit(page);
      await stage.scrollIntoViewIfNeeded();
      await page.locator('[data-saturn-stage][data-renderer="playcanvas-webgl2"]').waitFor({ timeout: 15000 });
      cold.push(await page.evaluate(() => {
        const navigation = performance.getEntriesByType('navigation')[0];
        const resources = performance.getEntriesByType('resource');
        const control = performance.getEntriesByName('saturn:controls-ready')[0].startTime;
        const firstFrame = performance.getEntriesByName('saturn:first-3d-frame')[0].startTime;
        const bytesBefore = point => navigation.transferSize + resources.filter(entry => entry.responseEnd <= point).reduce((sum, entry) => sum + entry.transferSize, 0);
        return { controlMs: control, frameMs: firstFrame, bytesThroughControl: bytesBefore(control), bytesThroughFrame: bytesBefore(firstFrame), modelBytes: resources.find(entry => entry.name.endsWith('/saturn.glb'))?.transferSize };
      }));
      await page.close();
    }
  } finally {
    await coldBrowser.close();
  }
  report.measurements.coldNavigations = cold;
  await captureComparison();
  await writeFile(resolve(out, 'saturn-results.json'), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
