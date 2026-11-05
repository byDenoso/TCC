// Actual runtime, camera and rasterization; positions and geometry are synthetic.
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {chromium} from 'playwright';
import sharp from 'sharp';
import {join} from 'node:path';
import {mkdir} from 'node:fs/promises';
import {installGpuLifecycleObserver} from './lib/gpu-lifecycle-observer.mjs';

const server=await createServer({configFile:false,root:process.cwd(),logLevel:'error',server:{host:'127.0.0.1',port:0,strictPort:false}});
await server.listen();
const address=server.httpServer.address(),base=`http://127.0.0.1:${address.port}`;
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true,args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist',...(process.platform==='win32'&&process.env.WORLD_FRAME_SOFTWARE!=='1'?['--use-angle=d3d11']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])]});
const rows=[];
try{
  for(const mode of ['webgl2','native']){
    const page=await browser.newPage({viewport:{width:800,height:600}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    await page.goto(`${base}/tests/fixtures/world-frame.html?backend=${mode}`);
    const stage=page.locator('.mx-stage'),canvas=stage.locator('canvas.cosmos-volume');
    await canvas.waitFor({timeout:30000});await page.waitForTimeout(500);
    const backend=await stage.getAttribute('data-renderer');
    if(mode!=='native')assert.equal(backend,'webgl2');
    if(mode==='native'&&process.env.REQUIRE_WEBGPU==='1')assert.equal(backend,'webgpu','hardware WebGPU requested');
    await page.locator('.cosmos-view-options summary').click();
    await page.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('standard');await page.waitForTimeout(150);
    const frame=async()=>sharp(await canvas.screenshot()).ensureAlpha().raw().toBuffer({resolveWithObject:true});
    const first=await frame(),pixel=(im,x,y)=>[...im.data.slice((y*im.info.width+x)*4,(y*im.info.width+x)*4+4)];
    const center=pixel(first,160,120),edge=pixel(first,15,15);
    console.log(JSON.stringify({mode,backend,center,edge}));
    assert.ok(center[0]>center[2]*1.5,'near red plane occludes the distant plane drawn after it');
    assert.ok(edge[2]>=80&&edge[2]>edge[0]*2&&edge[2]>edge[1]*2,'distant blue plane must be visibly brighter than the background');
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.nearVisible(false));const exposed=await frame();
    const exposedCenter=pixel(exposed,160,120);assert.ok(exposedCenter[2]>=80&&exposedCenter[2]>exposedCenter[0]*2,'removing the near plane exposes the blue distant plane');
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.nearVisible(true));const restored=await frame();
    const restoredCenter=pixel(restored,160,120);assert.ok(restoredCenter[0]>restoredCenter[2]*1.5,'restoring near plane reestablishes occlusion');
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.farVisible(false));const withoutFar=await frame();
    const clearEdge=pixel(withoutFar,15,15);assert.ok(edge[2]-clearEdge[2]>=80,'far plane differs visibly from the clear color');
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.farVisible(true));
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.foregroundColor(0x22ff22));const green=await frame();
    const greenCenter=pixel(green,160,120);assert.ok(greenCenter[1]>greenCenter[0]*1.5,'updates to the original material remain visible');
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.foregroundColor(0xff2222));
    if(backend==='webgl2'){
      assert.equal(await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.addStandard()),true,'new materials are normalized');
      assert.equal(await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.removeStandard()),true,'removed materials have original callbacks restored');
    }
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.rebase(1));await page.waitForTimeout(200);
    const rebased=await frame();let delta=0;for(let i=0;i<first.data.length;i++)delta+=Math.abs(first.data[i]-rebased.data[i]);
    const meanDelta=delta/first.data.length;assert.ok(meanDelta<.5,`rebase must preserve rasterized pixels: ${meanDelta}`);
    await page.getByRole('button',{name:'Girar visão para a direita'}).click();
    const rotation=await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.cameraDelta());
    assert.ok(Math.hypot(...rotation)>.1,'camera orbit updates world position');
    assert.ok(Math.abs((await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.cameraDistance()))-3)<1e-8,'orbit preserves the physical initial distance rather than the placeholder home');
    await page.getByRole('button',{name:'Aproximar +'}).click();
    const zoom=await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.cameraDelta());
    assert.ok(Math.hypot(...zoom)>.1&&zoom.some((v,i)=>Math.abs(v-rotation[i])>.01),'zoom updates world position');
    assert.ok((await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.cameraDistance()))<3,'zoom approaches the target');
    const target=await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.targetDelta());
    assert.ok(target.every(v=>Math.abs(v)<1e-8),'camera target remains fixed in world coordinates');
    await page.getByRole('button',{name:'Restaurar visão'}).click();await page.waitForTimeout(200);
    assert.ok((await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.cameraDelta())).every(v=>Math.abs(v)<1e-8),'reset restores world camera');
    let cinematicRebase=null,settledAfterDrag=null,transitionDelta=null;
    if(backend==='webgpu'){
      await page.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('standard');await page.waitForTimeout(150);
      const previous=await sharp(await stage.screenshot()).ensureAlpha().raw().toBuffer();
      await page.evaluate(()=>{
        const original=window.requestAnimationFrame.bind(window);let held;
        window.requestAnimationFrame=callback=>{
          const stage=document.querySelector('.mx-stage');
          if(!held&&stage?.dataset.cinematic==='warming'){
            held=callback;window.__RELEASE_CINEMATIC=()=>{window.requestAnimationFrame=original;original(held);};return -1;
          }
          return original(callback);
        };
      });
      await page.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('high');
      await page.waitForFunction(()=>typeof window.__RELEASE_CINEMATIC==='function',null,{timeout:30000});
      await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.rebase(1));
      const warming=await sharp(await stage.screenshot()).ensureAlpha().raw().toBuffer();let warmDelta=0;
      for(let i=0;i<previous.length;i++)warmDelta+=Math.abs(previous[i]-warming[i]);warmDelta/=previous.length;
      assert.ok(warmDelta<.5,`direct image stays visible during cinematic warmup: ${warmDelta}`);
      await page.evaluate(()=>window.__RELEASE_CINEMATIC());
      await page.waitForFunction(()=>document.querySelector('.mx-stage')?.dataset.cinematic==='active',null,{timeout:30000});
      const firstPaint=await sharp(await stage.screenshot()).ensureAlpha().raw().toBuffer();let transition=0;
      for(let i=0;i<previous.length;i++)transition+=Math.abs(previous[i]-firstPaint[i]);transitionDelta=transition/previous.length;
      if(process.env.WORLD_FRAME_DEBUG_DIR){await mkdir(process.env.WORLD_FRAME_DEBUG_DIR,{recursive:true});await sharp(previous,{raw:{width:320,height:240,channels:4}}).png().toFile(join(process.env.WORLD_FRAME_DEBUG_DIR,'transition-before.png'));await sharp(firstPaint,{raw:{width:320,height:240,channels:4}}).png().toFile(join(process.env.WORLD_FRAME_DEBUG_DIR,'transition-first-paint.png'));}
      const firstStats=await sharp(firstPaint,{raw:{width:320,height:240,channels:4}}).stats();
      assert.ok(firstStats.channels.slice(0,3).some(c=>c.stdev>4),'first presented cinematic frame contains scene detail');
      await page.waitForTimeout(300);
      const before=await frame();await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.rebase(0));await page.waitForTimeout(300);
      const after=await frame();let error=0;for(let i=0;i<before.data.length;i++)error+=Math.abs(before.data[i]-after.data[i]);
      cinematicRebase=error/before.data.length;
      assert.ok(cinematicRebase<.5,`cinematic camera history survives rebase: ${cinematicRebase}`);
      await page.getByRole('button',{name:'Girar a cena'}).click();
      const rect=await canvas.boundingBox();assert.ok(rect);
      await page.mouse.move(rect.x+160,rect.y+120);await page.mouse.down();
      await page.mouse.move(rect.x+200,rect.y+130,{steps:6});await page.mouse.up();await page.waitForTimeout(400);
      const settled=await frame();await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.rebase(0));await page.waitForTimeout(250);
      const redraw=await frame();let changed=0;for(let i=0;i<settled.data.length;i++)changed+=Math.abs(settled.data[i]-redraw.data[i]);
      settledAfterDrag=changed/settled.data.length;
      // On the reference GPU, removing the end listener gives ~0.05/255;
      // the stationary redraw with the listener gives 0/255.
      assert.ok(settledAfterDrag<.02,`released camera must not retain blur: ${settledAfterDrag}`);
    }
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.fail());
    await page.waitForFunction(()=>document.querySelector('.mx-stage')?.dataset.visualFallback==='true');
    assert.equal(await canvas.count(),0,'invalid world frame releases 3D canvas');
    assert.ok(await stage.locator('svg').isVisible(),'2D alternative remains');
    assert.deepEqual(errors,[]);
    rows.push({mode,backend,meanDelta,center,edge,exposedCenter,restoredCenter,clearEdge,greenCenter,rotation,zoom,transitionDelta,cinematicRebase,settledAfterDrag,invalidFrame:'2d'});
    await page.close();
  }
  for(const scenario of ['dynamic-custom','initial-custom','shadows','ortho','ortho-extreme','ortho-native']){
    const page=await browser.newPage({viewport:{width:800,height:600},reducedMotion:'reduce'}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    if(scenario==='ortho-native')await page.addInitScript(installGpuLifecycleObserver);
    const query=scenario==='initial-custom'?'&custom=1':scenario==='shadows'?'&shadows=1':scenario==='ortho-extreme'?'&ortho-extreme=1':scenario==='ortho'||scenario==='ortho-native'?'&ortho=1':'';
    await page.goto(`${base}/tests/fixtures/world-frame.html?backend=${scenario==='ortho-native'?'native':'webgl2'}${query}`);
    if(scenario==='dynamic-custom'){await page.locator('canvas.cosmos-volume').waitFor({timeout:30000});await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.addUnsupported());}
    await page.waitForFunction(()=>document.querySelector('.mx-stage')?.dataset.visualFallback==='true',null,{timeout:30000});
    assert.equal(await page.locator('canvas.cosmos-volume').count(),0,`${scenario}: unsupported frame releases the canvas`);
    assert.equal(await page.locator('.mx-stage').getAttribute('data-renderer'),null,`${scenario}: fallback does not report an active renderer`);
    assert.ok(await page.locator('.mx-stage svg').isVisible(),`${scenario}: 2D alternative stays available`);
    const gpuEvents=scenario==='ortho-native'?await page.evaluate(()=>window.__TEST_GPU_LIFECYCLE.map(event=>event.event)):[];
    if(scenario==='ortho-native'&&process.env.REQUIRE_WEBGPU==='1')assert.ok(gpuEvents.includes('device-ready')&&gpuEvents.includes('destroy-device'),'unsupported native WebGPU frame releases its device');
    assert.deepEqual(errors,[]);rows.push({scenario,result:'2d',...(scenario==='ortho-native'?{gpuEvents}:{})});await page.close();
  }
  for(const mode of ['webgl2','native']){
    const page=await browser.newPage({viewport:{width:800,height:600},reducedMotion:'reduce'}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    await page.goto(`${base}/tests/fixtures/world-frame.html?backend=${mode}&normalized-ortho=1`);
    const stage=page.locator('.mx-stage'),canvas=stage.locator('canvas.cosmos-volume');await canvas.waitFor({timeout:30000});
    const backend=await stage.getAttribute('data-renderer');
    if(mode==='webgl2')assert.equal(backend,'webgl2');
    if(mode==='native'&&process.env.REQUIRE_WEBGPU==='1')assert.equal(backend,'webgpu');
    const read=async()=>{const {data,info}=await sharp(await canvas.screenshot()).ensureAlpha().raw().toBuffer({resolveWithObject:true});return [...data.slice((120*info.width+160)*4,(120*info.width+160)*4+4)];};
    const front=await read();assert.ok(front[0]>front[2]*1.5,'normalized orthographic scene shows near plane');
    await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.nearVisible(false));const behind=await read();assert.ok(behind[2]>behind[0]*2&&behind[2]>=80,'normalized orthographic scene exposes far plane');
    assert.deepEqual(errors,[]);rows.push({scenario:'normalized-ortho',mode,backend,front,behind});await page.close();
  }
  console.log(JSON.stringify({method:'real runtime and raster; synthetic 10^27 m anchor, 1 m local offsets, depth and camera controls; no physical mobile',rows}));
}finally{await browser.close();await server.close();}
