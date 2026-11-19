import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4378').replace(/\/$/,'');
const chapters=JSON.parse(await readFile(new URL('../src/data/chapters.json',import.meta.url),'utf8'));
const evidence=process.env.DEPTH_CAPTURES;
const rows=[], errors=[];
if (evidence) await mkdir(evidence,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROMIUM || undefined});
async function pixels(canvas) {
  await canvas.waitFor();
  return canvas.evaluate(el=>{
    const sample=document.createElement('canvas'); sample.width=96; sample.height=54;
    const ctx=sample.getContext('2d');
    ctx.drawImage(el,0,0,96,54);
    const {data}=ctx.getImageData(4,4,88,44);
    let sum=0,hash=2166136261;
    for(let i=0;i<data.length;i+=4) {
      sum+=data[i]+data[i+1]+data[i+2];
      for(let j=i;j<i+3;j++) hash=Math.imul(hash^data[j],16777619);
    }
    return {hash:hash>>>0,sum};
  });
}
try {
 for (const width of [390,1280]) {
  const page=await browser.newPage({viewport:{width,height:880},reducedMotion:'reduce'});
  page.setDefaultTimeout(9000);
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',r=>{if(r.status()>=400 && r.url().startsWith(base)) errors.push(r.status()+' '+r.url());});
  let count=0;
  for (const chapter of chapters) {
    const url=base+'/capitulos/'+chapter.id+'/';
    await page.goto(url);
    const ids=await page.locator('[data-mx]').evaluateAll(els=>els.map(el=>el.getAttribute('data-mx')));
    for (const id of ids) {
      await page.goto(url+'#'+id);
      const root=page.locator('[data-mx="'+id+'"]'),canvas=root.locator('[data-mx-depth]');
      await root.scrollIntoViewIfNeeded();
      await root.locator('[data-mx-reset]').click(); await canvas.waitFor();
      await page.waitForLoadState('networkidle');
      const before=await pixels(canvas);
      if (id === 'sistema-solar-pequenos-corpos') {
        await root.getByText('Materiais e créditos da cena', {exact:true}).press('Enter');
        assert.ok(await root.getByRole('link',{name:'NASA/JPL-Caltech/UMD · EPOXI'}).isVisible());
      }
      if(evidence && width===1280) {
        await mkdir(evidence+'/abertura',{recursive:true});
        await canvas.screenshot({path:evidence+'/abertura/'+id+'.png'});
      }
      assert.ok(before.sum>20000,id+' empty');
      const options=root.locator('[data-mx-opt]'),range=root.locator('[data-mx-range]');
      if (await options.count()) await options.last().click(); else await range.press('End');
      await page.waitForLoadState('networkidle');
      const after=await pixels(canvas);
      assert.notEqual(before.hash,after.hash,id+' unchanged between endpoints');
      if(evidence && width===1280) await canvas.screenshot({path:evidence+'/'+id+'.png'});
      await root.getByRole('button',{name:'Ver diagrama'}).click();
      assert.ok(await root.locator('[data-mx-svg]').isVisible());
      await root.getByRole('button',{name:'Ver cena'}).click();await canvas.waitFor();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,id+' overflow');
      const credits = await root.locator('.mx-detail-note summary').allTextContents();
      rows.push({width,id,initial:before.hash,selected:after.hash,credits:credits.length});count++;
    }
  }
  assert.equal(count,35);
  const selected = page.locator('[data-mx="terra-e-atmosfera-habitabilidade"]');
  const credits = selected.getByText('Materiais e créditos da cena', {exact:true});
  await credits.click();
  assert.ok(await selected.locator('details.mx-detail-note a[href*="blue-marble"]').isVisible());
  assert.equal(await selected.locator('[data-mx-play]').getAttribute('aria-pressed'),'false');
  await page.close();
 }
 assert.deepEqual(errors,[]);
 const fail=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
 await fail.route('**/formation/disc.webp',route=>route.fulfill({status:503,body:''}));
 await fail.goto(base+'/capitulos/sistema-solar/#sistema-solar-disco');
 const root=fail.locator('[data-mx="sistema-solar-disco"]');
 await root.locator('[data-mx-opt="1"]').click();
 await fail.waitForLoadState('networkidle');
 assert.ok(await root.locator('[data-mx-svg]').isVisible());
 assert.equal(await root.locator('[data-mx-opt="1"]').getAttribute('aria-pressed'),'true');
 await root.locator('[data-mx-opt="0"]').click();await root.locator('[data-mx-depth]').waitFor();
 if(evidence)await writeFile(evidence+'/micro-depth.json',JSON.stringify(rows,null,2));
 console.log('35 cenas × 2 telas com mudanças de pixels, diagrama alternativo, recuperação de textura e sem rolagem horizontal.');
} finally { await browser.close(); }

