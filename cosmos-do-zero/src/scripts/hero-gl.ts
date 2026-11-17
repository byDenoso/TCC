import {
  AppBase, AppOptions, BLEND_ADDITIVE, CameraComponentSystem, Color,
  CULLFACE_NONE, Entity, Mesh, MeshInstance, PRIMITIVE_POINTS, RenderComponentSystem,
  RESOLUTION_FIXED, SEMANTIC_COLOR, SEMANTIC_POSITION, SEMANTIC_TEXCOORD0,
  ShaderMaterial, WebglGraphicsDevice
} from 'playcanvas';
import { motionPreference, motionFactor } from './motion-preference';
import { claimContext, mountWithGpu } from './visual/gpu-lease';

const nebulaShader = `
      precision highp float;
      precision highp int;
      varying vec2 vUv; uniform float uTime; uniform vec2 uPointer; uniform float uAspect; uniform float uScroll;
      float hash(vec2 position) {
        uvec2 sampleGrid = uvec2(ivec2(position));
        uint bits = sampleGrid.x * 1664525u + sampleGrid.y * 1013904223u;
        bits = (bits ^ (bits >> 16u)) * 2246822519u;
        bits = (bits ^ (bits >> 13u)) * 3266489917u;
        return float((bits ^ (bits >> 16u)) & 0xffffffu) / 16777216.0;
      }
      float noise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.0-2.0*f);
        return mix(mix(hash(i),hash(i+vec2(1,0)),u.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x), u.y); }
      float fbm(vec2 p){ float v=0.0, a=0.5; mat2 r=mat2(0.8,0.6,-0.6,0.8); for(int i=0;i<5;i++){ v+=a*noise(p); p=r*p*2.02+3.1; a*=0.5; } return v; }
      void main(){
        vec2 p = vec2((vUv.x-0.5)*uAspect, vUv.y-0.5) * 2.2;
        p.y += uScroll * 0.6;
        float t = uTime * 0.025;
        vec2 m = vec2((uPointer.x-0.5)*uAspect, uPointer.y-0.5) * 2.2;
        vec2 q = vec2(fbm(p + t), fbm(p + vec2(5.2, 1.3) - t));
        vec2 r = vec2(fbm(p + 3.5*q + vec2(1.7, 9.2) + 0.6*t), fbm(p + 3.5*q + vec2(8.3, 2.8) - 0.4*t));
        float f = fbm(p + 3.0*r);
        float glow = exp(-2.6 * length(p - m));
        vec3 deep = vec3(0.018, 0.025, 0.075);
        vec3 ocean = vec3(0.045, 0.11, 0.25);
        vec3 teal = vec3(0.025, 0.30, 0.38);
        vec3 violet = vec3(0.27, 0.13, 0.50);
        vec3 ice = vec3(0.32, 0.62, 0.72);
        vec3 col = mix(deep, ocean, smoothstep(0.25, 0.9, f));
        col = mix(col, teal, smoothstep(0.35, 0.95, length(q)) * 0.55);
        col = mix(col, violet, smoothstep(0.2, 0.9, vUv.x) * (0.3 + 0.45*f));
        col += ice * pow(smoothstep(0.55, 1.0, f*f*1.6), 2.0) * 0.45;
        col += vec3(0.20, 0.48, 0.65) * glow * 0.18;
        float vign = 1.0 - smoothstep(0.25, 1.55, length(vec2((vUv.x-0.68)*1.25, vUv.y-0.55)));
        float alpha = (0.18 + 0.82 * f) * (0.35 + 0.65 * vign);
        gl_FragColor = vec4(col, alpha * 0.92);
      }
`;

const starPositionShader = `
      attribute vec2 starData; attribute vec3 starPosition; attribute vec3 starColor;
      varying vec3 vColor; varying float vTw;
      uniform float uTime; uniform float uPx;
      uniform mat4 matrix_view; uniform mat4 matrix_model; uniform mat4 matrix_projection;
      void main(){
        vec4 mv = matrix_view * matrix_model * vec4(starPosition, 1.0);
        gl_Position = matrix_projection * mv;
        vTw = 0.7 + 0.3 * sin(uTime * (0.2 + fract(starData.y) * 0.4) + starData.y * 7.0);
        vColor = starColor;
        gl_PointSize = starData.x * uPx * (14.0 / -mv.z);
      }
`;

const starColorShader = `
      varying vec3 vColor; varying float vTw;
      void main(){
        vec2 d = gl_PointCoord - 0.5; float r = length(d);
        float core = 1.0 - smoothstep(0.0, 0.5, r);
        float spike = max(0.0, 1.0 - abs(d.x) * 14.0) * max(0.0, 1.0 - abs(d.y) * 2.2) + max(0.0, 1.0 - abs(d.y) * 14.0) * max(0.0, 1.0 - abs(d.x) * 2.2);
        float a = (core * core + spike * 0.25) * vTw;
        if (a < 0.01) discard;
        gl_FragColor = vec4(vColor * a, a);
      }
`;

const liveScenes = new WeakMap<HTMLElement, () => void>();

export function stopHeroGl(): void {
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  if (hero) liveScenes.get(hero)?.();
}

export async function initHeroGl(): Promise<boolean> {
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  if (!hero) return false;
  if (liveScenes.has(hero)) return true;
  const visible = () => {
    const rect = hero.getBoundingClientRect();
    return hero.isConnected && !document.hidden && rect.bottom > 0 && rect.top < innerHeight;
  };
  return await mountWithGpu(visible, () => createSky(hero, visible)) === true;
}

function createSky(hero: HTMLElement, visible: () => boolean): true {
  const canvas = document.createElement('canvas');
  canvas.id = 'cosmos-sky-nebula';
  canvas.className = 'hero-gl';
  canvas.dataset.renderer = 'playcanvas-webgl2';
  canvas.setAttribute('aria-hidden', 'true');
  const force = new URLSearchParams(location.search).has('gl');
  const device = new WebglGraphicsDevice(canvas, {
    alpha: true,
    antialias: false,
    premultipliedAlpha: false,
    powerPreference: 'low-power',
    failIfMajorPerformanceCaveat: !force
  });
  const lose = device.gl.getExtension('WEBGL_lose_context');
  const app = new AppBase(canvas);
  const options = new AppOptions();
  options.graphicsDevice = device;
  options.componentSystems = [CameraComponentSystem, RenderComponentSystem];
  options.resourceHandlers = [];

  let ready = false;
  let releaseGpu: (() => void) | undefined;
  let disposeListeners: (() => void) | undefined;
  let nebula: ShaderMaterial | undefined;
  let stars: ShaderMaterial | undefined;
  function dispose(failed = false) {
    if (!ready && !releaseGpu) return;
    const wasReady = ready;
    ready = false;
    const release = releaseGpu;
    releaseGpu = undefined;
    try {
      disposeListeners?.();
      nebula?.destroy();
      stars?.destroy();
      app.destroy();
    } finally {
      lose?.loseContext();
      canvas.remove();
      hero.classList.remove('has-gl');
      liveScenes.delete(hero);
      release?.();
      if (wasReady) hero.dispatchEvent(new CustomEvent('cosmos:hero3dlost', { detail: { failed } }));
    }
  }

  try {
    app.init(options);
    releaseGpu = claimContext(dispose);
    app.autoRender = false;
    hero.prepend(canvas);

    const camera = new Entity('Câmera da nebulosa');
    camera.addComponent('camera', {
      fov: 55, nearClip: 0.1, farClip: 100, clearColor: new Color(0, 0, 0, 0),
    });
    app.root.addChild(camera);

    nebula = new ShaderMaterial({
      uniqueName: 'cosmos-nebula',
      attributes: { aPosition: SEMANTIC_POSITION },
      vertexGLSL: `
        attribute vec3 aPosition;
        varying vec2 vUv;
        void main() {
          vUv = aPosition.xy * 0.5 + 0.5;
          gl_Position = vec4(aPosition.xy, 0.999, 1.0);
        }
      `,
      fragmentGLSL: nebulaShader,
    });
    nebula.cull = CULLFACE_NONE;
    nebula.depthWrite = false;
    nebula.depthTest = false;
    const backdrop = new Mesh(device);
    backdrop.setPositions([-1, -1, 0, 3, -1, 0, -1, 3, 0]);
    backdrop.update();
    addGeometry('Nebulosa', backdrop, nebula);

    stars = new ShaderMaterial({
      uniqueName: 'cosmos-deep-starfield',
      attributes: {
        starPosition: SEMANTIC_POSITION,
        starColor: SEMANTIC_COLOR,
        starData: SEMANTIC_TEXCOORD0,
      },
      vertexGLSL: starPositionShader,
      fragmentGLSL: starColorShader,
    });
    stars.blendType = BLEND_ADDITIVE;
    stars.depthWrite = false;
    const starsEntity = addGeometry('Campo de estrelas', starMesh(device, innerWidth < 700 ? 1400 : 3200), stars);

    disposeListeners = animateSky(hero, canvas, app, camera, nebula, stars, starsEntity, visible, dispose, force);
    liveScenes.set(hero, dispose);
    hero.classList.add('has-gl');
    ready = true;
    return true;
  } catch (error) {
    if (releaseGpu) dispose(true);
    else {
      device.destroy();
      lose?.loseContext();
    }
    throw error;
  }

  function addGeometry(name: string, mesh: Mesh, material: ShaderMaterial): Entity {
    const entity = new Entity(name);
    const instance = new MeshInstance(mesh, material, entity);
    instance.cull = false;
    entity.addComponent('render', { meshInstances: [instance] });
    app.root.addChild(entity);
    return entity;
  }
}

function starMesh(device: WebglGraphicsDevice, count: number): Mesh {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizeAndSeed = new Float32Array(count * 2);
  const palette = [[0.75, 0.86, 1], [0.54, 0.77, 1], [0.62, 0.64, 1], [0.91, 0.91, 1]];
  let seed = 20261101;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  for (let i = 0; i < count; i++) {
    positions.set([random() * 22 - 11, random() * 14 - 7, 3 - random() * 26], i * 3);
    colors.set(palette[Math.floor(random() * palette.length)], i * 3);
    sizeAndSeed.set([0.6 + random() ** 6 * 3.1, random() * Math.PI * 2], i * 2);
  }
  const mesh = new Mesh(device);
  mesh.setPositions(positions);
  mesh.setVertexStream(SEMANTIC_COLOR, colors, 3);
  mesh.setUvs(0, sizeAndSeed);
  mesh.update(PRIMITIVE_POINTS, false);
  return mesh;
}

function animateSky(
  hero: HTMLElement, canvas: HTMLCanvasElement, app: AppBase, camera: Entity,
  nebula: ShaderMaterial, stars: ShaderMaterial, starsEntity: Entity,
  visible: () => boolean, dispose: (failed?: boolean) => void, force: boolean,
): () => void {
  const pointer = new Float32Array([0.62, 0.42]);
  const target = new Float32Array(pointer);
  const events = new AbortController();
  const { signal } = events;
  const paused = () => hero.dataset.ambientPaused === 'true' ||
    hero.dataset.ambientSuspended === 'true' || motionPreference.matches ||
    document.documentElement.dataset.theme === 'light';
  let alive = true;
  let frame = 0;
  let elapsed = 0;
  let previousTime = 0;
  let scroll = 0;
  let slowFrames = 0;
  let frozen = false;

  const draw = () => {
    nebula.setParameter('uTime', elapsed);
    nebula.setParameter('uPointer', pointer);
    nebula.setParameter('uScroll', scroll);
    stars.setParameter('uTime', elapsed);
    starsEntity.setLocalEulerAngles(0, 0, elapsed * 0.086);
    starsEntity.setLocalPosition(0, 0, -scroll * 1.4);
    camera.setLocalPosition((pointer[0] - 0.5) * 0.5, -(pointer[1] - 0.5) * 0.35 - scroll * 0.5, 6);
    camera.lookAt(0, -scroll * 0.5, -8);
    app.render();
  };

  const resize = () => {
    const width = hero.clientWidth;
    const height = hero.clientHeight;
    if (!alive || !width || !height || !visible()) return;
    const scale = Math.min(devicePixelRatio, 1) * (width < 700 ? 0.5 : 0.65);
    app.setCanvasResolution(RESOLUTION_FIXED, Math.round(width * scale), Math.round(height * scale));
    nebula.setParameter('uAspect', width / height);
    stars.setParameter('uPx', scale);
    draw();
  };

  const update = (timestamp: number) => {
    frame = 0;
    if (!alive) return;
    if (!visible()) { dispose(); return; }
    if (paused() || frozen) return;
    const delta = (timestamp - previousTime) / 1000;
    previousTime = timestamp;
    elapsed += Math.min(0.05, delta) * motionFactor();
    slowFrames = delta > 0.04 ? slowFrames + 1 : Math.max(0, slowFrames - 1);
    if (slowFrames > 24 && !force) { frozen = true; return; }
    pointer[0] += (target[0] - pointer[0]) * 0.035;
    pointer[1] += (target[1] - pointer[1]) * 0.035;
    try {
      draw();
      frame = requestAnimationFrame(update);
    } catch {
      dispose(true);
    }
  };

  const schedule = () => {
    if (!alive) return;
    if (!visible()) { dispose(); return; }
    if (paused() || frozen) {
      cancelAnimationFrame(frame);
      frame = 0;
    } else if (!frame) {
      previousTime = performance.now();
      frame = requestAnimationFrame(update);
    }
  };

  resize();
  const sizeObserver = new ResizeObserver(resize);
  sizeObserver.observe(hero);
  const visibilityObserver = new IntersectionObserver(schedule);
  visibilityObserver.observe(hero);
  const ambient = new MutationObserver(schedule);
  ambient.observe(hero, { attributes: true, attributeFilter: ['data-ambient-paused', 'data-ambient-suspended'] });
  ambient.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  hero.addEventListener('pointermove', (event) => {
    if (paused() || event.pointerType === 'touch') return;
    const bounds = hero.getBoundingClientRect();
    target[0] = (event.clientX - bounds.left) / bounds.width;
    target[1] = 1 - (event.clientY - bounds.top) / bounds.height;
  }, { signal });
  hero.addEventListener('pointerleave', () => target.set([0.62, 0.42]), { signal });
  window.addEventListener('scroll', () => {
    if (visible() && !paused()) {
      scroll = Math.min(1, Math.max(0, -hero.getBoundingClientRect().top / hero.offsetHeight));
    }
  }, { passive: true, signal });
  window.addEventListener('pagehide', () => dispose(), { signal });
  document.addEventListener('visibilitychange', schedule, { signal });
  motionPreference.addEventListener('change', schedule);
  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault();
    dispose(true);
  }, { signal });

  schedule();
  return () => {
    alive = false;
    cancelAnimationFrame(frame);
    events.abort();
    sizeObserver.disconnect();
    visibilityObserver.disconnect();
    ambient.disconnect();
    motionPreference.removeEventListener('change', schedule);
  };
}
