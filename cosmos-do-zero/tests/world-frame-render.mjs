// Actual PlayCanvas rasterization of a synthetic world: a 10^27 m anchor with 1 m local offsets.
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { chromium } from 'playwright';
import sharp from 'sharp';
import { installGpuProbe } from './lib/gpu-probe.mjs';

const server = await createServer({ configFile: false, root: process.cwd(), logLevel: 'error', server: { host: '127.0.0.1', port: 0 } });
await server.listen();
const url = 'http://127.0.0.1:' + server.httpServer.address().port + '/tests/fixtures/world-frame.html';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });

const rows = [];
const pixel = (image, x = 160, y = 120) => [...image.data.slice((y * image.info.width + x) * 4, (y * image.info.width + x) * 4 + 4)];
const frame = canvas => canvas.screenshot().then(png => sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true }));
const assertRed = (value, label) => assert.ok(value[0] > value[2] * 1.5 && value[0] > value[1] * 1.5, label + ': ' + value);
const assertBlue = (value, label) => assert.ok(value[2] >= 80 && value[2] > value[0] * 2 && value[2] > value[1] * 2, label + ': ' + value);

async function open(query = '') {
  const page = await browser.newPage({ viewport: { width: 800, height: 600 }, reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.addInitScript(installGpuProbe);
  await page.goto(url + query);
  return { page, errors, stage: page.locator('.mx-stage'), canvas: page.locator('.cosmos-volume') };
}

try {
  const { page, errors, stage, canvas } = await open();
  await canvas.waitFor({ timeout: 30000 });
  assert.equal(await stage.getAttribute('data-renderer-engine'), 'playcanvas');
  assert.equal(await stage.getAttribute('data-renderer'), 'webgl2');
  const first = await frame(canvas);
  const center = pixel(first), edge = pixel(first, 15, 15);
  assertRed(center, 'near plane occludes the distant plane drawn after it');
  assertBlue(edge, 'distant plane remains visible');
  await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.nearVisible(false));
  assertBlue(pixel(await frame(canvas)), 'removing the near plane exposes the distant plane');
  await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.nearVisible(true));
  assertRed(pixel(await frame(canvas)), 'restoring the near plane reestablishes occlusion');
  await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.farVisible(false));
  const clearEdge = pixel(await frame(canvas), 15, 15);
  assert.ok(edge[2] - clearEdge[2] >= 80, 'far plane differs visibly from the clear color');
  await page.evaluate(() => {
    window.__WORLD_FRAME_FIXTURE.farVisible(true);
    window.__WORLD_FRAME_FIXTURE.foregroundColor(0x22ff22);
  });
  const green = pixel(await frame(canvas));
  assert.ok(green[1] > green[0] * 1.5, 'updates to the original material remain visible');
  await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.foregroundColor(0xff2222));
  const added = {};
  for (const model of ['standard', 'custom']) {
    await page.evaluate(model => window.__WORLD_FRAME_FIXTURE.addForeground(model), model);
    const color = pixel(await frame(canvas));
    assert.ok(color[0] >= 80 && color[1] >= 80 && color[2] < Math.min(color[0], color[1]) / 2,
      `a new mesh with a ${model} material closer to the camera occludes existing geometry: ${color}`);
    added[model] = color;
    await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.removeForeground());
    assertRed(pixel(await frame(canvas)), 'removed mesh no longer draws');
  }
  await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.rebase(1));
  const rebased = await frame(canvas);
  assert.equal(first.data.length, rebased.data.length);
  let difference = 0;
  for (let i = 0; i < first.data.length; i++) difference += Math.abs(first.data[i] - rebased.data[i]);
  const meanDelta = difference / first.data.length;
  assert.ok(meanDelta < .5, 'rebase preserves rasterized pixels, mean delta ' + meanDelta);
  await page.locator('.cosmos-view-options summary').click();
  await page.getByRole('button', { name: 'Girar visão para a direita' }).click();
  const rotation = await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.cameraDelta());
  assert.ok(Math.hypot(...rotation) > .1, 'camera orbit updates world position');
  assert.ok(Math.abs(await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.cameraDistance()) - 3) < 1e-8,
    'orbit preserves the physical initial distance rather than the placeholder home');
  await page.getByRole('button', { name: 'Aproximar +' }).click();
  const zoom = await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.cameraDelta());
  assert.ok(zoom.some((value, i) => Math.abs(value - rotation[i]) > .01), 'zoom updates world position');
  assert.ok(await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.cameraDistance()) < 3, 'zoom approaches the target');
  assert.ok(await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.targetDelta().every(value => Math.abs(value) < 1e-8)),
    'camera target remains fixed in world coordinates');
  await page.getByRole('button', { name: 'Restaurar visão' }).click();
  assert.ok(await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.cameraDelta().every(value => Math.abs(value) < 1e-8)),
    'reset restores world camera');
  await page.evaluate(() => window.__WORLD_FRAME_FIXTURE.fail());
  await stage.locator('svg').waitFor();
  await canvas.waitFor({ state: 'detached' });
  assert.equal(await stage.getAttribute('data-visual-fallback'), 'true');
  assert.equal(await page.evaluate(() => window.__GPU_PROBE.active()), 0, 'invalid frame releases the actual context');
  assert.deepEqual(errors, []);
  rows.push({ scenario: 'physical perspective', meanDelta, center, edge, added, invalidFrame: 'svg' });
  await page.close();

  for (const scenario of ['shadows', 'ortho', 'ortho-extreme']) {
    const { page, errors, stage, canvas } = await open('?' + scenario + '=1');
    await page.locator('.mx-stage[data-visual-fallback="true"]').waitFor({ timeout: 30000 });
    assert.equal(await canvas.count(), 0);
    assert.equal(await stage.getAttribute('data-renderer'), null);
    assert.ok(await stage.locator('svg').isVisible());
    assert.equal(await page.evaluate(() => window.__GPU_PROBE.active()), 0);
    assert.deepEqual(errors, []);
    rows.push({ scenario, result: 'svg' });
    await page.close();
  }

  const ortho = await open('?normalized-ortho=1');
  await ortho.canvas.waitFor({ timeout: 30000 });
  assert.equal(await ortho.stage.getAttribute('data-renderer-engine'), 'playcanvas');
  const front = pixel(await frame(ortho.canvas));
  assertRed(front, 'normalized orthographic scene shows the near plane');
  await ortho.page.evaluate(() => window.__WORLD_FRAME_FIXTURE.nearVisible(false));
  const behind = pixel(await frame(ortho.canvas));
  assertBlue(behind, 'normalized orthographic scene exposes the far plane');
  assert.deepEqual(ortho.errors, []);
  rows.push({ scenario: 'normalized ortho', front, behind });
  await ortho.page.close();
  console.log(JSON.stringify({ engine: 'PlayCanvas WebGL2', world: 'synthetic', rows }));
} finally {
  await browser.close();
  await server.close();
}
