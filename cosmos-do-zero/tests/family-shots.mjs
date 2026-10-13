import { chromium } from 'playwright';
import { mkdirSync,writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const out=resolve('../../..','outputs/familias');mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const specimens=[
 ['solar','sistema-solar',1,'[data-solar-studio]',null],
 ['sol','vida-das-estrelas',2,'[data-mx="vida-das-estrelas-sol"]',2],
 ['nebulosa','galaxias-e-nebulosas',3,'[data-mx="galaxias-e-nebulosas-nebulosas"]',null],
 ['lente','misterios-do-cosmos',3,'[data-lens]',null],
 ['buraco-negro','vida-das-estrelas',4,'[data-mx="vida-das-estrelas-massivas"]',3],
 ['terra','terra-e-atmosfera',0,'[data-mx="terra-e-atmosfera-formacao-da-terra"]',2]
];
const results=[];
try{for(const width of [390,1440])for(const [name,chapter,step,selector,opt] of specimens){
 const p=await browser.newPage({viewport:{width,height:1000},colorScheme:'dark'});const errors=[];p.on('pageerror',e=>errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await p.goto(`http://127.0.0.1:4321/capitulos/${chapter}/`);await p.locator(`[data-step-dot="${step}"]`).click();
 const root=p.locator(selector);await root.waitFor({state:'visible'});if(opt!==null)await root.locator(`[data-mx-opt="${opt}"]`).click();
 if(name==='lente')await root.locator('..').locator('[data-lens-ready]').waitFor(); if(name==='lente' && width===390){await root.locator('[data-lens-geometry]').evaluate(e=>e.open=true);} const stage=root.locator('.mx-stage').first();await stage.scrollIntoViewIfNeeded();
 await stage.locator('.cosmos-volume').waitFor({state:'visible',timeout:15000});
 await p.evaluate(selector=>{const stage=document.querySelector(selector).querySelector('.mx-stage');window.scrollBy(0,stage.getBoundingClientRect().top-160);},selector);
 await p.waitForTimeout(450);await p.screenshot({path:resolve(out,`${name}-${width}.png`)});
 results.push({name,width,viewport:await p.evaluate(()=>({width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth-innerWidth,contexts:document.documentElement.dataset.cosmosContexts})),errors});await p.close();
}}finally{await browser.close();}
writeFileSync(resolve(out,'familias.json'),JSON.stringify(results,null,2));console.log(results);


