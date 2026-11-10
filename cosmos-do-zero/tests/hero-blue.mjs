// Confere os pixels do céu WebGL, inclusive quando a GPU é emulada pelo CI.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import sharp from 'sharp';
const base=(process.env.BASE_URL||'http://127.0.0.1:4321').replace(/\/$/,'');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM||undefined,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
let checks=0;
try{
 for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce',colorScheme:'dark'});
  const pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.message));
  // Preserva o buffer apenas para ler os pixels; a geometria e o shader são os de produção.
  await page.addInitScript(()=>{localStorage.setItem('cosmos-theme','dark');const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,options){return original.call(this,type,/webgl/.test(type)&&this.classList.contains('hero-gl')?{...options,preserveDrawingBuffer:true}:options);};});
  await page.goto(base+'/ceu/?gl',{waitUntil:'networkidle'});
  assert.equal(await page.locator('.hero-shell.has-gl>.hero-gl').count(),0,'nebulosa aguarda ativação');
  await page.getByRole('button',{name:'Ativar nebulosa 3D'}).click();
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
 console.log(`Céu espacial em WebGL: ${checks} verificações aprovadas`);
}finally{await browser.close();}
