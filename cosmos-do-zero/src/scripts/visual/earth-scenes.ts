import * as THREE from 'three';
import { atmosphereLayer } from '../../lib/teaching-numerics';
import type { Exhibit } from './runtime';
import { createWorldFactory } from './assets';
import { styleEarth } from './world-view';

const earthRadiusKm = 6371;
const light = {
  ambient: .30, key: 3.4, fill: .07, exposure: 1.18, neutral: true,
  keyPosition: [-5, 4, 6] as [number, number, number]
};
const textureSize = (mode: 'auto' | 'low', width: number) => mode === 'low' ? 512 : width < 600 ? 1024 : 2048;

function rockTexture(): THREE.Texture {
  const size = 128;
  const samples = new Float32Array(size * size);
  let seed = 917;
  for (let i = 0; i < samples.length; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    samples[i] = seed / 4294967296;
  }
  const sample = (x: number, y: number) => samples[(y % size) * size + (x % size)];
  function noise(x: number, y: number) {
    const ix = Math.floor(x), iy = Math.floor(y);
    const u = THREE.MathUtils.smoothstep(x - ix, 0, 1);
    const v = THREE.MathUtils.smoothstep(y - iy, 0, 1);
    return THREE.MathUtils.lerp(
      THREE.MathUtils.lerp(sample(ix, iy), sample(ix + 1, iy), u),
      THREE.MathUtils.lerp(sample(ix, iy + 1), sample(ix + 1, iy + 1), u),
      v
    );
  }
  const pixels = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const veins = noise(x / 17, y / 17);
    const aggregate = noise(x / 5 + 2 * veins, y / 5);
    const grain = sample(x, y);
    const shade = Math.round(126 + 46 * veins + 51 * aggregate + 31 * grain);
    pixels.set([shade, shade, shade, 255], (y * size + x) * 4);
  }
  const map = new THREE.DataTexture(pixels, size, size, THREE.RGBAFormat);
  map.colorSpace = THREE.SRGBColorSpace;
  map.generateMipmaps = true;
  map.minFilter = THREE.LinearMipmapLinearFilter;
  map.magFilter = THREE.LinearFilter;
  map.needsUpdate = true;
  return map;
}

export function earthLayersScene(): Exhibit {
  const make = createWorldFactory(), group = new THREE.Group(), earth = make('terra');
  // Retain the original MODIS UVs on the remaining three quarters of the globe.
  earth.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    const original = object.geometry;
    const geometry = original.clone(), position = geometry.getAttribute('position'), index = geometry.index;
    const kept: number[] = [];
    for (let i = 0; i < (index?.count ?? position.count); i += 3) {
      const ids = [0, 1, 2].map(k => index ? index.getX(i + k) : i + k);
      const x = ids.reduce((sum, id) => sum + position.getX(id), 0);
      const z = ids.reduce((sum, id) => sum + position.getZ(id), 0);
      if (!(x < 0 && z > 0)) kept.push(...ids);
    }
    geometry.setIndex(kept);
    object.geometry = geometry;
    original.dispose();
  });
  styleEarth(earth, true);
  group.add(earth);

  const map = rockTexture();
  const material = (color: number, roughness: number, metalness = 0) =>
    new THREE.MeshStandardMaterial({
      color, map, bumpMap: map, bumpScale: .018 * roughness, roughness, metalness,
      side: THREE.DoubleSide
    });
  const crust = material(0x837669, .96);
  const mantle = material(0xb58055, .86);
  const outerCore = material(0xe4a167, .48, .18);
  const innerCore = material(0xe6c798, .38, .30);
  const mixedRock = material(0xa66c51, .88);
  const shell = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64, Math.PI / 2, Math.PI * 1.5), crust);
  group.add(shell);

  const faces = new THREE.Group();
  group.add(faces);
  // Radial reference for the model. The selected crust thickness is illustrative.
  const radii = [0, 1221.5 / earthRadiusKm, 3480 / earthRadiusKm, 1 - 35 / earthRadiusKm, 1];
  const materials = [innerCore, outerCore, mantle, crust];
  const cutAngles = [Math.PI, Math.PI * 1.5];
  materials.forEach((surface, i) => {
    const geometry = new THREE.RingGeometry(radii[i], radii[i + 1], 96, 4, -Math.PI / 2, Math.PI);
    for (const angle of cutAngles) {
      const face = new THREE.Mesh(geometry, surface);
      face.rotation.y = angle;
      faces.add(face);
    }
  });
  const mixed = new THREE.Group();
  const mixedFace = new THREE.CircleGeometry(1, 96, -Math.PI / 2, Math.PI);
  for (const angle of cutAngles) {
    const face = new THREE.Mesh(mixedFace, mixedRock);
    face.rotation.y = angle;
    mixed.add(face);
  }
  group.add(mixed);

  const iron = new THREE.Group();
  group.add(iron);
  const ironGeometry = new THREE.IcosahedronGeometry(1, 2);
  const ironMaterial = material(0x553c32, .42, .52);
  const drops = Array.from({ length: 36 }, (_, i) => {
    const drop = new THREE.Mesh(ironGeometry, ironMaterial);
    const r = .72 * Math.sqrt((i + .5) / 36), angle = i * 2.399;
    const radius = .012 + .021 * ((i * 13 % 31) / 30);
    drop.scale.set(radius, radius * 1.35, radius * .9);
    drop.rotation.z = i * .9;
    iron.add(drop);
    return { drop, start: new THREE.Vector3(-r * Math.abs(Math.sin(angle)), r * Math.cos(angle), r * Math.abs(Math.cos(angle))) };
  });
  const labels = [{ text: '', position: new THREE.Vector3(0, -1.06, 0) }];
  return {
    group, lighting: { ...light, keyPosition: [-4, 4, 6] }, labels,
    camera: [-1.8, 1.25, 3.9],
    cameraForAspect: aspect => aspect < 1.4 ? [-1.5, 1.1, 4.2] : [-1.8, 1.25, 3.9],
    quality(mode, width) { make.quality(textureSize(mode, width)); },
    update({ value, phase }) {
      const step = Math.round(value);
      earth.visible = step === 3;
      shell.visible = step < 3;
      mixed.visible = iron.visible = step < 2;
      faces.visible = step >= 2;
      innerCore.color.set(step === 3 ? 0xe6c798 : 0xe4a167);
      drops.forEach(({ drop, start }) => drop.position.copy(start).multiplyScalar(step === 1 ? 1 - phase * .72 : 1));
      labels[0].text = step < 2 ? 'Ferro e rochas · cores atribuídas'
        : step === 2 ? 'Núcleo, manto e crosta · corte ilustrativo'
        : 'Núcleo sólido e líquido · cores atribuídas';
    }
  };
}

export function atmosphereScene(): Exhibit {
  const make = createWorldFactory(), group = new THREE.Group(), earth = make('terra');
  earth.rotation.y = -1.8;
  styleEarth(earth);
  // The soft limb is illustrative. The marker radius itself is proportional to altitude.
  earth.getObjectByName('terra_halo')?.scale.setScalar(1.028 / 1.06);
  group.add(earth);
  const direction = new THREE.Vector3(.76, .59, .27).normalize();
  const marker = new THREE.Mesh(new THREE.SphereGeometry(.018, 24, 12), new THREE.MeshBasicMaterial({ color: 0xffdeb6 }));
  marker.add(new THREE.Mesh(new THREE.SphereGeometry(.025, 24, 12), new THREE.MeshBasicMaterial({ color: 0x162334, side: THREE.BackSide })));
  group.add(marker);
  const label = { text: '', position: new THREE.Vector3(), pixelOffset: [34, -26] as [number, number] };
  return {
    group, lighting: light, camera: [0, .48, 4.1],
    labels: [label, { text: 'Altitude em proporção ao raio terrestre', position: new THREE.Vector3(0, -1.18, 0), pixelOffset: [0, 0] }],
    quality(mode, width) { make.quality(textureSize(mode, width)); },
    update({ value }) {
      const altitude = THREE.MathUtils.clamp(value, 0, 120);
      marker.position.copy(direction).multiplyScalar(1 + altitude / earthRadiusKm);
      label.position.copy(marker.position);
      label.text = Math.round(altitude) + ' km · ' + atmosphereLayer(altitude);
    }
  };
}

const fieldEarthRadius = .55;
const magneticTilt = -.16;

function curtain(hemisphere: number) {
  const positions: number[] = [], uvs: number[] = [], indices: number[] = [];
  const steps = 160;
  for (let i = 0; i <= steps; i++) {
    const angle = i / steps * Math.PI * 2;
    const polar = .29 + .032 * Math.sin(angle * 3) + .019 * Math.sin(angle * 11) + .009 * Math.sin(angle * 23);
    const heights = [108 + 9 * Math.sin(angle * 6), 365 + 82 * Math.sin(angle * 7) ** 2];
    for (let j = 0; j < 2; j++) {
      const radius = fieldEarthRadius * (1 + heights[j] / earthRadiusKm);
      positions.push(
        radius * Math.sin(polar) * Math.cos(angle), hemisphere * radius * Math.cos(polar),
        radius * Math.sin(polar) * Math.sin(angle)
      );
      uvs.push(i / steps, j);
    }
    if (i < steps) {
      const k = i * 2;
      indices.push(k, k + 1, k + 2, k + 1, k + 3, k + 2);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  const oval = new THREE.Mesh(geometry, new THREE.ShaderMaterial({
    side: THREE.DoubleSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uPhase: { value: 1 } },
    vertexShader: 'varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader: `
      uniform float uPhase;
      varying vec2 vUv;
      void main(){
        float folds=.58+.25*sin(vUv.x*75.4+uPhase*6.283)+.17*sin(vUv.x*144.5);
        float rays=pow(.5+.5*sin(vUv.x*553.+sin(vUv.x*31.4)*3.),3.);
        float layer=smoothstep(0.,.12,vUv.y)*(1.-smoothstep(.66,1.,vUv.y))*exp(-2.25*vUv.y);
        vec3 color=mix(vec3(.12,.89,.48),vec3(.76,.15,.22),smoothstep(.31,.83,vUv.y));
        gl_FragColor=vec4(color,layer*folds*(.54+.46*rays));
      }`
  }));
  oval.rotation.z = magneticTilt;
  return oval;
}

export function magnetosphereScene(): Exhibit {
  const make = createWorldFactory(), group = new THREE.Group(), earth = make('terra');
  earth.rotation.y = -1.8;
  styleEarth(earth);
  earth.scale.setScalar(fieldEarthRadius);
  group.add(earth);

  const field = new THREE.Group();
  group.add(field);
  const fieldMaterial = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: .62 });
  const cold = new THREE.Color(0x395c7c), pale = new THREE.Color(0x80ccd5), tint = new THREE.Color();
  const tiltAxis = new THREE.Vector3(0, 0, 1);
  for (const shellRadius of [1.15, 1.65, 2.15]) for (let i = 0; i < 6; i++) {
    const azimuth = i / 6 * Math.PI * 2, start = Math.asin(Math.sqrt(fieldEarthRadius / shellRadius));
    const points: THREE.Vector3[] = [], colors: number[] = [];
    for (let j = 0; j <= 72; j++) {
      const theta = start + (Math.PI - 2 * start) * j / 72, r = shellRadius * Math.sin(theta) ** 2;
      const point = new THREE.Vector3(r * Math.sin(theta) * Math.cos(azimuth), r * Math.cos(theta), r * Math.sin(theta) * Math.sin(azimuth));
      point.applyAxisAngle(tiltAxis, magneticTilt);
      const distance = (r - fieldEarthRadius) / 1.6;
      point.x *= point.x < 0 ? 1 - .36 * distance : 1 + .65 * distance;
      points.push(point);
      tint.copy(cold).lerp(pale, 1 - distance * .82);
      colors.push(tint.r, tint.g, tint.b);
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    field.add(new THREE.Line(geometry, fieldMaterial));
  }

  const north = curtain(1), south = curtain(-1);
  group.add(north, south);
  const particleCount = 48;
  const trajectories = Array.from({ length: particleCount }, (_, i) => {
    const polar = i % 4 === 0;
    const hemisphere = polar ? (Math.floor(i / 4) % 2 ? 1 : -1) : (i % 2 ? 1 : -1);
    const y = Math.sin(i * 5.7) * 1.1, z = Math.cos(i * 3.2) * .5;
    const start = new THREE.Vector3(-3.1, y, z);
    const end = new THREE.Vector3(.12, hemisphere * .549, .14).applyAxisAngle(tiltAxis, magneticTilt);
    const curve = polar
      ? new THREE.CubicBezierCurve3(start, new THREE.Vector3(-1.6, hemisphere * 1.1, z), new THREE.Vector3(-.55, hemisphere * 1.1, .15), end)
      : new THREE.CubicBezierCurve3(start, new THREE.Vector3(-1.3, hemisphere * 1.7, z), new THREE.Vector3(1.5, hemisphere * 1.6, z), new THREE.Vector3(3.8, hemisphere * 1.1, z));
    return { y, z, curve };
  });

  const geometry = new THREE.BufferGeometry();
  const positions = new THREE.BufferAttribute(new Float32Array(particleCount * 3), 3);
  positions.setUsage(THREE.DynamicDrawUsage);
  geometry.setAttribute('position', positions);
  const dots = new THREE.Points(geometry, new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, toneMapped: false, blending: THREE.AdditiveBlending,
    vertexShader: 'void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_PointSize=4.;}',
    fragmentShader: 'void main(){float a=exp(-dot(gl_PointCoord-.5,gl_PointCoord-.5)*25.);gl_FragColor=vec4(.95,.74,.39,a);}'
  }));
  dots.frustumCulled = false;
  group.add(dots);
  const auroraLabel = {
    text: 'Auroras polares · emissão ilustrativa', position: new THREE.Vector3(.14, .67, 0),
    pixelOffset: [36, -23] as [number, number], visible: () => field.visible
  };
  return {
    group, lighting: { ...light, ambient: .20, keyPosition: [-6, 2, 3] },
    views: [{ label: 'Ver polo norte de perto', camera: [.65, 1.3, 2.1] }],
    camera: [0, 2.1, 5.7],
    cameraForAspect: aspect => aspect < 1.4 ? [0, 2.7, 7.4] : [0, 2.1, 5.7],
    labels: [
      { text: 'Vento solar →', position: new THREE.Vector3(-2.3, .2, 0) },
      auroraLabel,
      { text: 'Linhas do modelo · fora de escala', position: new THREE.Vector3(.35, -1.64, 0), visible: () => field.visible }
    ],
    inspect() { return { windPositions: Array.from(positions.array), fieldOn: field.visible }; },
    quality(mode, width) { make.quality(textureSize(mode, width)); },
    update({ value, phase }) {
      const fieldOn = value === 0;
      field.visible = north.visible = south.visible = fieldOn;
      for (const oval of [north, south]) oval.material.uniforms.uPhase.value = phase;
      trajectories.forEach((path, i) => {
        const t = (phase + i / particleCount) % 1;
        const point = fieldOn ? path.curve.getPoint(t) : new THREE.Vector3(-3.1 + t * 6.8, path.y, path.z);
        const radiusSquared = point.y * point.y + point.z * point.z;
        if (!fieldOn && radiusSquared < fieldEarthRadius ** 2) {
          point.x = Math.min(point.x, -Math.sqrt(fieldEarthRadius ** 2 - radiusSquared));
        }
        positions.setXYZ(i, point.x, point.y, point.z);
      });
      positions.needsUpdate = true;
    }
  };
}
