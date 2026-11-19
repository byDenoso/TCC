import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {chromium} from 'playwright';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4339').replace(/\/$/, '');
const out = 'test-results/lab-plates';
await mkdir(out, {recursive:true});
const browser = await chromium.launch();
try {
  const page = await browser.newPage({viewport:{width:1120,height:900}, reducedMotion:'reduce'});
  const errors = [];
  await page.addInitScript(() => {
    window.labGLRequests = [];
    const get = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type,...args) {
      if (/webgl|webgpu/i.test(type)) { window.labGLRequests.push(type); return null; }
      return get.call(this,type,...args);
    };
  });
  page.on('pageerror', e => errors.push(e.message));
  const q = selector => page.locator(selector);
  const snapshot = async (selector, name) => {
    const stage = q(selector);
    await stage.scrollIntoViewIfNeeded();
    await page.waitForFunction(s => document.querySelector(s)?.dataset.labPlate === 'ready', selector);
    const hash = await stage.locator('canvas').evaluate(canvas => canvas.toDataURL());
    if (name) {
      await page.locator('.badge-toast').first().waitFor({state:'hidden'});
      await stage.screenshot({path:out+'/'+name+'.png'});
    }
    return hash;
  };
  await page.goto(base+'/laboratorio/');
  const orbit = '.orbit-view svg';
  const orbitBefore = await snapshot(orbit);
  await q('[data-orbit-preset="circle"]').click();
  await q('[data-orbit-input="phase"]').fill('25');
  assert.match(await q('[data-orbit-distance]').innerText(),/1,00 UA/);
  assert.notEqual(await snapshot(orbit,'orbita'),orbitBefore);
  await q('[data-orbit-play]').click();
  assert.equal(await q('[data-orbit-input="phase"]').inputValue(),'37.5');
  const initialExpansion = await snapshot('[data-expansion-group]');
  await q('[data-expansion-input="z"]').fill('3');
  assert.match(await q('[data-expansion-epoch]').innerText(),/0,250/);
  assert.notEqual(await snapshot('[data-expansion-group]','expansao-flrw'), initialExpansion);
  const initialTransit = await snapshot('[data-transit-sky]','transito');
  await q('[data-transit-preset="miss"]').click();
  assert.match(await q('[data-transit-flux]').innerText(),/100/);
  assert.notEqual(await snapshot('[data-transit-sky]'), initialTransit);
  const initialHR = await snapshot('[data-hr-surface]');
  await q('[data-hr-preset="gigante"]').click();
  assert.notEqual(await snapshot('[data-hr-surface]','gigante'),initialHR);
  await q('[data-lens-geometry]').evaluate(el => el.open = true);
  const initialLens = await snapshot('[data-lens-fallback]');
  await q('[data-lens-example]').click();
  assert.notEqual(await snapshot('[data-lens-fallback]','lente-geometria'),initialLens);
  await q('[data-lens-image]').scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>document.querySelector('[data-lens-brightness]').value==='photo');
  const image = q('[data-lens-image]');
  const lensed = await image.evaluate(el=>el.toDataURL());
  await image.screenshot({path:out+'/lente-fonte.png'});
  await q('[data-lens-brightness]').selectOption('gaussian');
  assert.notEqual(await image.evaluate(el=>el.toDataURL()),lensed);

  await page.context().setOffline(true);
  await q('[data-hr-preset="branca"]').click();
  assert.notEqual(await snapshot('[data-hr-surface]'), initialHR);
  assert.deepEqual(await page.evaluate(()=>window.labGLRequests),[]);
  await page.context().setOffline(false);
  await page.goto(base+'/observatorio/?z=0.5');
  const tempo = '[data-t-3d] svg';
  const first = await snapshot(tempo);
  await q('[data-3d-play]').click();
  assert.notEqual(await snapshot(tempo), first);
  await q('[data-t-preset="1090"]').click();
  await snapshot(tempo,'tempo');
  assert.match(await q('[data-t-out="age"]').innerText(),/mil/);
  for(const [station,stage] of [['expansao','[data-e-svg]'],['hubble','[data-h-sky]'],['receita','[data-r-group]']]) {
    await q('[data-obs-tab="'+station+'"]').click();
    const skip=q('[data-station="'+station+'"] [data-guess-skip]');
    if(await skip.isVisible())await skip.click();
    const before = await snapshot(stage);
    if(station==='expansao') {
      await q('[data-e-range]').fill('2.5');
      assert.match(await q('[data-e-selection]').innerText(),/5,7 agora/);
    } else if(station==='hubble') {
      await q('[data-h-next]').click();
      assert.ok((await q('[data-h-reading]').innerText()).length>15);
      await q('[data-h-new]').click();
    } else {
      await q('[data-r-scenario="crunch"]').click();
    }
    assert.notEqual(await snapshot(stage,station),before);
  }
  const mobile = await browser.newPage({ viewport:{width:390,height:844} });
  mobile.setDefaultTimeout(8000);
  const scrollAway = async () => { await mobile.locator('footer').scrollIntoViewIfNeeded(); };
  const until = (selector, value) => mobile.waitForFunction(([s,v]) =>
    document.querySelector(s)?.getAttribute('aria-pressed') === v, [selector,value]);
  await mobile.goto(base+'/laboratorio/');
  for (const [play,input] of [['[data-transit-play]','[data-transit-input="phase"]'],
    ['[data-expansion-play]','[data-expansion-input="z"]'], ['[data-orbit-play]','[data-orbit-input="phase"]']]) {
    const control = mobile.locator(play);
    await control.click();
    await until(play,'true');
    const start = await mobile.locator(input).inputValue();
    await mobile.waitForFunction(([s,v])=>document.querySelector(s).value !== v,[input,start]);
    await scrollAway();
    await until(play,'false');
    const paused = await mobile.locator(input).inputValue();
    await mobile.waitForTimeout(200);
    assert.equal(await mobile.locator(input).inputValue(), paused);
  }
  await mobile.goto(base+'/observatorio/?z=0.5');
  const flight=mobile.locator('[data-t-3d]');
  await flight.scrollIntoViewIfNeeded();
  if(await mobile.locator('[data-3d-play]').getAttribute('aria-pressed')!=='true')
    await mobile.locator('[data-3d-play]').click();
  await until('[data-3d-play]','true'); await scrollAway(); await until('[data-3d-play]','false');
  await mobile.emulateMedia({reducedMotion:'reduce'});
  await flight.scrollIntoViewIfNeeded();
  await mobile.locator('[data-3d-play]').click();
  assert.equal(await mobile.locator('[data-3d-play]').getAttribute('aria-pressed'),'false');
  await flight.screenshot({path:out+'/tempo-mobile.png'});

  for(const mode of ['assets','canvas']) {
    const ctx = await browser.newContext({reducedMotion:'reduce'});
    if(mode==='assets') await ctx.route('**/models/lab/photosphere.webp',r=>r.abort());
    else await ctx.addInitScript(()=>{
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(kind,...args) {
        if (kind==='2d') return null;
        return original.call(this,kind,...args);
      };
    });
    const test = await ctx.newPage();
    await test.goto(base+'/laboratorio/');
    const stage=test.locator('[data-transit-sky]');
    await stage.scrollIntoViewIfNeeded();
    await test.locator('[data-transit-preset="earth"]').click();
    assert.notEqual(await stage.getAttribute('data-lab-plate'),'ready');
    assert.equal(await test.locator('[data-transit-star]').evaluate(e=>getComputedStyle(e).opacity),'1');
    assert.match(await test.locator('[data-transit-depth]').innerText(),/0,00839/);
    if(mode==='canvas') {
      await test.locator('[data-lens-example]').click();
      assert.ok(await test.locator('[data-lens-image-fallback]').isVisible());
      assert.equal(await test.locator('[data-lens-image-point]').first().getAttribute('visibility'),'visible');
    }
    await ctx.close();
  }
  console.log('Celular: reprodução e pausa fora da tela em quatro instrumentos. Trânsito e lente preservados no fallback.');
  assert.deepEqual(await page.evaluate(()=>window.labGLRequests),[]);
  assert.deepEqual(errors,[]);
  console.log('9 cenas atualizadas por controles, curvas e leituras preservadas; imagens em '+out);
} finally {await browser.close();}
