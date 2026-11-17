import { Application, Asset, Color, Entity, PROJECTION_ORTHOGRAPHIC, StandardMaterial, Vec3, TONEMAP_ACES2 } from 'playcanvas';

/** Coordinates here are the authored Blender scene in glTF's Y-up basis. */
export async function openInstrument(canvas: HTMLCanvasElement, url: string) {
  const app = new Application(canvas, {
    graphicsDeviceOptions: { alpha: false, antialias: true, powerPreference: 'low-power' }
  });
  app.autoRender = false;
  app.scene.ambientLight = new Color(.20, .23, .27);
  const camera = new Entity('Vista da mesa');
  camera.addComponent('camera', {
    projection: PROJECTION_ORTHOGRAPHIC, orthoHeight: 3.1,
    clearColor: new Color(.035, .075, .086), nearClip: .1, farClip: 100
  });
  app.root.addChild(camera);
  camera.camera!.toneMapping = TONEMAP_ACES2;
  const aim = new Vec3(0, .50, .05);
  const views = {
    mesa: { eye: new Vec3(3.55, 6.65, 7.75), center: aim, height: 3.02 },
    superior: { eye: new Vec3(0, 10, .65), center: aim, height: 3.75 },
    terra: { eye: new Vec3(-1.0, 1.59, 3.25), center: new Vec3(-1.5, .84, 1.16), height: .55 }
  };
  let selected: keyof typeof views = 'mesa';
  function frame() {
    const { width, height } = canvas.getBoundingClientRect();
    if (!width || !height) return;
    const scene = views[selected];
    camera.camera!.orthoHeight = scene.height * Math.max(1, 1.35 * height / width);
    app.graphicsDevice.maxPixelRatio = Math.min(window.devicePixelRatio || 1, 2.5, Math.sqrt(1300000 / (width * height)));
    app.graphicsDevice.resizeCanvas(Math.round(width), Math.round(height));
    app.renderNextFrame = true;
  }
  function view(preset: keyof typeof views) {
    selected = preset;
    const scene = views[preset];
    camera.setPosition(scene.eye);
    camera.lookAt(scene.center);
    frame();
  }
  view('mesa');
  for (const [position, color, strength, key] of [
    [new Vec3(-3, 7, 3), new Color(1, .88, .72), 1.40, true],
    [new Vec3(1, 4, -5), new Color(.52, .79, 1), .72, false],
    [new Vec3(5, 2, 1), new Color(.96, .87, .76), .34, false]
  ] as const) {
    const lamp = new Entity('Luz de estúdio');
    lamp.addComponent('light', {
      type: 'directional', color, intensity: strength, castShadows: key,
      shadowDistance: 16, shadowResolution: 1024, shadowIntensity: .72,
      shadowBias: .03, normalOffsetBias: .025
    });
    lamp.setPosition(position);
    lamp.lookAt(aim);
    lamp.rotateLocal(90, 0, 0);
    app.root.addChild(lamp);
  }
  const tableMaterial = new StandardMaterial();
  tableMaterial.diffuse = new Color(.043, .050, .063);
  tableMaterial.specular = new Color(.14, .16, .17);
  tableMaterial.gloss = .28;
  tableMaterial.update();
  const table = new Entity('Mesa de exposição');
  table.addComponent('render', { type: 'plane', material: tableMaterial, castShadows: false });
  table.setLocalScale(48, 1, 48);
  table.setPosition(0, -.19, 0);
  app.root.addChild(table);
  const lines = [-1.5, 1.5].map((x, index) => {
    const mat = new StandardMaterial();
    mat.diffuse = index ? new Color(.27, .77, .94) : new Color(1, .50, .22);
    mat.emissive = mat.diffuse.clone().mulScalar(.6);
    mat.update();
    const line = new Entity(index ? 'Visada B' : 'Visada A');
    line.addComponent('render', { type: 'box', material: mat });
    app.root.addChild(line);
    return { start: new Vec3(x, .87, 1.16), line, mat };
  });
  const observer = new ResizeObserver(frame);
  observer.observe(canvas);
  const dispose = () => {
    observer.disconnect();
    tableMaterial.destroy();
    for (const { mat } of lines) mat.destroy();
    app.destroy();
  };
  try {
    // The reflection field is prefiltered offline. Only the interactive view
    // requests it; a missing studio map still leaves the direct studio lights.
    const reflection = new Asset('Softboxes da bancada', 'texture',
      { url: new URL('studio.png', new URL(url, document.baseURI)).href },
      { type: 'rgbm', flipY: false, mipmaps: false, srgb: false });
    const lightingReady = new Promise<void>(resolve => {
      reflection.once('load', () => {
        if (app.scene) app.scene.envAtlas = reflection.resource ?? null;
        resolve();
      });
      reflection.once('error', () => resolve());
    });
    app.assets.add(reflection);
    app.assets.load(reflection);
    const modelReady = new Promise<Entity>((resolve, reject) => {
      app.assets.loadFromUrl(url, 'container', (error, asset) => {
        if (error || !asset?.resource) reject(error || new Error('Modelo indisponível'));
        else resolve(asset.resource.instantiateRenderEntity());
      });
    });
    const [model] = await Promise.all([modelReady, lightingReady]);
    app.root.addChild(model);
    const target = model.findByName('Target');
    if (!target) throw new Error('Alvo ausente no modelo');
    function setDistance(pc: number) {
      const end = new Vec3(0, 1.18, -(.30 + .32 * pc));
      target!.setPosition(end);
      for (const { start, line } of lines) {
        line.setPosition(start.clone().lerp(start, end, .5));
        line.lookAt(end);
        line.setLocalScale(.018, .018, start.distance(end));
      }
      app.renderNextFrame = true;
    }
    frame();
    app.start();
    return { setDistance, view, dispose };
  } catch (error) {
    dispose();
    throw error;
  }
}
