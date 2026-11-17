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
    const mobile=process.env.ATLAS_MOBILE==='1';
    const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1024,height:768}, isMobile:mobile,hasTouch:mobile,reducedMotion:'reduce'});
    try {
      const page=await context.newPage();
      const requested=[], errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      page.on('console',msg=>{if(msg.type()==='error' && /shader|program/i.test(msg.text())) errors.push(msg.text());});
      page.on('request',r=>{if(r.url().includes('/models/atlas-studies/') && r.url().endsWith('.glb')) requested.push(r.url());});
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
      if(process.env.ATLAS_FRAMES) await plate.locator('.study-viewport').screenshot({path:process.env.ATLAS_FRAMES+'/'+key+'-3d.png'});
      const {channels}=await sharp(frame).stats();
      assert.ok(channels.slice(0,3).some(c=>c.stdev>7),'frame must contain visible geometry');
      await slider.press('Home');
      await slider.press('ArrowRight');
      assert.notEqual(await result.textContent(),expected);
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const first=await sharp(frame).resize(180,90).removeAlpha().raw().toBuffer();
      const moved=await sharp(await canvas.screenshot()).resize(180,90).removeAlpha().raw().toBuffer();
      let changed=0;
      for(let j=0;j<first.length;j+=3) if(Math.abs(first[j]-moved[j])+Math.abs(first[j+1]-moved[j+1])+Math.abs(first[j+2]-moved[j+2])>25) changed++;
      assert.ok(changed>24,'a changed slider must redraw the measured object itself');
      assert.ok(await plate.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'instrument fits viewport');
      await button.click();
      assert.ok(await plate.locator('svg').isVisible());
      assert.ok(await canvas.isHidden());
      if(process.env.ATLAS_FRAMES) { await slider.fill(input); await plate.locator('.study-viewport').screenshot({path:process.env.ATLAS_FRAMES+'/'+key+'-2d.png'}); }
      assert.deepEqual(errors,[]);
      console.log('PASS',key,expected,'2D → 3D → 2D');
    } finally {await context.close();}
  }
} finally {await browser.close();}
