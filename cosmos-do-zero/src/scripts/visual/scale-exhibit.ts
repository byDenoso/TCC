import * as THREE from 'three';
import earthMapUrl from '../../../assets/source/solar-materials/terra.jpg?url';
import type { Exhibit } from './runtime';
import { scaleFlight } from './scale-flight';

const cream = new THREE.Color(0xffe4b3);
const clay = new THREE.Color(0xcf572d);
const ink = new THREE.Color(0x7c8baf);
const tau = 2 * Math.PI;

function rng(seed: number) {
  return () => (seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296;
}

function direction(random: () => number) {
  const y = 2 * random() - 1;
  const a = tau * random();
  const r = Math.sqrt(1 - y * y);
  return new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a));
}

type Grain = { position: THREE.Vector3; size: number; color: THREE.Color };

function grains(count: number, sample: (index: number) => Grain, opacity = .9) {
  const mesh = new THREE.InstancedMesh(
    new THREE.IcosahedronGeometry(1),
    new THREE.MeshBasicMaterial({ transparent: true, opacity, depthWrite: false, toneMapped: false }),
    count,
  );
  const matrix = new THREE.Matrix4();
  for (let i = 0; i < count; i++) {
    const { position, size, color } = sample(i);
    mesh.setMatrixAt(i, matrix.makeScale(size, size, size).setPosition(position));
    mesh.setColorAt(i, color);
  }
  mesh.computeBoundingSphere();
  return mesh;
}

function sphere(radius: number, color: number, mobile: boolean, emissive = 0) {
  return new THREE.Mesh(
    new THREE.SphereGeometry(radius, mobile ? 28 : 48, mobile ? 20 : 32),
    new THREE.MeshStandardMaterial({ color, emissive, roughness: .65, metalness: .02 }),
  );
}

function rings(radii: number[], color: number, opacity: number) {
  const segments: number[] = [];
  for (const r of radii) for (let i = 0; i < 96; i++) {
    const a = tau * i / 96;
    const b = tau * (i + 1) / 96;
    segments.push(r * Math.cos(a), 0, r * Math.sin(a), r * Math.cos(b), 0, r * Math.sin(b));
  }
  const geometry = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(segments, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color, opacity, transparent: true, depthWrite: false }));
}

function proton(mobile: boolean) {
  const group = new THREE.Group();
  const random = rng(135);
  const centers = [new THREE.Vector3(-.35, -.1, .2), new THREE.Vector3(.28, -.19, -.12), new THREE.Vector3(.05, .34, .06)];
  group.add(grains(mobile ? 1850 : 3400, (i) => {
    const radius = Math.min(1.45, -.29 * Math.log(random() * random() + 1e-8));
    const position = direction(random).multiplyScalar(radius).add(centers[i % 3]);
    const color = clay.clone().lerp(cream, Math.pow(random(), 2) * Math.exp(-.48 * radius));
    return { position, size: .012 + .023 * random() * Math.exp(-radius), color };
  }, .72));
  return group;
}

function hydrogen(mobile: boolean) {
  const group = new THREE.Group();
  const random = rng(329);
  // r² exp(-2r/a₀) is the 1s radial probability. Sum three exponential draws.
  group.add(grains(mobile ? 2400 : 4400, () => {
    const radius = -.24 * Math.log(random() * random() * random() + 1e-12);
    const position = direction(random).multiplyScalar(radius);
    const color = ink.clone().lerp(cream, .65 * Math.exp(-radius) + random() * .18);
    return { position, size: .009 + random() * .014, color };
  }, .72));
  group.add(sphere(.058, 0xda713d, mobile, 0xba4a29));
  return group;
}

function cell(mobile: boolean) {
  const group = new THREE.Group();
  const profile = Array.from({ length: 49 }, (_, i) => {
    const a = Math.PI * i / 48;
    const r = Math.sin(a);
    const halfThickness = Math.cos(a) * (.09 + .78 * r * r - .37 * r ** 4);
    return new THREE.Vector2(1.26 * r, -halfThickness);
  });
  const geometry = new THREE.LatheGeometry(profile, mobile ? 48 : 80);
  const material = new THREE.MeshStandardMaterial({ color: 0xa93523, emissive: 0x2d0802, metalness: .04, roughness: .46 });
  const specimen = new THREE.Mesh(geometry, material);
  specimen.rotation.set(.06, .24, -.1);
  group.add(specimen);
  const surround = new THREE.InstancedMesh(geometry, material.clone(), 4);
  const sample = new THREE.Object3D();
  [[-2.02, -.52, -1.02], [1.94, .35, -.82], [.95, -.92, -1.62], [-.94, .92, -2.1]].forEach(([x, y, z], i) => {
    sample.position.set(x, y, z);
    sample.rotation.set(i * .4, i * .7, (i + 1) * .57);
    sample.scale.setScalar(.46 - i * .06);
    sample.updateMatrix();
    surround.setMatrixAt(i, sample.matrix);
  });
  group.add(surround);
  return group;
}

function metre() {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(3.26, .07, .48), new THREE.MeshStandardMaterial({ color: 0xe3b389, roughness: .62 }));
  const marks = new THREE.InstancedMesh(new THREE.BoxGeometry(.014, .004, 1), new THREE.MeshStandardMaterial({ color: 0x472417 }), 101);
  const matrix = new THREE.Matrix4();
  for (let i = 0; i <= 100; i++) {
    const length = i % 10 === 0 ? .38 : i % 5 === 0 ? .23 : .13;
    marks.setMatrixAt(i, matrix.makeScale(1, 1, length).setPosition((i / 100 - .5) * 3.2, .037, .225 - length / 2));
  }
  const band = new THREE.Mesh(new THREE.BoxGeometry(3.26, .075, .045), new THREE.MeshStandardMaterial({ color: 0xb76040, roughness: .55 }));
  band.position.z = -.199;
  group.rotation.set(.16, -.17, .38);
  group.add(body, marks, band);
  return group;
}

function galaxy(seed: number, count: number) {
  const group = new THREE.Group();
  const random = rng(seed);
  group.add(grains(count, (i) => {
    const core = i < count * .27;
    const r = core ? random() ** 1.7 * .53 : Math.sqrt(random()) * 1.95;
    const arm = i % 4;
    const a = r * 2.45 + arm * tau / 4 + (random() - .5) * (.42 + .16 / (r + .35));
    const position = core ? direction(random).multiplyScalar(r) : new THREE.Vector3(Math.cos(a) * r, (random() - .5) * .21 * (1 - r / 2.5), Math.sin(a) * r);
    const color = (core ? clay : ink).clone().lerp(cream, (core ? .36 : .25) + .62 * random());
    return { position, color, size: .008 + Math.pow(random(), 4) * .016 };
  }, .82));
  return group;
}

function cosmicWeb(count: number) {
  const group = new THREE.Group();
  const random = rng(526);
  const nodes = Array.from({ length: 32 }, () => direction(random).multiplyScalar(random() ** .48 * 2.15));
  const segments = nodes.map((a, i) => nodes.map((b, j) => ({ b, j, distance: a.distanceToSquared(b) }))
    .filter(row => row.j !== i).sort((b, c) => b.distance - c.distance).slice(0, 4).map(row => row.b));
  group.add(grains(count, (i) => {
    const index = i % nodes.length;
    const a = nodes[index];
    const b = segments[index][Math.floor(random() * 4)];
    const atNode = random() < .21;
    const phase = atNode ? 0 : random();
    const position = a.clone().lerp(b, phase).addScaledVector(direction(random), random() ** 2.1 * (atNode ? .3 : .22));
    position.y += Math.sin(phase * Math.PI) * (index % 2 ? .12 : -.12);
    const color = (atNode ? clay : ink).clone().lerp(cream, .2 + random() * .68);
    return { position, color, size: .007 + .011 * random() };
  }, .83));
  return { group, anchor: nodes[0] };
}

function horizon(count: number) {
  const group = new THREE.Group();
  const random = rng(167);
  const radius = 1.94;
  group.add(grains(count, () => {
    const position = direction(random).multiplyScalar(random() ** (1 / 3) * radius);
    return { position, size: .004 + .022 * random() ** 3, color: ink.clone().lerp(cream, random() * .8) };
  }, .78));
  const markers = [rings([radius], 0xc68b62, .58), rings([radius], 0xe7bb91, .3), rings([radius], 0xe7bb91, .28)];
  markers[1].rotateX(Math.PI / 2);
  markers[2].rotateZ(Math.PI / 2);
  group.add(...markers);
  return group;
}

/** Normalised local frames keep the camera precise across the full logarithmic range. */
export function scaleExhibit(mobile: boolean, redraw: () => void): Exhibit {
  const group = new THREE.Group();
  const planet = new THREE.Group();
  const globe = sphere(1.22, 0x608bb3, mobile);
  globe.rotation.set(.04, -1.3, -.16);
  planet.add(globe);
  let requestingMap = false;
  let alive = true;
  const system = new THREE.Group();
  const sun = sphere(.31, 0xfec169, mobile, 0xdb692e);
  const orbits = [.46, .61, .79, .96, 1.13, 1.39, 1.61, 1.9];
  const colors = [0x936b57, 0xc9ad82, 0x6c9cbd, 0xba5335, 0xd6a273, 0xddb58b, 0x78acb9, 0x557eab];
  const planets = orbits.map((radius, i) => {
    const world = sphere(i === 4 ? .132 : i === 5 ? .106 : .06, colors[i], mobile);
    const angle = .7 + i * 2.4;
    world.position.set(radius * Math.cos(angle), 0, radius * Math.sin(angle));
    if (i === 5) world.add(rings([.15, .171], 0xd6a273, .78));
    return world;
  });
  system.add(sun, rings(orbits, 0xc09473, .4), ...planets);
  const milkyWay = galaxy(52, mobile ? 4400 : 8400);
  const solarAddress = new THREE.Vector3(.98, .025, .51);
  const marker = rings([.084], 0xffce9b, .9);
  marker.position.copy(solarAddress);
  milkyWay.add(marker);
  const local = new THREE.Group();
  const localPositions = [[-.93, -.03, .18], [.91, .11, -.18], [.51, -.61, .67], [-1.46, .37, -.67], [1.43, .58, -.53], [-.25, .73, -.68]];
  const localGalaxies = localPositions.map(([x, y, z], i) => {
    const disc = galaxy(149 + i * 7, i > 1 ? 310 : mobile ? 1450 : 2400);
    disc.position.set(x, y, z);
    disc.scale.setScalar(i > 1 ? .135 : .42);
    disc.rotation.set(i * .68 - .2, i * .21, -.61 + i * .49);
    return disc;
  });
  local.add(...localGalaxies);
  const web = cosmicWeb(mobile ? 3900 : 7900);
  const steps = [proton(mobile), hydrogen(mobile), cell(mobile), metre(), planet, system, milkyWay, local, web.group, horizon(mobile ? 1900 : 3400)];
  const origin = new THREE.Vector3();
  const anchors = [origin, origin, origin, origin, origin, planets[2].position, solarAddress, localGalaxies[0].position, web.anchor, origin];
  const views: [number, number, number][] = [[.5, .68, 4.8], [-.5, 1.0, 4.8], [.4, 3.7, 3.5], [.22, 2.05, 4.5], [-.15, .45, 4.85], [.2, 3.3, 4.47], [.25, 4.38, 3.57], [-.28, 2.6, 4.9], [.6, 1.38, 5.7], [.35, 1.37, 6.56]];
  group.add(...steps);
  const exhibit: Exhibit = {
    group,
    background: 0x202027,
    camera: views[0],
    cameraForValue: (value) => views[value],
    lighting: { neutral: true, ambient: .6, key: 2.9, fill: .23, exposure: .83 },
    update() {},
    dispose() { alive = false; },
  };
  const flight = scaleFlight(exhibit, steps, anchors, true);
  return {
    ...flight,
    update(state) {
      if (!requestingMap && state.value > 3 && state.value < 6) {
        requestingMap = true;
        void new THREE.TextureLoader().loadAsync(earthMapUrl).then(map => {
          if (!alive) { map.dispose(); return; }
          map.colorSpace = THREE.SRGBColorSpace;
          globe.material.map = map;
          globe.material.color.set(0xffffff);
          globe.material.needsUpdate = true;
          redraw();
        }).catch(() => { /* Other stages and the initial Earth material remain available. */ });
      }
      flight.update(state);
    },
  };
}
