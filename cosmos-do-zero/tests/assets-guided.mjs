// BASE_URL may include the deployment prefix. CHROMIUM selects a local browser.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { chromium, devices } from 'playwright';
import { sceneInventory } from '../scripts/rework-inventory.mjs';
import { openExtraExperiments, openLessonStory, selectLessonStep } from './lib/reader-navigation.mjs';

const base = new URL((process.env.BASE_URL || 'http://127.0.0.1:4378').replace(/\/+$/, '') + '/');
const address = route => new URL(route.replace(/^\/+/, ''), base).href;
const inventory = sceneInventory.filter(entry => entry.kind === '3d');
assert.equal(sceneInventory.length, 68);
assert.equal(new Set(inventory.map(entry => entry.id)).size, 27);
assert.equal(inventory.length, 27);
const forbidden = /\.gl(?:b|tf)$|(?:^|[/_.-])(?:playcanvas|three|babylon(?:js)?|GLTFLoader|WebglGraphicsDevice)(?=[/_.-]|$)/i;
const profiles = {desktop:{viewport:{width:1440,height:900}}, mobile:devices['Pixel 7']};

function blockGraphics() {
  for (const type of [globalThis.HTMLCanvasElement, globalThis.OffscreenCanvas]) {
    if (!type) continue;
    const original = type.prototype.getContext;
    type.prototype.getContext = function(kind, ...args) {
      if (/^(?:(?:experimental-|webkit-|moz-)?webgl2?|webgpu)$/i.test(kind)) {
        void globalThis.reportGpu(type.name + '.' + kind);
        return null;
      }
      return original.call(this, kind, ...args);
    };
  }
  Object.defineProperty(Navigator.prototype, 'gpu', {
    get() { void globalThis.reportGpu('navigator.gpu'); return undefined; }
  });
}

async function visibleImage(image) {
  await image.waitFor({state:'visible'});
  await image.evaluate(async el => { await el.decode(); if (!el.naturalWidth) throw Error('empty image'); });
}

async function checkFrameEndpoints(request) {
  const planets = ['mercurio','venus','terra','marte','jupiter','saturno','urano','netuno'];
  const manifests = [
    {dir:'models/solar-turntable/', name:'manifest.json', series:planets, last:35, step:10},
    {dir:'models/saturn/', name:'frames.json', series:['frames'], last:90, step:1}
  ];
  let checked = 0;
  for (const {dir,name,series,last,step} of manifests) {
    const response = await request.get(address(dir + name));
    assert.equal(response.status(),200,dir + name);
    const {frames} = await response.json();
    for (const body of series) {
      const rows = frames.filter(row => row.file.startsWith(body + '/'));
      assert.equal(rows.length,last + 1,body);
      for (let i = 0; i <= last; i++) {
        const file = body + '/' + String(i).padStart(2,'0') + '.webp';
        const row = rows.find(frame => frame.file === file);
        assert.equal(row?.degrees ?? row?.degree,i * step,file);
        if (i !== 0 && i !== last) continue;
        const asset = await request.get(address(dir + file));
        assert.equal(asset.status(),200,file);
        assert.match(asset.headers()['content-type'],/image\/webp/,file);
        assert.equal(createHash('sha256').update(await asset.body()).digest('hex'),row.sha256,file);
        checked++;
      }
    }
  }
  return checked;
}

async function pressed(button) {
  await button.click();
  await button.and(button.page().locator('[aria-pressed="true"]')).waitFor();
}

async function tabs(page, report) {
  for (const list of await page.getByRole('tablist').all()) {
    const buttons = await list.getByRole('tab').all();
    assert.ok(buttons.length > 1);
    for (const active of buttons) {
      await active.click();
      for (const button of buttons) {
        const selected = button === active;
        assert.equal(await button.getAttribute('aria-selected'), String(selected));
        const panel = page.locator('#' + await button.getAttribute('aria-controls'));
        assert.equal(await panel.count(), 1);
        assert.equal(await panel.isVisible(), selected);
      }
      report.tabs++;
    }
  }
}

async function exercise(page, entry, report) {
  const el = selector => page.locator(selector);
  const {id} = entry;
  const micro = el(`[data-mx="${id}"]`);
  if (entry.anchor && entry.route.startsWith('/capitulos/')) {
    const section = await el('#' + entry.anchor).evaluate(node => node.closest('.lesson-section')?.id);
    if (section) {
      const ids = await el('.lesson-section').evaluateAll(nodes => nodes.map(node => node.id));
      await selectLessonStep(page, ids.indexOf(section));
    }
  }
  if (entry.story) {
    await openLessonStory(page);
    await el('[data-story-phase="1"]').click();
    assert.equal(await el('[data-story-phase="1"]').getAttribute('aria-current'), 'step');
    const video = el('[data-story-film]');
    assert.equal(await video.isVisible(), false);
    const src = await video.locator('source').evaluate(node => node.src);
    const filmButton = el('[data-story-mode="film"]');
    await filmButton.click();
    assert.equal(await filmButton.getAttribute('aria-pressed'),'true');
    await video.waitFor({state:'visible'});
    await video.scrollIntoViewIfNeeded();
    // A presented frame proves decoding even when Chrome reuses a media response.
    const [frame] = await Promise.all([
      video.evaluate(v => new Promise((resolve,reject) => {
        const timer = setTimeout(() => finish(new Error(
          'No presented frame: ' + JSON.stringify({src:v.currentSrc,ready:v.readyState,
            network:v.networkState,paused:v.paused,error:v.error?.message})
        )),15000);
        const onError = () => finish(new Error(v.error?.message || 'media error'));
        const callback = v.requestVideoFrameCallback((_, frame) => finish(null,{
          src:v.currentSrc,width:frame.width,height:frame.height,presented:frame.presentedFrames
        }));
        function finish(error, result) {
          clearTimeout(timer);
          v.removeEventListener('error',onError);
          v.cancelVideoFrameCallback(callback);
          if (error) reject(error);
          else resolve(result);
        }
        v.addEventListener('error',onError,{once:true});
      })),
      el('[data-story-play]').click()
    ]);
    assert.equal(frame.src,src);
    assert.ok(frame.presented > 0 && frame.width > 0 && frame.height > 0);
    report.films.push({id,...frame});
    await page.waitForFunction(() => !document.querySelector('[data-story-film]').paused);
    await video.scrollIntoViewIfNeeded();
    await page.locator('footer').last().scrollIntoViewIfNeeded();
    await page.waitForFunction(() => {
      const film = document.querySelector('[data-story-film]');
      const box = film.getBoundingClientRect();
      return (box.bottom <= 0 || box.top >= innerHeight) && film.paused;
    });
    await el('[data-story-mode="scene"]').click();
    assert.equal(await video.isVisible(), false);
    return;
  }
  if (await micro.count()) {
    const toggle = micro.locator('[data-mx-reference-toggle]');
    const image = micro.locator('[data-mx-reference]');
    await toggle.scrollIntoViewIfNeeded();
    assert.ok(!await image.getAttribute('src'), 'reference loaded before opening');
    await toggle.click();
    await visibleImage(image);
    await micro.locator('[data-mx-step]').click();
    assert.equal(await micro.getAttribute('data-guide'), 'manual');
    await micro.locator('[data-mx-reset]').click();
    await toggle.click();
    assert.equal(await image.isVisible(), false);
    return;
  }
  switch (id) {
    case 'saturno-aneis':
      for (const value of ['0','90']) {
        await pressed(el(`[data-saturn-preset="${value}"]`));
        assert.equal(await el('[data-saturn-slider]').inputValue(), value);
        const image = el(`[data-saturn-frame][src$="/${value.padStart(2,'0')}.webp"]`);
        await visibleImage(image);
      }
      // Inject one failed frame. The diagram and angle readout must still work.
      {
        const failure = '**/saturn/frames/45.webp';
        await page.route(failure, route => route.fulfill({status:404,body:''}));
        try {
          await Promise.all([page.waitForResponse(r => r.url().endsWith('/saturn/frames/45.webp') && r.status() === 404),
            el('[data-saturn-slider]').fill('45')]);
          await el('[data-saturn-stage][data-renderer="diagram"]').waitFor();
          assert.ok(await el('[data-saturn-diagram]').isVisible());
          assert.equal(await el('[data-saturn-angle]').innerText(),'45°');
        } finally { await page.unroute(failure); }
      }
      break;
    case 'solar-planetas':
    case 'catalogo-planetas': {
      const catalog = id === 'catalogo-planetas';
      const buttons = await el(catalog ? 'button.planet-tab[data-planet]' : '[data-solar-planet]').all();
      assert.equal(buttons.length, 8);
      const root = el(catalog ? '[data-island="planets"]' : '[data-solar-studio]');
      const image = root.locator(catalog ? '[data-planet-img]' : '[data-solar-poster]');
      for (const button of buttons) {
        await pressed(button);
        const name = (await button.innerText()).trim();
        const text = await el(catalog ? '[data-planet-name]' : '[data-solar-caption]').innerText();
        assert.ok(text.includes(name), name);
        await visibleImage(image);
        const planetId = name.toLowerCase().normalize('NFD').replace(/\p{M}/gu,'');
        assert.match(await image.getAttribute('src'),new RegExp('/solar-turntable/' + planetId + '/'));
      }
      await root.locator('[data-world-angle]').fill('35');
      await visibleImage(image.and(el('[src$="/35.webp"]')));
      assert.equal(await root.locator('[data-world-degrees]').innerText(),'350°');
      await root.locator('[data-world-zoom]').fill('175');
      assert.equal(await root.locator('[data-world-percent]').innerText(),'175%');
      break;
    }
    case 'endereco-cosmico':
      await openExtraExperiments(page);
      await pressed(el('[data-scale-step]').last());
      break;
    case 'lente-gravitacional':
      await el('[data-lens-geometry] > summary').click();
      await el('[data-lens-stage]').waitFor({state:'visible'});
      await el('[data-lens-example]').click();
      assert.notEqual(await el('[data-lens-source]').inputValue(), '0');
      await el('[data-lens-reset]').click();
      assert.equal(await el('[data-lens-source]').inputValue(), '0');
      break;
    case 'tempo-flrw':
      await el('[data-obs-tab="tempo"]').click();
      await el('[data-t-preset="1090"]').scrollIntoViewIfNeeded();
      await el('[data-station="tempo"][data-station-ready="true"]').waitFor();
      await pressed(el('[data-t-preset="1090"]'));
      break;
    case 'expansao-observatorio':
      await el('[data-obs-tab="expansao"]').click();
      await pressed(el('[data-e-observer="1"]'));
      break;
    case 'comparador-planetas': {
      const a = el('[data-compare-a]'), b = el('[data-compare-b]');
      const before = [await a.inputValue(), await b.inputValue()];
      await el('[data-compare-swap]').click();
      assert.deepEqual([await b.inputValue(), await a.inputValue()], before);
      break;
    }
    case 'massa-estelar':
      await pressed(el('[data-mass="15"]'));
      assert.equal(await el('[data-star-mass]').inputValue(), '15');
      break;
    case 'escala-continua': {
      const jump = el('[data-scale-jump]');
      const last = el('.cosmic-exhibit-nav a').last();
      const hash = await last.getAttribute('href');
      if (await jump.isVisible()) {
        await jump.selectOption({index:await jump.locator('option').count() - 1});
      } else {
        await last.click();
      }
      assert.equal(new URL(page.url()).hash,hash);
      await el(hash).waitFor({state:'visible'});
      break;
    }
    case 'nebulosa-ceu': {
      const image = el('[data-nebula-plate]'), button = el('[data-hero-gl-enable]');
      assert.ok(!await image.getAttribute('src'));
      await pressed(button);
      await visibleImage(image);
      await button.click();
      assert.equal(await image.isVisible(), false);
      break;
    }
    default: throw Error('Missing interaction for ' + id);
  }
}

const browser = await chromium.launch({executablePath:process.env.CHROMIUM || undefined});
async function run(profile, options) {
  const context = await browser.newContext({...options, serviceWorkers:'block'});
  context.setDefaultTimeout(6500);
  const report = {profile,browser:browser.version(),base:base.href, routes:[], entries:[], films:[], tabs:0, gpu:[], blocked:[], transfers:[], pageerrors:[], failures:[]};
  let label = '';
  const allowedVideos = new Set();
  async function check(name, action) {
    label = name;
    try { await action(); return true; }
    catch (error) {
      report.failures.push({name, message:error.message.split('\n').slice(0,3).join(' '),
        source:error.stack?.split('\n').find(line => line.includes('assets-guided.mjs:'))?.trim()});
      return false;
    }
  }
  try {
    await context.exposeBinding('reportFilmSelection', (_,src) => { allowedVideos.add(src); });
    await context.addInitScript(() => {
      document.addEventListener('click', event => {
        const button = event.target.closest?.('[data-story-mode="film"]');
        if (event.isTrusted && button) {
          const source = button.closest('[data-story]').querySelector('[data-story-film] source');
          void globalThis.reportFilmSelection(source.src);
        }
      },true);
    });
    await context.exposeBinding('reportGpu', ({frame}, kind) => report.gpu.push({kind,url:frame.url()}));
    await context.addInitScript(blockGraphics);
    context.on('weberror', error => report.pageerrors.push({label,message:error.error().message}));
    context.on('page', page => page.on('worker', worker => report.failures.push({label,unprobedWorker:worker.url()})));
    await context.route('**/*', route => {
      const url = route.request().url();
      if (forbidden.test(new URL(url).pathname)) {
        report.blocked.push({label,url});
        return route.abort();
      }
      return route.continue();
    });
    context.on('response', response => {
      const url = response.url();
      if (forbidden.test(new URL(url).pathname) || /model\/gltf/.test(response.headers()['content-type'] || '')) report.transfers.push({label,url});
    });
    context.on('request', request => {
      const url = request.url();
      if (/\.(mp4|webm)$/i.test(new URL(url).pathname) && !allowedVideos.has(url))
        report.failures.push({label,unsolicitedVideo:url});
    });
    const page = await context.newPage();
    // Positive control in an empty document, separate from the site counters.
    await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      const offscreen = new OffscreenCanvas(1,1);
      if ([canvas.getContext('webgl'),canvas.getContext('webgl2'),
        offscreen.getContext('webgl2'),offscreen.getContext('webgpu'),navigator.gpu].some(Boolean))
        throw Error('GPU probe failed to block access');
      if (!canvas.getContext('2d')) throw Error('2D context incorrectly blocked');
    });
    await page.evaluate(() => globalThis.reportGpu('probe-complete'));
    assert.deepEqual(report.gpu.map(event => event.kind).sort(),[
      'HTMLCanvasElement.webgl','HTMLCanvasElement.webgl2','OffscreenCanvas.webgl2',
      'OffscreenCanvas.webgpu','navigator.gpu','probe-complete'
    ].sort());
    report.gpu.length = 0;
    const sitemap = await context.request.get(address('sitemap.xml'));
    assert.equal(sitemap.status(), 200);
    const locations = [...(await sitemap.text()).matchAll(/<loc>([^<]+)<\/loc>/g)];
    const paths = locations.map(([,href]) => {
      const path = new URL(href).pathname;
      return path.startsWith(base.pathname) ? '/' + path.slice(base.pathname.length) : path;
    });
    const expectedRoutes = new Set(['/', '/luz/', '/escalas/', '/imagens/', '/observatorio/',
      '/desafio/', '/explorar/', '/ceu/', '/laboratorio/', '/glossario/', '/fontes/',
      ...inventory.map(entry => entry.route)]);
    assert.equal(expectedRoutes.size,17);
    assert.equal(paths.length,17);
    assert.deepEqual(new Set(paths),expectedRoutes);
    await check('frame endpoints', async () => {
      report.frameEndpoints = await checkFrameEndpoints(context.request);
    });
    await check('robots.txt', async () => {
      const r = await context.request.get(address('robots.txt'));
      assert.equal(r.status(),200);
      assert.match(await r.text(), /User-agent:\s*\*/i);
    });
    for (const path of paths) {
      allowedVideos.clear();
      const opened = await check(path,async () => {
        const r = await page.goto(address(path),{waitUntil:'load'});
        assert.equal(r.status(),200);
        assert.equal(new URL(page.url()).pathname,new URL(address(path)).pathname);
        await page.locator('main h1, h1').first().waitFor({state:'visible'});
        report.routes.push(path);
      });
      if (!opened) continue;
      for (const entry of inventory.filter(item => item.route === path)) {
        if (await check(entry.id, () => exercise(page,entry,report))) report.entries.push(entry.id);
      }
      await check('tabs ' + path,async () => {
        if (path.startsWith('/capitulos/')) await openExtraExperiments(page);
        if (path === '/observatorio/') {
          assert.equal(await page.locator('[data-obs-tab]').count(),4);
          assert.ok(await page.locator('[data-obs-tabs]').isVisible());
        }
        if (path === '/') await page.locator('[data-sci-tabs]').waitFor({state:'visible'});
        await tabs(page,report);
      });
      await page.waitForTimeout(200);
    }
    await check('404 fallback',async () => {
      const r = await page.goto(address('__qa_missing_page__/'));
      assert.equal(r.status(),404);
      const link = page.getByRole('link',{name:/voltar ao início/i});
      await link.click();
      assert.equal(new URL(page.url()).pathname,base.pathname);
    });
    await check('diagram fallback', async () => {
      const id = 'sistema-solar-gigantes';
      const r = await page.goto(address('/capitulos/sistema-solar/?visual=diagram#' + id));
      assert.equal(r.status(),200);
      const root = page.locator(`[data-mx="${id}"]`);
      await root.locator('[data-mx-step]').click();
      assert.equal(await root.getAttribute('data-guide'),'manual');
      assert.ok(await root.locator('[data-mx-svg]').isVisible());
      assert.equal(await root.locator('[data-mx-reference-toggle]').isVisible(),false);
      assert.ok(!await root.locator('[data-mx-reference]').getAttribute('src'));
    });
  } finally { await context.close(); }
  console.log(JSON.stringify(report));
  return report.routes.length === 17 && report.entries.length === 27 && report.tabs > 0 &&
    [report.gpu,report.blocked,report.transfers,report.pageerrors,report.failures].every(items => items.length === 0);
}
try {
  const results = await Promise.allSettled(Object.entries(profiles).map(([name, options]) => run(name,options)));
  for (const result of results) {
    if (result.status === 'rejected') console.error(result.reason);
    if (result.status !== 'fulfilled' || !result.value) process.exitCode = 1;
  }
} finally { await browser.close(); }
