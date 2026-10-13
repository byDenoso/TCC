import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {writeFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {installGpuProbe} from './lib/gpu-probe.mjs';
const base=process.env.BASE_URL||'http://127.0.0.1:4350',out=resolve('../../..','outputs/qa-funcional');mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={conditions:'Chrome / ANGLE SwiftShader; viewport emulation; deterministic requestAnimationFrame cadence on the active Observatory implementation',origins:[],cadences:[]};
try {
 for(const initialWidth of[390,1280]){
  const p=await browser.newPage({viewport:{width:initialWidth,height:900},reducedMotion:'reduce'});await p.addInitScript(installGpuProbe);const errors=[];p.on('pageerror',e=>errors.push(String(e)));
  await p.goto(base+'/capitulos/origem-do-universo/');await p.locator('[data-step-dot="0"]').click();const root=p.locator('[data-mx="origem-do-universo-o-universo"]'),stage=root.locator('.mx-volume-stage');await stage.scrollIntoViewIfNeeded();await stage.locator('canvas.cosmos-volume').waitFor();
  await p.waitForFunction(()=>document.querySelector('[data-mx="origem-do-universo-o-universo"] .mx-volume-stage').dataset.qualityPending==='false');
  const prepared=await stage.getAttribute('data-galaxy-seed-size');assert.ok(['768','1536'].includes(prepared));
  if(initialWidth===390){await p.setViewportSize({width:1280,height:900});await p.waitForFunction(()=>document.querySelector('[data-mx="origem-do-universo-o-universo"] .mx-volume-stage').dataset.textureQuality==='1536');}
  await root.locator('[data-mx-range]').fill('1.5');assert.match(await root.locator('[data-mx-caption]').innerText(),/1,5|1.5/);
  const texture=await p.evaluate(()=>[...__COSMOS_QA.scenes.values()].map(f=>f()).find(s=>s.name==='origem-do-universo-o-universo').textureDimensions);assert.equal(texture.length,6);assert.ok(texture.every(t=>t.width===1536));assert.deepEqual(errors,[]);assert.equal(await p.evaluate(()=>__GPU_PROBE.maxActive()),1);
  report.origins.push({initialWidth,finalWidth:1280,preparedSize:prepared,textureDimensions:texture,errors,maxActualContexts:1});await p.close();
 }
 for(const hz of[60,120]){
  const p=await browser.newPage({viewport:{width:1280,height:900}});await p.goto(base+'/?lab=expansao#observatorio');const stage=p.locator('[data-e-volume]');await stage.scrollIntoViewIfNeeded();await p.waitForTimeout(100);
  await p.evaluate(()=>{window.__nativeRAF=requestAnimationFrame;window.__nativeCAF=cancelAnimationFrame;window.__cadence={queue:new Map(),sequence:0};window.requestAnimationFrame=fn=>{const id=++__cadence.sequence;__cadence.queue.set(id,fn);return id;};window.cancelAnimationFrame=id=>__cadence.queue.delete(id);document.querySelector('[data-e-play]').click();});
  const state=await p.evaluate(hz=>{let now=1000;for(let i=0;i<hz;i++){const callbacks=[...__cadence.queue.values()];__cadence.queue.clear();for(const fn of callbacks)fn(now);now+=1000/hz;}const e=document.querySelector('[data-e-range]'),value=Number(e.value),pressed=document.querySelector('[data-e-play]').getAttribute('aria-pressed');document.querySelector('[data-e-play]').click();const queueAfterPause=__cadence.queue.size;window.requestAnimationFrame=__nativeRAF;window.cancelAnimationFrame=__nativeCAF;return{value,pressed,queueAfterPause,positions:[...document.querySelectorAll('.e-galaxy')].map(e=>e.getAttribute('transform'))};},hz);
  const expected=1+(16+(hz-1)*1000/hz)*.00022;assert.ok(Math.abs(state.value-expected)<=.0051,`${hz}Hz: ${state.value} vs ${expected}`);assert.equal(state.pressed,'true');assert.equal(state.queueAfterPause,0);assert.ok(state.value>1.2);
  await p.waitForTimeout(100);assert.equal(Number(await p.locator('[data-e-range]').inputValue()),state.value);
  report.cadences.push({hz,expectedUnquantized:expected,...state});await p.close();
 }
}finally{await browser.close();}
writeFileSync(resolve(out,'origin-cadence-regression.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
