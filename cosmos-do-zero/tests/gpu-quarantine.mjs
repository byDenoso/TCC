// Exercise queue ownership against real contexts and deliberately interrupted PlayCanvas mounts.
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {chromium} from 'playwright';
import {installGpuProbe} from './lib/gpu-probe.mjs';

const server = await createServer({configFile:false, root:process.cwd(), logLevel:'error', server:{host:'127.0.0.1',port:0}});
await server.listen();
const url = 'http://127.0.0.1:' + server.httpServer.address().port + '/tests/fixtures/gpu-pending.html';
const browser = await chromium.launch({
  executablePath:process.env.CHROMIUM || undefined,
  args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'],
});

const rows = [];
try {
  for (const mode of ['handoff', 'module-pending', 'teardown-failure']) {
    const page = await browser.newPage({viewport:{width:900,height:600}, reducedMotion:'reduce'});
    const errors = [];
    const warnings = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
      if (message.type() === 'error') errors.push(message.text());
      if (message.type() === 'warning') warnings.push(message.text());
    });
    await page.addInitScript(installGpuProbe);
    const stage = name => page.locator('[data-fixture="' + name + '"]');
    const frame = name => stage(name).locator('.cosmos-volume');
    if (mode === 'module-pending') {
      let release;
      const delayed = new Promise(resolve => { release = resolve; });
      let observed;
      const requested = new Promise(resolve => { observed = resolve; });
      await page.route('**/playcanvas-adapter.ts*', async route => {
        observed();
        await delayed;
        await route.continue();
      });
      await page.goto(url, {waitUntil:'commit'});
      try {
        await Promise.race([requested, page.waitForTimeout(15000).then(() => assert.fail('adapter import did not start'))]);
        await page.evaluate(() => {
          window.__GPU_PENDING.dispose('first');
          window.__GPU_PENDING.add('second');
        });
        assert.equal(await page.evaluate(() => window.__GPU_PROBE.maxActive()), 0);
      } finally {
        release();
      }
      await frame('second').waitFor({timeout:30000});
      assert.equal(await stage('second').getAttribute('data-renderer-engine'), 'playcanvas');
      assert.deepEqual(await page.evaluate(() => window.__GPU_PENDING.events), [{name:'second',type:'cosmos:ready'}]);
      assert.equal(await frame('first').count(), 0);
      assert.ok(await stage('first').locator('svg').isVisible());
      await page.evaluate(() => window.__GPU_PENDING.dispose('second'));
      await page.waitForFunction(() => window.__GPU_PROBE.active() === 0);
    } else {
      await page.goto(url + (mode === 'teardown-failure' ? '?teardown=1' : ''));
      await frame('first').waitFor({timeout:30000});
      assert.equal(await stage('first').getAttribute('data-renderer-engine'), 'playcanvas');
      assert.equal(await page.evaluate(() => window.__GPU_PROBE.active()), 1);
      if (mode === 'teardown-failure') {
        const firstContext = await frame('first').evaluateHandle(canvas => canvas.getContext('webgl2'));
        await frame('first').evaluate(canvas => { canvas.dataset.rejectTeardown = 'true'; });
        await page.evaluate(() => {
          window.__GPU_PENDING.add('second');
          window.__GPU_PENDING.add('third');
        });
        for (const name of ['second','third']) {
          await stage(name).locator('xpath=self::*[@data-visual-fallback="true"]').waitFor();
          assert.equal(await frame(name).count(), 0);
          assert.ok(await stage(name).locator('svg').isVisible());
        }
        assert.ok(warnings.some(warning => warning.includes('fixture-teardown-sentinel')), 'the injected teardown error surfaced');
        assert.equal(await page.evaluate(() => window.__GPU_PROBE.active()), 1, 'the fixture still owns the context that failed to release');
        await firstContext.evaluate(gl => gl.getExtension('WEBGL_lose_context').loseContext());
        await firstContext.dispose();
      } else {
        await page.evaluate(() => {
          window.__GPU_PENDING.add('second');
          window.__GPU_PENDING.add('third');
        });
        await frame('third').waitFor({timeout:30000});
        assert.equal(await stage('third').getAttribute('data-renderer-engine'), 'playcanvas');
        assert.deepEqual(await page.evaluate(() => window.__GPU_PENDING.events.map(event => event.name)), ['first','second','third']);
        for (const name of ['first','second']) {
          assert.equal(await frame(name).count(), 0);
          assert.ok(await stage(name).locator('svg').isVisible());
        }
        await page.evaluate(() => window.__GPU_PENDING.dispose('third'));
      }
      await page.waitForFunction(() => window.__GPU_PROBE.active() === 0);
    }
    const contexts = await page.evaluate(() => ({peak:window.__GPU_PROBE.maxActive(), allocated:window.__GPU_PROBE.snapshot().length}));
    assert.equal(contexts.peak, 1, 'context serialization holds below the application counter');
    assert.equal(contexts.allocated, mode === 'handoff' ? 3 : 1);
    assert.deepEqual(errors, []);
    rows.push({mode,...contexts, activeAfterTest:0});
    await page.close();
  }
  console.log(JSON.stringify({engine:'PlayCanvas WebGL2', rows}));
} finally {
  await browser.close();
  await server.close();
}
