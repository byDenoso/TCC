import {chromium} from 'playwright';
import {selectLessonStep} from './lib/reader-navigation.mjs';
const base=(process.env.BASE_URL||'https://cosmos.denerpereira.com.br').replace(/\/$/,'');
const browser=await chromium.launch();let failures=0;
try{
 for(const delay of [0,0,50,100,150,250,500,0]){
  const page=await browser.newPage({viewport:{width:390,height:800},reducedMotion:'no-preference'});
  await page.addInitScript(()=>{
   const id='origem-do-universo-primeiras-estruturas';window.__transport=[];
   const record=(kind,extra={})=>{const root=document.querySelector(`[data-mx="${id}"]`);if(!root)return;const stage=root.querySelector('[data-mx-visuals]'),box=stage.getBoundingClientRect(),button=root.querySelector('[data-mx-play]');window.__transport.push({kind,at:Math.round(performance.now()),scroll:scrollY,box:{top:box.top,bottom:box.bottom,height:box.height},playing:button.getAttribute('aria-pressed'),guide:root.dataset.guide,hidden:!!root.closest('[hidden]'),others:[...document.querySelectorAll('[data-mx-play][aria-pressed="true"]')].map(b=>b.closest('[data-mx]').dataset.mx),stages:[...stage.children].map(s=>({hidden:s.hidden,height:s.getBoundingClientRect().height,classes:s.className})),...extra});};
   const set=Element.prototype.setAttribute;Element.prototype.setAttribute=function(name,value){if(name==='aria-pressed'&&this.matches('[data-mx-play]')&&this.getAttribute(name)!==String(value))record('play-write',{scene:this.closest('[data-mx]').dataset.mx,from:this.getAttribute(name),to:String(value),stack:new Error().stack});return set.call(this,name,value);};
   const IO=window.IntersectionObserver;window.IntersectionObserver=class extends IO{constructor(cb,options){super((entries,observer)=>{for(const e of entries)if(e.target.matches('[data-mx-visuals]')&&e.target.closest('[data-mx]')?.dataset.mx===id)record('io-before',{intersecting:e.isIntersecting,ratio:e.intersectionRatio,entryTime:Math.round(e.time),delay:Math.round(performance.now()-e.time)});cb(entries,observer);},options);}};
   document.addEventListener('click',event=>{const button=event.target.closest('[data-mx-play],[data-mx-reset]');if(button?.closest('[data-mx]')?.dataset.mx!==id)return;record('click-before',{control:button.hasAttribute('data-mx-play')?'play':'reset'});queueMicrotask(()=>record('click-after'));requestAnimationFrame(()=>record('next-frame'));},true);
   document.addEventListener('scrollend',()=>record('scroll-end'),true);document.addEventListener('animationend',event=>{if(event.target.id===id)record('entry-animation-end');},true);
   new MutationObserver(records=>{for(const change of records){if(change.type==='attributes'&&change.target.matches('.mx-volume-stage')&&change.target.closest('[data-mx]')?.dataset.mx===id)record('volume-visibility');if(change.type==='childList'&&[...change.addedNodes].some(n=>n.nodeType===1&&n.matches?.('.mx-volume-stage'))&&change.target.closest('[data-mx]')?.dataset.mx===id)record('volume-added');}}).observe(document,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','style']});
  });
  if(delay)await page.route('**/models/stellar/cloud-density-128.bin',async route=>{await new Promise(r=>setTimeout(r,delay));await route.continue();});
  await page.goto(base+'/capitulos/origem-do-universo/',{waitUntil:'networkidle'});
  for(const dot of [0,1,2,4]){
   await selectLessonStep(page,dot);const root=page.locator('.lesson-section').nth(dot).locator('[data-mx]');
   const id=await root.getAttribute('data-mx');await root.locator('[data-mx-visuals]').scrollIntoViewIfNeeded();await page.waitForFunction(id=>document.querySelector(`[data-mx="${id}"]`)?.classList.contains('is-ready'),id);
   const play=root.locator('[data-mx-play]');await root.locator('[data-mx-reset]').click();await root.locator('[data-mx-range]').focus();await page.keyboard.press('End');await root.locator('[data-mx-reset]').click();await play.click();await page.waitForTimeout(100);
   const active=await play.getAttribute('aria-pressed')==='true';await play.click();const svg=await root.locator('[data-mx-svg]').innerHTML();await page.waitForTimeout(80);const paused=await play.getAttribute('aria-pressed')==='false'&&svg===await root.locator('[data-mx-svg]').innerHTML();
   if(dot===4){console.log('TRANSPORT_PROBE',JSON.stringify({delay,active,paused,timeline:await page.evaluate(()=>window.__transport)}));if(!active||!paused)failures++;}
   await root.locator('[data-mx-reset]').click();const choices=root.locator('[data-mx-check]'),right=Number(await root.locator('[data-mx-check-box]').getAttribute('data-right'));await choices.nth((right+1)%await choices.count()).click();await choices.nth(right).click();
  }
  await page.close();
 }
 console.log('TRANSPORT_FAILURES',failures);if(failures)process.exitCode=1;
}finally{await browser.close();}
