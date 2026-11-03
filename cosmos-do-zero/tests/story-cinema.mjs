import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base=(process.env.BASE_URL||'http://127.0.0.1:4321').replace(/\/$/,'');
const ids=['galaxias-e-nebulosas','origem-do-universo','misterios-do-cosmos','vida-das-estrelas','sistema-solar','terra-e-atmosfera'];
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,ignoreDefaultArgs:['--disable-back-forward-cache']});
let checks=0;const ok=(x,message)=>{assert.ok(x,message);checks++;};
try{
 for(const width of [390,1280]){
  const page=await browser.newPage({viewport:{width,height:width<500?667:900},reducedMotion:'no-preference'});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  for(const id of ids){
   await page.goto(`${base}/capitulos/${id}/`,{waitUntil:'networkidle'});
   const root=page.locator(`[data-story="${id}"]`),stage=root.locator('[data-story-viewport]');
   ok(await root.count()===1,`${id}/${width}: abertura narrativa presente`);
   await stage.scrollIntoViewIfNeeded();
   await page.waitForFunction(id=>document.querySelector(`[data-story="${id}"] [data-story-play]`)?.getAttribute('aria-pressed')==='true',id);
   ok(await root.locator('[data-story-phase]').count()===3,`${id}/${width}: três momentos nomeados`);
   await root.locator('[data-story-phase]').last().click();
   ok(await root.locator('[data-story-play]').getAttribute('aria-pressed')==='false',`${id}/${width}: etapa escolhida fica pausada`);
   const svg=await root.locator('[data-story-stage]').innerHTML();await page.waitForTimeout(100);
   ok(await root.locator('[data-story-stage]').innerHTML()===svg,`${id}/${width}: escolha manual não é sobrescrita`);
   await root.locator('[data-story-mode="film"]').click();
   const video=root.locator('[data-story-film]');await video.waitFor({state:'visible'});
   await page.waitForFunction(id=>Number.isFinite(document.querySelector(`[data-story="${id}"] video`)?.duration),id);
   ok(await video.evaluate(v=>v.duration===20&&v.videoWidth===1280),`${id}/${width}: filme real 720p e 20s`);
   await root.locator('[data-story-play]').click();
   await page.waitForFunction(id=>{const v=document.querySelector(`[data-story="${id}"] video`);return v&&!v.paused&&v.currentTime>0;},id);
   await root.locator('[data-story-play]').click();
   ok(await video.evaluate(v=>v.paused),`${id}/${width}: vídeo pode ser pausado`);
   await root.locator('[data-story-mode="scene"]').click();
   ok(await root.locator('[data-story-play]').getAttribute('aria-pressed')==='false',`${id}/${width}: voltar do filme preserva a pausa manual`);
   ok(await root.locator('[data-story-stage]').innerHTML()===svg,`${id}/${width}: voltar do filme preserva a etapa escolhida`);
   await root.locator('[data-experience-expand]').click();
   ok(await root.getAttribute('data-expanded')==='true',`${id}/${width}: cinema aberto`);
   const fit=await root.evaluate(r=>{const stage=r.querySelector('[data-story-viewport]').getBoundingClientRect(),controls=r.querySelector('.story-transport').getBoundingClientRect();return stage.top>=0&&stage.bottom<=innerHeight&&controls.top>=0&&controls.bottom<=innerHeight;});
   ok(fit,`${id}/${width}: palco e comandos cabem na janela`);
   await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('[data-expanded]'));
   ok(await root.locator('[data-experience-expand]').evaluate(b=>b===document.activeElement),`${id}/${width}: Escape devolve foco`);
   ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${id}/${width}: sem overflow`);
  }
  ok(errors.length===0,`${width}: sem erros ${errors.join(' | ')}`);await page.close();
 }
 const landscape=await browser.newPage({viewport:{width:667,height:375}});
 for(const id of ids){
  await landscape.goto(`${base}/capitulos/${id}/`,{waitUntil:'networkidle'});
  const root=landscape.locator('[data-story]');await root.locator('[data-experience-expand]').click();
  await root.locator('[data-story-play]').scrollIntoViewIfNeeded();
  ok(await root.locator('[data-story-play]').evaluate(b=>{const r=b.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}),`${id}: comandos alcançáveis no celular deitado`);
  ok(await landscape.locator('.experience-close').evaluate(b=>{const r=b.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}),`${id}: Fechar sempre visível no celular deitado`);
  await landscape.keyboard.press('Escape');
 }
 await landscape.close();
 const history=await browser.newPage({viewport:{width:1280,height:900}});
 await history.addInitScript(()=>window.addEventListener('pageshow',e=>{document.documentElement.dataset.historyCache=String(e.persisted);}));
 await history.goto(`${base}/capitulos/origem-do-universo/`,{waitUntil:'networkidle'});
 await history.goto(`${base}/glossario/`,{waitUntil:'networkidle'});await history.goBack({waitUntil:'load'});
 const restored=history.locator('[data-story]');await restored.locator('[data-story-play]').scrollIntoViewIfNeeded();
 await history.waitForFunction(()=>document.querySelector('[data-story-play]')?.getAttribute('aria-pressed')==='true');
 await history.locator('footer').scrollIntoViewIfNeeded();
 await history.waitForFunction(()=>document.querySelector('[data-story-play]')?.getAttribute('aria-pressed')==='false');
 ok(true,'retorno pelo histórico preserva reprodução e pausa fora da tela');
 console.log('Histórico: cache restaurado = '+await history.locator('html').getAttribute('data-history-cache'));
 await history.close();
 const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});
 await page.goto(`${base}/capitulos/origem-do-universo/`,{waitUntil:'networkidle'});
 const story=page.locator('[data-story]');await story.locator('[data-story-viewport]').scrollIntoViewIfNeeded();
 ok(await story.locator('[data-story-play]').getAttribute('aria-pressed')==='false','movimento reduzido: cena estática');
 ok(await story.locator('[data-story-caption]').innerText().then(t=>t.includes('800 nm')),'movimento reduzido: conclusão legível');
 await story.locator('[data-story-phase]').first().click();
 ok(await story.locator('[data-story-caption]').innerText().then(t=>t.includes('400')),'movimento reduzido: etapas manuais disponíveis');
 await page.goto(base+'/',{waitUntil:'networkidle'});
 ok(await page.locator('[data-story-preview] svg').count()===6,'seis capas vetoriais');
 ok(await page.locator('#movimento').evaluate(e=>e.getBoundingClientRect().top+scrollY<2200),'demonstração próxima da entrada');
 await page.close();
 console.log(`Cinema: ${checks} verificações aprovadas`);
}finally{await browser.close();}
