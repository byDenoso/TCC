import * as THREE from 'three';
import { sampleStory, storyRotationVelocity } from '../../lib/story-scenes';
import { createWorldFactory, prepareWorlds } from './assets';
import { createGalaxyFactory } from './galaxy';
import { prepareEmissionGalaxies } from './galaxy-emission';
import type { Exhibit } from './runtime';
import { distantStar, lightStars, prepareStellarMaterials, stellarFactory } from './stellar-materials';
import { createStoryEarth } from './story-worlds';
import { cosmicWeb } from './web';

const textureSize = 768;
const framing = { camera: [0, 0, 8] as [number, number, number], orthographicHeight: () => 5.4 };

export async function prepareStoryGalaxies(id: string): Promise<void> {
  const galaxies = prepareEmissionGalaxies(textureSize);
  if (id === 'galaxias-e-nebulosas') {
    await Promise.all([galaxies, prepareWorlds(), prepareStellarMaterials('surface')]);
  } else {
    await galaxies;
  }
}

function starField(): THREE.Points<THREE.BufferGeometry, THREE.PointsMaterial> {
  const stars = lightStars(280);
  const material = stars.material as THREE.PointsMaterial;
  material.opacity = .48;
  material.toneMapped = false;
  material.size = .041;
  stars.scale.set(1.2, 1, 1);
  return stars as THREE.Points<THREE.BufferGeometry, THREE.PointsMaterial>;
}

/** Highlight the warm bulge and young blue stars in the existing illustrative emission map. */
function exposeGalaxy(group: THREE.Group): void {
  group.traverse(object => {
    const material = (object as THREE.Mesh).material;
    if (!(material instanceof THREE.MeshBasicMaterial) || !material.map) return;
    material.onBeforeCompile = shader => {
      shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
        vec3 light = diffuseColor.rgb;
        float blue = smoothstep(.0, .045, light.b - light.r);
        light *= mix(vec3(1.95, 1.72, 1.45), vec3(1.28, 1.92, 2.72), blue);
        diffuseColor.rgb = light / (1.0 + .38 * light);`);
    };
    material.customProgramCacheKey = () => 'story-galaxy-exposure';
  });
}

function cosmicAddress(): Exhibit {
  const id = 'galaxias-e-nebulosas';
  const galaxy = createGalaxyFactory(textureSize);
  const makeWorld = createWorldFactory();
  const group = new THREE.Group();
  const solar = new THREE.Group(), galactic = new THREE.Group();
  const earth = createStoryEarth(makeWorld);
  const earthLongitude = earth.rotation.y;
  earth.position.set(-.5, -.04, .15);
  earth.scale.setScalar(1.49);
  const sun = stellarFactory()(0xffd6a7);
  sun.position.set(2.5, .95, -1.7);
  sun.scale.setScalar(.46);
  const glare = distantStar(0xffb873);
  glare.position.copy(sun.position);
  glare.position.z -= .5;
  glare.scale.set(2.85, 2.85, 1);
  glare.material.opacity = .5;
  solar.add(earth, sun, glare);

  const milkyWay = galaxy(1);
  milkyWay.position.set(-.3, .09, 0);
  milkyWay.scale.setScalar(2.55);
  exposeGalaxy(milkyWay);
  const address = distantStar(0xffd291);
  address.position.set(1.25, -.01, 2.4);
  address.scale.set(.28, .28, 1);
  const locator = new THREE.Mesh(
    new THREE.RingGeometry(.067, .077, 48),
    new THREE.MeshBasicMaterial({ color: 0xffce84, transparent: true, opacity: .85, toneMapped: false })
  );
  locator.position.copy(address.position);
  galactic.add(milkyWay, address, locator);

  const network = cosmicWeb(textureSize, galaxy);
  network.group.position.y = .04;
  network.group.scale.set(1.23, 1.15, 1.12);
  network.update({ value: 1, phase: 1, elapsed: 0 });
  const sky = starField();
  group.add(sky, solar, galactic, network.group);
  const presentation = galaxy.presentation(group);

  return {
    group,
    ...presentation,
    ...framing,
    lighting: { ambient: .48, key: 3.4, fill: .16, exposure: 1.16, neutral: true, keyPosition: [4.5, 2.5, 6] },
    quality(mode, width) {
      makeWorld.quality(mode === 'low' ? 512 : width < 600 ? 1024 : 2048);
      return presentation.quality(mode, width);
    },
    update({ value }) {
      const { phase, progress } = sampleStory(id, value);
      solar.visible = phase === 0;
      galactic.visible = phase === 1;
      network.group.visible = phase === 2;
      sky.material.opacity = phase === 2 ? .24 : .48;
      earth.rotation.y = earthLongitude + progress * 1.08;
      sun.rotation.y = progress * .65;
      milkyWay.rotation.set(-.57 - (progress - .34) * .23, .1, -.28, 'ZYX');
      network.group.rotation.set(-.23, -.32 + (progress - .7) * .88, -.07);
    }
  };
}

function rotationStory(): Exhibit {
  const galaxy = createGalaxyFactory(textureSize);
  const group = new THREE.Group(), disc = galaxy(2);
  disc.position.set(-2.4, .05, 0);
  disc.scale.setScalar(2.16);
  disc.rotation.set(-.6, .13, -.25, 'ZYX');
  exposeGalaxy(disc);

  const tracers = lightStars(64);
  const material = tracers.material as THREE.PointsMaterial;
  material.color.set(0xabd4ff);
  material.opacity = .64;
  material.toneMapped = false;
  material.size = .031;
  const positions = tracers.geometry.getAttribute('position') as THREE.BufferAttribute;
  positions.setUsage(THREE.DynamicDrawUsage);
  tracers.frustumCulled = false;
  const orbits = Array.from({ length: positions.count }, (_, i) => {
    const radius = .13 + .69 * Math.sqrt((i + .5) / positions.count);
    return { radius, angle: i * 2.3999632, visible: storyRotationVelocity(radius, 0) };
  });
  disc.add(tracers);
  group.add(starField(), disc);

  return {
    group,
    ...galaxy.presentation(group),
    ...framing,
    update({ value }) {
      orbits.forEach(({ radius, angle, visible }, i) => {
        // Integrate the toy velocity sqrt(v_visible² + value * v_halo²) as the contribution grows.
        const speed = storyRotationVelocity(radius, value);
        const mean = 2 * (speed * speed + speed * visible + visible * visible) / (3 * (speed + visible));
        const azimuth = angle + .42 * value * mean / radius;
        positions.setXYZ(i, Math.cos(azimuth) * radius, Math.sin(azimuth) * radius, .07 + .012 * Math.sin(i * 3));
      });
      positions.needsUpdate = true;
    }
  };
}

export function createGalaxyStory(id: string): Exhibit {
  return id === 'galaxias-e-nebulosas' ? cosmicAddress() : rotationStory();
}
