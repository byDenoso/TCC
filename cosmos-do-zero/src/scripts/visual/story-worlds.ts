import * as THREE from 'three';
import { sampleStory } from '../../lib/story-scenes';
import { createWorldFactory, prepareWorlds } from './assets';
import type { Exhibit } from './runtime';
import { lightStars, prepareStellarMaterials, stellarFactory } from './stellar-materials';
import { styleEarth } from './world-view';

const stageCamera: [number, number, number] = [0, 0, 8];
const stageHeight = () => 5.4;
const sunDirection: [number, number, number] = [-5, 4, 6];

export async function prepareStoryWorlds(id: string): Promise<void> {
  await Promise.all([
    prepareWorlds(),
    ...(id === 'sistema-solar' ? [prepareStellarMaterials('surface')] : [])
  ]);
}

export function createStoryEarth(make = createWorldFactory()): THREE.Group {
  const earth = make('terra');
  styleEarth(earth);
  // Keep the scattering halo close to the surface. The altitude ruler is the scale reference.
  earth.getObjectByName('terra_halo')?.scale.setScalar(1.025 / 1.06);
  earth.rotation.y = -1.8;
  return earth;
}

function atmosphereStory(): Exhibit {
  const group = new THREE.Group();
  const make = createWorldFactory();
  const earth = createStoryEarth(make);
  const axis = new THREE.Group();
  axis.position.set(-2.2, -0.43, 0);
  axis.rotation.z = -THREE.MathUtils.degToRad(23.44);
  axis.scale.setScalar(1.43);
  axis.add(earth);
  group.add(lightStars(125), axis);

  return {
    group,
    camera: stageCamera,
    orthographicHeight: stageHeight,
    lighting: { ambient: 0.48, key: 3.4, fill: 0.16, exposure: 1.16, neutral: true, keyPosition: sunDirection },
    quality(mode, width) { make.quality(mode === 'low' ? 512 : width < 600 ? 1024 : 2048); },
    update({ value }) {
      earth.rotation.y = -1.8 + value * 0.68;
      const clouds = earth.getObjectByName('terra_nuvens');
      if (clouds) clouds.rotation.y = value * 0.08;
    }
  };
}

function solarStory(): Exhibit {
  const group = new THREE.Group();
  const system = new THREE.Group();
  system.rotation.set(0.41, 0, -0.10, 'ZXY');
  system.position.y = -0.02;
  const { axes, periods } = sampleStory('sistema-solar', 0);
  const radii = axes.map(axis => axis * 2.35);
  const make = createWorldFactory();
  const sun = stellarFactory()(0xffe7cb);
  sun.scale.setScalar(0.43);
  sun.material.uniforms.uIntensity.value = 1.24;
  // Illuminating all three small display spheres requires a compressed exposure range.
  const sunlight = new THREE.PointLight(0xfff3e0, 6.8, 0, 0.6);
  system.add(sun, sunlight);

  const planetIds = ['mercurio', 'terra', 'marte'];
  const bodyRadii = [0.145, 0.245, 0.192];
  const orbitColors = [0xdbbc8e, 0x76b9d1, 0xcc917e];
  const worlds = planetIds.map((id, index) => {
    const body = id === 'terra' ? createStoryEarth(make) : make(id);
    body.scale.setScalar(bodyRadii[index]);
    const vertices = Array.from({ length: 180 }, (_, i) => {
      const theta = i / 180 * Math.PI * 2;
      return new THREE.Vector3(radii[index] * Math.cos(theta), 0, radii[index] * Math.sin(theta));
    });
    const trail = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(vertices),
      new THREE.LineBasicMaterial({ color: orbitColors[index], transparent: true, opacity: 0.56, toneMapped: false })
    );
    system.add(trail, body);
    return body;
  });
  group.add(lightStars(160), system);

  return {
    group,
    camera: stageCamera,
    orthographicHeight: stageHeight,
    lighting: { ambient: 0.48, key: 0, fill: 0, exposure: 1, neutral: true },
    quality(mode, width) { make.quality(mode === 'low' || width < 600 ? 512 : 1024); },
    update({ value }) {
      sun.rotation.y = value * 0.35;
      worlds.forEach((body, index) => {
        const theta = -0.52 + value * 4 * Math.PI * 2 / periods[index];
        body.position.set(radii[index] * Math.cos(theta), 0, radii[index] * Math.sin(theta));
        body.rotation.y = (index === 1 ? -1.8 : index) + value * 1.1;
      });
    }
  };
}

export function createWorldStory(id: string): Exhibit {
  if (id === 'terra-e-atmosfera') return atmosphereStory();
  if (id === 'sistema-solar') return solarStory();
  throw new RangeError(`Aula sem cena planetária: ${id}`);
}
