import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium } from 'playwright';
import sharp from 'sharp';

const base = new URL((process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/?$/, '/'));
const out = process.env.HD_OUTPUT ?? 'test-results/site-hd';
const chapters = JSON.parse(await readFile(new URL('../src/data/chapters.json', import.meta.url), 'utf8'));
const routes = [
  '',
  'explorar/',
  'imagens/',
  'escalas/',
  'luz/',
  'ceu/',
  'observatorio/',
  'laboratorio/',
  'desafio/',
  'fontes/',
  'glossario/',
  ...chapters.map((c) => 'capitulos/' + c.id + '/'),
  '404.html',
];
const report = { base: base.href, routes: {}, http: {}, otherHttp: [], problems: [], gpu: [] };
await mkdir(join(out, 'regions'), { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM });
const context = await browser.newContext({ viewport: { width: 1280, height: 840 }, reducedMotion: 'reduce' });
await context.exposeBinding('reportGpu', (_, kind) => report.gpu.push(kind));
await context.addInitScript(() => {
  const get = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
    if (/webgl|webgpu/i.test(kind)) window.reportGpu(kind);
    return get.call(this, kind, ...args);
  };
  if (typeof OffscreenCanvas !== 'undefined') {
    const offscreenGet = OffscreenCanvas.prototype.getContext;
    OffscreenCanvas.prototype.getContext = function (kind, ...args) {
      if (/webgl|webgpu/i.test(kind)) window.reportGpu(kind);
      return offscreenGet.call(this, kind, ...args);
    };
  }
  const draws = new WeakMap();
  const draw = CanvasRenderingContext2D.prototype.drawImage;
  CanvasRenderingContext2D.prototype.drawImage = function (source, ...args) {
    const sources = draws.get(this.canvas) ?? new Set();
    if (source instanceof HTMLImageElement || source instanceof HTMLVideoElement) {
      if (source.currentSrc) sources.add(new URL(source.currentSrc).pathname);
    } else if (draws.has(source)) {
      for (const url of draws.get(source)) sources.add(url);
    }
    draws.set(this.canvas, sources);
    return draw.call(this, source, ...args);
  };
  window.drawnAssets = (canvas) => [...(draws.get(canvas) ?? [])];
});
const page = await context.newPage();
page.setDefaultTimeout(8000);
page.on('pageerror', (e) => report.problems.push(page.url() + ' ' + e.message));
// Credit links and third-party URLs are valid on public hosts. Only failed page
// navigations and missing site render resources are acceptance failures.
const assetPath = /^\/(?:_astro|models|posters|photos|media|renders|fonts)\//;
page.on('response', (response) => {
  if (response.status() < 400) return;
  const req = response.request(),
    url = new URL(response.url());
  const entry = response.status() + ' ' + url.href;
  // checkRoute validates the main document, including redirects and custom 404 status.
  if (req.isNavigationRequest() && req.frame() === page.mainFrame()) return;
  if (
    url.origin === base.origin &&
    (assetPath.test('/' + url.pathname.slice(base.pathname.length)) || assetPath.test(url.pathname))
  )
    report.problems.push(entry);
  else report.otherHttp.push(entry);
});
page.on('request', (req) => {
  const url = new URL(req.url());
  if (req.resourceType() === 'script' && /(?:^|\/)(?:playcanvas|three)(?:[./-]|$)/i.test(url.pathname))
    report.problems.push('3D engine script: ' + url.href);
  if (url.origin === base.origin && assetPath.test(url.pathname) && !url.pathname.startsWith(base.pathname))
    report.problems.push('Asset outside base: ' + url.href);
});
let regions;
async function capture(name, selector, kind = 'scene') {
  const node = typeof selector === 'string' ? page.locator(selector).first() : selector;
  await node.scrollIntoViewIfNeeded();
  await node.waitFor({ state: 'visible' });
  await node.evaluate(async (root) => {
    const imgs = [root, ...root.querySelectorAll('img')].filter(
      (el) => el instanceof HTMLImageElement && el.getBoundingClientRect().width && el.currentSrc,
    );
    await Promise.all(imgs.map((img) => img.decode()));
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  const raster = await node.evaluate((root) => {
    const data = new Set();
    for (const el of [root, ...root.querySelectorAll('canvas,img,video,image')]) {
      if (!el.getBoundingClientRect().width || getComputedStyle(el).visibility === 'hidden') continue;
      if (el instanceof HTMLCanvasElement) window.drawnAssets(el).forEach((url) => data.add(url));
      else if (
        (el instanceof HTMLImageElement && el.naturalWidth) ||
        (el instanceof HTMLVideoElement && el.videoWidth)
      )
        data.add(new URL(el.currentSrc).pathname);
      else if (el instanceof SVGImageElement && el.href.baseVal)
        data.add(new URL(el.href.baseVal, location.href).pathname);
    }
    return [...data];
  });
  const file = String(Object.keys(report.routes).length).padStart(2, '0') + '-' + name + '.webp';
  const shot = await node.screenshot({ animations: 'disabled' });
  if (name === 'm51-detail' || name === 'carina-cosmic-cliffs')
    await writeFile(join(out, 'regions', name + '-native.png'), shot);
  const pixels = await sharp(shot)
    .resize({ width: 680, height: 440, fit: 'inside', withoutEnlargement: true })
    .webp({ quality: 83 })
    .toBuffer();
  const { channels } = await sharp(pixels).stats();
  assert.ok(
    channels.some((channel) => channel.stdev > 3),
    name + ' empty region',
  );
  await writeFile(join(out, 'regions', file), pixels);
  const image = await node
    .locator('img')
    .first()
    .evaluateAll((els) => {
      const img = els[0];
      if (!img) return null;
      const selected = img.srcset
        .split(',')
        .map((candidate) => candidate.trim().split(/\s+/))
        .find(([url]) => url && new URL(url, location.href).href === img.currentSrc);
      return {
        source: img.currentSrc,
        candidate: selected?.[1] ?? null,
        displayWidth: Math.round(img.getBoundingClientRect().width),
      };
    });
  regions.push({ name, kind, file, raster, image });
}
const click = (sel) => page.locator(sel).first().click();
async function checkRoute(route) {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const url = new URL(route, base).href;
  const response = await page.goto(url);
  report.http['/' + route] = response.status();
  if (route === '404.html') {
    assert.ok([200, 404].includes(response.status()), 'custom error document');
    assert.match(await page.locator('h1').innerText(), /não\s+encontrada/i);
    const home = await page.locator('main a.cta').evaluate((a) => a.href);
    assert.equal(new URL(home).pathname, base.pathname);
  } else assert.equal(response.status(), 200, route);
  assert.equal(await page.locator('h1').count(), 1);
  if (route === '') {
    await capture('webb', '.arrival-window');
    await capture('six-covers', '[data-home-section="02"]');
    for (const id of ['luz', 'expansao', 'hubble', 'frio', 'giro']) {
      await click('[data-sci-tab="' + id + '"]');
      await capture('motion-' + id, '[data-sci-panel="' + id + '"] .sci-fig');
    }
    const select = page.locator('[data-journey-select]');
    await select.scrollIntoViewIfNeeded();
    for (let index = 0; index < (await select.locator('option').count()); index++) {
      await select.selectOption(String(index));
      await page.waitForFunction(
        (i) => document.querySelector('[data-journey-step="' + i + '"]')?.classList.contains('is-active'),
        index,
      );
      const still = page.locator('[data-journey-step="' + index + '"] [data-journey-still]');
      if (await still.isVisible()) await capture('journey-' + index, still);
      else await capture('journey-' + index, '[data-journey-canvas]');
    }
  } else if (route === 'explorar/') {
    const cards = page.locator('.igrid-card');
    assert.equal(await cards.count(), 6);
    for (const [i, card] of (await cards.all()).entries())
      await capture('cover-' + i, card.locator('.igrid-media'));
    const credited = await page.locator('a.igrid-credit[href^="https://"]').count();
    if (regions.some((r) => !r.raster.length)) report.problems.push('explorar: observational image missing');
    if (credited !== 6) report.problems.push('explorar: ' + credited + '/6 credited observation covers');
  } else if (route === 'imagens/') {
    for (const tab of await page.locator('[data-px-tab]').all()) {
      await tab.click();
      const id = await tab.getAttribute('data-px-tab');
      const panel = page.locator('[data-px-panel="' + id + '"]'),
        image = panel.locator('[data-px-canvas] img');
      await panel.locator('[data-px-zoom="reset"]').click();
      await capture(id, panel.locator('[data-px-view]'));
      const whole = await image.evaluate((img) => {
        const box = img.closest('[data-px-view]').getBoundingClientRect(),
          photo = img.getBoundingClientRect();
        return photo.width <= box.width + 2 && photo.height <= box.height + 2;
      });
      if (!whole) report.problems.push('imagens: full frame cropped ' + id);
      await panel.locator('[data-px-step="1"]').click();
      assert.match(await panel.locator('[data-px-reading-count]').innerText(), /2/);
      if (id === 'm51') {
        await panel.locator('[data-px-zoom="in"]').click();
        await panel.locator('[data-px-zoom="in"]').click();
        const detail = await page.waitForFunction((img) => img.complete && img.naturalWidth > 0 &&
          img.srcset.split(',').some((entry) => {
            const [source, width] = entry.trim().split(/\s+/);
            return width === '4000w' && new URL(source, location.href).href === img.currentSrc;
          }), await image.elementHandle(), { timeout: 15000 }).then(() => true, () => false);
        if (!detail) report.problems.push('imagens: native M51 detail unavailable at high zoom');
        await capture('m51-detail', panel.locator('[data-px-view]'));
      }
    }
  } else if (route === 'escalas/') {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await click('[data-scale-light]');
    const options = page.locator('[data-scale-jump] option');
    for (let i = 0; i < (await options.count()); i++) {
      await page.locator('[data-scale-jump]').selectOption(String(i));
      await page.waitForFunction(
        (i) => document.querySelectorAll('.scale-journey-posters img')[i]?.naturalWidth > 0,
        i,
      );
      await capture('scale-' + i, '.scale-scene-window');
    }
  } else if (route === 'observatorio/') {
    for (const id of ['tempo', 'expansao', 'hubble', 'receita']) {
      await click('[data-obs-tab="' + id + '"]');
      const panel = page.locator('[data-station="' + id + '"]');
      const skip = panel.locator('[data-guess-skip]');
      if (await skip.isVisible()) await skip.click();
      await capture(id, panel.locator('figure').first());
    }
  } else if (route === 'laboratorio/') {
    for (const [name, selector] of Object.entries({
      orbit: '.orbit-view svg',
      expansion: '[data-expansion-group]',
      transit: '[data-transit-sky]',
      hr: '[data-hr-surface]',
      lens: '[data-lens-image]',
      timeline: '[data-timeline-visual]',
      planets: '[data-planet-stage]',
      compare: '[data-compare-visual]',
      stellar: '[data-star-svg]',
    }))
      await capture(name, selector);
    for (const index of [3, 5, 8]) {
      await click('[data-era-index="' + index + '"]');
      await capture('era-' + index, '[data-timeline-visual]');
    }
  } else if (route === 'luz/') {
    await capture('webb', '[data-light-view="photo"]');
    await click('[data-light-go="2"]');
    await capture('spectrum', '[data-light-view="spectrum"]');
  } else if (route === 'ceu/') {
    await capture('cmb-map', '[data-cmb-frame]');
    await capture('cmb-observation', '.cmb-pair');
  } else if (route.startsWith('capitulos/')) {
    const chapter = chapters.find((c) => route.includes('/' + c.id + '/'));
    for (const section of chapter.sections) {
      await page.goto(url + '#' + section.id);
      const root = page.locator('[data-mx="' + section.id + '"]');
      if (await root.count()) {
        await root.locator('[data-mx-reset]').click();
        await root.locator('[data-mx-depth]:visible').waitFor();
        await capture(section.id, root.locator('.mx-stage'));
        const options = root.locator('[data-mx-opt]');
        if (await options.count()) await options.last().click();
        else await root.locator('input[type=range]').press('End');
        await capture(section.id + '-end', root.locator('.mx-stage'));
      } else {
        for (const button of await page.locator('[data-cmbj-goto]').all()) {
          await button.click();
          await capture(
            section.id + '-' + (await button.getAttribute('data-cmbj-goto')),
            '[data-cmbj-stage]',
          );
        }
      }
      const extra = page.locator('#' + section.id);
      for (const selector of [
        '[data-bh-stage]',
        '[data-solar-stage]',
        '[data-saturn-stage]',
        '[data-lens-image]',
        '[data-hr-surface]',
        '[data-expansion-group]',
        '[data-transit-sky]',
        '.orbit-view svg',
      ]) {
        for (const [i, region] of (await extra.locator(selector).all()).entries())
          await capture(section.id + '-' + selector.replace(/\W+/g, '') + '-' + i, region);
      }
    }
    await click('.school-extra > summary');
    await click('.lesson-film > summary');
    await capture('lesson-film-scene', '[data-story-viewport]');
    for (const selector of [
      '[data-scale-stage]',
      '[data-evidence-panel="0"]',
      '[data-station]:visible figure',
    ]) {
      const region = page.locator('.school-extra ' + selector).first();
      if (await region.isVisible()) await capture('extra-' + selector.replace(/\W+/g, ''), region);
    }
  } else {
    if (route !== 'desafio/') await capture('photo-band', '.plate', 'photograph');
    const selector = {
      'desafio/': '#desafio',
      'glossario/': '.glossary-search',
      'fontes/': '#creditos-das-capas',
      '404.html': 'main',
    }[route];
    await capture('reading', selector, 'text or reference');
  }
}
try {
  for (const route of routes) {
    regions = [];
    report.routes['/' + route] = regions;
    try {
      await checkRoute(route);
    } catch (err) {
      report.problems.push(route + ' ' + String(err).slice(0, 450));
    }
    console.log('/' + route, regions.length, 'regiões');
  }
  // Check the narrow reading surface and the no-JS photo archive independently.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(new URL('imagens/', base).href);
  regions = report.routes['/imagens/'];
  const panel = page.locator('[data-px-panel="carina-cosmic-cliffs"]');
  await panel.locator('[data-px-zoom="reset"]').click();
  await capture('mobile-carina', panel.locator('[data-px-view]'), 'photograph');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  const staticPage = await browser.newPage({ javaScriptEnabled: false });
  try {
    await staticPage.goto(new URL('imagens/', base).href);
    assert.equal(await staticPage.locator('[data-px-panel]:visible .px-credit a:visible').count(), 4);
    assert.equal(await staticPage.locator('[data-px-panel]:visible [data-px-list]:visible').count(), 4);
  } finally {
    await staticPage.close();
  }
} finally {
  await browser.close();
  await writeFile(join(out, 'audit.json'), JSON.stringify(report, null, 2));
}
assert.deepEqual(report.gpu, []);
assert.deepEqual(report.problems, []);
