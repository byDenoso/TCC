// Failure injection around the actual runtime; no rejected GPU errors are masked.
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {chromium} from 'playwright';
import {installGpuProbe} from './lib/gpu-probe.mjs';
import {installGpuLifecycleObserver} from './lib/gpu-lifecycle-observer.mjs';

const server=await createServer({configFile:false,root:process.cwd(),logLevel:'error',server:{host:'127.0.0.1',port:0,strictPort:false}});
await server.listen();const address=server.httpServer.address(),base=`http://127.0.0.1:${address.port}`;
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true,args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist',...(process.platform==='win32'?['--use-angle=d3d11']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])]});
const rows=[];
try{
 for(const mode of ['adapter-pending','module-pending','init-pending','hidden-init','discard-rejected','dispose-pending','validation-error','validation-initialization']){
  const page=await browser.newPage({viewport:{width:900,height:600},reducedMotion:'reduce'}),errors=[],injectedErrors=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{
   if(message.type()!=='error')return;
   const expected=mode==='validation-initialization'?'[cosmos] erro assíncrono do WebGPU durante inicialização falha de validação injetada':mode==='validation-error'?'[cosmos] erro assíncrono do WebGPU; tentando WebGL2 falha de validação injetada':null;
   const value=message.text();if(expected&&(value===expected||value.startsWith(`${expected} `)))injectedErrors.push(value);else errors.push(value);
  });
  await page.addInitScript(installGpuProbe);await page.addInitScript(installGpuLifecycleObserver);
  if(mode==='validation-error')await page.addInitScript(()=>{const request=GPUAdapter.prototype.requestDevice;GPUAdapter.prototype.requestDevice=async function(...args){const device=await request.apply(this,args);window.__INJECT_GPU_VALIDATION=()=>device.dispatchEvent(new GPUUncapturedErrorEvent('uncapturederror',{error:new GPUValidationError('falha de validação injetada')}));return device;};});
  if(mode==='validation-initialization')await page.addInitScript(()=>{const descriptor=Object.getOwnPropertyDescriptor(GPUDevice.prototype,'onuncapturederror');Object.defineProperty(GPUDevice.prototype,'onuncapturederror',{...descriptor,set(handler){descriptor.set.call(this,handler);if(handler)queueMicrotask(()=>this.dispatchEvent(new GPUUncapturedErrorEvent('uncapturederror',{error:new GPUValidationError('falha de validação injetada')})));}});});
  if(mode==='adapter-pending')await page.addInitScript(()=>Object.defineProperty(navigator,'gpu',{configurable:true,value:{requestAdapter:()=>new Promise(()=>{})}}));
  if(['init-pending','hidden-init'].includes(mode))await page.addInitScript(()=>{
   const original=GPUAdapter.prototype.requestDevice;let held=false;
   GPUAdapter.prototype.requestDevice=function(...args){if(held)return original.apply(this,args);held=true;return new Promise((resolve,reject)=>{window.__RELEASE_DEVICE=()=>original.apply(this,args).then(resolve,reject);});};
  });
  if(mode==='discard-rejected')await page.addInitScript(()=>{
   Object.defineProperty(GPUDevice.prototype,'adapterInfo',{configurable:true,get(){return {isFallbackAdapter:true};}});
   GPUDevice.prototype.destroy=function(){throw new Error('falha de descarte injetada');};
  });
  let moduleRequested=false,moduleDone=Promise.resolve();
  if(mode==='module-pending')await page.route('**/three_webgpu.js*',route=>{moduleRequested=true;moduleDone=new Promise(resolve=>setTimeout(resolve,6000)).then(()=>route.continue());return moduleDone;});
  const started=Date.now();await page.goto(`${base}/tests/fixtures/gpu-pending.html?scenario=${mode}`);
  if(mode!=='adapter-pending'){
   const adapter=await page.evaluate(async()=>{const a=await navigator.gpu?.requestAdapter({powerPreference:'low-power',featureLevel:'compatibility',xrCompatible:false});return a?{fallback:a.info?.isFallbackAdapter??null,vendor:a.info?.vendor??'',architecture:a.info?.architecture??''}:null;});
   if(!adapter||adapter.fallback===true){if(process.env.REQUIRE_WEBGPU==='1')throw new Error(`${mode}: physical WebGPU unavailable`);assert.deepEqual(errors,[]);rows.push({mode,adapter,result:'not-tested: physical WebGPU unavailable'});await page.close();continue;}
  }
  const stage=name=>page.locator(`[data-fixture="${name}"]`);
  if(mode==='validation-initialization'){
   await stage('first').locator('.cosmos-volume').waitFor({timeout:12000});
   assert.equal(await stage('first').getAttribute('data-renderer'),'webgl2');
   assert.ok(await page.evaluate(()=>window.__TEST_GPU_LIFECYCLE.some(event=>event.event==='destroy-device')),'failed GPU candidate released before WebGL fallback');
   assert.equal(injectedErrors.length,1,'only the explicitly injected GPU error was logged');
   rows.push({mode,result:'initialization-to-webgl2',elapsedMs:Date.now()-started});
  }else if(mode==='validation-error'){
   await stage('first').locator('.cosmos-volume').waitFor({timeout:12000});
   assert.equal(await stage('first').getAttribute('data-renderer'),'webgpu');
   await page.evaluate(()=>window.__INJECT_GPU_VALIDATION());
   await page.waitForFunction(()=>document.querySelector('[data-fixture="first"]')?.dataset.renderer==='webgl2',null,{timeout:12000});
   assert.ok(await page.evaluate(()=>window.__TEST_GPU_LIFECYCLE.some(event=>event.event==='destroy-device')),'device released before WebGL fallback');
   assert.equal(injectedErrors.length,1,'only the explicitly injected GPU error was logged');
   assert.equal(await page.evaluate(()=>__GPU_PROBE.maxActive()),1);
   rows.push({mode,result:'webgpu-to-webgl2',elapsedMs:Date.now()-started});
  }else if(mode==='adapter-pending'||mode==='module-pending'){
   await stage('first').locator('.cosmos-volume').waitFor({timeout:7000});
   assert.equal(await stage('first').getAttribute('data-renderer'),'webgl2');
   if(mode==='module-pending'){assert.ok(moduleRequested,'delayed WebGPU module was actually requested');await moduleDone;}
   rows.push({mode,result:'webgl2',elapsedMs:Date.now()-started});
  }else{
   if(mode==='dispose-pending'){
    await stage('first').locator('.cosmos-volume').waitFor({timeout:12000});
    assert.equal(await stage('first').getAttribute('data-renderer'),'webgpu');
    await page.evaluate(()=>window.__GPU_PENDING.dispose('first'));
    await page.waitForFunction(()=>typeof window.__RELEASE_DISPOSAL==='function');
   } else if(mode==='init-pending'||mode==='hidden-init'){
    await page.waitForFunction(()=>typeof window.__RELEASE_DEVICE==='function',null,{timeout:12000});
    if(mode==='hidden-init')await page.evaluate(()=>window.__GPU_PENDING.hide('first'));
    else await page.waitForFunction(()=>document.querySelector('[data-fixture="first"]')?.dataset.visualFallback==='true',null,{timeout:7000});
   } else await page.waitForFunction(()=>document.querySelector('[data-fixture="first"]')?.dataset.visualFallback==='true',null,{timeout:12000});
   const requestsBefore=await page.evaluate(()=>window.__TEST_GPU_LIFECYCLE.filter(event=>event.event==='request-device').length);
   await page.evaluate(()=>{window.__GPU_PENDING.add('second');});
   await page.waitForFunction(()=>document.querySelector('[data-fixture="second"]')?.dataset.visualFallback==='true',null,{timeout:7000});
   assert.equal(await stage('second').locator('.cosmos-volume').count(),0,'no competing context while quarantined');
   assert.equal(await page.evaluate(()=>__GPU_PROBE.maxActive()),0,'no WebGL context opened while GPU resource state is unknown');
   assert.equal(await page.evaluate(()=>window.__TEST_GPU_LIFECYCLE.filter(event=>event.event==='request-device').length),requestsBefore,'no second WebGPU device requested while quarantined');
   if(mode==='init-pending'||mode==='hidden-init'||mode==='dispose-pending'){
    if(mode==='dispose-pending')await page.evaluate(()=>window.__RELEASE_DISPOSAL());else await page.evaluate(()=>window.__RELEASE_DEVICE());
    await page.waitForFunction(()=>window.__TEST_GPU_LIFECYCLE.some(event=>event.event==='destroy-device'),null,{timeout:12000});await page.waitForTimeout(150);
    await page.evaluate(()=>{window.__GPU_PENDING.add('third');});
    await stage('third').locator('.cosmos-volume').waitFor({timeout:12000});
    assert.equal(await stage('third').getAttribute('data-renderer'),'webgpu','3D returns after safe cleanup');
   }
   rows.push({mode,result:mode==='discard-rejected'?'2d-until-reload':'2d-then-webgpu',elapsedMs:Date.now()-started});
  }
  assert.deepEqual(errors,[]);await page.close();
 }
 console.log(JSON.stringify({method:'bounded injected promises with real runtime; hardware path reported separately',rows}));
}finally{await browser.close();await server.close();}
