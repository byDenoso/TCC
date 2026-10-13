/** Observe every real WebGL context, independent of Cosmos' own counters. */
export function installGpuProbe(){
 const real=HTMLCanvasElement.prototype.getContext,seen=new WeakMap(),entries=new Map();let sequence=0,maxActive=0;
 const snapshot=()=>[...entries.values()].map(e=>({id:e.id,active:e.active,textures:e.textures.size,buffers:e.buffers.size,textureBytes:[...e.textures.values()].reduce((s,t)=>s+[...t.levels.values()].reduce((a,b)=>a+b,0),0),bufferBytes:[...e.buffers.values()].reduce((s,v)=>s+v,0),draws:e.draws,lost:e.lost}));
 HTMLCanvasElement.prototype.getContext=function(type,...args){const gl=real.call(this,type,...args);if(!gl||!/^webgl|experimental-webgl/.test(type)||seen.has(gl))return gl;
  const e={id:++sequence,active:true,textures:new Map(),buffers:new Map(),boundTextures:new Map(),boundBuffers:new Map(),draws:0,lost:null};entries.set(e.id,e);seen.set(gl,e.id);
  maxActive=Math.max(maxActive,[...entries.values()].filter(v=>v.active).length);
  const lose=()=>{if(!e.active)return;e.lost=snapshot().find(s=>s.id===e.id);e.active=false;e.textures.clear();e.buffers.clear();e.boundTextures.clear();e.boundBuffers.clear();};this.addEventListener('webglcontextlost',lose);
  const wrap=(name,fn)=>{const native=gl[name].bind(gl);gl[name]=(...a)=>fn(native,a);};
  wrap('createTexture',(f,a)=>{const t=f(...a);e.textures.set(t,{levels:new Map(),width:0,height:0,depth:1,bpp:4,faces:1,immutable:false});return t;});wrap('deleteTexture',(f,a)=>{e.textures.delete(a[0]);return f(...a);});
  wrap('bindTexture',(f,a)=>{e.boundTextures.set(a[0],a[1]);return f(...a);});
  const bytes=(format,type)=>{const channels=format===6403||format===6406||format===6409||format===36244?1:format===33319||format===6410?2:format===6407?3:4;return channels*(type===5126||type===5125?4:type===5131||type===5123?2:1);};
  const internalBytes=format=>({33321:1,33325:2,33326:4,33323:2,33327:4,33328:8,32849:3,35905:3,32856:4,35907:4,34842:8,34836:16,35056:4,33190:3,36012:4}[format]??4);
  const texture=target=>e.textures.get(e.boundTextures.get(target>=34069&&target<=34074?34067:target));
  wrap('texImage2D',(f,a)=>{const t=texture(a[0]);if(t){const explicit=a.length>=9,w=explicit?a[3]:a[5]?.width,h=explicit?a[4]:a[5]?.height,bpp=bytes(explicit?a[6]:a[3],explicit?a[7]:a[4]);if(w&&h){t.levels.set(`${a[0]}:${a[1]}`,w*h*bpp);if(a[1]===0)Object.assign(t,{width:w,height:h,bpp,faces:a[0]>=34069&&a[0]<=34074?6:1});}}return f(...a);});
  if(gl.texImage3D)wrap('texImage3D',(f,a)=>{const t=texture(a[0]);if(t){const bpp=bytes(a[7],a[8]);t.levels.set(`${a[0]}:${a[1]}`,a[3]*a[4]*a[5]*bpp);if(a[1]===0)Object.assign(t,{width:a[3],height:a[4],depth:a[5],bpp});}return f(...a);});
  for(const dimensions of[2,3]){const name=`texStorage${dimensions}D`;if(gl[name])wrap(name,(f,a)=>{const t=texture(a[0]);if(t){Object.assign(t,{width:a[3],height:a[4],depth:dimensions===3?a[5]:1,bpp:internalBytes(a[2]),faces:a[0]===34067?6:1,immutable:true});for(let level=0;level<a[1];level++)t.levels.set(`${a[0]}:${level}`,Math.max(1,a[3]>>level)*Math.max(1,a[4]>>level)*Math.max(1,t.depth>>level)*t.bpp*t.faces);}return f(...a);});}
  wrap('generateMipmap',(f,a)=>{const t=texture(a[0]);if(t&&!t.immutable){let w=t.width,h=t.height,d=t.depth,level=0;while(w>1||h>1||d>1){w=Math.max(1,w>>1);h=Math.max(1,h>>1);d=Math.max(1,d>>1);t.levels.set(`${a[0]}:${++level}`,w*h*d*t.bpp*t.faces);}}return f(...a);});
  wrap('createBuffer',(f,a)=>{const b=f(...a);e.buffers.set(b,0);return b;});wrap('deleteBuffer',(f,a)=>{e.buffers.delete(a[0]);return f(...a);});wrap('bindBuffer',(f,a)=>{e.boundBuffers.set(a[0],a[1]);return f(...a);});wrap('bufferData',(f,a)=>{const b=e.boundBuffers.get(a[0]);if(b)e.buffers.set(b,typeof a[1]==='number'?a[1]:a[1]?.byteLength??0);return f(...a);});
  for(const name of ['drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced'])if(gl[name])wrap(name,(f,a)=>{e.draws++;return f(...a);});
  wrap('getExtension',(f,a)=>{const ext=f(...a);if(a[0]==='WEBGL_lose_context'&&ext&&!ext.__wrapped){const native=ext.loseContext.bind(ext);ext.loseContext=()=>{lose();native();};ext.__wrapped=true;}return ext;});
  return gl;
 };
 window.__GPU_PROBE={snapshot,maxActive:()=>maxActive,active:()=>snapshot().filter(e=>e.active).length,prune:()=>{for(const[id,e]of entries)if(!e.active)entries.delete(id);}};
 window.__COSMOS_QA={scenes:new Map(),history:[],sequence:0};
 window.__PAGE_EVENTS=[];addEventListener('pageshow',e=>window.__PAGE_EVENTS.push({kind:'pageshow',persisted:e.persisted}));
}
