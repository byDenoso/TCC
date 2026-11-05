import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import sharp from 'sharp';
import {installGpuProbe} from './gpu-probe.mjs';

export async function installSceneQa(page){
  await page.addInitScript({content:`(${installGpuProbe.toString()})();window.__COSMOS_QA.objects=new Map();window.__GRAPHICS_MATRIX_QA=new Map();(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,options){return get.call(this,type,/^webgl/.test(type)&&this.classList.contains('cosmos-volume')?{...options,preserveDrawingBuffer:true}:options);};const ids=new WeakMap();let next=0;const original=WebGL2RenderingContext.prototype.uniformMatrix4fv;WebGL2RenderingContext.prototype.uniformMatrix4fv=function(location,transpose,values,...rest){if(this.canvas.closest('[data-t-3d],[data-solar-stage]')&&location){let id=ids.get(location);if(!id){id=++next;ids.set(location,id);}window.__GRAPHICS_MATRIX_QA.set(id,Array.from(values).slice(0,16));}return original.call(this,location,transpose,values,...rest);};})();`});
}

// QA retains the WebGL drawing buffer so the full 3D frame can be read without browser composition.
const sceneCapture={source:'canvas.toDataURL(image/png)',context:'WebGL2 preserveDrawingBuffer=true only in QA',composition:'not measured'};
export const captureState = async canvas => canvas.evaluate(element=>{
  const rect=node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,top:r.top,bottom:r.bottom,left:r.left,right:r.right};};
  const nodes=[];for(let node=element;node instanceof Element;node=node.parentElement){const css=getComputedStyle(node);nodes.push({tag:node.tagName,id:node.id,class:node.getAttribute('class'),rect:rect(node),client:[node.clientWidth,node.clientHeight],offset:[node.offsetWidth,node.offsetHeight],scroll:[node.scrollLeft,node.scrollTop],transform:css.transform,opacity:css.opacity,position:css.position,overflow:[css.overflowX,css.overflowY]});}
  const ancestors=new Set();for(let node=element;node instanceof Element;node=node.parentElement)ancestors.add(node);
  const animations=document.getAnimations().filter(animation=>{const target=animation.effect?.target;if(!(target instanceof Element))return false;if(ancestors.has(target))return true;const r=target.getBoundingClientRect(),c=element.getBoundingClientRect();return r.right>c.left&&r.left<c.right&&r.bottom>c.top&&r.top<c.bottom;}).map(animation=>({playState:animation.playState,currentTime:animation.currentTime,target:animation.effect?.target?.tagName,class:animation.effect?.target?.getAttribute('class')}));
  const stage=element.closest('[data-t-3d],.mx-stage,[data-solar-stage]')??element.parentElement;
  const owner=stage?.closest('[data-solar-studio]')??document.querySelector('[data-station="tempo"]');
  const overlays=[...document.querySelectorAll('[data-3d-play],[data-solar-play],.obs3d-label,.obs3d-tag,.cosmos-object-label,header')].filter(node=>{const r=node.getBoundingClientRect(),c=element.getBoundingClientRect();return r.right>c.left&&r.left<c.right&&r.bottom>c.top&&r.top<c.bottom;}).map(node=>{const css=getComputedStyle(node);return {tag:node.tagName,class:node.getAttribute('class'),rect:rect(node),hidden:node.hidden,transform:css.transform,opacity:css.opacity,display:css.display,visibility:css.visibility,zIndex:css.zIndex,backgroundColor:css.backgroundColor,color:css.color,borderColor:css.borderColor,transitionProperty:css.transitionProperty,transitionDuration:css.transitionDuration,ariaPressed:node.getAttribute('aria-pressed')};});
  const inputs=[...(owner?.querySelectorAll('input,select')??[])].map(input=>({tag:input.tagName,type:input.type,name:input.name,value:input.value,min:input.min,max:input.max,dataset:{...input.dataset}}));
  const registry=window.__COSMOS_QA,scenes=[];for(const get of registry?.scenes?.values()??[]){try{const scene=get();scenes.push({name:scene.name,frames:scene.frames,quality:scene.quality,visibleTextureDimensions:scene.visibleTextureDimensions,render:scene.render});}catch(error){scenes.push({error:String(error)});}}
  const objects=[...(registry?.objects?.values()??[])].map(group=>group.children.map(object=>({name:object.name,visible:object.visible,position:object.position.toArray(),rotation:object.rotation.toArray(),scale:object.scale.toArray()})));
  const gl=element.getContext('webgl2');
  return {time:performance.now(),viewport:{width:innerWidth,height:innerHeight,devicePixelRatio,scrollX,scrollY,hidden:document.hidden},canvas:{rect:rect(element),client:[element.clientWidth,element.clientHeight],offset:[element.offsetWidth,element.offsetHeight],buffer:[element.width,element.height],drawingBuffer:gl?[gl.drawingBufferWidth,gl.drawingBufferHeight]:null,preserved:gl?.getContextAttributes()?.preserveDrawingBuffer??null,glViewport:gl?Array.from(gl.getParameter(gl.VIEWPORT)):null},stage:stage?{rect:rect(stage),dataset:{...stage.dataset}}:null,ariaPlay:owner?.querySelector('[data-3d-play],[data-solar-play]')?.getAttribute('aria-pressed')??null,inputs,ancestors:nodes,overlays,animations,scenes,objects,matrices:window.__GRAPHICS_MATRIX_QA?[...window.__GRAPHICS_MATRIX_QA.values()]:[]};
});
export const captureFramebuffer=async canvas=>{
  const frame=await canvas.evaluate(element=>{const gl=element.getContext('webgl2'),attributes=gl?.getContextAttributes();return {png:element.toDataURL('image/png'),preserved:attributes?.preserveDrawingBuffer??false,drawingBuffer:gl?[gl.drawingBufferWidth,gl.drawingBufferHeight]:null,canvas:[element.width,element.height]};});
  assert.equal(frame.preserved,true,'QA WebGL drawing buffer is preserved');
  assert.ok(frame.drawingBuffer&&frame.drawingBuffer[0]>0&&frame.drawingBuffer[1]>0,'drawing buffer has positive dimensions');
  assert.deepEqual(frame.canvas,frame.drawingBuffer,'canvas and drawing buffer dimensions agree');
  assert.ok(frame.png.startsWith('data:image/png;base64,'),'canvas produced a PNG');
  const png=Buffer.from(frame.png.slice('data:image/png;base64,'.length),'base64'),meta=await sharp(png).metadata();
  assert.deepEqual([meta.width,meta.height],frame.drawingBuffer,'PNG contains the entire drawing buffer');
  return png;
};
export const saveMismatch=async(label,a,b,first,second,states,expectation)=>{
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
export const assertPausedScene = async (canvas, label, intervalMs=450, initialDelayMs=0) => {
  console.log('GRAPHICS_CASE',label); 
  if(initialDelayMs)await canvas.page().waitForTimeout(initialDelayMs);
  const aBefore=await captureState(canvas);
  const a = await captureFramebuffer(canvas);
  const aAfter=await captureState(canvas);
  await canvas.page().waitForTimeout(intervalMs);
  const bBefore=await captureState(canvas);
  const b = await captureFramebuffer(canvas);
  const bAfter=await captureState(canvas);
  const first=await sharp(a).raw().toBuffer({resolveWithObject:true}),second=await sharp(b).raw().toBuffer({resolveWithObject:true});
  const equal=first.info.width===second.info.width&&first.info.height===second.info.height&&first.info.channels===second.info.channels&&first.data.equals(second.data);
  const { channels } = await sharp(a).stats();
  const hasContent=channels.slice(0, 3).some(c => c.stdev > 4);
  if(!equal||!hasContent)await saveMismatch(label,a,b,first,second,{aBefore,aAfter,bBefore,bAfter},'equal, with visible content');
  assert.ok(equal,`${label}: pausa congela todos os pixels da cena 3D`);
  assert.ok(hasContent, `${label}: cena tem conteúdo gráfico`);
};
// Separate a paused frame from the independent automatic quality calibration.
export const useStandardQuality = async(stage,owner,label,textureKind=null) => {
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
