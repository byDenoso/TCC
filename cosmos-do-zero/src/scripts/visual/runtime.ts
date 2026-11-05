import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { registerDiagnostics } from './diagnostics';
import { canUseWebGPU, FrameBudget } from './render-policy';

/** A página possui uma única licença de GPU. Uma cena nova devolve a anterior ao SVG. */
let active: (() => void) | null = null;
let contexts = 0;
let mountQueue: Promise<void> = Promise.resolve();
let gpuDisposal: Promise<void> = Promise.resolve();
export function claimContext(release: () => void): () => void {
  active?.(); active = release; contexts++;
  document.documentElement.dataset.cosmosContexts = String(contexts);
  return () => {
    contexts = Math.max(0, contexts - 1);
    if (active === release) active = null;
    document.documentElement.dataset.cosmosContexts = String(contexts);
  };
}

export interface VisualState { value: number; phase: number; elapsed: number }
export interface Exhibit {
  group: THREE.Group;
  update(state: VisualState): void;
  camera?: [number, number, number];
  cameraForValue?: (value:number,aspect:number)=>[number,number,number];
  cameraForAspect?: (aspect:number)=>[number,number,number];
  orthographicHeight?: (aspect:number)=>number;
  highDefinition?: boolean;
  views?:{label:string;camera:[number,number,number]}[];
  lighting?: { ambient:number; key:number; fill:number; exposure:number; shadows?:boolean; neutral?:boolean; keyPosition?:[number,number,number] };
  quality?(quality:'auto'|'low',width:number):Promise<void>|void;
  dispose?():void;
  inspect?():unknown;
  labels?: { text: string; position: THREE.Vector3; object?:THREE.Object3D; visible?:()=>boolean; pixelOffset?:[number,number] }[];
}
export interface MountedScene {
  state(next: Partial<VisualState>): void;
  play(on: boolean): void;
  resize(): void;
  resetView(): void;
  dispose(): void;
}

type Renderer = THREE.WebGLRenderer | import('three/webgpu').WebGPURenderer;
type PreparedRenderer = {renderer:Renderer;canvas:HTMLCanvasElement;backend:'webgpu'|'webgl2'};
const makeCanvas = () => {
  const canvas = document.createElement('canvas');
  canvas.className = 'cosmos-volume mx-gl'; canvas.setAttribute('aria-hidden', 'true');
  return canvas;
};
async function discardCandidate(candidate: import('three/webgpu').WebGPURenderer): Promise<void> {
  // The Three.js GPU renderer can internally fall back to a WebGL2 context.
  // Explicitly release that context before opening the legacy WebGL renderer.
  const gl = (candidate.backend as unknown as {gl?:WebGL2RenderingContext}).gl;
  gl?.getExtension('WEBGL_lose_context')?.loseContext();
  await candidate.dispose();
}

/** Never send legacy GLSL materials to WebGPURenderer. */
async function prepareRenderer(exhibit: Exhibit, forceWebGL: boolean): Promise<PreparedRenderer | null> {
  let canvas = makeCanvas();
  if (!forceWebGL && 'gpu' in navigator && navigator.gpu && canUseWebGPU(exhibit.group)) {
    let candidate: import('three/webgpu').WebGPURenderer | undefined;
    try {
      const {WebGPURenderer} = await import('three/webgpu');
      candidate = new WebGPURenderer({canvas, antialias:true, logarithmicDepthBuffer:true, powerPreference:'low-power'});
      await candidate.init();
      if ((candidate.backend as unknown as {isWebGPUBackend?:boolean}).isWebGPUBackend) return {renderer:candidate,canvas,backend:'webgpu'};
      await discardCandidate(candidate);
    } catch (error) {
      console.warn('[cosmos] WebGPU indisponível; usando WebGL2', error);
      if (candidate) await discardCandidate(candidate).catch(disposeError => console.warn('[cosmos] falha ao liberar candidato',disposeError));
    }
    // A canvas already bound to WebGPU or the WebGL backend cannot be rebound safely.
    canvas = makeCanvas();
  }
  // GLSL shaders without log-depth chunks must not mix with log-depth standard materials.
  try { return {renderer:new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'low-power',logarithmicDepthBuffer:canUseWebGPU(exhibit.group)}),canvas,backend:'webgl2'}; }
  catch (error) { console.warn('[cosmos] WebGL2 indisponível', error); return null; }
}

/** Sem relógio paralelo: o motor envia fase/tempo. Câmera só muda por ação explícita. */
function mount(stage: HTMLElement, exhibit: Exhibit, prepared: PreparedRenderer, onDispose?: () => void): MountedScene {
  active?.();
  stage.querySelector('.cosmos-preview')?.remove();
  const {canvas,renderer,backend} = prepared;
  stage.dataset.renderer = backend;
  renderer.setClearColor(0x070c18); renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = exhibit.lighting?.exposure??0.9;
  const scene = new THREE.Scene(); scene.add(exhibit.group);
  scene.add(new THREE.AmbientLight(exhibit.lighting?.neutral?0xffffff:0xb7c4d6, exhibit.lighting?.ambient??1.2));
  const key = new THREE.DirectionalLight(exhibit.lighting?.neutral?0xffffff:0xfff2df, exhibit.lighting?.key??3); key.position.set(...(exhibit.lighting?.keyPosition??[-5,4,6])); scene.add(key);
  const fill = new THREE.DirectionalLight(0x477ccf, exhibit.lighting?.fill??2); fill.position.set(4, -1, -4); scene.add(fill);
  if(exhibit.lighting?.shadows){renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-3;key.shadow.camera.right=3;key.shadow.camera.top=3;key.shadow.camera.bottom=-3;key.shadow.bias=-.0004;key.shadow.normalBias=.015;}
  const camera = exhibit.orthographicHeight?new THREE.OrthographicCamera(-2,2,2,-2,.02,150):new THREE.PerspectiveCamera(42, 1, 0.02, 150);
  const diagnostics=registerDiagnostics(stage,renderer,exhibit);
  const home = new THREE.Vector3(...(exhibit.camera ?? [0, 3.3, 9.5])); camera.position.copy(home);
  const controls = new OrbitControls(camera, canvas);
  controls.enabled = false; controls.enableDamping = false; controls.enablePan = false;
  controls.minDistance = home.length() * 0.5; controls.maxDistance = home.length() * 1.8;
  let alive = true;
  const state: VisualState = { value: 0, phase: 1, elapsed: 0 };
  const frameBudget = new FrameBudget();
  let lastFrame = 0, measuring = false, adaptiveProfile:'low'|'standard'|null = null;
  let cinematic: ReturnType<typeof import('./cinematic-pipeline').createCinematicPipeline>|null=null, cinematicRevision=0;
  const render = (animationFrame=false) => { if (!alive || document.hidden) return; const rect=stage.getBoundingClientRect();if(rect.bottom<=0||rect.top>=innerHeight){lastFrame=0;return;}const updateStart=diagnostics.enabled?performance.now():0;exhibit.update(state);const updateMs=diagnostics.enabled?performance.now()-updateStart:0;const start=diagnostics.enabled?performance.now():0; const frameStart=performance.now();
    // Scene updates can add an unsupported material/primitive after initialization.
    if(backend==='webgpu'&&!canUseWebGPU(exhibit.group)){stage.dataset.forceWebgl='true';queueMicrotask(()=>{if(alive){dispose();stage.dispatchEvent(new CustomEvent('cosmos:gpulost'));}});return;}
    try { if(cinematic)cinematic.render();else renderer.render(scene, camera); } catch (error) {
      console.warn('[cosmos] falha ao desenhar',error);
      if(cinematic){cinematic.dispose();cinematic=null;stage.dataset.cinematic='unavailable';try{renderer.render(scene,camera);return;}catch(fallbackError){console.warn('[cosmos] falha sem pós-processamento',fallbackError);}}
      if(backend==='webgpu')stage.dataset.forceWebgl='true';queueMicrotask(()=>{if(alive){dispose();stage.dispatchEvent(new CustomEvent(backend==='webgpu'?'cosmos:gpulost':'cosmos:contextlost'));}});return;
    }
    if (animationFrame && measuring && quality.value==='auto' && !adaptiveProfile) { if(lastFrame)frameBudget.record(frameStart-lastFrame); lastFrame=frameStart; const measured=frameBudget.decide(); if(measured){adaptiveProfile=measured;stage.dataset.adaptiveQuality=measured;queueMicrotask(resize);} }
    diagnostics.frame(diagnostics.enabled?performance.now()-start:0,updateMs); };
  const details = document.createElement('details'); details.className = 'cosmos-view-options';
  const summary = document.createElement('summary'); summary.textContent = 'Visão e qualidade da cena'; details.append(summary);
  const tools = document.createElement('div'); tools.className = 'cosmos-view-tools'; details.append(tools);
  const button = (label: string, action: () => void) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.addEventListener('click', action); tools.append(b); return b;
  };
  const rotate = button('Girar a cena', () => {
    controls.enabled = !controls.enabled;
    rotate.setAttribute('aria-pressed', String(controls.enabled));
    rotate.textContent = controls.enabled ? 'Liberar a rolagem' : 'Girar a cena';
    canvas.style.pointerEvents = controls.enabled ? 'auto' : 'none';
    canvas.style.touchAction = controls.enabled ? 'none' : 'pan-y';
  });
  rotate.setAttribute('aria-pressed', 'false');
  const resetView = () => { controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);camera.zoom=1;camera.updateProjectionMatrix(); controls.target.set(0, 0, 0); controls.update(); render(); };
  button('Restaurar visão', resetView);
  const left = button('↶', () => turn(-0.2)); left.setAttribute('aria-label', 'Girar visão para a esquerda');
  const right = button('↷', () => turn(0.2)); right.setAttribute('aria-label', 'Girar visão para a direita');
  for(const view of exhibit.views??[])button(view.label,()=>{const position=new THREE.Vector3(...view.camera);controls.minDistance=position.length()*.4;camera.position.copy(position);controls.update();render();projectLabels();});
  const up=button('↑',()=>pitch(-.15));up.setAttribute('aria-label','Ver a cena de cima');
  const down=button('↓',()=>pitch(.15));down.setAttribute('aria-label','Baixar a visão da cena');
  const zoom=(factor:number)=>{if(camera instanceof THREE.OrthographicCamera){camera.zoom*=factor;camera.updateProjectionMatrix();}else camera.position.multiplyScalar(1/factor);controls.update();render();};
  button('Aproximar +', () => zoom(1/.88));
  button('Afastar −', () => zoom(1/1.12));
  function turn(a: number) { camera.position.applyAxisAngle(new THREE.Vector3(0, 1, 0), a); controls.update(); render(); }
  function pitch(a:number){camera.position.applyAxisAngle(new THREE.Vector3(1,0,0),a);controls.update();render();}
  const quality = document.createElement('select'); quality.setAttribute('aria-label', 'Qualidade da cena');
  quality.innerHTML = `<option value="auto">Automática</option><option value="low">Econômica</option><option value="standard">Padrão</option><option value="high">${backend==='webgpu'?'Cinemática · WebGPU':'Alta definição · WebGL2'}</option>`;
  quality.value=['low','standard','high'].includes(stage.dataset.cosmosQuality??'')?stage.dataset.cosmosQuality!:'auto';
  tools.append(quality);
  stage.append(canvas); stage.classList.add('cosmos-volume-ready','mx-stage--gl');
  const explanation=stage.closest('.mx-lab,.solar-experiment')?.querySelector('.mx-caption') ?? stage.closest('.obs-expansion-grid')?.querySelector('.obs-reading') ?? stage.closest('[data-island="planets"]')?.querySelector('[data-planet-description]') ?? stage.closest('[data-island="compare"]')?.querySelector('.compare-insight') ?? stage.closest('[data-scene]')?.querySelector('.scene-reading');
  if(explanation)explanation.after(details);else stage.after(details);
  const labels = (exhibit.labels ?? []).map((label) => {
    const e = document.createElement('span'); e.className = 'cosmos-object-label'; e.textContent = label.text; stage.append(e); return { e, label };
  });
  const projectLabels = () => {
    const occupied:{x:number;y:number;w:number;h:number}[]=[];
    labels.forEach(({e,label}) => {
    e.textContent = label.text;
    const p = (label.object ? label.object.getWorldPosition(new THREE.Vector3()) : label.position.clone()).project(camera);
    e.hidden = label.visible?.()===false || p.z > 1 || Math.abs(p.x)>1 || Math.abs(p.y)>1;
    if(e.hidden)return;
    const w=e.offsetWidth,h=e.offsetHeight;
    const x=Math.max(w/2+6,Math.min(stage.clientWidth-w/2-6,(p.x*.5+.5)*stage.clientWidth+(label.pixelOffset?.[0]??0)));
    let y=(-p.y*.5+.5)*stage.clientHeight+(label.pixelOffset?.[1]??20);
    for(let i=0;i<5&&occupied.some(b=>x-w/2<b.x+b.w&&x+w/2>b.x&&y<b.y+b.h+4&&y+h>b.y-4);i++)y+=h+5;
    y=Math.max(6,Math.min(stage.clientHeight-h-6,y));
    e.style.left=`${x}px`;e.style.top=`${y}px`;occupied.push({x:x-w/2,y,w,h});
  });};
  let previousAspect=0,qualityKey='';
  const resize = () => {
    stage.dataset.cosmosQuality=quality.value;
    const w = stage.clientWidth, h = stage.clientHeight; if (!w || !h || !alive) return;
    const profile=quality.value==='auto'?(adaptiveProfile??'standard'):quality.value;
    renderer.setPixelRatio(profile==='high'?Math.min(2,Math.max(devicePixelRatio||1,w<600?1.25:1.5)):profile==='low'?1:Math.min(devicePixelRatio||1,w<600?1.25:1.5));
    renderer.setSize(w, h, false);const aspect=w/h;
    if(camera instanceof THREE.PerspectiveCamera)camera.aspect=aspect;else{const height=exhibit.orthographicHeight!(aspect);camera.left=-height*aspect/2;camera.right=height*aspect/2;camera.top=height/2;camera.bottom=-height/2;}
    if(exhibit.cameraForAspect&&aspect!==previousAspect){home.set(...exhibit.cameraForAspect(aspect));controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);controls.update();}previousAspect=aspect;
    const nextQualityKey=`${profile}:${w<600}`;
    if(exhibit.quality&&nextQualityKey!==qualityKey){qualityKey=nextQualityKey;stage.dataset.qualityPending='true';Promise.resolve(exhibit.quality(profile==='low'?'low':'auto',w)).then(()=>{if(alive){stage.dataset.textureQuality=String(exhibit.group.userData.textureQuality);stage.dataset.qualityPending='false';render();projectLabels();}}).catch(()=>{if(alive){stage.dataset.qualityPending='false';stage.dataset.qualityError='true';}});}
    if(exhibit.cameraForValue){home.set(...exhibit.cameraForValue(state.value,aspect));controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);controls.update();}
    camera.updateProjectionMatrix(); render(); projectLabels();
  };
  const updateCinematic=()=>{
    const revision=++cinematicRevision;
    cinematic?.dispose();cinematic=null;delete stage.dataset.cinematic;
    if(quality.value!=='high'||!('isWebGPURenderer' in renderer))return;
    stage.dataset.cinematic='loading';
    void import('./cinematic-pipeline').then(({createCinematicPipeline})=>{
      if(!alive||revision!==cinematicRevision)return;
      cinematic=createCinematicPipeline(renderer,scene,camera);stage.dataset.cinematic='active';render();
    }).catch(error=>{if(alive&&revision===cinematicRevision){stage.dataset.cinematic='unavailable';console.warn('[cosmos] pós-processamento indisponível',error);}});
  };
  quality.addEventListener('change', ()=>{resize();updateCinematic();}); controls.addEventListener('change', () => {render();projectLabels();});
  const ro = new ResizeObserver(resize); ro.observe(stage);
  const release = claimContext(dispose);
  const hide = () => { lastFrame=0; if (document.hidden) return; render(); };
  document.addEventListener('visibilitychange', hide);
  const lost = (e: Event) => { e.preventDefault(); dispose(); stage.dispatchEvent(new CustomEvent('cosmos:contextlost')); };
  canvas.addEventListener('webglcontextlost', lost);
  if ('isWebGPURenderer' in renderer) renderer.onDeviceLost = () => { if (!alive) return; stage.dataset.forceWebgl = 'true'; dispose(); stage.dispatchEvent(new CustomEvent('cosmos:gpulost')); };
  function dispose() {
    if (!alive) return; alive = false;
    ro.disconnect(); document.removeEventListener('visibilitychange', hide);
    canvas.removeEventListener('webglcontextlost', lost); controls.dispose();
    // A preserved scientific chart lives below this stage; retain a lightweight preview here.
    if(backend==='webgl2'&&!stage.querySelector('svg')&&!(renderer as THREE.WebGLRenderer).getContext().isContextLost()){try{renderer.render(scene,camera);const image=document.createElement('img');image.className='cosmos-preview';image.alt='Prévia da experiência no último estado; os controles e o esquema permanecem disponíveis.';image.src=canvas.toDataURL('image/webp',.82);stage.querySelector('.cosmos-preview')?.remove();stage.prepend(image);}catch{/* The functional2D chart remains available if a snapshot is unavailable. */}}
    cinematicRevision++;cinematic?.dispose();cinematic=null;exhibit.dispose?.();diagnostics.dispose();disposeObjects(scene);
    if ('isWebGPURenderer' in renderer) gpuDisposal = gpuDisposal.catch(error=>console.warn('[cosmos] descarte anterior da GPU',error)).then(() => renderer.dispose());
    else { renderer.dispose(); renderer.forceContextLoss(); }
    canvas.remove(); details.remove(); labels.forEach(({e})=>e.remove()); stage.classList.remove('cosmos-volume-ready','mx-stage--gl'); delete stage.dataset.renderer; release(); onDispose?.();
  }
  resize();
  updateCinematic();
  return { state(next) { const changed=next.value!==undefined&&next.value!==state.value;Object.assign(state, next);if(changed&&exhibit.cameraForValue){home.set(...exhibit.cameraForValue(state.value,stage.clientWidth/stage.clientHeight));controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);controls.target.set(0,0,0);controls.update();}render(true); projectLabels(); }, play(on) { measuring=on; lastFrame=0; }, resize, resetView, dispose };
}

export function disposeObjects(root: THREE.Object3D): void {
  const resources = new Set<{ dispose(): void }>();
  root.traverse((o) => {
    if(o instanceof THREE.Light)resources.add(o);
    const mesh = o as THREE.Mesh;
    if (mesh.geometry) resources.add(mesh.geometry);
    if (mesh.material) for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      resources.add(m);
      for (const v of Object.values(m)) if (v instanceof THREE.Texture) resources.add(v);
      if (m instanceof THREE.ShaderMaterial) for (const u of Object.values(m.uniforms)) if (u.value instanceof THREE.Texture) resources.add(u.value);
    }
  });
  resources.forEach((r) => r.dispose());
}

/** Criação só no palco visível. Revogação e falha preservam controles e estado SVG. */
export function observeScene(stage: HTMLElement, create: () => Exhibit): MountedScene {
  let view: MountedScene | null = null, disposed = false, failed = false, pending = false, generation = 0, playing = false;
  const latest: VisualState = { value: 0, phase: 1, elapsed: 0 };
  const interactionRoot=stage.closest('.obs-expansion-grid,.mx-lab,.solar-experiment,[data-island="planets"],[data-island="compare"],[data-scene]')??stage.parentElement;
  const optionsActive=()=>{const options=interactionRoot?.querySelector<HTMLDetailsElement>('.cosmos-view-options');if(!options)return false;const rect=options.getBoundingClientRect();return options.open||!!document.activeElement?.closest('.cosmos-view-options')&&!!interactionRoot?.contains(document.activeElement)||rect.bottom>0&&rect.top<innerHeight;};
  const cancelPending=()=>{if(pending){generation++;pending=false;}};
  const enter = () => {
    if (disposed || failed || stage.closest('[hidden]')) return;
    if(view){view.state(latest);return;}
    if(pending)return;
    pending=true;const ticket=++generation;
    const valid=()=>!disposed&&!failed&&ticket===generation&&stage.isConnected&&!stage.closest('[hidden]');
    mountQueue=mountQueue.catch(error=>console.warn('[cosmos] fila de renderização',error)).then(async()=>{
      if(!valid())return;
      active?.();
      await gpuDisposal.catch(error=>console.warn('[cosmos] descarte da GPU',error));
      if(!valid())return;
      let exhibit:Exhibit|undefined,prepared:PreparedRenderer|null=null;
      try{
        exhibit=create();
        prepared=await prepareRenderer(exhibit,stage.dataset.forceWebgl==='true');
        if(!valid()){
          exhibit.dispose?.();disposeObjects(exhibit.group);
          if(prepared){if('isWebGPURenderer' in prepared.renderer)await prepared.renderer.dispose();else{prepared.renderer.dispose();prepared.renderer.forceContextLoss();}}
          return;
        }
        if(!prepared)throw new Error('Nenhum backend 3D disponível');
        view=mount(stage,exhibit,prepared,()=>{view=null;});
        pending=false;view.play(playing);view.state(latest);stage.dispatchEvent(new CustomEvent('cosmos:ready'));
      }catch(error){
        console.warn('[cosmos] falha ao montar cena 3D',error);
        if(exhibit){exhibit.dispose?.();disposeObjects(exhibit.group);}
        if(prepared){if('isWebGPURenderer' in prepared.renderer)await prepared.renderer.dispose();else{prepared.renderer.dispose();prepared.renderer.forceContextLoss();}}
        if(valid()){pending=false;failed=true;stage.dataset.visualFallback='true';stage.dispatchEvent(new CustomEvent('cosmos:unavailable'));}
      }
    }).finally(()=>{if(ticket===generation)pending=false;});
  };
  const io = new IntersectionObserver(([e]) => {
    if (e.isIntersecting) enter(); else if(!optionsActive()) { cancelPending();view?.dispose(); view = null; }
  }, { threshold: 0.12 }); io.observe(stage);
  const focus = () => {const rect=stage.getBoundingClientRect();if(rect.bottom>0&&rect.top<innerHeight||optionsActive())enter();};interactionRoot?.addEventListener('focusin',focus);
  const blur=()=>queueMicrotask(()=>{const rect=stage.getBoundingClientRect();if((rect.bottom<=0||rect.top>=innerHeight)&&!optionsActive()){cancelPending();view?.dispose();view=null;}});interactionRoot?.addEventListener('focusout',blur);
  const optionsToggle=(event:Event)=>{const target=event.target as HTMLDetailsElement;if(!target.matches?.('.cosmos-view-options')||target.open)return;const rect=stage.getBoundingClientRect();if(rect.bottom<=0||rect.top>=innerHeight){cancelPending();view?.dispose();view=null;}};
  interactionRoot?.addEventListener('toggle',optionsToggle,true);
  const scroll=()=>{const rect=stage.getBoundingClientRect();if((rect.bottom<=0||rect.top>=innerHeight)&&!optionsActive()){cancelPending();view?.dispose();view=null;}};window.addEventListener('scroll',scroll,{passive:true});
  const lose = () => { failed = true; stage.dataset.visualFallback = 'true'; };
  stage.addEventListener('cosmos:contextlost', lose);
  const gpuLost = () => { cancelPending();enter(); };
  stage.addEventListener('cosmos:gpulost', gpuLost);
  const freeze = () => { cancelPending();view?.dispose(); view=null; };
  const resume = (event:PageTransitionEvent) => { if(event.persisted) { const r=stage.getBoundingClientRect(); if(r.bottom>0&&r.top<innerHeight)enter(); } };
  window.addEventListener('pagehide',freeze); window.addEventListener('pageshow',resume);
  return {
    state(next) { Object.assign(latest, next); view?.state(latest); },
    play(on) { playing=on;view?.play(on); }, resize() { view?.resize(); }, resetView() { view?.resetView(); },
    dispose() { disposed = true;cancelPending();io.disconnect(); window.removeEventListener('scroll',scroll);view?.dispose(); interactionRoot?.removeEventListener('focusin',focus);interactionRoot?.removeEventListener('focusout',blur);interactionRoot?.removeEventListener('toggle',optionsToggle,true);stage.removeEventListener('cosmos:contextlost', lose);stage.removeEventListener('cosmos:gpulost',gpuLost); window.removeEventListener('pagehide',freeze);window.removeEventListener('pageshow',resume); }
  };
}

/** Await proximity without requesting assets for hidden tabs or distant chapters. */
export function whenNear(stage:HTMLElement,valid:()=>boolean=()=>true):Promise<boolean>{return new Promise(resolve=>{if(!valid()){resolve(false);return;}let done=false;const finish=(ok:boolean)=>{if(done)return;done=true;observer.disconnect();window.removeEventListener('pagehide',hide);resolve(ok&&valid());};const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))finish(true);},{rootMargin:'300px 0px'});const hide=(e:PageTransitionEvent)=>{if(!e.persisted)finish(false);};window.addEventListener('pagehide',hide);observer.observe(stage);});}
