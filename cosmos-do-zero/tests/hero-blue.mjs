// Confere os pixels do céu WebGL, inclusive quando a GPU é emulada pelo CI.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium } from 'playwright';
import sharp from 'sharp';
const base=(process.env.BASE_URL||'http://127.0.0.1:4321').replace(/\/$/,'');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
let checks=0;
const output = process.env.COSMOS_SURFACE_CAPTURES;
if (output) await mkdir(output, { recursive: true });
try{
 for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce',colorScheme:'dark'});
  const pageErrors=[];
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('console',message=>{
    if(message.type()==='error' && message.text().includes('shader')) pageErrors.push(message.text());
  });
  await page.addInitScript(() => {
    window.heroPointDraws = 0;
    const original = WebGL2RenderingContext.prototype.drawArrays;
    WebGL2RenderingContext.prototype.drawArrays = function(mode, first, count) {
      if (mode === this.POINTS && this.canvas.classList.contains('hero-gl')) window.heroPointDraws++;
      return original.call(this, mode, first, count);
    };
  });
  // Preserva o buffer apenas para ler os pixels; a geometria e o shader são os de produção.
  await page.addInitScript(()=>{localStorage.setItem('cosmos-theme','dark');const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,options){return original.call(this,type,/webgl/.test(type)&&this.classList.contains('hero-gl')?{...options,preserveDrawingBuffer:true}:options);};});
  await page.goto(base+'/ceu/?gl',{waitUntil:'networkidle'});
  assert.equal(await page.locator('.hero-shell.has-gl>.hero-gl').count(),0,'nebulosa aguarda ativação');
  const activate = page.getByRole('button',{name:'Ativar nebulosa 3D'});
  await activate.focus();
  await activate.press('Enter');
  const sky=page.locator('.hero-shell.has-gl>.hero-gl');await sky.waitFor();
  const encoded=await sky.evaluate(c=>c.toDataURL('image/png'));
  const {data}=await sharp(Buffer.from(encoded.split(',')[1],'base64')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  let colored=0,blue=0,purple=0,light=0;
  for(let i=0;i<data.length;i+=4){
   const r=data[i]/255,g=data[i+1]/255,b=data[i+2]/255,max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;
   if(data[i+3]<20||d<.035||max>.7)continue;
   let h=max===r?(g-b)/d:max===g?(b-r)/d+2:(r-g)/d+4;h=(h*60+360)%360;
   colored++;if(h>=185&&h<240)blue++;if(h>=240&&h<=335)purple++;light+=(r+g+b)/3;
  }
  assert.ok(colored>1000,`${width}: céu contém uma nebulosa visível`);checks++;
  assert.ok((blue+purple)/colored>.9,`${width}: a nebulosa usa azul, ciano e violeta (${((blue+purple)/colored*100).toFixed(1)}%)`);checks++;
  assert.ok(blue/colored>.1&&purple/colored>.05,`${width}: há regiões frias e violetas distintas`);checks++;
  assert.ok(light/colored<.3,`${width}: fundo mantém a leitura sobre o céu profundo`);checks++;
  assert.equal(await sky.getAttribute('data-renderer'), 'playcanvas-webgl2');
  assert.equal(await page.locator('html').getAttribute('data-cosmos-contexts'), '1');
  const deactivate = page.getByRole('button',{name:'Desativar nebulosa 3D'});
  await deactivate.waitFor();
  assert.equal(await deactivate.evaluate(element => element === document.activeElement), true,
    'a alternância de modo preserva o foco');
  assert.equal(await sky.evaluate(c=>c.toDataURL('image/png')), encoded, 'movimento reduzido mantém o quadro');
  assert.ok(await page.evaluate(() => window.heroPointDraws > 0), 'o campo estelar foi rasterizado como pontos 3D');
  checks += 5;
  if (output) {
    await writeFile(join(output, `nebulosa-playcanvas-${width}.png`), Buffer.from(encoded.split(',')[1], 'base64'));
    if (width === 390) await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.screenshot({ path: join(output, `ceu-playcanvas-${width}.png`) });
  }
  if (width === 390) {
    await sky.evaluate(canvas => canvas.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await sky.waitFor({ state: 'detached' });
    await page.getByRole('button',{name:/Nebulosa 3D indisponível/}).waitFor();
    assert.equal(await page.locator('html').getAttribute('data-cosmos-contexts'), '0');
    assert.equal(await page.locator('[data-cmb-canvas]').isVisible(), true);
    checks += 2;
  } else {
    await deactivate.press('Enter');
    await sky.waitFor({ state: 'detached' });
    assert.equal(await page.locator('html').getAttribute('data-cosmos-contexts'), '0');
    assert.equal(await activate.evaluate(element => element === document.activeElement), true);
    checks += 2;
  }
  assert.deepEqual(pageErrors,[],'ativação não causa erro de página');
  await page.close();
 }
 const fallback=await browser.newPage({viewport:{width:390,height:900},colorScheme:'dark'});
 await fallback.addInitScript(()=>{localStorage.setItem('cosmos-theme','dark');const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,options){return this.classList.contains('hero-gl')&&/^webgl/.test(type)?null:original.call(this,type,options);};});
 await fallback.goto(base+'/ceu/?gl',{waitUntil:'networkidle'});
 await fallback.getByRole('button',{name:'Ativar nebulosa 3D'}).click();
 await fallback.getByRole('button',{name:/Nebulosa 3D indisponível/}).waitFor();
 assert.equal(await fallback.locator('.hero-shell.has-gl>.hero-gl').count(),0,'céu em CSS continua disponível quando o contexto 3D falha');checks++;
 await fallback.close();
 const touch = await browser.newPage({ viewport:{width:390,height:900}, isMobile:true, hasTouch:true });
 await touch.addInitScript(() => {
   window.__skyGpuRequests = 0;
   const original = HTMLCanvasElement.prototype.getContext;
   HTMLCanvasElement.prototype.getContext = function(type, options) {
     if (type.startsWith('webgl')) { window.__skyGpuRequests++; return null; }
     return original.call(this, type, options);
   };
 });
 await touch.goto(base+'/ceu/');
 const frame = touch.locator('[data-cmb-frame]');
 const read = touch.locator('[data-cmb-read]');
 await frame.locator('canvas').waitFor();
 await frame.focus();
 assert.match(await read.textContent(), /mapa simulado, este ponto está 56 milionésimos de kelvin acima/);
 await frame.press('ArrowRight');
 assert.match(await read.textContent(), /49 milionésimos de kelvin abaixo/);
 await frame.tap({ position: { x: 180, y: 90 } });
 assert.doesNotMatch(await read.textContent(), /49 milionésimos de kelvin abaixo/);
 assert.equal(await touch.evaluate(() => window.__skyGpuRequests), 0);
 checks += 4;
 if (output) await touch.locator('[data-cmb]').screenshot({ path: join(output, 'ceu-cmb-canvas.png') });
 await touch.close();

 const poster = await browser.newPage();
 await poster.addInitScript(() => {
   const original = HTMLCanvasElement.prototype.getContext;
   HTMLCanvasElement.prototype.getContext = function(type, options) {
     if (type === '2d' && this.hasAttribute('data-cmb-canvas')) return null;
     return original.call(this, type, options);
   };
 });
 await poster.goto(base+'/ceu/');
 await poster.locator('[data-cmb-frame]').focus();
 assert.match(await poster.locator('[data-cmb-read]').textContent(), /mapa simulado, este ponto está 56 milionésimos de kelvin acima/);
 assert.equal(await poster.locator('[data-cmb-poster]').isVisible(), true);
 assert.equal(await poster.locator('[data-cmb-canvas]').isVisible(), false);
 checks += 3;
 await poster.close();

 const noScript = await browser.newPage({ javaScriptEnabled: false });
 await noScript.goto(base+'/ceu/');
 const fallbackPoster = noScript.locator('[data-cmb-poster]');
 assert.equal(await fallbackPoster.isVisible(), true);
 assert.ok(await fallbackPoster.evaluate(image => image.naturalWidth === 480), 'a prévia HTML já contém o mapa');
 checks += 2;
 await noScript.close();

 console.log(`Nebulosa PlayCanvas e mapa 2D: ${checks} verificações aprovadas`);
}finally{await browser.close();}
