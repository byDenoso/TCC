// Five existing scale views; deterministic WebGL2 software renderer and reduced motion.
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {chromium} from 'playwright';
import sharp from 'sharp';
import {openExtraExperiments} from './lib/reader-navigation.mjs';

const base=(process.env.BASE_URL??'http://127.0.0.1:4321').replace(/\/$/,'');
const folder=join(process.cwd(),'tests','baselines','scale');
const update=process.env.UPDATE_SCALE_BASELINES==='1';
if(update&&process.env.CI)throw new Error('Visual baselines cannot be updated in CI');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1,reducedMotion:'reduce',colorScheme:'dark'}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
 await page.addInitScript(()=>{localStorage.setItem('cosmos-theme','dark');Object.defineProperty(navigator,'gpu',{configurable:true,value:undefined});});
 await page.goto(`${base}/capitulos/galaxias-e-nebulosas/`,{waitUntil:'networkidle'});await openExtraExperiments(page);
 const stage=page.locator('[data-scale-stage]');await stage.scrollIntoViewIfNeeded();await stage.locator('canvas.cosmos-volume').waitFor({timeout:30000});
 assert.equal(await stage.getAttribute('data-renderer'),'webgl2');
 const scene=page.locator('[data-scene="scale"]');await scene.locator('.cosmos-view-options summary').click();await scene.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('standard');
 const samples=[],references=[];
 const mean=(a,b)=>{let total=0;for(let n=0;n<a.length;n++)total+=Math.abs(a[n]-b[n]);return total/a.length;};
 if(update)await mkdir(folder,{recursive:true});
 for(let i=0;i<5;i++){
  await page.locator(`[data-scale-step="${i}"]`).click();await stage.scrollIntoViewIfNeeded();await stage.locator('canvas.cosmos-volume').waitFor({timeout:30000});
  await page.waitForFunction(()=>{const s=document.querySelector('[data-scale-stage]');return s?.dataset.qualityPending==='false'&&s.dataset.qualityError!=='true';},null,{timeout:30000});
  await page.waitForTimeout(1500);
  assert.equal(await page.locator(`[data-scale-step="${i}"]`).getAttribute('aria-pressed'),'true');
  assert.equal(await stage.getAttribute('data-renderer'),'webgl2');
  if(i===1) assert.match(await page.locator('[data-scale-panel="1"]').innerText(),/anel azul indica a órbita da Terra/);
  const image=await stage.locator('canvas.cosmos-volume').screenshot();
  const path=join(folder,`scale-${i}.png`);
  if(update)await writeFile(path,image);
  const reference=await readFile(path);
  const pixels=async input=>(await sharp(input).resize(96,64,{fit:'fill'}).removeAlpha().raw().toBuffer());
  const actual=await pixels(image),expected=await pixels(reference);
  const delta=mean(actual,expected),black=mean(Buffer.alloc(expected.length),expected);
  if(delta>=2){
   const failures=join(process.cwd(),'test-results','scale-visual');await mkdir(failures,{recursive:true});
   await writeFile(join(failures,`scale-${i}-actual.png`),image);
   const difference=Buffer.from(actual.map((value,n)=>Math.abs(value-expected[n])));
   await sharp(difference,{raw:{width:96,height:64,channels:3}}).png().toFile(join(failures,`scale-${i}-diff.png`));
  }
  assert.ok(delta<2,`scale ${i}: mean pixel error ${delta} >= 2/255`);
  assert.ok(black>=2,`scale ${i}: a black frame must fail the comparison`);
  references.push(expected);
  samples.push({scale:i,delta,blackFrameDelta:black});
 }
 let closestPair=Infinity;
 for(let i=0;i<references.length;i++)for(let j=i+1;j<references.length;j++)closestPair=Math.min(closestPair,mean(references[i],references[j]));
 assert.ok(closestPair>=2,`the wrong scale must fail comparison: closest pair ${closestPair}`);
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({method:'five existing views; Chromium WebGL2 SwiftShader; reduced motion; standard quality; 96x64 RGB mean absolute error < 2/255',update,closestPair,samples}));
}finally{await browser.close();}
