// Real rendering with controlled RAF timestamps to exercise profile decisions;
// these injected intervals are not a device-performance measurement.
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {chromium} from 'playwright';

const server=await createServer({configFile:false,root:process.cwd(),logLevel:'error',server:{host:'127.0.0.1',port:0,strictPort:false}});
await server.listen();const address=server.httpServer.address(),base=`http://127.0.0.1:${address.port}`;
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true,args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist',...(process.platform==='win32'?['--use-angle=d3d11']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])]});
const rows=[];
try{
 for(const scenario of ['slow','standard','fast','rollback','manual','reduced','hidden','no-frames','warm-delay','real']){
  const page=await browser.newPage({viewport:{width:800,height:600},reducedMotion:scenario==='reduced'?'reduce':'no-preference'}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  if(scenario!=='real')await page.addInitScript(mode=>{
   const original=window.requestAnimationFrame;let time=0,lastReal=-1;
   window.requestAnimationFrame=callback=>original.call(window,real=>{
    const phase=document.querySelector('.mx-stage')?.dataset.calibrationPhase;
    if(real!==lastReal){time+=mode==='slow'||mode==='rollback'&&phase==='high'?40:mode==='standard'?25:16;lastReal=real;}
    callback(time);
   });
  },scenario);
  let delayedDone=Promise.resolve();
  if(scenario==='warm-delay')await page.route('**/cinematic-pipeline.ts*',route=>{
   delayedDone=new Promise(resolve=>setTimeout(resolve,6500)).then(()=>route.continue());return delayedDone;
  });
  const gpu=['fast','rollback','warm-delay','real'].includes(scenario);
  await page.goto(`${base}/tests/fixtures/world-frame.html?backend=${gpu?'native':'webgl2'}`);
  const stage=page.locator('.mx-stage');await stage.locator('.cosmos-volume').waitFor({timeout:30000});
  const backend=await stage.getAttribute('data-renderer');
  if(gpu&&backend!=='webgpu'){
   if(process.env.REQUIRE_WEBGPU==='1')throw new Error(`${scenario}: WebGPU indisponível`);
   assert.deepEqual(errors,[]);rows.push({scenario,backend,result:'not-tested: WebGPU unavailable'});await page.close();continue;
  }
  if(scenario==='manual'){
   await page.locator('.cosmos-view-options summary').click();await page.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('low');
   assert.equal(await stage.getAttribute('data-calibration-status'),'manual');
  } else if(scenario==='reduced')assert.equal(await stage.getAttribute('data-calibration-status'),'paused');
  else if(scenario==='hidden'){
   await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
   assert.equal(await stage.getAttribute('data-calibration-status'),'paused');
  } else if(scenario==='no-frames'){
   await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.play(true));
   await page.waitForFunction(()=>document.querySelector('.mx-stage')?.dataset.calibrationStatus==='insufficient',null,{timeout:7000});
  }
  else{
   if(scenario==='warm-delay'){
    await page.waitForFunction(()=>document.querySelector('.mx-stage')?.dataset.calibrationStatus==='warming-high',null,{timeout:12000});
    await page.evaluate(()=>{window.__WORLD_FRAME_FIXTURE.play(true);window.__WORLD_FRAME_FIXTURE.play(false);});
   }
   await page.waitForFunction(()=>document.querySelector('.mx-stage')?.dataset.calibrationStatus==='ready',null,{timeout:16000});
   const selected=await stage.getAttribute('data-adaptive-quality');
   if(scenario==='real')assert.ok(['low','standard','high'].includes(selected),'real device selects a valid profile');
   else assert.equal(selected,scenario==='slow'?'low':scenario==='fast'?'high':'standard',`${scenario}: selected profile`);
   if(scenario==='warm-delay')await delayedDone;
  }
  await page.waitForTimeout(200);const before=await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.updates());
  await page.waitForTimeout(500);const after=await page.evaluate(()=>window.__WORLD_FRAME_FIXTURE.updates());
  assert.equal(after,before,`${scenario}: no perpetual render loop after calibration`);
  assert.deepEqual(errors,[]);
  rows.push({scenario,backend,profile:await stage.getAttribute('data-adaptive-quality'),status:await stage.getAttribute('data-calibration-status'),frames:await stage.getAttribute('data-calibration-frames'),updatesAfterStop:after-before});
  await page.close();
 }
 console.log(JSON.stringify({method:'controlled RAF timing for decision coverage; real uses unmodified RAF. Real scene rendering throughout; not a hardware FPS result',rows}));
}finally{await browser.close();await server.close();}
