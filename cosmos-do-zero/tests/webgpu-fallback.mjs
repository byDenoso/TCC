// Browser integration of real scene, failure injection, and bounded context ownership.
// Failure injection changes only the browser capability for this test; no data is invented.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import sharp from 'sharp';
import {mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import { installGpuProbe } from './lib/gpu-probe.mjs';
import { selectLessonStep } from './lib/reader-navigation.mjs';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const screenshots=process.env.SCREENSHOTS_DIR;
if(screenshots)await mkdir(screenshots,{recursive:true});
const rows=[];let blockedFrame=null;
const allModes=['missing', 'rejected', 'no3d', 'pipeline-blocked', 'native'];
const requested=process.env.COSMOS_WEBGPU_MODES?.split(',');
if(requested?.some(mode=>!allModes.includes(mode)))throw new Error('Modo de teste WebGPU desconhecido');
for (const mode of requested??allModes) {
  console.log(`WEBGPU_CASE ${mode}`);
  const nativeWindows=['native','pipeline-blocked'].includes(mode)&&process.platform==='win32'&&process.env.COSMOS_SOFTWARE_BACKEND!=='1';
  const args=nativeWindows?['--enable-unsafe-webgpu','--ignore-gpu-blocklist','--use-angle=d3d11']:
    ['--enable-unsafe-webgpu','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
  if(process.env.COSMOS_CHROME_GPU_FLAGS)args.push(...process.env.COSMOS_CHROME_GPU_FLAGS.split(',').filter(Boolean));
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM || undefined,headless:true,args});
  try {
    const page=await browser.newPage({viewport:{width:390,height:900},colorScheme:'dark'});
    if(mode==='pipeline-blocked')await page.route('**/cinematic-pipeline.*.js',route=>route.abort());
    await page.addInitScript(installGpuProbe);
    await page.addInitScript(()=>{
      window.__TEST_GPU_LIFECYCLE=[];
      const request=globalThis.GPUAdapter?.prototype.requestDevice;
      if(!request)return;
      GPUAdapter.prototype.requestDevice=async function(...args){
        const sequence=window.__TEST_GPU_LIFECYCLE.length;
        window.__TEST_GPU_LIFECYCLE.push({event:'request-device',sequence,time:performance.now()});
        try{
          const device=await request.apply(this,args);
          window.__TEST_GPU_LIFECYCLE.push({event:'device-ready',sequence,time:performance.now()});
          const destroy=device.destroy.bind(device);
          device.destroy=()=>{window.__TEST_GPU_LIFECYCLE.push({event:'destroy-device',sequence,time:performance.now()});return destroy();};
          return device;
        }catch(error){window.__TEST_GPU_LIFECYCLE.push({event:'device-rejected',sequence,time:performance.now()});throw error;}
      };
    });
    await page.addInitScript(()=>{if(window.__COSMOS_QA)window.__COSMOS_QA.objects=new Map();});
    if(mode==='missing'||mode==='no3d')await page.addInitScript(()=>Object.defineProperty(navigator,'gpu',{configurable:true,value:undefined}));
    if(mode==='rejected')await page.addInitScript(()=>Object.defineProperty(navigator,'gpu',{configurable:true,value:{requestAdapter:async()=>null}}));
    if(mode==='no3d')await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:get.call(this,type,...args);};});
    if(mode==='native')await page.addInitScript(()=>{
      const descriptor=globalThis.GPUDevice && Object.getOwnPropertyDescriptor(GPUDevice.prototype,'lost');
      if(!descriptor?.configurable || !descriptor.get)return;
      Object.defineProperty(GPUDevice.prototype,'lost',{...descriptor,get(){
        const actual=descriptor.get.call(this);
        const injected=new Promise(resolve=>{window.__TEST_INJECT_GPU_LOSS=()=>resolve({reason:'unknown',message:'injected test loss'});});
        return Promise.race([actual,injected]);
      }});
    });
    const errors=[];
    page.on('pageerror',e=>{console.error(`WEBGPU_PAGE_ERROR ${mode}: ${e.stack||e.message}`);errors.push(e.message);});
    page.on('console',m=>{const where=m.location();const blocked=mode==='pipeline-blocked'&&m.text().includes('ERR_FAILED')&&/\/_astro\/cinematic-pipeline\.[^/]+\.js(?:\?.*)?$/.test(where.url);if(m.type()==='error'&&!blocked){const expected=mode==='no3d'&&m.text()==='THREE.WebGLRenderer: THREE.WebGLRenderer: Error creating WebGL context.';console[expected?'log':'error'](`WEBGPU_${expected?'EXPECTED_':'CONSOLE_'}ERROR ${mode}: ${m.text()} at ${JSON.stringify(where)}`);errors.push(m.text());}});
    await page.goto(`${base}/capitulos/origem-do-universo/`);await selectLessonStep(page,2);
    const stage=page.locator('[data-mx="origem-do-universo-fase-quente"] .mx-stage').first();
    await stage.scrollIntoViewIfNeeded();
    if(mode==='no3d'){
      await page.waitForFunction(()=>document.querySelector('[data-mx="origem-do-universo-fase-quente"] [data-visual-fallback="true"]'));
      assert.equal(await stage.locator('.cosmos-volume').count(),0);
      assert.ok(await page.locator('[data-mx="origem-do-universo-fase-quente"] [data-mx-svg]').isVisible());
      // This case deliberately denies every WebGL2 context request. Three.js logs
      // this precise constructor error before the application selects its SVG.
      // Any additional or different error remains a test failure.
      assert.deepEqual(errors,['THREE.WebGLRenderer: THREE.WebGLRenderer: Error creating WebGL context.']);
      rows.push({mode,backend:'svg',webglMax:await page.evaluate(()=>__GPU_PROBE.maxActive())});
      await page.close();continue;
    }
    await stage.locator('.cosmos-volume').waitFor({timeout:30000});
    const backend=await stage.getAttribute('data-renderer');
    const adapter=mode==='native'?await page.evaluate(async()=>{const a=await navigator.gpu?.requestAdapter();return a?{vendor:a.info?.vendor||'',architecture:a.info?.architecture||'',description:a.info?.description||''}:null;}):null;
    if(!['native','pipeline-blocked'].includes(mode))assert.equal(backend,'webgl2');
    const img=await stage.locator('.cosmos-volume').screenshot();
    const {channels}=await sharp(img).stats();assert.ok(channels.slice(0,3).some(c=>c.stdev>4),'scene has visible detail');
    assert.equal(await page.evaluate(()=>__GPU_PROBE.maxActive()),backend==='webgl2'?1:0,'at most one WebGL context');
    if(errors.length)console.error(`WEBGPU_FAILURE_STATE ${mode}: ${JSON.stringify(await page.evaluate(()=>({contexts:document.documentElement.dataset.cosmosContexts,stages:[...document.querySelectorAll('[data-renderer]')].map(s=>({backend:s.dataset.renderer,cinematic:s.dataset.cinematic})),lifecycle:window.__TEST_GPU_LIFECYCLE})))}`);
    assert.deepEqual(errors,[]);
    const row={mode,scene:'origem-do-universo-fase-quente',backend,adapter,nativeWebGPU:backend==='webgpu',webglMax:await page.evaluate(()=>__GPU_PROBE.maxActive())};
    if(mode==='pipeline-blocked'&&backend==='webgpu'){
      const module=page.locator('[data-mx="origem-do-universo-fase-quente"]');
      await module.locator('[data-mx-reset]').click();await module.locator('.cosmos-view-options summary').click();
      await module.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('high');
      await page.waitForFunction(()=>document.querySelector('[data-mx="origem-do-universo-fase-quente"] .mx-stage[data-cinematic="unavailable"]'));
      await page.waitForTimeout(600);
      blockedFrame=await sharp(await stage.locator('.cosmos-volume').screenshot()).raw().toBuffer();
      await page.waitForTimeout(200);
      assert.ok(blockedFrame.equals(await sharp(await stage.locator('.cosmos-volume').screenshot()).raw().toBuffer()),'fallback image stays fixed while paused');
      assert.ok((await sharp(await stage.locator('.cosmos-volume').screenshot()).stats()).channels.slice(0,3).some(c=>c.stdev>4));
      row.pipelineFailure='direct-webgpu-visible';
    }
    if(mode==='native'){
      if(backend==='webgpu'){
        const module=page.locator('[data-mx="origem-do-universo-fase-quente"]');
        await module.locator('[data-mx-reset]').click();
        await module.locator('.cosmos-view-options summary').click();
        await module.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('high');
        await page.waitForFunction(()=>document.querySelector('[data-mx="origem-do-universo-fase-quente"] .mx-stage[data-cinematic="active"]'),null,{timeout:30000});
        await page.waitForTimeout(500);
        assert.equal(await stage.getAttribute('data-cinematic'),'active');
        const after=await stage.locator('.cosmos-volume').screenshot();
        const frozen=await sharp(after).raw().toBuffer();await page.waitForTimeout(200);
        assert.ok(frozen.equals(await sharp(await stage.locator('.cosmos-volume').screenshot()).raw().toBuffer()),'cinematic image stays fixed while paused');
        if(screenshots)await stage.screenshot({path:join(screenshots,'fase-quente-webgpu-cinematica-390.png')});
        const postStats=await sharp(after).stats();assert.ok(postStats.channels.slice(0,3).some(c=>c.stdev>4),'cinematic pipeline has visible content');
        row.cinematic='bloom+smaa';
        if(blockedFrame){
          const activeFrame=await sharp(after).raw().toBuffer();assert.equal(activeFrame.length,blockedFrame.length);
          let delta=0;for(let i=0;i<activeFrame.length;i++)delta+=Math.abs(activeFrame[i]-blockedFrame[i]);
          row.cinematicMeanPixelDelta=delta/activeFrame.length;
          assert.ok(row.cinematicMeanPixelDelta>.01,'fixed-scene pixels change when cinematic pipeline is applied');
        }
        await module.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('standard');
        assert.equal(await stage.getAttribute('data-cinematic'),null);
        const injected=await page.evaluate(()=>{if(typeof window.__TEST_INJECT_GPU_LOSS!=='function')return false;window.__TEST_INJECT_GPU_LOSS();return true;});
        if(injected){
          await page.waitForFunction(()=>document.querySelector('[data-mx="origem-do-universo-fase-quente"] .mx-stage[data-renderer="webgl2"]'),null,{timeout:30000});
          assert.equal(await page.evaluate(()=>__GPU_PROBE.active()),1);
          row.injectedDeviceLoss='fallback-webgl2';
        } else row.injectedDeviceLoss='not-available';
        await page.goto(`${base}/capitulos/origem-do-universo/`);await selectLessonStep(page,2);
        const changed=page.locator('[data-mx="origem-do-universo-fase-quente"] .mx-stage').first();
        await changed.scrollIntoViewIfNeeded();await changed.locator('.cosmos-volume').waitFor({timeout:30000});
        assert.equal(await changed.getAttribute('data-renderer'),'webgpu');
        const mutated=await page.evaluate(()=>{
          const root=[...window.__COSMOS_QA.objects.values()][0];let material;
          root?.traverse(object=>{if(!material&&object.material)material=Array.isArray(object.material)?object.material[0]:object.material;});
          if(!material)return false;
          material.onBeforeCompile=()=>{};return true;
        });
        assert.ok(mutated,'test adds unsupported material after mount');
        await page.locator('[data-mx="origem-do-universo-fase-quente"] [data-mx-reset]').click();
        await page.waitForFunction(()=>document.querySelector('[data-mx="origem-do-universo-fase-quente"] .mx-stage[data-renderer="webgl2"]'),null,{timeout:30000});
        row.mutationFallback='webgl2';
      }
      await page.goto(`${base}/capitulos/vida-das-estrelas/`);await selectLessonStep(page,2);
      const legacy=page.locator('[data-mx="vida-das-estrelas-sol"] .mx-stage').first();
      await legacy.scrollIntoViewIfNeeded();await legacy.locator('.cosmos-volume').waitFor({timeout:30000});
      row.legacyScene='vida-das-estrelas-sol';row.legacyBackend=await legacy.getAttribute('data-renderer');
      assert.equal(row.legacyBackend,'webgl2','GLSL scene remains on legacy renderer');
      if(screenshots)await legacy.screenshot({path:join(screenshots,'sol-webgl2-390.png')});
      const legacyImg=await legacy.locator('.cosmos-volume').screenshot();
      const legacyStats=await sharp(legacyImg).stats();assert.ok(legacyStats.channels.slice(0,3).some(c=>c.stdev>4),'GLSL scene is visible');
      assert.deepEqual(errors,[]);
      if(screenshots){
        await page.setViewportSize({width:1440,height:900});
        await page.goto(`${base}/capitulos/origem-do-universo/`);await selectLessonStep(page,2);
        const desktop=page.locator('[data-mx="origem-do-universo-fase-quente"] .mx-stage').first();
        await desktop.scrollIntoViewIfNeeded();await desktop.locator('.cosmos-volume').waitFor({timeout:30000});
        row.desktopBackend=await desktop.getAttribute('data-renderer');
        await desktop.screenshot({path:join(screenshots,'fase-quente-desktop.png')});
      }
      await page.goto(`${base}/capitulos/sistema-solar/#sistema-solar-orbitas`);
      const orbit=page.locator('[data-mx="sistema-solar-orbitas"] .mx-stage').first();
      await orbit.scrollIntoViewIfNeeded();await orbit.locator('.cosmos-volume').waitFor({timeout:30000});
      row.lineLoopScene='sistema-solar-orbitas';row.lineLoopBackend=await orbit.getAttribute('data-renderer');
      assert.equal(row.lineLoopBackend,'webgl2','LineLoop scene remains on WebGL2');
      assert.deepEqual(errors,[]);
    }
    rows.push(row);
    await page.close();
  } finally { await browser.close(); }
}
console.log(JSON.stringify(rows));
