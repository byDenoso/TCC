import {
  AppBase, AppOptions, Asset, BLEND_NORMAL, CULLFACE_NONE, CameraComponentSystem,
  Color, ContainerHandler, DEVICETYPE_WEBGL2, Entity, LAYERID_WORLD,
  PROJECTION_ORTHOGRAPHIC, RESOLUTION_FIXED, RenderComponentSystem, SEMANTIC_NORMAL,
  SEMANTIC_POSITION, SEMANTIC_TEXCOORD0, SORTMODE_MANUAL, ShaderMaterial,
  StandardMaterial, TextureHandler, Vec3, WebglGraphicsDevice, createGraphicsDevice,
  type MeshInstance, type Texture
} from 'playcanvas';
import settings from '../../../public/models/saturn/scene.json';
import { claimContext } from './gpu-lease';

export interface SaturnView {
  setAngle(degrees: number): void;
  dispose(): void;
}

type ReleaseReason = 'disposed' | 'revoked' | 'failed';

interface ViewOptions {
  angle(): number;
  signal: AbortSignal;
  valid(): boolean;
  released(reason: ReleaseReason): void;
}

const vertex = `
  attribute vec3 aPosition;
  attribute vec3 aNormal;
  attribute vec2 aUv;
  uniform mat4 matrix_model;
  uniform mat3 matrix_normal;
  uniform mat4 matrix_viewProjection;
  varying vec3 position;
  varying vec3 normal;
  varying vec2 uv;
  void main(void) {
    vec4 world = matrix_model * vec4(aPosition, 1.0);
    position = world.xyz;
    normal = matrix_normal * aNormal;
    uv = aUv;
    gl_Position = matrix_viewProjection * world;
  }
`;

const fragment = `
  varying vec3 position;
  varying vec3 normal;
  varying vec2 uv;
  uniform vec3 sunDirection;
  uniform vec3 viewDirection;
  uniform vec2 ringRadii;
  uniform float polarRadius;
  uniform sampler2D surfaceMap;
  uniform sampler2D ringProfile;

  vec3 toDisplay(vec3 linear) {
    return mix(1.055 * pow(max(linear, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055, 12.92 * linear,
      lessThanEqual(linear, vec3(0.0031308)));
  }

  float ringShadow() {
    // Project the point along the fixed solar ray onto the flat ring plane.
    float distanceToPlane = -position.y / sunDirection.y;
    if (distanceToPlane <= 0.0) return 1.0;
    float radius = length((position + sunDirection * distanceToPlane).xz);
    float radialUV = (radius - ringRadii.x) / (ringRadii.y - ringRadii.x);
    if (radialUV <= 0.0 || radialUV >= 1.0) return 1.0;
    return 1.0 - texture2D(ringProfile, vec2(radialUV, 0.5)).a * 0.90;
  }

  float planetShadow() {
    // Rescale the oblate planet to a unit sphere to find closest approach.
    vec3 p = vec3(position.x, position.y / polarRadius, position.z);
    vec3 d = normalize(vec3(sunDirection.x, sunDirection.y / polarRadius, sunDirection.z));
    float t = -dot(p, d);
    if (t <= 0.0) return 1.0;
    return mix(0.11, 1.0, smoothstep(0.985, 1.015, length(p + d * t)));
  }

  void main(void) {
    vec3 n = normalize(normal);
    float sun = dot(n, sunDirection);
    float facing = max(dot(n, viewDirection), 0.0);
    #if defined(SATURN_RINGS)
      vec4 profile = texture2D(ringProfile, uv);
      float lit = 0.47 * planetShadow();
      gl_FragColor = vec4(toDisplay(profile.rgb * lit), profile.a);
    #elif defined(SATURN_LIMB)
      float alpha = 0.20 * pow(1.0 - facing, 3.0) * mix(0.16, 1.0, smoothstep(-0.35, 0.7, sun));
      gl_FragColor = vec4(toDisplay(vec3(0.66, 0.38, 0.22)), alpha);
    #else
      vec3 albedo = texture2D(surfaceMap, uv).rgb;
      vec3 ambient = vec3(0.044, 0.048, 0.058);
      vec3 light = max(sun, 0.0) * ringShadow() * vec3(1.12, 1.08, 1.00);
      float limbDarkening = mix(0.87, 1.0, sqrt(facing));
      gl_FragColor = vec4(toDisplay(albedo * (ambient + light) * limbDarkening), 1.0);
    #endif
  }
`;

function material(role: string, sun: Vec3, ringProfile: Texture, order: number, mesh: MeshInstance, surfaceMap?: Texture): ShaderMaterial {
  const shader = new ShaderMaterial({
    uniqueName: `saturn-${role}`,
    attributes: { aPosition: SEMANTIC_POSITION, aNormal: SEMANTIC_NORMAL, aUv: SEMANTIC_TEXCOORD0 },
    vertexGLSL: vertex,
    fragmentGLSL: `#define ${role}\n${fragment}`
  });
  shader.setParameter('sunDirection', [sun.x, sun.y, sun.z]);
  shader.setParameter('ringRadii', [settings.geometry.ringInnerRadius, settings.geometry.ringOuterRadius]);
  shader.setParameter('polarRadius', settings.geometry.polarRadius);
  shader.setParameter('ringProfile', ringProfile);
  if (surfaceMap) shader.setParameter('surfaceMap', surfaceMap);
  if (role !== 'SATURN_GLOBE') {
    shader.blendType = BLEND_NORMAL;
    shader.depthWrite = false;
  }
  if (role === 'SATURN_RINGS') shader.cull = CULLFACE_NONE;
  shader.update();
  mesh.material = shader;
  mesh.drawOrder = order;
  return shader;
}

function modelMesh(root: Entity, name: string): MeshInstance {
  const node = root.findByName(name);
  const mesh = node instanceof Entity ? node.render?.meshInstances[0] : undefined;
  if (!mesh) throw new Error(`Saturn: missing GLB node ${name}`);
  return mesh;
}

function texture(mesh: MeshInstance): Texture {
  const map = mesh.material instanceof StandardMaterial ? mesh.material.diffuseMap : null;
  if (!map) throw new Error('Saturn: missing GLB base color texture');
  return map;
}

function loadModel(app: AppBase, url: string, contents: ArrayBuffer, signal: AbortSignal): Promise<Entity> {
  return new Promise((resolve, reject) => {
    const asset = new Asset('Saturno', 'container', { url, filename: settings.model, contents });
    const stop = () => {
      clearTimeout(timeout);
      signal.removeEventListener('abort', abort);
      asset.off('error', fail);
      asset.off('load', ready);
    };
    const fail = (error: unknown) => { stop(); reject(new Error('Saturn GLB could not be read', { cause: error })); };
    const abort = () => fail(signal.reason);
    const ready = () => {
      stop();
      const root = asset.resource?.instantiateRenderEntity();
      if (root) resolve(root);
      else reject(new Error('Empty Saturn GLB'));
    };
    const timeout = window.setTimeout(() => fail('timed out'), 8000);
    if (signal.aborted) { abort(); return; }
    signal.addEventListener('abort', abort, { once: true });
    asset.once('error', fail);
    asset.once('load', ready);
    app.assets.add(asset);
    app.assets.load(asset);
  });
}

export async function createSaturnView(stage: HTMLElement, modelUrl: string, bytes: ArrayBuffer, options: ViewOptions): Promise<SaturnView | null> {
  const canvas = document.createElement('canvas');
  canvas.id = 'saturn-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  stage.append(canvas);

  let app: AppBase | undefined;
  let device: WebglGraphicsDevice | undefined;
  let resize: ResizeObserver | undefined;
  let frame = 0;
  let disposed = false;
  let release: (() => void) | undefined;
  const shaders: ShaderMaterial[] = [];

  function dispose(reason: ReleaseReason) {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(frame);
    resize?.disconnect();
    canvas.removeEventListener('webglcontextlost', lost);
    delete stage.dataset.renderer;
    const loseContext = device?.gl.getExtension('WEBGL_lose_context');
    try {
      for (const shader of shaders) shader.destroy();
      if (app) app.destroy();
      else device?.destroy();
      loseContext?.loseContext();
    } finally {
      canvas.remove();
      release?.();
      options.released(reason);
    }
  }

  const lost = (event: Event) => {
    event.preventDefault();
    dispose('failed');
  };

  try {
    const graphics = await createGraphicsDevice(canvas, { deviceTypes: [DEVICETYPE_WEBGL2], alpha: false, antialias: true, powerPreference: 'low-power' });
    if (!(graphics instanceof WebglGraphicsDevice)) { graphics.destroy(); throw new Error('Saturn requires WebGL2'); }
    device = graphics;
    if (!options.valid()) { dispose('disposed'); return null; }
    canvas.addEventListener('webglcontextlost', lost);
    app = new AppBase(canvas);
    app.autoRender = false;
    const configuration = new AppOptions();
    configuration.graphicsDevice = device;
    configuration.componentSystems = [RenderComponentSystem, CameraComponentSystem];
    configuration.resourceHandlers = [TextureHandler, ContainerHandler];
    configuration.devtools = false;
    app.init(configuration);
    const model = await loadModel(app, modelUrl, bytes, options.signal);
    if (disposed || !options.valid()) { model.destroy(); dispose('disposed'); return null; }
    app.root.addChild(model);
    const globe = modelMesh(model, settings.globeNode);
    const rings = modelMesh(model, settings.ringsNode);
    const limb = modelMesh(model, settings.atmosphereNode);
    const ringProfile = texture(rings);
    const sun = new Vec3(...settings.sunDirection as [number, number, number]).normalize();
    shaders.push(material('SATURN_GLOBE', sun, ringProfile, 0, globe, texture(globe)));
    shaders.push(material('SATURN_LIMB', sun, ringProfile, 1, limb));
    shaders.push(material('SATURN_RINGS', sun, ringProfile, 2, rings));
    app.scene.layers.getLayerById(LAYERID_WORLD)!.transparentSortMode = SORTMODE_MANUAL;

    const camera = new Entity('Saturn camera', app);
    camera.addComponent('camera', {
      projection: PROJECTION_ORTHOGRAPHIC,
      clearColor: new Color().fromString(settings.background),
      nearClip: 0.1, farClip: 24
    });
    app.root.addChild(camera);
    let degrees = options.angle();

    function draw() {
      if (disposed || !app || !device) return;
      const width = stage.clientWidth;
      const height = stage.clientHeight;
      if (!width || !height) return;
      const pixelRatio = Math.min(window.devicePixelRatio || 1, width >= 650 ? 2 : 1.5, 1440 / width);
      app.setCanvasResolution(RESOLUTION_FIXED, Math.floor(width * pixelRatio), Math.floor(height * pixelRatio));
      camera.camera!.orthoHeight = settings.camera.frameWidth * height / width / 2;
      const radians = degrees * Math.PI / 180;
      const direction = [0, Math.sin(radians), Math.cos(radians)];
      camera.setPosition(0, direction[1] * settings.camera.distance, direction[2] * settings.camera.distance);
      camera.setEulerAngles(-degrees, 0, 0);
      for (const shader of shaders) shader.setParameter('viewDirection', direction);
      app.render();
      if (device.gl.isContextLost()) throw new Error('Saturn WebGL context lost');
      stage.dispatchEvent(new CustomEvent('saturn:frame', { detail: { angle: degrees, time: performance.now() } }));
    }

    function requestFrame() {
      if (frame || disposed) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        try { draw(); } catch { dispose('failed'); }
      });
    }

    draw();
    if (shaders.some(shader => [...shader.variants.values()].some(variant => variant.failed))) {
      throw new Error('Saturn shaders could not be linked');
    }
    stage.dataset.renderer = 'playcanvas-webgl2';
    performance.mark('saturn:first-3d-frame');
    release = claimContext(() => dispose('revoked'));
    resize = new ResizeObserver(requestFrame);
    resize.observe(stage);
    return {
      setAngle(value) {
        if (degrees === value) return;
        degrees = value;
        requestFrame();
      },
      dispose() { dispose('disposed'); }
    };
  } catch (error) {
    dispose(options.valid() ? 'failed' : 'disposed');
    throw error;
  }
}
