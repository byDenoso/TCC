import * as pc from 'playcanvas';
import * as THREE from 'three';
import { attributes, SceneMaterials } from './playcanvas-adapter-materials';
import { worldFrameClipScale } from './world-frame-webgl';

type Camera = THREE.PerspectiveCamera | THREE.OrthographicCamera;
type Drawable = THREE.Mesh | THREE.Line | THREE.Points | THREE.Sprite;
type ViewBuffer = THREE.BufferAttribute | THREE.InterleavedBufferAttribute;
type MeshBinding = {
  mesh: pc.Mesh;
  versions: Map<ViewBuffer, number>;
  vertexCount: number;
  index: THREE.BufferAttribute | null;
};
type ObjectBinding = {
  items: pc.MeshInstance[];
  node: pc.GraphNode;
  geometry: THREE.BufferGeometry;
  instancing?: pc.VertexBuffer;
  matrixVersion?: number;
  colorVersion?: number;
  instanceData?: Float32Array;
};

const spriteGeometry = new THREE.PlaneGeometry(1, 1);
const location = new THREE.Vector3();
const rotation = new THREE.Quaternion();
const scale = new THREE.Vector3();
const direction = new THREE.Vector3();
const down = new THREE.Vector3(0, -1, 0);
const forward = new THREE.Vector3(0, 0, 1);
const spriteRotation = new THREE.Quaternion();
const displayColor = new THREE.Color();
let canvasCounter = 0;

function primitive(object: Drawable) {
  if (object instanceof THREE.Points) return pc.PRIMITIVE_POINTS;
  if (object instanceof THREE.LineLoop) return pc.PRIMITIVE_LINELOOP;
  if (object instanceof THREE.LineSegments) return pc.PRIMITIVE_LINES;
  if (object instanceof THREE.Line) return pc.PRIMITIVE_LINESTRIP;
  return pc.PRIMITIVE_TRIANGLES;
}

function floatArray(attribute: ViewBuffer) {
  if (attribute instanceof THREE.BufferAttribute && attribute.array instanceof Float32Array && !attribute.normalized) return attribute.array;
  const values = new Float32Array(attribute.count * attribute.itemSize);
  for (let vertex = 0; vertex < attribute.count; vertex++) {
    for (let component = 0; component < attribute.itemSize; component++) {
      values[vertex * attribute.itemSize + component] = attribute.getComponent(vertex, component);
    }
  }
  return values;
}

function attributeVersion(attribute: ViewBuffer) {
  return attribute instanceof THREE.InterleavedBufferAttribute ? attribute.data.version : attribute.version;
}

function copyWorld(node: pc.GraphNode, world: THREE.Matrix4, billboarding?: THREE.Quaternion) {
  world.decompose(location, rotation, scale);
  const q = billboarding ?? rotation;
  node.setPosition(location.x, location.y, location.z);
  node.setRotation(q.x, q.y, q.z, q.w);
  node.setLocalScale(scale.x, scale.y, scale.z);
}

function color(source: THREE.Color, amount = 1) {
  source.getRGB(displayColor, THREE.SRGBColorSpace);
  return new pc.Color(displayColor.r * amount, displayColor.g * amount, displayColor.b * amount, 1);
}

/**
 * Draw existing exhibits in PlayCanvas. Existing authoring graphs supply
 * geometry, animation state and camera projections to the renderer.
 */
export class PlayCanvasRenderer {
  private readonly app: pc.AppBase;
  private readonly camera: pc.Entity;
  private readonly device: pc.WebglGraphicsDevice;
  private readonly materials: SceneMaterials;
  private readonly meshes = new Map<THREE.BufferGeometry, Map<string, MeshBinding>>();
  private readonly objects = new Map<Drawable, ObjectBinding>();
  private readonly lights = new Map<THREE.DirectionalLight | THREE.PointLight, pc.Entity>();
  private readonly world: pc.Layer;
  private frame = 0;
  private instanceColorFormat?: pc.VertexFormat;
  private pixelRatio = 1;
  private closed = false;
  private projection: Camera | undefined;
  private logDepthFar = 0;
  private clipScale = 1;
  toneMappingExposure = 1;
  readonly shadowMap = { enabled: false };
  readonly info = {
    memory: { geometries: 0, textures: 0 },
    render: { frame: 0, calls: 0, triangles: 0, points: 0, lines: 0 },
  };

  constructor(readonly canvas: HTMLCanvasElement) {
    if (!canvas.id) canvas.id = `cosmos-playcanvas-${++canvasCounter}`;
    this.device = new pc.WebglGraphicsDevice(canvas, { alpha: false, antialias: true, powerPreference: 'low-power' });
    this.app = new pc.AppBase(canvas);
    try {
      const options = new pc.AppOptions();
      options.graphicsDevice = this.device;
      options.componentSystems = [pc.CameraComponentSystem, pc.LightComponentSystem];
      this.app.init(options);
      this.app.autoRender = false;
      this.app.setCanvasResolution(pc.RESOLUTION_FIXED);
      this.camera = new pc.Entity('Câmera');
      this.camera.addComponent('camera', {
        gammaCorrection: pc.GAMMA_SRGB,
        toneMapping: pc.TONEMAP_ACES,
      });
      this.camera.camera!.calculateProjection = projection => {
        if (this.projection) projection.set(this.projection.projectionMatrix.elements);
      };
      this.app.root.addChild(this.camera);
      this.world = this.app.scene.layers.getLayerById(pc.LAYERID_WORLD)!;
      this.world.transparentSortMode = pc.SORTMODE_CUSTOM;
      this.world.customSortCallback = (a: pc.MeshInstance, b: pc.MeshInstance) =>
        a.drawOrder - b.drawOrder ||
        b.aabb.center.distance(this.camera.getPosition()) - a.aabb.center.distance(this.camera.getPosition());
      this.materials = new SceneMaterials(this.device);
    } catch (error) {
      const loss = this.device.gl.getExtension('WEBGL_lose_context');
      try { this.app.destroy(); } finally { loss?.loseContext(); }
      throw error;
    }
  }

  setClearColor(value: number) {
    this.camera.camera!.clearColor = color(new THREE.Color(value));
  }

  setPixelRatio(value: number) { this.pixelRatio = value; }

  setSize(width: number, height: number) {
    this.device.resizeCanvas(Math.max(1, Math.round(width * this.pixelRatio)), Math.max(1, Math.round(height * this.pixelRatio)));
  }

  getContext() { return this.device.gl; }

  setPhysicalClip(near: number, far: number) {
    this.clipScale = worldFrameClipScale(near, far);
    this.logDepthFar = far;
  }

  private mesh(geometry: THREE.BufferGeometry, type: number, group?: THREE.GeometryGroup) {
    let entries = this.meshes.get(geometry);
    if (!entries) this.meshes.set(geometry, entries = new Map());
    const key = group ? `${type}:${group.start}:${group.count}` : String(type);
    let binding = entries.get(key);
    if (!binding) {
      const mesh = new pc.Mesh(this.device);
      mesh.incRefCount();
      binding = { mesh, versions: new Map(), vertexCount: 0, index: null };
      entries.set(key, binding);
    }
    const { mesh, versions } = binding;
    const positions = geometry.getAttribute('position');
    if (!positions) throw new Error('malha sem posições');
    const streams = Object.entries(geometry.attributes);
    if (positions.count !== binding.vertexCount) {
      mesh.clear(true, false);
      versions.clear();
      binding.vertexCount = positions.count;
      binding.index = null;
    }
    let dirty = false;
    for (const [name, attribute] of streams) {
      const semantic = attributes[name as keyof typeof attributes];
      if (!semantic || versions.get(attribute) === attributeVersion(attribute)) continue;
      mesh.setVertexStream(semantic, floatArray(attribute), attribute.itemSize, attribute.count);
      versions.set(attribute, attributeVersion(attribute));
      dirty = true;
    }
    const index = geometry.index;
    if (index && (binding.index !== index || versions.get(index) !== index.version)) {
      mesh.setIndices(index.array as Uint16Array | Uint32Array);
      binding.index = index;
      versions.set(index, index.version);
      dirty = true;
    }
    if (dirty) mesh.update(type);
    const size = index ? index.count : positions.count;
    const start = Math.max(group?.start ?? 0, geometry.drawRange.start);
    const end = Math.min(size, group ? group.start + group.count : size, geometry.drawRange.start + geometry.drawRange.count);
    mesh.primitive[0].base = start;
    mesh.primitive[0].count = Math.max(0, end - start);
    return mesh;
  }

  private draw(object: Drawable, camera: Camera): ObjectBinding {
    const geometry = object instanceof THREE.Sprite ? spriteGeometry : object.geometry;
    const type = primitive(object);
    const instanceColors = object instanceof THREE.InstancedMesh ? object.instanceColor : null;
    const groups = Array.isArray(object.material) ? geometry.groups : [undefined];
    const sourceMaterials = Array.isArray(object.material) ? object.material : [object.material];
    let binding = this.objects.get(object);
    if (binding && (binding.geometry !== geometry || binding.items.length !== groups.length)) {
      this.remove(binding);
      this.objects.delete(object);
      binding = undefined;
    }
    if (!binding) {
      const node = new pc.GraphNode(object.name);
      const items = groups.map(group => {
        const material = sourceMaterials[group?.materialIndex ?? 0];
        const item = new pc.MeshInstance(this.mesh(geometry, type, group), this.material(material, !!instanceColors), node);
        item.castShadows = object.castShadow;
        item.receiveShadows = object.receiveShadow;
        item.cull = object.frustumCulled;
        return item;
      });
      binding = { items, node, geometry };
      if (object instanceof THREE.InstancedMesh) {
        const base = pc.VertexFormat.getDefaultInstancingFormat(this.device);
        if (instanceColors) {
          this.instanceColorFormat ??= new pc.VertexFormat(this.device, [
            ...base.elements.map(element => ({ semantic: element.name, components: 4, type: pc.TYPE_FLOAT32 })),
            { semantic: attributes.cosmosInstanceColor, components: 3, type: pc.TYPE_FLOAT32 },
          ]);
          binding.instanceData = new Float32Array(object.instanceMatrix.count * 19);
        }
        binding.instancing = new pc.VertexBuffer(this.device, instanceColors ? this.instanceColorFormat! : base,
          object.instanceMatrix.count, { usage: pc.BUFFER_DYNAMIC });
        for (const item of items) item.setInstancing(binding.instancing);
      }
      this.objects.set(object, binding);
      this.world.addMeshInstances(items);
    }
    const {items, node} = binding;
    if (object instanceof THREE.Sprite) {
      spriteRotation.setFromAxisAngle(forward, object.material.rotation).premultiply(camera.quaternion);
      copyWorld(node, object.matrixWorld, spriteRotation);
    } else {
      copyWorld(node, object.matrixWorld);
    }
    if (object instanceof THREE.InstancedMesh && binding.instancing &&
      (binding.matrixVersion !== object.instanceMatrix.version || binding.colorVersion !== instanceColors?.version)) {
      const matrix = object.instanceMatrix.array;
      const data = binding.instanceData;
      if (instanceColors && data) {
        for (let index = 0; index < object.instanceMatrix.count; index++) {
          const offset = index * 19;
          for (let channel = 0; channel < 16; channel++) data[offset + channel] = matrix[index * 16 + channel];
          data[offset + 16] = instanceColors.getX(index);
          data[offset + 17] = instanceColors.getY(index);
          data[offset + 18] = instanceColors.getZ(index);
        }
      }
      binding.instancing.setData(data ?? matrix);
      binding.matrixVersion = object.instanceMatrix.version;
      binding.colorVersion = instanceColors?.version;
    }
    groups.forEach((group, index) => {
      const material = sourceMaterials[group?.materialIndex ?? 0];
      const item = items[index];
      this.mesh(geometry, type, group);
      const next = this.material(material, !!instanceColors);
      if (item.material !== next) item.material = next;
      item.visible = material.visible;
      item.drawOrder = object.renderOrder;
      if (object instanceof THREE.InstancedMesh) item.instancingCount = object.count;
      if (item.visible) this.count(item);
    });
    return binding;
  }

  private material(source: THREE.Material, instanceColors: boolean) {
    return this.materials.update(source, this.frame, this.canvas.height, this.pixelRatio, instanceColors, this.logDepthFar, this.clipScale);
  }

  private count(instance: pc.MeshInstance) {
    this.info.render.calls++;
    const primitive = instance.mesh!.primitive[0];
    const count = primitive.count * Math.max(1, instance.instancingCount);
    if (primitive.type === pc.PRIMITIVE_TRIANGLES) this.info.render.triangles += count / 3;
    else if (primitive.type === pc.PRIMITIVE_POINTS) this.info.render.points += count;
    else this.info.render.lines += primitive.type === pc.PRIMITIVE_LINES ? count / 2 : Math.max(0, count - 1);
  }

  private remove(binding: ObjectBinding) {
    this.world.removeMeshInstances(binding.items);
    for (const item of binding.items) item.destroy();
    binding.instancing?.destroy();
  }

  private light(source: THREE.DirectionalLight | THREE.PointLight) {
    let entity = this.lights.get(source);
    if (!entity) {
      entity = new pc.Entity(source.name);
      entity.addComponent('light', { type: source instanceof THREE.DirectionalLight ? 'directional' : 'omni' });
      this.app.root.addChild(entity);
      this.lights.set(source, entity);
    }
    entity.enabled = true;
    const light = entity.light!;
    light.color = color(source.color);
    light.intensity = source.intensity * this.toneMappingExposure * 0.65;
    light.castShadows = this.shadowMap.enabled && source.castShadow;
    if (source instanceof THREE.DirectionalLight) {
      source.getWorldPosition(location);
      source.target.getWorldPosition(direction).sub(location).normalize();
      if (direction.lengthSq() === 0) direction.copy(down);
      rotation.setFromUnitVectors(down, direction);
      entity.setRotation(rotation.x, rotation.y, rotation.z, rotation.w);
      light.shadowResolution = source.shadow.mapSize.x;
    } else {
      source.getWorldPosition(location);
      entity.setPosition(location.x, location.y, location.z);
      light.range = source.distance || 100;
    }
  }

  render(scene: THREE.Scene, camera: Camera) {
    if (this.closed || this.getContext().isContextLost()) return;
    this.frame++;
    this.info.render = { frame: this.frame, calls: 0, triangles: 0, points: 0, lines: 0 };
    scene.updateMatrixWorld();
    camera.updateMatrixWorld();
    this.projection = camera;
    copyWorld(this.camera, camera.matrixWorld);
    const view = this.camera.camera!;
    view.projection = camera instanceof THREE.OrthographicCamera ? pc.PROJECTION_ORTHOGRAPHIC : pc.PROJECTION_PERSPECTIVE;
    view.nearClip = camera.near;
    view.farClip = camera.far;
    // Float32 frustum extraction loses the far plane when the perspective z coefficients round to the same value.
    view.frustumCulling = !this.logDepthFar;
    if (camera instanceof THREE.PerspectiveCamera) view.fov = camera.getEffectiveFOV();
    else view.orthoHeight = (camera.top - camera.bottom) / (2 * camera.zoom);

    const seen = new Set<Drawable>();
    const lights = new Set<THREE.DirectionalLight | THREE.PointLight>();
    const ambient = new pc.Color(0, 0, 0);
    scene.traverseVisible(object => {
      if (object instanceof THREE.AmbientLight) {
        const rgb = color(object.color, object.intensity * this.toneMappingExposure * 0.35);
        ambient.set(ambient.r + rgb.r, ambient.g + rgb.g, ambient.b + rgb.b);
      } else if (object instanceof THREE.DirectionalLight || object instanceof THREE.PointLight) {
        this.light(object);
        lights.add(object);
      } else if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points || object instanceof THREE.Sprite) {
        if (object.layers.test(camera.layers)) {
          this.draw(object, camera);
          seen.add(object);
        }
      }
    });
    for (const [object, binding] of this.objects) {
      if (seen.has(object)) continue;
      for (const item of binding.items) item.visible = false;
    }
    for (const [source, entity] of this.lights) {
      if (!lights.has(source)) entity.enabled = false;
    }
    this.app.scene.ambientLight.copy(ambient);
    this.app.render();
    this.info.render.calls = this.device._drawCallsPerFrame;
    this.device._drawCallsPerFrame = 0;
    this.info.memory = {
      geometries: Array.from(this.meshes.values()).reduce((total, value) => total + value.size, 0),
      textures: this.materials.textureCount,
    };
  }

  dispose() {
    if (this.closed) return;
    this.closed = true;
    const loss = this.device.gl.getExtension('WEBGL_lose_context');
    try {
      for (const binding of this.objects.values()) this.remove(binding);
      this.objects.clear();
      for (const entries of this.meshes.values()) for (const { mesh } of entries.values()) mesh.destroy();
      this.meshes.clear();
      this.materials.destroy();
      this.app.destroy();
    } finally {
      loss?.loseContext();
    }
  }
}
