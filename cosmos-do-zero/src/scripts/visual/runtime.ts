import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { registerDiagnostics } from './diagnostics';
import { FrameBudget } from './render-policy';
import { photographicExposure, type CameraExposure } from './camera-exposure';
import { moveWorldPosition, rebaseWorld, relativePositionMeters, type WorldAnchor, type WorldPosition } from './world-frame';
import { motionPreference } from '../motion-preference';
import { claimContext, mountWithGpu } from './gpu-lease';
import type { PlayCanvasRenderer } from './playcanvas-adapter';

export interface VisualState { value: number; phase: number; elapsed: number }
export interface Exhibit {
  group: THREE.Group;
  background?: number;
  update(state: VisualState): void;
  camera?: [number, number, number];
  cameraForValue?: (value:number,aspect:number)=>[number,number,number];
  cameraForAspect?: (aspect:number)=>[number,number,number];
  orthographicHeight?: (aspect:number)=>number;
  cameraClip?: {near:number;far:number};
  highDefinition?: boolean;
  views?:{label:string;camera:[number,number,number]}[];
  lighting?: { ambient:number; key:number; fill:number; exposure:number; shadows?:boolean; neutral?:boolean; keyPosition?:[number,number,number] };
  photography?: { camera:CameraExposure; artisticLuminanceScale:number };
  worldFrame?: {
    origin(state:VisualState):WorldPosition;
    camera():WorldPosition;
    target():WorldPosition;
    setView(camera:WorldPosition,target:WorldPosition):void;
    resetView():void;
    anchors(state:VisualState):readonly WorldAnchor[];
    sceneUnitsPerMeter?:number;
  };
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

type PreparedRenderer = { renderer: PlayCanvasRenderer; canvas: HTMLCanvasElement };

function makeCanvas() {
  const canvas = document.createElement('canvas');
  canvas.className = 'cosmos-volume mx-gl';
  canvas.setAttribute('aria-hidden', 'true');
  return canvas;
}

type AuthoringObserver = (
  stage: HTMLElement,
  scene: THREE.Scene,
  camera: THREE.PerspectiveCamera | THREE.OrthographicCamera,
  state: Readonly<VisualState>
) => void;

/** Sem relógio paralelo: o motor envia fase/tempo. Câmera só muda por ação explícita. */
function mount(stage: HTMLElement, exhibit: Exhibit, prepared: PreparedRenderer, onDispose?: () => void): MountedScene {
  const { canvas, renderer } = prepared;
  const {near,far}=exhibit.cameraClip??{near:.02,far:150};
  if(!Number.isFinite(near)||!Number.isFinite(far)||near<=0||far<=near)throw new RangeError('planos da câmera inválidos');
  if(exhibit.worldFrame&&(exhibit.cameraForValue||exhibit.cameraForAspect))throw new Error('câmera física não aceita enquadramento normalizado');
  if(exhibit.worldFrame&&exhibit.orthographicHeight)throw new Error('câmera ortográfica não suportada no frame físico');
  if(exhibit.worldFrame&&exhibit.lighting?.shadows)throw new Error('sombras não suportadas no frame físico WebGL');
  if(exhibit.worldFrame)renderer.setPhysicalClip(near,far);
  stage.querySelector('.cosmos-preview')?.remove();
  stage.dataset.renderer = 'webgl2';
  stage.dataset.rendererEngine = 'playcanvas';
  renderer.setClearColor(exhibit.background??0x070c18);
  const exposure=exhibit.lighting?.exposure??0.9;
  renderer.toneMappingExposure=exhibit.photography?photographicExposure(exhibit.photography.camera).normalization*exhibit.photography.artisticLuminanceScale*exposure:exposure;
  const scene = new THREE.Scene(); scene.add(exhibit.group);
  scene.add(new THREE.AmbientLight(exhibit.lighting?.neutral?0xffffff:0xb7c4d6, exhibit.lighting?.ambient??1.2));
  const key = new THREE.DirectionalLight(exhibit.lighting?.neutral?0xffffff:0xfff2df, exhibit.lighting?.key??3); key.position.set(...(exhibit.lighting?.keyPosition??[-5,4,6])); scene.add(key);
  const fill = new THREE.DirectionalLight(0x477ccf, exhibit.lighting?.fill??2); fill.position.set(4, -1, -4); scene.add(fill);
  if(exhibit.lighting?.shadows){renderer.shadowMap.enabled=true;key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-3;key.shadow.camera.right=3;key.shadow.camera.top=3;key.shadow.camera.bottom=-3;key.shadow.bias=-.0004;key.shadow.normalBias=.015;}
  const camera = exhibit.orthographicHeight?new THREE.OrthographicCamera(-2,2,2,-2,near,far):new THREE.PerspectiveCamera(42, 1, near, far);
  const home = new THREE.Vector3(...(exhibit.camera ?? [0, 3.3, 9.5])); camera.position.copy(home);
  const homeDistance=exhibit.worldFrame?Math.hypot(...relativePositionMeters(exhibit.worldFrame.camera(),exhibit.worldFrame.target()))*(exhibit.worldFrame.sceneUnitsPerMeter??1):home.length();
  if(!Number.isFinite(homeDistance)||homeDistance<=0)throw new RangeError('distância inicial da câmera inválida');
  const controls = new OrbitControls(camera, canvas);
  controls.enabled = false; controls.enableDamping = false; controls.enablePan = false;
  controls.minDistance = homeDistance * 0.5; controls.maxDistance = homeDistance * 1.8;
  const diagnostics=registerDiagnostics(stage,renderer,exhibit);
  let alive = true;
  const state: VisualState = { value: 0, phase: 1, elapsed: 0 };
  let frameOrigin:WorldPosition|null=null;
  const frameBudget = new FrameBudget();
  let lastFrame = 0, measuring = false, adaptiveProfile:'low'|'standard'|'high'|null = null, calibrationRaf=0, calibrationStart=0, calibrationTimer=0;
  let calibrationComplete = false;
  const failScene=(error:unknown)=>{
    console.warn('[cosmos] falha ao atualizar cena',error);
    queueMicrotask(()=>{if(alive){stage.dataset.visualFallback='true';dispose();stage.dispatchEvent(new CustomEvent('cosmos:contextlost'));}});
  };
  const render = (animationFrame=false) => { if (!alive || document.hidden) return; const rect=stage.getBoundingClientRect();if(rect.bottom<=0||rect.top>=innerHeight){lastFrame=0;return;}const updateStart=diagnostics.enabled?performance.now():0;
    try {
      exhibit.update(state);
      const frame=exhibit.worldFrame;
      if(frame){
        const origin=frame.origin(state),scale=frame.sceneUnitsPerMeter??1;
        rebaseWorld(origin,[{object:camera,position:frame.camera()},...frame.anchors(state)],scale);
        const target=relativePositionMeters(frame.target(),origin).map(value=>value*scale) as [number,number,number];
        if(target.some(value=>!Number.isFinite(value)))throw new RangeError('alvo da câmera fora do intervalo numérico');
        controls.target.set(...target);camera.lookAt(controls.target);frameOrigin=origin;
      }
    } catch(error){
      failScene(error);return;
    }
    const updateMs=diagnostics.enabled?performance.now()-updateStart:0;const start=diagnostics.enabled?performance.now():0; const frameStart=performance.now();
    try {
      renderer.render(scene, camera);
    } catch (error) {
      failScene(error);
      return;
    }
    if(animationFrame&&measuring&&canCalibrate())recordCalibration(frameStart);
    diagnostics.frame(diagnostics.enabled?performance.now()-start:0,updateMs);
    const observe = (window as Window & { __COSMOS_AUTHORING?: AuthoringObserver }).__COSMOS_AUTHORING;
    if (observe) {
      try { observe(stage, scene, camera, { ...state }); }
      catch (error) { console.warn('[cosmos] observação da cena', error); }
    }
  };
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
  const resetView = () => { if(exhibit.worldFrame){exhibit.worldFrame.resetView();camera.zoom=1;camera.updateProjectionMatrix();render();return;}controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);camera.zoom=1;camera.updateProjectionMatrix(); controls.target.set(0, 0, 0); controls.update(); render(); };
  button('Restaurar visão', resetView);
  const left = button('↶', () => turn(-0.2)); left.setAttribute('aria-label', 'Girar visão para a esquerda');
  const right = button('↷', () => turn(0.2)); right.setAttribute('aria-label', 'Girar visão para a direita');
  for(const view of exhibit.views??[])button(view.label,()=>{const position=new THREE.Vector3(...view.camera);controls.minDistance=position.length()*.4;camera.position.copy(position);controls.update();render();projectLabels();});
  const up=button('↑',()=>pitch(-.15));up.setAttribute('aria-label','Ver a cena de cima');
  const down=button('↓',()=>pitch(.15));down.setAttribute('aria-label','Baixar a visão da cena');
  const zoom=(factor:number)=>{if(camera instanceof THREE.OrthographicCamera){camera.zoom*=factor;camera.updateProjectionMatrix();}else camera.position.sub(controls.target).multiplyScalar(1/factor).add(controls.target);controls.update();render();};
  button('Aproximar +', () => zoom(1/.88));
  button('Afastar −', () => zoom(1/1.12));
  function turn(a: number) { camera.position.sub(controls.target).applyAxisAngle(new THREE.Vector3(0, 1, 0), a).add(controls.target); controls.update(); render(); }
  function pitch(a:number){camera.position.sub(controls.target).applyAxisAngle(new THREE.Vector3(1,0,0),a).add(controls.target);controls.update();render();}
  const quality = document.createElement('select'); quality.setAttribute('aria-label', 'Qualidade da cena');
  quality.innerHTML = `<option value="auto">Automática</option><option value="low">Econômica</option><option value="standard">Padrão</option><option value="high">Alta definição</option>`;
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
    renderer.setSize(w, h);const aspect=w/h;
    if(camera instanceof THREE.PerspectiveCamera)camera.aspect=aspect;else{const height=exhibit.orthographicHeight!(aspect);camera.left=-height*aspect/2;camera.right=height*aspect/2;camera.top=height/2;camera.bottom=-height/2;}
    if(exhibit.cameraForAspect&&aspect!==previousAspect){home.set(...exhibit.cameraForAspect(aspect));controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);controls.update();}previousAspect=aspect;
    const nextQualityKey=`${profile}:${w<600}`;
    if(exhibit.quality&&nextQualityKey!==qualityKey){qualityKey=nextQualityKey;stage.dataset.qualityPending='true';Promise.resolve(exhibit.quality(profile==='low'?'low':'auto',w)).then(()=>{if(alive){stage.dataset.textureQuality=String(exhibit.group.userData.textureQuality);stage.dataset.qualityPending='false';render();projectLabels();}}).catch(()=>{if(alive){stage.dataset.qualityPending='false';stage.dataset.qualityError='true';}});}
    if(exhibit.cameraForValue){home.set(...exhibit.cameraForValue(state.value,aspect));controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);controls.update();}
    camera.updateProjectionMatrix(); render(); projectLabels();
  };
  function canCalibrate(): boolean {
    const rect = stage.getBoundingClientRect();
    return alive && !calibrationComplete && !document.hidden && !motionPreference.matches &&
      quality.value === 'auto' && rect.bottom > 0 && rect.top < innerHeight;
  }

  function stopCalibration(status: string): void {
    if (calibrationRaf) cancelAnimationFrame(calibrationRaf);
    if (calibrationTimer) clearTimeout(calibrationTimer);
    calibrationRaf = 0;
    calibrationTimer = 0;
    lastFrame = 0;
    calibrationStart = 0;
    frameBudget.reset();
    stage.dataset.calibrationStatus = status;
  }

  function finishCalibration(result: 'low' | 'standard' | null): void {
    stopCalibration(result ? 'ready' : 'insufficient');
    calibrationComplete = true;
    if (result) {
      adaptiveProfile = result;
      stage.dataset.adaptiveQuality = result;
      queueMicrotask(() => { if (alive) resize(); });
    }
  }

  function recordCalibration(now: number): boolean {
    if (!calibrationStart) calibrationStart = now;
    if (lastFrame) frameBudget.record(now - lastFrame);
    lastFrame = now;
    stage.dataset.calibrationFrames = String(frameBudget.count);
    const elapsed = now - calibrationStart;
    const result = frameBudget.decide() ?? (elapsed >= 5000 ? frameBudget.decide(30) : null);
    if (result || elapsed >= 5000) {
      finishCalibration(result);
      return true;
    }
    return false;
  }

  function startCalibration(): void {
    if (calibrationComplete) return;
    if (!canCalibrate()) {
      stopCalibration(quality.value === 'auto' ? 'paused' : 'manual');
      return;
    }
    stopCalibration('measuring');
    stage.dataset.calibrationFrames = '0';
    stage.dataset.calibrationPhase = 'standard';
    calibrationTimer = window.setTimeout(() => {
      if (!canCalibrate()) { stopCalibration('paused'); return; }
      finishCalibration(lastFrame && performance.now() - lastFrame <= 150 ? frameBudget.decide(30) : null);
    }, 5100);
    if (measuring) return;
    const probe = (now: number) => {
      calibrationRaf = 0;
      if (!canCalibrate()) { stopCalibration('paused'); return; }
      render();
      if (alive && !recordCalibration(now)) calibrationRaf = requestAnimationFrame(probe);
    };
    calibrationRaf = requestAnimationFrame(probe);
  }

  quality.addEventListener('change', () => {
    stopCalibration('manual');
    calibrationComplete = false;
    adaptiveProfile = null;
    delete stage.dataset.adaptiveQuality;
    resize();
    if (quality.value === 'auto') startCalibration();
  });
  controls.addEventListener('change', () => {
    const frame=exhibit.worldFrame;
    try {if(frame&&frameOrigin){const scale=frame.sceneUnitsPerMeter??1;const world=(v:THREE.Vector3)=>moveWorldPosition(frameOrigin!,[v.x/scale,v.y/scale,v.z/scale]);frame.setView(world(camera.position),world(controls.target));}}
    catch(error){failScene(error);return;}
    render();projectLabels();
  });
  const ro = new ResizeObserver(resize); ro.observe(stage);
  const release = claimContext(dispose);
  const interruptCalibration = () => { if (!calibrationComplete) stopCalibration('paused'); };
  const hide = () => { if(document.hidden){interruptCalibration();return;}render();startCalibration(); };
  const motionChanged=()=>{if(motionPreference.matches)interruptCalibration();else startCalibration();};
  document.addEventListener('visibilitychange', hide);
  motionPreference.addEventListener('change',motionChanged);
  const lost = (e: Event) => { e.preventDefault(); dispose(); stage.dispatchEvent(new CustomEvent('cosmos:contextlost')); };
  canvas.addEventListener('webglcontextlost', lost);
  function dispose() {
    if (!alive) return; alive = false;
    stopCalibration('disposed');ro.disconnect(); document.removeEventListener('visibilitychange', hide);motionPreference.removeEventListener('change',motionChanged);
    canvas.removeEventListener('webglcontextlost', lost); controls.dispose();
    // Retain an image of the last view when the chart is outside this stage.
    if (!stage.querySelector('svg,[data-story-poster]') && !renderer.getContext().isContextLost()) {
      try {
        renderer.render(scene, camera);
        const image = document.createElement('img');
        image.className = 'cosmos-preview';
        image.alt = 'Prévia da experiência no último estado.';
        image.src = canvas.toDataURL('image/webp', .82);
        stage.querySelector('.cosmos-preview')?.remove();
        stage.prepend(image);
      } catch { /* The interactive chart remains available. */ }
    }
    try {
      exhibit.dispose?.();
      diagnostics.dispose();
      disposeObjects(scene);
    } finally {
      try { renderer.dispose(); }
      finally {
        canvas.remove();
        details.remove();
        labels.forEach(({e}) => e.remove());
        stage.classList.remove('cosmos-volume-ready', 'mx-stage--gl');
        delete stage.dataset.renderer;
        delete stage.dataset.rendererEngine;
        release();
        onDispose?.();
      }
    }
  }
  resize();
  startCalibration();
  return { state(next) { const changed=next.value!==undefined&&next.value!==state.value;Object.assign(state, next);if(changed&&exhibit.cameraForValue){home.set(...exhibit.cameraForValue(state.value,stage.clientWidth/stage.clientHeight));controls.minDistance=home.length()*.5;controls.maxDistance=home.length()*1.8;camera.position.copy(home);controls.target.set(0,0,0);controls.update();}render(true);projectLabels();if(!measuring&&!calibrationRaf&&!adaptiveProfile)startCalibration(); }, play(on) { if(measuring===on)return;measuring=on;stopCalibration('paused');startCalibration(); }, resize, resetView, dispose };
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
    if (disposed || failed || document.hidden || stage.closest('[hidden]')) return;
    if(view){view.state(latest);return;}
    if(pending)return;
    pending=true;const ticket=++generation;
    const valid=()=>!disposed&&!failed&&ticket===generation&&stage.isConnected&&!document.hidden&&!stage.closest('[hidden]');
    const unavailable=()=>{if(valid()){pending=false;failed=true;stage.dataset.visualFallback='true';stage.dispatchEvent(new CustomEvent('cosmos:unavailable'));}};
    void import('./playcanvas-adapter').then(({ PlayCanvasRenderer }) => mountWithGpu(valid, () => {
      let exhibit: Exhibit | undefined;
      let renderer: PlayCanvasRenderer | undefined;
      try {
        exhibit = create();
        const canvas = makeCanvas();
        renderer = new PlayCanvasRenderer(canvas);
        view = mount(stage, exhibit, { renderer, canvas }, () => { view = null; });
        pending = false;
        view.play(playing);
        view.state(latest);
        stage.dispatchEvent(new CustomEvent('cosmos:ready'));
        return view;
      } catch (error) {
        console.warn('[cosmos] falha ao montar cena 3D', error);
        if (view) {
          view.dispose();
        } else {
          try {
            exhibit?.dispose?.();
            if (exhibit) disposeObjects(exhibit.group);
          } finally {
            renderer?.dispose();
          }
        }
        unavailable();
        return null;
      }
    })).then(result => { if (!result && !failed) unavailable(); }, error => {
      console.warn('[cosmos] fila de renderização', error);
      unavailable();
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
  const freeze = () => { cancelPending();view?.dispose(); view=null; };
  const resume = (event:PageTransitionEvent) => { if(event.persisted) { const r=stage.getBoundingClientRect(); if(r.bottom>0&&r.top<innerHeight)enter(); } };
  const visibility = () => {
    if (document.hidden) freeze();
    else {
      const rect = stage.getBoundingClientRect();
      if (rect.bottom > 0 && rect.top < innerHeight) enter();
    }
  };
  document.addEventListener('visibilitychange', visibility);
  window.addEventListener('pagehide',freeze); window.addEventListener('pageshow',resume);
  return {
    state(next) { Object.assign(latest, next); view?.state(latest); },
    play(on) { playing=on;view?.play(on); }, resize() { view?.resize(); }, resetView() { view?.resetView(); },
    dispose() { disposed = true;cancelPending();io.disconnect(); window.removeEventListener('scroll',scroll);view?.dispose(); interactionRoot?.removeEventListener('focusin',focus);interactionRoot?.removeEventListener('focusout',blur);interactionRoot?.removeEventListener('toggle',optionsToggle,true);stage.removeEventListener('cosmos:contextlost', lose);document.removeEventListener('visibilitychange', visibility); window.removeEventListener('pagehide',freeze);window.removeEventListener('pageshow',resume); }
  };
}

/** Await proximity without requesting assets for hidden tabs or distant chapters. */
export function whenNear(stage:HTMLElement,valid:()=>boolean=()=>true):Promise<boolean>{return new Promise(resolve=>{if(!valid()){resolve(false);return;}let done=false;const finish=(ok:boolean)=>{if(done)return;done=true;observer.disconnect();window.removeEventListener('pagehide',hide);resolve(ok&&valid());};const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))finish(true);},{rootMargin:'300px 0px'});const hide=(e:PageTransitionEvent)=>{if(!e.persisted)finish(false);};window.addEventListener('pagehide',hide);observer.observe(stage);});}
