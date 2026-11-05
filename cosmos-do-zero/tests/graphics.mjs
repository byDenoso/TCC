// Exercita os shaders de produção em WebGL (ANGLE/SwiftShader), incluindo emulação de viewport390; não é celular físico.
import assert from 'node:assert/strict';
import {openExtraExperiments, selectLessonStep} from './lib/reader-navigation.mjs';
import { mkdirSync,writeFileSync } from 'node:fs';
import { join } from 'node:path';
import {installGpuProbe} from './lib/gpu-probe.mjs';
import { chromium } from 'playwright';
import sharp from 'sharp';

const base = (process.env.BASE_URL ?? 'http://127.0.0.1:4321').replace(/\/$/, '');
const tempoOnly = process.env.COSMOS_GRAPHICS_TEMPO_ONLY === '1';
const cpuRate = Number(process.env.COSMOS_GRAPHICS_CPU_RATE ?? '1');
assert.ok(Number.isFinite(cpuRate) && cpuRate >= 1, 'CPU throttling rate must be at least 1');
const widths = process.env.COSMOS_GRAPHICS_WIDTH ? [Number(process.env.COSMOS_GRAPHICS_WIDTH)] : [390, 1440];
assert.ok(widths.every(width => [390, 1440].includes(width)), 'graphics test width must be 390 or 1440');
const browser = await chromium.launch({ executablePath:process.env.CHROMIUM||undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
let checked = 0;
// QA retains the WebGL drawing buffer so the full 3D frame can be read without browser composition.
const sceneCapture={source:'canvas.toDataURL(image/png)',context:'WebGL2 preserveDrawingBuffer=true only in QA',composition:'not measured'};
const captureState = async canvas => canvas.evaluate(element=>{
  const rect=node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,top:r.top,bottom:r.bottom,left:r.left,right:r.right};};
  const nodes=[];for(let node=element;node instanceof Element;node=node.parentElement){const css=getComputedStyle(node);nodes.push({tag:node.tagName,id:node.id,class:node.getAttribute('class'),rect:rect(node),client:[node.clientWidth,node.clientHeight],offset:[node.offsetWidth,node.offsetHeight],scroll:[node.scrollLeft,node.scrollTop],transform:css.transform,opacity:css.opacity,position:css.position,overflow:[css.overflowX,css.overflowY]});}
  const ancestors=new Set();for(let node=element;node instanceof Element;node=node.parentElement)ancestors.add(node);
  const animations=document.getAnimations().filter(animation=>{const target=animation.effect?.target;if(!(target instanceof Element))return false;if(ancestors.has(target))return true;const r=target.getBoundingClientRect(),c=element.getBoundingClientRect();return r.right>c.left&&r.left<c.right&&r.bottom>c.top&&r.top<c.bottom;}).map(animation=>({playState:animation.playState,currentTime:animation.currentTime,target:animation.effect?.target?.tagName,class:animation.effect?.target?.getAttribute('class')}));
  const stage=element.closest('[data-t-3d],.mx-stage,[data-solar-stage]')??element.parentElement;
  const tempo=document.querySelector('[data-station="tempo"]');
  const overlays=[...document.querySelectorAll('[data-3d-play],.obs3d-label,.obs3d-tag,.cosmos-object-label,header')].filter(node=>{const r=node.getBoundingClientRect(),c=element.getBoundingClientRect();return r.right>c.left&&r.left<c.right&&r.bottom>c.top&&r.top<c.bottom;}).map(node=>{const css=getComputedStyle(node);return {tag:node.tagName,class:node.getAttribute('class'),rect:rect(node),hidden:node.hidden,transform:css.transform,opacity:css.opacity,display:css.display,visibility:css.visibility,zIndex:css.zIndex,backgroundColor:css.backgroundColor,color:css.color,borderColor:css.borderColor,transitionProperty:css.transitionProperty,transitionDuration:css.transitionDuration,ariaPressed:node.getAttribute('aria-pressed')};});
  const inputs=[...(tempo?.querySelectorAll('input,select')??[])].map(input=>({tag:input.tagName,type:input.type,name:input.name,value:input.value,min:input.min,max:input.max,dataset:{...input.dataset}}));
  const registry=window.__COSMOS_QA,scenes=[];for(const get of registry?.scenes?.values()??[]){try{const scene=get();scenes.push({name:scene.name,frames:scene.frames,quality:scene.quality,visibleTextureDimensions:scene.visibleTextureDimensions,render:scene.render});}catch(error){scenes.push({error:String(error)});}}
  const objects=[...(registry?.objects?.values()??[])].map(group=>group.children.map(object=>({name:object.name,visible:object.visible,position:object.position.toArray(),rotation:object.rotation.toArray(),scale:object.scale.toArray()})));
  const gl=element.getContext('webgl2');
  return {time:performance.now(),viewport:{width:innerWidth,height:innerHeight,devicePixelRatio,scrollX,scrollY,hidden:document.hidden},canvas:{rect:rect(element),client:[element.clientWidth,element.clientHeight],offset:[element.offsetWidth,element.offsetHeight],buffer:[element.width,element.height],drawingBuffer:gl?[gl.drawingBufferWidth,gl.drawingBufferHeight]:null,preserved:gl?.getContextAttributes()?.preserveDrawingBuffer??null,glViewport:gl?Array.from(gl.getParameter(gl.VIEWPORT)):null},stage:stage?{rect:rect(stage),dataset:{...stage.dataset}}:null,ariaPlay:tempo?.querySelector('[data-3d-play]')?.getAttribute('aria-pressed')??null,inputs,ancestors:nodes,overlays,animations,scenes,objects,matrices:window.__GRAPHICS_MATRIX_QA?[...window.__GRAPHICS_MATRIX_QA.values()]:[]};
});
const captureFramebuffer=async canvas=>{
  const frame=await canvas.evaluate(element=>{const gl=element.getContext('webgl2'),attributes=gl?.getContextAttributes();return {png:element.toDataURL('image/png'),preserved:attributes?.preserveDrawingBuffer??false,drawingBuffer:gl?[gl.drawingBufferWidth,gl.drawingBufferHeight]:null,canvas:[element.width,element.height]};});
  assert.equal(frame.preserved,true,'QA WebGL drawing buffer is preserved');
  assert.ok(frame.drawingBuffer&&frame.drawingBuffer[0]>0&&frame.drawingBuffer[1]>0,'drawing buffer has positive dimensions');
  assert.deepEqual(frame.canvas,frame.drawingBuffer,'canvas and drawing buffer dimensions agree');
  assert.ok(frame.png.startsWith('data:image/png;base64,'),'canvas produced a PNG');
  const png=Buffer.from(frame.png.slice('data:image/png;base64,'.length),'base64'),meta=await sharp(png).metadata();
  assert.deepEqual([meta.width,meta.height],frame.drawingBuffer,'PNG contains the entire drawing buffer');
  return png;
};
const saveMismatch=async(label,a,b,first,second,states,expectation)=>{
  const directory=join(process.cwd(),'test-results','graphics');mkdirSync(directory,{recursive:true});
  const name=label.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
  const width=Math.max(first.info.width,second.info.width),height=Math.max(first.info.height,second.info.height),diff=Buffer.alloc(width*height*3);
  let changed=0,maxDifference=0,minX=width,minY=height,maxX=-1,maxY=-1;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    let max=0;for(let c=0;c<Math.max(first.info.channels,second.info.channels);c++){
      const read=(image)=>x<image.info.width&&y<image.info.height&&c<image.info.channels?image.data[(y*image.info.width+x)*image.info.channels+c]:0;
      max=Math.max(max,Math.abs(read(first)-read(second)));
    }
    if(max){changed++;maxDifference=Math.max(maxDifference,max);minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);}
    diff.fill(Math.min(255,max*8),(y*width+x)*3,(y*width+x)*3+3);
  }
  writeFileSync(join(directory,`${name}-a.png`),a);writeFileSync(join(directory,`${name}-b.png`),b);
  await sharp(diff,{raw:{width,height,channels:3}}).png().toFile(join(directory,`${name}-diff.png`));
  writeFileSync(join(directory,`${name}-state.json`),JSON.stringify({label,expectation,capturePolicy:sceneCapture,first:first.info,second:second.info,changedPixels:changed,maxDifference,diffGain:8,boundingBox:changed?{minX,minY,maxX,maxY}:null,states},null,2));
  console.error(`GRAPHICS_MISMATCH ${label}: ${changed} pixels; evidence in ${directory}`);
};
const still = async (canvas, label) => {
  console.log('GRAPHICS_CASE',label); 
  await canvas.page().waitForTimeout(100);
  const aBefore=await captureState(canvas);
  const a = await captureFramebuffer(canvas);
  const aAfter=await captureState(canvas);
  await canvas.page().waitForTimeout(450);
  const bBefore=await captureState(canvas);
  const b = await captureFramebuffer(canvas);
  const bAfter=await captureState(canvas);
  const first=await sharp(a).raw().toBuffer({resolveWithObject:true}),second=await sharp(b).raw().toBuffer({resolveWithObject:true});
  const equal=first.info.width===second.info.width&&first.info.height===second.info.height&&first.info.channels===second.info.channels&&first.data.equals(second.data);
  if(!equal)await saveMismatch(label,a,b,first,second,{aBefore,aAfter,bBefore,bAfter},'equal');
  assert.ok(equal,`${label}: pausa congela todos os pixels da cena 3D`);
  const { channels } = await sharp(a).stats();
  assert.ok(channels.slice(0, 3).some(c => c.stdev > 4), `${label}: cena tem conteúdo gráfico`);
  checked += 2;
};
// Separate a paused frame from the independent automatic quality calibration.
const useStandardQuality = async(stage,owner,label,textureKind=null) => {
  const options=owner.locator('.cosmos-view-options').first();
  await options.locator('summary').click();
  await options.getByRole('combobox',{name:'Qualidade da cena'}).selectOption('standard');
  await stage.scrollIntoViewIfNeeded();
  const element=await stage.elementHandle();assert.ok(element,`${label}: palco disponível`);
  try {
    await stage.page().waitForFunction(({element,textureKind})=>{
      const data=element.dataset;
      const expected=textureKind==='galaxy'?(element.clientWidth<600?'768':'1536'):textureKind==='world'?(element.clientWidth<600?'1024':'2048'):null;
      const settled=expected===null?(data.qualityPending===undefined||data.qualityPending==='false'):data.qualityPending==='false';
      return element.isConnected&&data.cosmosQuality==='standard'&&data.calibrationStatus==='manual'&&data.qualityError!=='true'&&settled&&(expected===null||data.textureQuality===expected);
    },{element,textureKind},{timeout:30000});
    const state=await stage.evaluate(element=>({quality:element.dataset.cosmosQuality,calibration:element.dataset.calibrationStatus,pending:element.dataset.qualityPending??null,texture:element.dataset.textureQuality??null,width:element.clientWidth}));
    console.log(`GRAPHICS_QUALITY ${label} ${JSON.stringify(state)}`);
  } finally { await element.dispose(); }
};
try {
  for (const width of widths) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'no-preference', colorScheme: 'dark' });
    if(cpuRate>1){const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setCPUThrottlingRate',{rate:cpuRate});}
    await page.addInitScript({content:`(${installGpuProbe.toString()})();window.__COSMOS_QA.objects=new Map();window.__GRAPHICS_MATRIX_QA=new Map();(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,options){return get.call(this,type,/^webgl/.test(type)&&this.classList.contains('cosmos-volume')?{...options,preserveDrawingBuffer:true}:options);};const ids=new WeakMap();let next=0;const original=WebGL2RenderingContext.prototype.uniformMatrix4fv;WebGL2RenderingContext.prototype.uniformMatrix4fv=function(location,transpose,values,...rest){if(this.canvas.closest('[data-t-3d]')&&location){let id=ids.get(location);if(!id){id=++next;ids.set(location,id);}window.__GRAPHICS_MATRIX_QA.set(id,Array.from(values).slice(0,16));}return original.call(this,location,transpose,values,...rest);};})();`});
    await page.addInitScript(() => localStorage.setItem('cosmos-theme', 'dark'));
    const errors = [];
    const warnings = [];
    const failedResources = [];
    page.on('pageerror', e => { if (!/Transition was aborted/.test(String(e))) errors.push(String(e)); });
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('console', m => { if (m.type() === 'warning') warnings.push(m.text()); });
    page.on('requestfailed', request => failedResources.push({ url: request.url(), error: request.failure()?.errorText }));
    await page.goto(`${base}/?lab=tempo&z=0.5#observatorio`, { waitUntil: 'networkidle' });
    const tempo = page.locator('[data-t-3d]');
    const canvas = tempo.locator('canvas');
    await page.locator('[data-station="tempo"] .obs-viz').scrollIntoViewIfNeeded();
    await canvas.waitFor({ state: 'visible' });
    await tempo.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    await useStandardQuality(tempo,page.locator('[data-station="tempo"]'),`tempo ${width}`,'galaxy');
    const playButton=tempo.locator('[data-3d-play]'),playLabel=playButton.locator('[data-3d-play-label]');
    if(await playButton.getAttribute('aria-pressed')==='true')await playButton.click();
    assert.equal(await playButton.getAttribute('aria-pressed'),'false','Tempo realmente pausado antes de verificar pixels');
    assert.ok(await playButton.isVisible());assert.ok(await playLabel.isVisible());const pausedLabel=await playLabel.textContent();assert.ok(pausedLabel?.trim());
    await still(canvas, `tempo ${width}`);
    assert.equal(await playButton.getAttribute('aria-pressed'),'false');assert.equal(await playLabel.textContent(),pausedLabel);assert.ok(await playButton.isVisible());assert.ok(await playLabel.isVisible());
    await playButton.click();assert.equal(await playButton.getAttribute('aria-pressed'),'true');
    const playingLabel=await playLabel.textContent();assert.ok(playingLabel?.trim());
    const aBefore=await captureState(canvas),a=await captureFramebuffer(canvas),aAfter=await captureState(canvas);
    await page.waitForTimeout(300);
    const bBefore=await captureState(canvas),b=await captureFramebuffer(canvas),bAfter=await captureState(canvas);
    const first=await sharp(a).raw().toBuffer({resolveWithObject:true}),second=await sharp(b).raw().toBuffer({resolveWithObject:true});
    const sameDimensions=first.info.width===second.info.width&&first.info.height===second.info.height&&first.info.channels===second.info.channels;
    if(!sameDimensions||first.data.equals(second.data))await saveMismatch(`retomada-tempo-${width}`,a,b,first,second,{aBefore,aAfter,bBefore,bAfter},'same dimensions, different pixels');
    assert.ok(sameDimensions,'retomada mantém as dimensões da captura');assert.ok(!first.data.equals(second.data),'continuar retoma a cena 3D');assert.equal(await playButton.getAttribute('aria-pressed'),'true');assert.equal(await playLabel.textContent(),playingLabel);assert.ok(await playButton.isVisible());assert.ok(await playLabel.isVisible());checked++;
    await playButton.click();assert.equal(await playButton.getAttribute('aria-pressed'),'false');
    mkdirSync('docs/screenshots', { recursive: true });
    await tempo.screenshot({ path: `docs/screenshots/render-tempo-${width}.png` });
    await canvas.evaluate(c => c.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await page.waitForFunction(() => document.querySelector('[data-t-3d]').hidden);
    assert.equal(await page.locator('[data-t-svg]').getAttribute('viewBox'), '0 0 640 420'); checked++;
    if(tempoOnly){assert.deepEqual(errors,[],`Tempo sem erros de shader ${width}`);await page.context().close();continue;}

    await page.goto(`${base}/capitulos/galaxias-e-nebulosas/`, { waitUntil: 'networkidle' });
    const root = page.locator('[data-mx="galaxias-e-nebulosas-teia-cosmica"]');
    // Seleciona o passo que contém a teia a partir da estrutura da própria aula.
    const dot = await root.evaluate(r => [...document.querySelectorAll('.lesson-section')].indexOf(r.closest('.lesson-section')));
    await selectLessonStep(page,dot);
    await root.locator('.mx-stage').first().scrollIntoViewIfNeeded();
    const web = root.locator('.mx-gl');
    try { await web.waitFor({ state: 'visible' }); }
    catch (error) {
      const state = await root.evaluate(root => ({
        root: { ...root.dataset },
        viewport: { height: innerHeight, width: innerWidth, scrollY },
        parentHidden: !!root.closest('[hidden]'),
        stages: [...root.querySelectorAll('.mx-stage')].map(stage => {
          const rect = stage.getBoundingClientRect();
          return { class: stage.className, data: { ...stage.dataset }, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height, canvas: !!stage.querySelector('canvas') };
        }),
        visualNotice: root.querySelector('[data-mx-visual-state]')?.textContent,
        activeContexts: document.documentElement.dataset.cosmosContexts,
        currentStep: document.querySelector('[data-step-select]')?.value,
      }));
      console.error('GRAPHICS_DIAGNOSTIC', JSON.stringify({ id: 'teia', width, state, errors, warnings, failedResources }));
      throw error;
    }
    await root.locator('[data-mx-range]').focus(); await page.keyboard.press('End');
    for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowLeft');
    await root.locator('[data-mx-play]').click();
    await page.waitForTimeout(350);
    await root.locator('[data-mx-play]').click();
    await useStandardQuality(root.locator('.mx-stage').first(),root,`teia ${width}`,'galaxy');
    await still(web, `teia ${width}`);
    await root.locator('[data-mx-range]').focus(); await page.keyboard.press('End');
    const { data, info } = await sharp(await web.screenshot()).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    let clipped = 0, colored = 0;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      if (Math.min(r, g, b) > 245) clipped++;
      if (Math.max(r, g, b) > 25 && Math.max(r, g, b) - Math.min(r, g, b) > 15) colored++;
    }
    assert.ok(clipped / (info.width * info.height) < 0.01, 'aglomerados preservam textura sem áreas brancas estouradas'); checked++;
    assert.ok(colored > 100, 'cores dos filamentos e aglomerados permanecem visíveis'); checked++;
    await root.locator('.mx-stage').screenshot({ path: `docs/screenshots/render-teia-${width}.png` });
    await web.evaluate(c => c.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await page.waitForFunction(() => !document.querySelector('[data-mx="galaxias-e-nebulosas-teia-cosmica"] .mx-stage').classList.contains('mx-stage--gl'));
    assert.ok(await root.locator('.mx-flat circle').first().isVisible()); checked++;
    assert.deepEqual(errors, [], `sem erros de shader ${width}`); checked++;
    assert.equal(await page.evaluate(()=>__GPU_PROBE.maxActive()),1,'máximo1WebGL real incluindo todos os caminhos');checked++;
    for (const [route, step, id] of [['vida-das-estrelas',2,'vida-das-estrelas-sol'],['terra-e-atmosfera',0,'terra-e-atmosfera-formacao-da-terra'],['sistema-solar',2,'sistema-solar-gigantes'],['origem-do-universo',2,'origem-do-universo-fase-quente']]) {
      await page.goto(`${base}/capitulos/${route}/`); await selectLessonStep(page, step);
      const module = page.locator(`[data-mx="${id}"]`), stage = module.locator('.mx-stage').first();
      await stage.scrollIntoViewIfNeeded();
      try { await stage.locator('.cosmos-volume').waitFor(); }
      catch (error) {
        const state = await module.evaluate(root => ({ booted:root.dataset.mxBooted, fallback:root.dataset.visualFallback, stages:[...root.querySelectorAll('.mx-stage')].map(el => ({ class:el.className, hidden:el.hidden, fallback:el.dataset.visualFallback, top:Math.round(el.getBoundingClientRect().top), bottom:Math.round(el.getBoundingClientRect().bottom), canvas:!!el.querySelector('.cosmos-volume') })) }));
        console.error('GRAPHICS_DIAGNOSTIC', JSON.stringify({ id, width, state, errors }));
        throw error;
      }
      await module.locator('[data-mx-reset]').click();
      await stage.scrollIntoViewIfNeeded();
      await useStandardQuality(stage,module,`${id} ${width}`);
      await still(stage.locator('.cosmos-volume'), `${id} ${width}`);
      assert.equal(await page.evaluate(() => __GPU_PROBE.active()), 1); checked++;
    }
    await page.goto(`${base}/capitulos/sistema-solar/#sistema-solar-sol-e-planetas`);await openExtraExperiments(page);const solar=page.locator('[data-solar-stage]');await solar.scrollIntoViewIfNeeded();await solar.locator('.cosmos-volume').waitFor();await page.locator('[data-solar-reset]').click();await solar.scrollIntoViewIfNeeded();await useStandardQuality(solar,page.locator('[data-solar-studio]'),`Solar ${width}`,'world');await still(solar.locator('.cosmos-volume'),`Solar ${width}`);assert.equal(await page.evaluate(()=>__GPU_PROBE.maxActive()),1);checked++;
    assert.deepEqual(errors,[],`novas famílias sem erros de shader${width}`);checked++;
    await page.context().close();
  }
  console.log(tempoOnly?`${checked} verificações WebGL de Tempo: pausa, retomada e perda de contexto; ${widths.join(' e ')} px.`:`${checked} verificações WebGL: shaders, pausa completa, retomada, cor, saturação e perda de contexto; ${widths.join(' e ')} px.`);
} finally { await browser.close(); }
