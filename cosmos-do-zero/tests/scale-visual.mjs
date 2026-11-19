// Pixel regression of the five local illustrated address panels.
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {chromium} from 'playwright';
import sharp from 'sharp';
import {openExtraExperiments} from './lib/reader-navigation.mjs';

const base=(process.env.BASE_URL??'http://127.0.0.1:4321').replace(/\/$/,'');
const folder=join(process.cwd(),'tests','baselines','scale-assets');
const update=process.env.UPDATE_SCALE_BASELINES==='1';
if(update&&process.env.CI)throw new Error('Visual baselines cannot be updated in CI');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true});
try{
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1,reducedMotion:'reduce',colorScheme:'dark'}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
 await page.addInitScript(()=>{localStorage.setItem('cosmos-theme','dark');Object.defineProperty(navigator,'gpu',{configurable:true,value:undefined});});
 await page.goto(`${base}/capitulos/galaxias-e-nebulosas/`,{waitUntil:'networkidle'});await openExtraExperiments(page);
 const stage=page.locator('[data-scale-stage]');await stage.scrollIntoViewIfNeeded();
 const diagram=stage.locator('[data-scale-svg]');
 const samples=[],references=[],regressions=[];
 const mean=(a,b)=>{let total=0;for(let n=0;n<a.length;n++)total+=Math.abs(a[n]-b[n]);return total/a.length;};
 if(update)await mkdir(folder,{recursive:true});
 for(let i=0;i<5;i++){
  await page.locator(`[data-scale-step="${i}"]`).click();await stage.scrollIntoViewIfNeeded();
  const selected=diagram.locator(`[data-scale-visual="${i}"]`);
  assert.ok(await selected.isVisible());
  assert.equal(await diagram.locator('[data-scale-visual]:visible').count(),1);
  assert.equal(await page.locator(`[data-scale-step="${i}"]`).getAttribute('aria-pressed'),'true');
  await selected.locator('image').evaluateAll(nodes=>Promise.all(nodes.map(node=>{
   const image=new Image();image.src=node.href.baseVal;return image.decode();
  })));
  await page.evaluate(()=>document.fonts.ready);
  const image=await diagram.screenshot();
  const path=join(folder,`scale-${i}.png`);
  if(update)await writeFile(path,image);
  const reference=await readFile(path);
  const pixels=async input=>(await sharp(input).resize(96,64,{fit:'fill'}).removeAlpha().raw().toBuffer());
  const bounds=await sharp(image).metadata(), target=await sharp(reference).metadata();
  // Chromium includes one extra top scanline when the scrolled SVG starts between CSS pixels.
  // Compare the same rectangle; other viewport and artwork changes keep their original error.
  const aligned=bounds.width===target.width && bounds.height===target.height+1
   ? await sharp(image).extract({left:0,top:1,width:target.width,height:target.height}).png().toBuffer()
   : image;
  const actual=await pixels(aligned),expected=await pixels(reference);
  const delta=mean(actual,expected),black=mean(Buffer.alloc(expected.length),expected);
  if(delta>=2){
   const failures=join(process.cwd(),'test-results','scale-visual');await mkdir(failures,{recursive:true});
   await writeFile(join(failures,`scale-${i}-actual.png`),image);
   const difference=Buffer.from(actual.map((value,n)=>Math.abs(value-expected[n])));
   await sharp(difference,{raw:{width:96,height:64,channels:3}}).png().toFile(join(failures,`scale-${i}-diff.png`));
   regressions.push({scale:i,delta});
  }
  assert.ok(black>=2,`scale ${i}: a black frame must fail the comparison`);
  references.push(expected);
  samples.push({scale:i,delta,blackFrameDelta:black});
 }
 let closestPair=Infinity;
 for(let i=0;i<references.length;i++)for(let j=i+1;j<references.length;j++)closestPair=Math.min(closestPair,mean(references[i],references[j]));
 assert.ok(closestPair>=2,`the wrong scale must fail comparison: closest pair ${closestPair}`);
 assert.deepEqual(regressions,[],`mean pixel error >= 2/255: ${JSON.stringify(regressions)}`);
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({method:'five existing views; Chromium SVG with local rasters; reduced motion; 96x64 RGB mean absolute error < 2/255',update,closestPair,samples}));
}finally{await browser.close();}
