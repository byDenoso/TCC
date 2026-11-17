/** Runtime regression for the five teaching plates. Supply BASE and optionally CHROMIUM. */
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import sharp from 'sharp';

const base=process.env.BASE ?? 'http://localhost:4321';
const options={executablePath:process.env.CHROMIUM, args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']};
const browser=await chromium.launch(options);
const probes=[
  ['origem-do-universo','redshift','1','1.000 nm'],
  ['misterios-do-cosmos','lens','4','2 θ₀'],
  ['vida-das-estrelas','star','2','4 L☉'],
  ['sistema-solar','orbit','2','2,83 anos'],
  ['terra-e-atmosfera','air','8','36,79 %']
];

try {
  for(const [chapter,key,input,expected] of probes) {
    const context=await browser.newContext({ viewport:{width:1024,height:768},reducedMotion:'reduce' });
    try {
      const page=await context.newPage();
      const requested=[];
      page.on('request',r=>{if(r.url().includes('/models/atlas-studies/')) requested.push(r.url());});
      await page.goto(base+'/capitulos/'+chapter+'/#prancha',{waitUntil:'domcontentloaded'});
      const plate=page.locator('[data-study="'+key+'"]');
      const slider=plate.getByRole('slider');
      await slider.fill(input);
      const result=plate.locator('[data-study-out]');
      await page.waitForFunction(([key,text])=>document.querySelector('[data-study="'+key+'"] [data-study-out]').value===text,[key,expected]);
      assert.equal(requested.length,0,'GLB transfers must wait for explicit opt-in');
      const button=plate.locator('[data-study-toggle]');
      await button.click();
      await page.waitForFunction(key=>document.querySelector('[data-study="'+key+'"] [data-study-toggle]').getAttribute('aria-pressed')==='true',key,{timeout:60000});
      assert.ok(requested.some(url=>url.endsWith('/'+key+'.glb')));
      assert.equal(await result.textContent(),expected);
      const canvas=plate.locator('canvas');
      assert.ok(await canvas.isVisible());
      const frame=await canvas.screenshot();
      const {channels}=await sharp(frame).stats();
      assert.ok(channels.slice(0,3).some(c=>c.stdev>7),'frame must contain visible geometry');
      await slider.press('Home');
      await slider.press('ArrowRight');
      assert.notEqual(await result.textContent(),expected);
      await button.click();
      assert.ok(await plate.locator('svg').isVisible());
      assert.ok(await canvas.isHidden());
      console.log('PASS',key,expected,'2D → 3D → 2D');
    } finally {await context.close();}
  }
} finally {await browser.close();}
