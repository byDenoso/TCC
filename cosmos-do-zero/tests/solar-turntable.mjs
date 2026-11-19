// Run against the local site with node tests/solar-turntable.mjs http://127.0.0.1:4339
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { existsSync, readFileSync } from 'node:fs';

const base = process.argv[2] || 'http://127.0.0.1:4321';
const viewSource = readFileSync(new URL('../src/scripts/visual/world-view.ts', import.meta.url), 'utf8');
assert.doesNotMatch(viewSource, /styleEarth|from ['"]three|from ['"].*runtime['"]/);
const chrome = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const browser = await chromium.launch({ executablePath: existsSync(chrome) ? chrome : undefined });
try {
  const page = await browser.newPage({ reducedMotion: 'reduce', viewport: { width: 1024, height: 860 } });
  page.setDefaultTimeout(12000);
  const blocked = [];
  const frames = new Set();
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== new URL(base).origin) {
      blocked.push(url.href);
      return route.abort();
    }
    if (url.pathname.includes('/models/solar-turntable/')) frames.add(url.pathname);
    return route.continue();
  });
  await page.addInitScript(() => {
    window.solarGLCalls = [];
    for (const type of [HTMLCanvasElement, window.OffscreenCanvas].filter(Boolean)) {
      const native = type.prototype.getContext;
      type.prototype.getContext = function (kind, ...args) {
        if (/webgl/i.test(kind)) { window.solarGLCalls.push(kind); return null; }
        return native.call(this, kind, ...args);
      };
    }
  });
  async function shown(img, path) {
    await img.scrollIntoViewIfNeeded();
    await page.waitForFunction(([el, path]) => el.complete && el.naturalWidth > 0 &&
      el.currentSrc.endsWith(path), [await img.elementHandle(), path]);
  }
  const angle = root => root.locator('[data-world-angle]');
  await page.goto(base+'/laboratorio/?planeta=marte#a');
  const catalog = page.locator('[data-island="planets"]');
  const planet = catalog.locator('[data-planet-img]');
  await shown(planet, 'marte/00.webp');
  assert.ok([...frames].every(url => url.endsWith('/00.webp')));
  await catalog.locator('[data-planet="mercurio"]').first().click();
  await angle(catalog).press('ArrowRight');
  await shown(planet, 'mercurio/01.webp');
  const stage = catalog.locator('[data-planet-stage]');
  await stage.scrollIntoViewIfNeeded();
  const box = await stage.boundingBox();
  const x = box.x + box.width/2, y = box.y + box.height/2;
  await page.mouse.move(x,y); await page.mouse.down(); await page.mouse.move(x+20,y); await page.mouse.up();
  await shown(planet, 'mercurio/03.webp');
  await catalog.locator('[data-world-zoom]').press('ArrowRight');
  assert.equal(await planet.evaluate(el => el.style.scale), '1.05');

  const compare = page.locator('[data-island="compare"]');
  await compare.locator('[data-compare-b]').selectOption('saturno');
  const right = compare.locator('[data-compare-img="b"]');
  await shown(right,'saturno-globo/00.webp');
  const left = compare.locator('[data-compare-img="a"]');
  const ratio = await left.evaluate(el => parseFloat(el.style.width)/100);
  assert.ok(Math.abs(ratio - 6378/60268) < 0.00002);
  await compare.locator('[data-compare-swap]').click();
  await shown(left,'saturno-globo/00.webp');
  assert.match(await compare.locator('[data-compare-values]').innerText(), /km/);
  assert.deepEqual(await page.evaluate(() => window.solarGLCalls), []);

  await page.goto(base+'/capitulos/sistema-solar/#sistema-solar-sol-e-planetas');
  const studio = page.locator('[data-solar-studio]');
  await studio.evaluate(el => { for (let p=el; p; p=p.parentElement) if (p.tagName==='DETAILS') p.open=true; });
  const disk = studio.locator('[data-solar-poster]');
  await studio.locator('[data-solar-layer="clouds"]').uncheck();
  await shown(disk,'terra-ar/00.webp');
  await studio.locator('[data-solar-moon]').click();
  await shown(disk,'lua/00.webp');
  await studio.locator('[data-solar-play]').click();
  await shown(disk,'lua/01.webp');
  await page.route('**/lua/02.webp', route => route.abort());
  await angle(studio).press('ArrowRight');
  await shown(disk,'lua/00.webp');
  assert.equal(await angle(studio).inputValue(), '0');
  await page.route('**/marte/00.webp', route => route.abort());
  await studio.locator('[data-solar-planet="3"]').click();
  await shown(disk,'portraits/marte.webp');
  await studio.locator('[data-solar-mode="distances"]').click();
  assert.match(await studio.locator('[data-solar-limit]').innerText(), /Semieixos/);
  assert.ok(await studio.locator('.solar-credit-line').isVisible());
  assert.deepEqual(await page.evaluate(() => window.solarGLCalls), []);
  assert.deepEqual(blocked, []);
  console.log('PASS: local-only routes, 0 WebGL calls, lazy frames, drag, zoom, radius ratio, swap, layers, Moon rotation and failed-frame recovery.');
} finally {
  await browser.close();
}
