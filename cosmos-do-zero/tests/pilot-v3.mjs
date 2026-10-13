import { chromium } from 'playwright';
import { mkdirSync,writeFileSync } from 'node:fs';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const output=resolve('../../..','outputs/piloto-v3');mkdirSync(output,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const results=[];
try{
 for(const width of [1440,390]){
  const p=await browser.newPage({viewport:{width,height:1000},colorScheme:'dark'});const errors=[];p.on('pageerror',e=>errors.push(String(e)));
  await p.goto('http://127.0.0.1:4321/?lab=expansao#observatorio');
  const root=p.locator('[data-station="expansao"]');await root.locator('[data-guess-skip]').click();
  const stage=root.locator('[data-e-volume]');await stage.scrollIntoViewIfNeeded();await stage.locator('.cosmos-volume').waitFor();await p.waitForTimeout(350);
  await stage.evaluate(e=>window.scrollBy(0,e.getBoundingClientRect().top-(innerWidth<600?165:190)));
  await p.waitForTimeout(250);await p.screenshot({path:resolve(output,`expansao-${width}.png`)});
  await stage.screenshot({path:resolve(output,`campo-${width}.png`)});
  if(width===1440){const height=Math.ceil(await root.evaluate(e=>e.getBoundingClientRect().height))+192;await p.setViewportSize({width,height});await root.evaluate(e=>window.scrollBy(0,e.getBoundingClientRect().top-96));await p.waitForTimeout(200);await p.screenshot({path:resolve(output,'modulo-1440.png')});writeFileSync(resolve(output,'modulo-viewport.json'),JSON.stringify({width,height},null,2));await p.setViewportSize({width,height:1000});await stage.evaluate(e=>window.scrollBy(0,e.getBoundingClientRect().top-190));await p.waitForTimeout(200);}
  await p.locator('[data-theme-toggle]').click();await p.waitForTimeout(250);await p.screenshot({path:resolve(output,`expansao-claro-${width}.png`)});await p.locator('[data-theme-toggle]').click();await p.waitForTimeout(250);
  assert.equal(await stage.locator('.cosmos-volume').count(),1);
  assert.equal(await stage.locator('.cosmos-object-label:visible').count(),3);
  const still=await stage.screenshot();await p.waitForTimeout(200);assert.ok(still.equals(await stage.screenshot()),'A cena pausada precisa permanecer idêntica');
  await root.locator('[data-e-observer="1"]').click();assert.match(await root.locator('.obs-reading').innerText(),/Da galáxia B/);
  await root.locator('[data-e-observer="0"]').click();
  await root.locator('[data-e-range]').fill('1.45');await p.waitForTimeout(150);await stage.screenshot({path:resolve(output,`expansao-145-${width}.png`)});
  await root.locator('.cosmos-view-options summary').click(); await root.getByRole('button',{name:'Aproximar +',exact:true}).click(); await root.getByRole('button',{name:'Aproximar +',exact:true}).click(); await stage.screenshot({path:resolve(output,`close-up-${width}.png`)});
  for(let i=0;i<5;i++)await root.getByRole('button',{name:'Girar visão para a direita',exact:true}).click();await stage.screenshot({path:resolve(output,`visao-obliqua-${width}.png`)});
  results.push({width,viewport:await p.evaluate(()=>({width:innerWidth,height:innerHeight,contexts:document.documentElement.dataset.cosmosContexts,overflow:document.documentElement.scrollWidth-innerWidth})),stage:await stage.boundingBox(),errors,renderer:'Chrome ANGLE SwiftShader software'});await p.close();
 }
}finally{await browser.close();}
writeFileSync(resolve(output,'evidencia.json'),JSON.stringify(results,null,2));console.log(results);
