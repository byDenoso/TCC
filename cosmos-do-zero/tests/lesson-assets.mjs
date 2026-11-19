import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import { openExtraExperiments, openLessonStory } from './lib/reader-navigation.mjs';

const base = (process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
const read = async path => JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
const chapters = await read('../src/data/chapters.json');
const frames = await read('../src/data/micro-frames.json');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
try {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const external = [], gl = [];
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (/^https?:$/.test(url.protocol) && url.origin !== new URL(base).origin) {
      external.push(url.href);
      return route.abort();
    }
    return route.continue();
  });
  await context.exposeBinding('reportGL', (_, type) => gl.push(type));
  await context.addInitScript(() => {
    for (const canvas of [HTMLCanvasElement, globalThis.OffscreenCanvas].filter(Boolean)) {
      const original = canvas.prototype.getContext;
      canvas.prototype.getContext = function(type, ...args) {
        if (/webgl/i.test(type)) { Reflect.get(window, 'reportGL')(type); return null; }
        return original.call(this, type, ...args);
      };
    }
  });
  const page = await context.newPage();
  let diagrams = 0, references = 0;
  for (const chapter of chapters) {
    const url = base + '/capitulos/' + chapter.id + '/';
    await page.goto(url);
    for (const section of chapter.sections) {
      const micro = page.locator(`[data-mx="${section.id}"]`);
      if (!(await micro.count())) continue;
      await page.goto(url + '#' + section.id);
      await micro.scrollIntoViewIfNeeded();
      const toggle = micro.locator('[data-mx-reference-toggle]');
      if (frames[section.id]) {
        references++;
        await toggle.click();
        const img = micro.locator('[data-mx-reference]');
        for (const [i, path] of frames[section.id].paths.entries()) {
          if (i) await micro.locator(`[data-mx-opt="${i}"]`).click();
          await img.evaluate(image => image.decode());
          assert.ok((await img.getAttribute('src')).endsWith(path));
        }
      }
      const svg = micro.locator('[data-mx-svg]');
      const original = await svg.innerHTML();
      await micro.locator('[data-mx-step]').click();
      assert.notEqual(await svg.innerHTML(), original, section.id);
      if (frames[section.id]) {
        await toggle.click();
        assert.ok(await micro.locator('[data-mx-reference]').isHidden());
      }
      const view = micro.getByRole('button',{name:'Ver diagrama'});
      await view.click();
      assert.ok(await svg.isVisible());
      await micro.getByRole('button',{name:'Ver cena'}).click();
      await micro.locator('[data-mx-depth]').waitFor();
      diagrams++;
    }
    await openLessonStory(page);
    const story = page.locator('[data-story]');
    await story.locator('[data-story-phase="2"]').click();
    assert.equal(await story.locator('[data-story-phase="2"]').getAttribute('aria-current'), 'step');
    const time = Number(await story.locator('[data-story-time]').inputValue());
    assert.ok(time > 0);
    if (chapter.id !== 'origem-do-universo') {
      const poster = story.locator('[data-story-poster]');
      await poster.evaluate(img => img.decode());
      assert.ok((await poster.getAttribute('src')).endsWith('-3.webp'));
    }
    await story.locator('[data-story-mode="film"]').click();
    await page.waitForFunction(t => Math.abs(document.querySelector('[data-story-film]').currentTime - t) < .1, time);
    await story.locator('[data-story-mode="scene"]').click();
    assert.ok(Math.abs(Number(await story.locator('[data-story-time]').inputValue()) - time) < .1);
    console.log(chapter.id, 'OK');
  }
  await page.goto(base + '/capitulos/galaxias-e-nebulosas/');
  await openExtraExperiments(page);
  for (let i = 0; i < 5; i++) {
    await page.locator(`[data-scale-step="${i}"]`).click();
    assert.equal(await page.locator(`[data-scale-visual="${i}"]`).getAttribute('data-hidden'), 'false');
    assert.ok(await page.locator(`[data-scale-panel="${i}"]`).isVisible());
  }
  await page.goto(base + '/laboratorio/#estrelas');
  for (const mass of ['0.3','1','15']) {
    await page.locator(`[data-mass="${mass}"]`).click();
    await page.locator('[data-star-step="0"]').click();
    assert.equal(await page.locator('[data-star-svg] image').getAttribute('visibility'), 'visible');
    await page.locator('[data-star-step="4"]').click();
    assert.equal(await page.locator('[data-star-svg] image').getAttribute('visibility'), 'hidden');
    const caption = await page.locator('[data-star-caption]').innerText();
    assert.match(caption, mass === '0.3' ? /prevista/i : mass === '1' ? /Anã branca/ : /buraco negro/);
  }
  assert.equal(diagrams, 35);
  assert.equal(references, 10);
  assert.deepEqual(gl, []);
  assert.deepEqual(external, []);
  console.log('35 diagrams, 10 micro references, 6 stories, 5 address scales, 3 stellar paths; 0 GL contexts requested, 0 external HTTP requests.');
} finally {
  await browser.close();
}
