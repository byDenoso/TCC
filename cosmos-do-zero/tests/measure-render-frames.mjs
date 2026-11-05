// Measures browser animation callbacks and application render calls, not physical display FPS.
import {chromium} from 'playwright';
import {selectLessonStep} from './lib/reader-navigation.mjs';
import {installGpuProbe} from './lib/gpu-probe.mjs';

const base=(process.env.BASE_URL??'http://127.0.0.1:4321').replace(/\/$/,'');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,headless:true,args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist','--use-angle=d3d11']});
const rows=[];
try{
  const page=await browser.newPage({viewport:{width:390,height:900},colorScheme:'dark',reducedMotion:'no-preference'});
  await page.addInitScript(installGpuProbe);
  for(const [route,step,id] of [['origem-do-universo',2,'origem-do-universo-fase-quente'],['vida-das-estrelas',2,'vida-das-estrelas-sol']]){
    await page.goto(`${base}/capitulos/${route}/`);await selectLessonStep(page,step);
    const root=page.locator(`[data-mx="${id}"]`),stage=root.locator('.mx-stage').first();
    await stage.scrollIntoViewIfNeeded();await stage.locator('.cosmos-volume').waitFor();
    await root.locator('.cosmos-view-options summary').click();
    await root.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('standard');
    await root.locator('.cosmos-view-options summary').click();
    await root.locator('[data-mx-auto]').click();await stage.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    const backend=await stage.getAttribute('data-renderer');
    const sample=await page.evaluate(async id=>{
      const button=document.querySelector(`[data-mx="${id}"] [data-mx-play]`);
      const get=()=>[...window.__COSMOS_QA.scenes.values()].map(f=>f()).find(s=>s.name===id);
      const startFrames=get()?.frames??0,startPlay=button?.getAttribute('aria-pressed');
      return await new Promise(resolve=>{
        const times=[],start=performance.now();
        const frame=now=>{
          times.push(now);
          if(now-start<5000){requestAnimationFrame(frame);return;}
          const duration=(now-start)/1000,intervals=times.slice(1).map((t,i)=>t-times[i]).sort((a,b)=>a-b);
          resolve({durationSeconds:duration,rafCallbacks:times.length,rafPerSecond:times.length/duration,rafP95Ms:intervals[Math.ceil(intervals.length*.95)-1]??null,rendererCalls:(get()?.frames??startFrames)-startFrames,playingStart:startPlay,playingEnd:button?.getAttribute('aria-pressed'),visibility:document.visibilityState});
        };requestAnimationFrame(frame);
      });
    },id);
    rows.push({scene:id,backend,viewport:'390x900 emulado',sample});
  }
  const adapter=await page.evaluate(async()=>{const a=await navigator.gpu?.requestAdapter();return a?{vendor:a.info?.vendor||'',architecture:a.info?.architecture||'',description:a.info?.description||''}:null;});
  console.log(JSON.stringify({adapter,method:'requestAnimationFrame e chamadas do renderer; não mede quadros físicos apresentados',rows}));
} finally{await browser.close();}
