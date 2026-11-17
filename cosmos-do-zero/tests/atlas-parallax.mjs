// Run against a built preview: BASE_URL=… [CHROMIUM_PATH=…] node tests/atlas-parallax.mjs
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import sharp from 'sharp';

const base = process.env.BASE_URL || 'http://127.0.0.1:4173';
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH,
  args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']
});
try {
  const page = await browser.newPage({viewport:{width:1200,height:850}, reducedMotion:'reduce'});
  const errors = [];
  const glbs = [];
  page.on('pageerror', err => errors.push(err.message));
  page.on('request', req => { if(req.url().endsWith('/parallax/instrument.glb')) glbs.push(req.url()); });
  await page.goto(base + '/laboratorio/#paralaxe', {waitUntil:'domcontentloaded'});
  const bench = page.locator('[data-parallax]');
  const slider = bench.getByRole('slider');
  await bench.getByLabel('Cai à metade').check();
  const total = bench.locator('[data-total]');
  assert.equal(await total.innerText(), '0,50″');
  await slider.fill('8');
  assert.equal(await total.innerText(), '0,25″');
  assert.equal(await bench.locator('[data-p]').innerText(), '0,125″');
  assert.match(await bench.locator('[data-feedback]').innerText(), /Seu palpite confere/);
  assert.equal(glbs.length,0);
  await bench.getByRole('button',{name:'Explorar a maquete em 3D'}).click();
  await bench.getByRole('button',{name:'Fechar 3D'}).waitFor({timeout:50000});
  assert.ok(glbs.length);
  const canvas = bench.locator('canvas');
  const pixels = async () => {
    const frame = await canvas.screenshot();
    const chars = await sharp(frame).stats();
    assert.ok(chars.channels.slice(0,3).some(x=>x.stdev>9));
    return frame;
  };
  const first = await pixels();
  await slider.fill('1');
  assert.equal(await total.innerText(),'2,00″');
  assert.notDeepEqual(await pixels(),first);
  await bench.getByRole('button',{name:'Vista superior'}).click();
  assert.equal(await bench.locator('[data-top]').getAttribute('aria-pressed'),'true');
  const above = await pixels();
  const detail = bench.getByRole('button',{name:'Detalhe da Terra A'});
  await detail.click();
  assert.equal(await detail.getAttribute('aria-pressed'), 'true');
  assert.equal(await bench.locator('[data-top]').getAttribute('aria-pressed'),'false');
  assert.notDeepEqual(await pixels(), above);
  await bench.getByRole('button',{name:'Fechar 3D'}).click();
  assert.ok(await canvas.isHidden());
  await page.setViewportSize({width:390,height:844});
  await slider.press('End');
  assert.equal(await total.innerText(),'0,20″');
  assert.ok(await bench.evaluate(el=>el.getBoundingClientRect().right<=window.innerWidth+1));
  assert.deepEqual(errors,[]);
  console.log('Paralaxe: régua 1/4/8/10 pc, 2D sem GLB, 3D com geometria e atualização, vista superior e detalhe da Terra A, teclado e largura 390 px.');
} finally {
  await browser.close();
}
