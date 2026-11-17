import * as pc from 'playcanvas';
import * as THREE from 'three';

export const attributes = {
  position: pc.SEMANTIC_POSITION,
  normal: pc.SEMANTIC_NORMAL,
  uv: pc.SEMANTIC_TEXCOORD0,
  uv1: pc.SEMANTIC_TEXCOORD1,
  color: pc.SEMANTIC_COLOR,
  tangent: pc.SEMANTIC_TANGENT,
  aStart: pc.SEMANTIC_ATTR10,
  aWeight: pc.SEMANTIC_ATTR11,
  lineDistance: pc.SEMANTIC_ATTR12,
  cosmosBasisX: pc.SEMANTIC_ATTR11,
  cosmosBasisY: pc.SEMANTIC_ATTR12,
  cosmosBasisZ: pc.SEMANTIC_ATTR14,
  cosmosOffset: pc.SEMANTIC_ATTR15,
  cosmosInstanceColor: pc.SEMANTIC_ATTR10,
};

const vertexHeader = `
attribute vec3 position;
attribute vec3 normal;
attribute vec2 uv;
uniform mat4 matrix_projection;
uniform mat4 matrix_model;
uniform mat4 matrix_view;
uniform vec3 view_position;
#define modelMatrix matrix_model
#define modelViewMatrix (matrix_view * matrix_model)
#define projectionMatrix matrix_projection
#define viewMatrix matrix_view
#define normalMatrix transpose(inverse(mat3(modelViewMatrix)))
#define cameraPosition view_position
`;

const encodeSrgb = `
vec3 cosmosSrgb(vec3 c) {
  c = max(c, vec3(0.0));
  return mix(1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, 12.92 * c, lessThanEqual(c, vec3(0.0031308)));
}
`;

const logDepthVarying = 'varying float cosmosViewDistance;\n';
const clipScaleDeclaration = logDepthVarying + 'uniform float cosmosClipScale;\n';
const logDepthDeclaration = logDepthVarying + 'uniform float cosmosDepthFar;\n';
const logDepthPosition = `
  cosmosViewDistance = gl_Position.w;
  gl_Position.z = min(gl_Position.z, gl_Position.w * 0.9999999);
  gl_Position *= cosmosClipScale;
`;
const logDepthFragment = `
  if (cosmosViewDistance > cosmosDepthFar) discard;
  gl_FragDepth = log2(1.0 + cosmosViewDistance) / log2(1.0 + cosmosDepthFar);
`;

function appendToMain(shader: string, code: string) {
  return shader.replace(/\bvoid\s+main\s*\(\s*(?:void)?\s*\)/, 'void cosmosSourceMain()') +
    '\nvoid main() { cosmosSourceMain();\n' + code + '\n}';
}

const unlitVertex = `
varying vec2 vMapUv;
varying vec3 vTint;
#ifdef INSTANCING
attribute vec4 cosmosBasisX;
attribute vec4 cosmosBasisY;
attribute vec4 cosmosBasisZ;
attribute vec4 cosmosOffset;
#ifdef COSMOS_INSTANCE_COLOR
attribute vec3 cosmosInstanceColor;
#endif
#endif
void main() {
  vMapUv = uv;
  vTint = vec3(1.0);
  mat4 model = matrix_model;
  #ifdef INSTANCING
  model *= mat4(cosmosBasisX, cosmosBasisY, cosmosBasisZ, cosmosOffset);
  #ifdef COSMOS_INSTANCE_COLOR
  vTint = cosmosInstanceColor;
  #endif
  #endif
  gl_Position = projectionMatrix * matrix_view * model * vec4(position, 1.0);
}
`;

const unlitFragment = `
uniform vec4 cosmosColor;
uniform vec4 cosmosMapTransform;
uniform vec3 cosmosFlags;
uniform sampler2D cosmosMap;
uniform sampler2D cosmosAlpha;
varying vec2 vMapUv;
varying vec3 vTint;
void main() {
  vec2 coord = vMapUv * cosmosMapTransform.xy + cosmosMapTransform.zw;
  vec4 texel = texture2D(cosmosMap, coord);
  float opacity = cosmosColor.a * texel.a;
  if (cosmosFlags.x > 0.0) opacity *= texture2D(cosmosAlpha, vMapUv).g;
  if (opacity < cosmosFlags.y) discard;
  vec3 light = texel.rgb * vTint * cosmosColor.rgb;
  #ifdef COSMOS_GALAXY_EXPOSURE
  float blue = smoothstep(0.0, 0.045, light.b - light.r);
  light *= mix(vec3(1.95, 1.72, 1.45), vec3(1.28, 1.92, 2.72), blue);
  light /= 1.0 + 0.38 * light;
  #endif
  gl_FragColor = vec4(cosmosSrgb(light), opacity);
}
`;

const cloudVertex = `
varying vec3 vGlobe;
varying vec3 vNormalWorld;
void main() {
  vGlobe = position;
  vNormalWorld = normalize(transpose(inverse(mat3(matrix_model))) * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const cloudFragment = `
varying vec3 vGlobe;
varying vec3 vNormalWorld;
uniform vec4 cosmosColor;
float cloudHash(vec3 p) {
  p = fract(p * .1031);
  p += dot(p, p.yzx + 33.33);
  return fract((p.x + p.y) * p.z);
}
float cloudNoise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float low = mix(mix(cloudHash(i), cloudHash(i + vec3(1,0,0)), f.x),
    mix(cloudHash(i + vec3(0,1,0)), cloudHash(i + vec3(1,1,0)), f.x), f.y);
  float high = mix(mix(cloudHash(i + vec3(0,0,1)), cloudHash(i + vec3(1,0,1)), f.x),
    mix(cloudHash(i + vec3(0,1,1)), cloudHash(i + vec3(1,1,1)), f.x), f.y);
  return mix(low, high, f.z);
}
float cloudFbm(vec3 p) {
  return .52 * cloudNoise(p) + .27 * cloudNoise(p * 2.03) +
    .14 * cloudNoise(p * 4.11) + .07 * cloudNoise(p * 8.19);
}
void main() {
  vec3 globe = normalize(vGlobe);
  float warp = cloudFbm(globe * 3.4 + vec3(7.1, 2.4, 5.7));
  float cloud = cloudFbm(globe * 8.0 + vec3(warp * 2.2, warp, -warp * 1.7));
  cloud += .12 * (cloudNoise(globe * 25.0 + 9.0) - .5);
  cloud += .045 * (cloudNoise(globe * 52.0 + 2.3) - .5);
  float light = .17 + .83 * max(0.0, dot(normalize(vNormalWorld), normalize(vec3(-5., 4., 6.))));
  gl_FragColor = vec4(cosmosSrgb(cosmosColor.rgb * light), cosmosColor.a * smoothstep(.50, .67, cloud));
}
`;

const pointVertex = `
attribute vec3 color;
uniform vec4 cosmosPoint;
varying vec3 vPointColor;
void main() {
  vec4 p = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * p;
  gl_PointSize = cosmosPoint.x * (cosmosPoint.y > 0.0 ? cosmosPoint.y / max(-p.z, 0.01) : 1.0);
  vPointColor = color;
}
`;

const pointFragment = `
uniform vec4 cosmosColor;
uniform vec4 cosmosPoint;
uniform sampler2D cosmosMap;
varying vec3 vPointColor;
void main() {
  vec4 texel = cosmosPoint.z > 0.0 ? texture2D(cosmosMap, vec2(gl_PointCoord.x, 1.0 - gl_PointCoord.y)) : vec4(1.0);
  vec3 tint = cosmosColor.rgb * (cosmosPoint.w > 0.0 ? vPointColor : vec3(1.0));
  gl_FragColor = vec4(cosmosSrgb(tint * texel.rgb), cosmosColor.a * texel.a);
}
`;

const lineVertex = `
attribute float lineDistance;
varying float vLineDistance;
void main() {
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  vLineDistance = lineDistance;
}
`;

const lineFragment = `
uniform vec4 cosmosColor;
uniform vec3 cosmosDash;
varying float vLineDistance;
void main() {
  if (cosmosDash.x > 0.0 && mod(vLineDistance * cosmosDash.z, cosmosDash.x + cosmosDash.y) > cosmosDash.x) discard;
  gl_FragColor = vec4(cosmosSrgb(cosmosColor.rgb), cosmosColor.a);
}
`;

function blendType(source: THREE.Material) {
  if (source.blending === THREE.AdditiveBlending) return pc.BLEND_ADDITIVEALPHA;
  if (source.blending === THREE.MultiplyBlending) return pc.BLEND_MULTIPLICATIVE;
  if (source.blending === THREE.SubtractiveBlending) return pc.BLEND_SUBTRACTIVE;
  return source.transparent && source.blending !== THREE.NoBlending
    ? source.premultipliedAlpha ? pc.BLEND_PREMULTIPLIED : pc.BLEND_NORMAL
    : pc.BLEND_NONE;
}

function copyColor(target: pc.Color, source: THREE.Color) {
  const color = source.getRGB(new THREE.Color(), THREE.SRGBColorSpace);
  target.set(color.r, color.g, color.b);
}

function sourceAddress(wrap: THREE.Wrapping) {
  if (wrap === THREE.RepeatWrapping) return pc.ADDRESS_REPEAT;
  if (wrap === THREE.MirroredRepeatWrapping) return pc.ADDRESS_MIRRORED_REPEAT;
  return pc.ADDRESS_CLAMP_TO_EDGE;
}

const minFilters: Partial<Record<THREE.MinificationTextureFilter, number>> = {
  [THREE.NearestFilter]: pc.FILTER_NEAREST,
  [THREE.LinearFilter]: pc.FILTER_LINEAR,
  [THREE.NearestMipmapNearestFilter]: pc.FILTER_NEAREST_MIPMAP_NEAREST,
  [THREE.NearestMipmapLinearFilter]: pc.FILTER_NEAREST_MIPMAP_LINEAR,
  [THREE.LinearMipmapNearestFilter]: pc.FILTER_LINEAR_MIPMAP_NEAREST,
  [THREE.LinearMipmapLinearFilter]: pc.FILTER_LINEAR_MIPMAP_LINEAR,
};

type SourceImage = { width: number; height: number; depth?: number; data?: Uint8Array };
type TextureBinding = { texture: pc.Texture; version: number; image: unknown; dispose: () => void };
type MaterialBinding = { material: pc.Material; map: pc.Texture | null; version: number; frame: number };

export class SceneMaterials {
  private readonly textures = new Map<THREE.Texture, TextureBinding>();
  private readonly materials = new Map<THREE.Material, MaterialBinding>();
  private readonly instancedMaterials = new Map<THREE.Material, MaterialBinding>();
  private readonly noMap: pc.Texture;

  constructor(private readonly device: pc.GraphicsDevice) {
    this.noMap = new pc.Texture(device, {
      width: 1, height: 1, mipmaps: false, levels: [new Uint8Array([255, 255, 255, 255])],
    });
  }

  private texture(source: THREE.Texture | null | undefined): pc.Texture | null {
    if (!source || !source.image) return null;
    const existing = this.textures.get(source);
    if (existing?.version === source.version && existing.image === source.image) return existing.texture;
    existing?.dispose();

    const image = source.image as SourceImage | (HTMLImageElement | HTMLCanvasElement)[];
    const first = Array.isArray(image) ? image[0] : image;
    if (!first?.width || !first.height) return null;
    const raw = 'data' in first ? first.data : undefined;
    const format = source.format === THREE.RedFormat ? pc.PIXELFORMAT_R8
      : source.colorSpace === THREE.SRGBColorSpace ? pc.PIXELFORMAT_SRGBA8 : pc.PIXELFORMAT_RGBA8;
    const volume = source instanceof THREE.Data3DTexture;
    const texture = new pc.Texture(this.device, {
      name: source.name,
      width: first.width,
      height: first.height,
      depth: 'depth' in first ? first.depth : undefined,
      volume,
      cubemap: Array.isArray(image),
      format,
      mipmaps: source.generateMipmaps,
      flipY: source.flipY,
      minFilter: minFilters[source.minFilter],
      magFilter: source.magFilter === THREE.NearestFilter ? pc.FILTER_NEAREST : pc.FILTER_LINEAR,
      addressU: sourceAddress(source.wrapS),
      addressV: sourceAddress(source.wrapT),
      anisotropy: source.anisotropy,
      levels: raw ? [raw] : undefined,
    });
    if (!raw) texture.setSource(image as HTMLImageElement);
    const dispose = () => {
      this.textures.delete(source);
      source.removeEventListener('dispose', dispose);
      texture.destroy();
    };
    source.addEventListener('dispose', dispose);
    this.textures.set(source, { texture, version: source.version, image, dispose });
    return texture;
  }

  private uniform(value: unknown): number | Float32Array | pc.Texture | number[] | undefined {
    if (typeof value === 'number') return value;
    if (typeof value === 'boolean') return Number(value);
    if (value instanceof THREE.Texture) return this.texture(value) ?? this.noMap;
    if (value instanceof Float32Array) return value;
    if (value instanceof THREE.Color) return [value.r, value.g, value.b];
    if (value instanceof THREE.Vector2) return [value.x, value.y];
    if (value instanceof THREE.Vector3) return [value.x, value.y, value.z];
    if (value instanceof THREE.Vector4) return [value.x, value.y, value.z, value.w];
    if (value instanceof THREE.Matrix3 || value instanceof THREE.Matrix4) return Array.from(value.elements);
    if (Array.isArray(value) && value.every(item => typeof item === 'number')) return value;
    return undefined;
  }

  private shader(name: string, vertex: string, fragment: string, logarithmic: boolean) {
    const vertexGLSL = vertexHeader + (logarithmic ? clipScaleDeclaration + appendToMain(vertex, logDepthPosition) : vertex);
    if (logarithmic) fragment = logDepthDeclaration + appendToMain(fragment, logDepthFragment);
    return new pc.ShaderMaterial({
      uniqueName: logarithmic ? `${name}-log-depth` : name,
      vertexGLSL,
      fragmentGLSL: encodeSrgb + fragment
        .replace(/#include\s+<colorspace_fragment>/g, 'gl_FragColor.rgb = cosmosSrgb(gl_FragColor.rgb);')
        .replace(/\bout\s+vec4\s+outColor\s*;/g, '')
        .replace(/\boutColor\b/g, 'gl_FragColor'),
      attributes: Object.fromEntries(Object.entries(attributes).filter(([attribute]) =>
        new RegExp(`\\battribute\\s+\\w+\\s+${attribute}\\s*;`).test(vertexGLSL))),
    });
  }

  update(source: THREE.Material, frame: number, viewportHeight: number, pixelRatio: number, instanceColors: boolean, logDepthFar: number, clipScale: number): pc.Material {
    const bindings = instanceColors ? this.instancedMaterials : this.materials;
    let binding = bindings.get(source);
    const custom = source instanceof THREE.ShaderMaterial;
    const point = source instanceof THREE.PointsMaterial;
    const line = source instanceof THREE.LineBasicMaterial;
    const unlit = source instanceof THREE.MeshBasicMaterial || source instanceof THREE.SpriteMaterial;
    const clouds = source instanceof THREE.MeshStandardMaterial && source.userData.cosmosClouds;
    if (!binding) {
      let material: pc.Material;
      if (custom) material = this.shader(source.name || 'cosmos-scene', source.vertexShader, source.fragmentShader, !!logDepthFar);
      else if (point) material = this.shader('cosmos-points', pointVertex, pointFragment, !!logDepthFar);
      else if (line) material = this.shader('cosmos-lines', lineVertex, lineFragment, !!logDepthFar);
      else if (clouds) material = this.shader('cosmos-earth-clouds', cloudVertex, cloudFragment, !!logDepthFar);
      else if (unlit) {
        const vertex = (instanceColors ? '#define COSMOS_INSTANCE_COLOR\n' : '') + unlitVertex;
        const exposure = source.customProgramCacheKey() === 'story-galaxy-exposure' ? '#define COSMOS_GALAXY_EXPOSURE\n' : '';
        material = this.shader('cosmos-unlit', vertex, exposure + unlitFragment, !!logDepthFar);
      } else {
        material = this.standard(source, instanceColors, !!logDepthFar);
      }
      binding = { material, map: null, version: -1, frame: -1 };
      bindings.set(source, binding);
    }
    const { material } = binding;
    if (binding.frame === frame) return material;
    binding.frame = frame;
    material.name = source.name || source.type;
    material.blendType = blendType(source);
    material.cull = source.side === THREE.DoubleSide ? pc.CULLFACE_NONE : source.side === THREE.BackSide ? pc.CULLFACE_FRONT : pc.CULLFACE_BACK;
    material.depthWrite = source.depthWrite;
    material.depthTest = source.depthTest;
    material.alphaTest = source.alphaTest;
    if (logDepthFar) {
      material.setParameter('cosmosDepthFar', logDepthFar);
      material.setParameter('cosmosClipScale', clipScale);
    }

    if (custom) {
      for (const [key, { value }] of Object.entries(source.uniforms)) {
        const parameter = this.uniform(value);
        if (parameter !== undefined) material.setParameter(key, parameter);
      }
    } else if (point) {
      material.setParameter('cosmosMap', this.texture(source.map) ?? this.noMap);
      material.setParameter('cosmosColor', [source.color.r, source.color.g, source.color.b, source.opacity]);
      material.setParameter('cosmosPoint', [source.size * pixelRatio,
        source.sizeAttenuation ? viewportHeight * 0.5 / pixelRatio : 0, Number(!!source.map), Number(source.vertexColors)]);
    } else if (line) {
      material.setParameter('cosmosColor', [source.color.r, source.color.g, source.color.b, source.opacity]);
      const dash = source instanceof THREE.LineDashedMaterial ? [source.dashSize, source.gapSize, source.scale] : [0, 0, 1];
      material.setParameter('cosmosDash', dash);
    } else if (clouds && source instanceof THREE.MeshStandardMaterial) {
      material.setParameter('cosmosColor', [source.color.r, source.color.g, source.color.b, source.opacity]);
    } else if (unlit) {
      material.setParameter('cosmosMap', this.texture(source.map) ?? this.noMap);
      material.setParameter('cosmosAlpha', this.texture(source.alphaMap) ?? this.noMap);
      material.setParameter('cosmosColor', [source.color.r, source.color.g, source.color.b, source.opacity]);
      material.setParameter('cosmosMapTransform', [source.map?.repeat.x ?? 1, source.map?.repeat.y ?? 1,
        source.map?.offset.x ?? 0, source.map?.offset.y ?? 0]);
      material.setParameter('cosmosFlags', [Number(!!source.alphaMap), source.alphaTest, 0]);
    } else {
      this.updateStandard(material as pc.StandardMaterial, source, binding);
    }
    return material;
  }

  private standard(source: THREE.Material, instanceColors: boolean, logarithmic: boolean) {
    const material = new pc.StandardMaterial();
    if (logarithmic) {
      const chunks = material.getShaderChunks(pc.SHADERLANGUAGE_GLSL);
      chunks.set('litUserDeclarationVS', clipScaleDeclaration);
      chunks.set('litUserMainEndVS', logDepthPosition);
      chunks.set('litUserDeclarationPS', logDepthDeclaration);
      chunks.set('litUserMainEndPS', logDepthFragment);
    }
    if (!source.userData.cosmosOcean && !instanceColors) return material;
    const chunks = material.getShaderChunks(pc.SHADERLANGUAGE_GLSL);
    const defaults = pc.ShaderChunks.get(this.device, pc.SHADERLANGUAGE_GLSL);
    let diffuse = defaults.get('diffusePS') ?? '';
    if (source.userData.cosmosOcean) {
      diffuse = diffuse.replace(/}\s*$/, `
        float water = smoothstep(.002, .007, dAlbedo.b - dAlbedo.r) *
          (1.0 - smoothstep(.018, .06, max(dAlbedo.r, max(dAlbedo.g, dAlbedo.b))));
        dAlbedo = mix(dAlbedo, vec3(.012,.065,.16), water * .9);
      }`);
    }
    if (instanceColors) {
      material.setAttribute('cosmosInstanceColor', attributes.cosmosInstanceColor);
      const transform = (defaults.get('transformInstancingVS') ?? '').replace('mat4 getModelMatrix() {',
        'mat4 getModelMatrix() { vCosmosTint = cosmosInstanceColor;');
      chunks.set('transformInstancingVS',
        'attribute vec3 cosmosInstanceColor; varying vec3 vCosmosTint;\n' + transform);
      diffuse = 'varying vec3 vCosmosTint;\n' + diffuse.replace(/}\s*$/, 'dAlbedo *= vCosmosTint; }');
    }
    chunks.set('diffusePS', diffuse);
    return material;
  }

  private updateStandard(material: pc.StandardMaterial, original: THREE.Material, binding: MaterialBinding) {
    const source = original as THREE.MeshStandardMaterial;
    const lit = source instanceof THREE.MeshStandardMaterial;
    const map = this.texture(source.map);
    const opacity = this.texture(source.alphaMap) ?? (original.transparent || original.alphaTest > 0 ? map : null);
    copyColor(material.diffuse, source.color ?? new THREE.Color(1, 1, 1));
    material.opacity = source.opacity;
    if (lit) {
      copyColor(material.emissive, source.emissive);
      material.emissiveIntensity = source.emissiveIntensity;
      material.gloss = source.roughness;
      material.metalness = source.metalness;
      material.bumpiness = source.normalScale?.x ?? 1;
    }
    const normal = this.texture(source.normalMap), emissive = this.texture(source.emissiveMap);
    const metalness = this.texture(source.metalnessMap), roughness = this.texture(source.roughnessMap), ao = this.texture(source.aoMap);
    if (binding.version !== source.version || binding.map !== map || material.opacityMap !== opacity ||
      material.normalMap !== normal || material.emissiveMap !== emissive || material.metalnessMap !== metalness ||
      material.glossMap !== roughness || material.aoMap !== ao) {
      material.useLighting = lit;
      material.useSkybox = false;
      material.useTonemap = original.toneMapped;
      material.useMetalness = lit;
      material.diffuseVertexColor = source.vertexColors;
      material.diffuseMap = map;
      if (source.map) {
        material.diffuseMapTiling.set(source.map.repeat.x, source.map.repeat.y);
        material.diffuseMapOffset.set(source.map.offset.x, source.map.offset.y);
      }
      material.opacityMap = opacity;
      material.opacityMapChannel = source.alphaMap ? 'g' : 'a';
      material.normalMap = normal;
      material.emissiveMap = emissive;
      material.metalnessMap = metalness;
      material.metalnessMapChannel = 'b';
      material.glossInvert = true;
      material.glossMap = roughness;
      material.glossMapChannel = 'g';
      material.aoMap = ao;
      binding.map = map;
      binding.version = source.version;
    }
    // Source scenes animate opacity and colors without changing the texture layout.
    material.update();
  }

  destroy() {
    for (const bindings of [this.materials, this.instancedMaterials]) {
      for (const { material } of bindings.values()) material.destroy();
      bindings.clear();
    }
    for (const { dispose } of this.textures.values()) dispose();
    this.noMap.destroy();
  }

  get textureCount() { return this.textures.size; }
}
