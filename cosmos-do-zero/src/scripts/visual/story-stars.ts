import * as THREE from 'three';
import type { Exhibit } from './runtime';
import { cloudFactory, lightStars, prepareStellarMaterials, stellarFactory } from './stellar-materials';

export function prepareStoryStars(): Promise<void> {
  return prepareStellarMaterials('nebula');
}

function bloomMap(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const context = canvas.getContext('2d')!;
  const glow = context.createRadialGradient(64, 64, 0, 64, 64, 64);
  glow.addColorStop(0, '#fff');
  glow.addColorStop(.35, '#ffffff90');
  glow.addColorStop(.55, '#ffffff2c');
  glow.addColorStop(.82, '#ffffff06');
  glow.addColorStop(1, '#fff0');
  context.fillStyle = glow;
  context.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(canvas);
}

// A stylized lensed background with a dark central mask. The arc is background light.
function lensedBackground(): THREE.Mesh {
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: { uPhase: { value: 0 } },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.);
      }
    `,
    fragmentShader: `
      uniform float uPhase;
      varying vec2 vUv;

      float light(vec2 p, vec2 center, float width) {
        vec2 d = (p - center) / width;
        return exp(-dot(d, d));
      }

      void main() {
        vec2 image = (vUv - .5) * 2.;
        float radius = length(image);
        if (radius >= 1.) discard;
        if (radius < .27) {
          gl_FragColor = vec4(.002, .003, .007, 1.);
          return;
        }

        // Weak-field thin-lens mapping for a point mass, in illustrative units.
        vec2 source = image * (1. - .23 / dot(image, image));
        vec2 alignment = vec2(.013 + .028 * uPhase, .018);
        float arc = light(source, alignment, .032);
        float stars = light(source, vec2(.19, -.26), .020)
                    + light(source, vec2(-.33, .21), .024)
                    + light(source, vec2(-.22, -.36), .015);
        float diffuse = .19 * light(source, vec2(-.075, .045), .34);
        vec3 radiance = vec3(.14, .25, .42) * diffuse
                      + vec3(.62, .77, .94) * arc
                      + vec3(.95, .89, .79) * stars;
        gl_FragColor = vec4(radiance, (1. - smoothstep(.67, 1., radius)) * .94);
      }
    `,
  });
  return new THREE.Mesh(new THREE.PlaneGeometry(1.62, 1.62), material);
}

export function createStarStory(): Exhibit {
  const group = new THREE.Group();
  const background = lightStars(260);
  background.scale.set(1.75, 1.38, 1);
  const backgroundMaterial = background.material as THREE.PointsMaterial;
  backgroundMaterial.size = .061;
  backgroundMaterial.opacity = .66;
  backgroundMaterial.toneMapped = false;

  const makeStar = stellarFactory();
  const gas = cloudFactory(true)();
  const shell = cloudFactory()();
  const protostar = makeStar(0xffe3bb);
  const solar = makeStar(0xffe8ca);
  const massive = makeStar(0xb8d5ff);
  const dwarf = makeStar(0xe2edff);
  const neutron = makeStar(0xd0e3ff);
  const blackHole = lensedBackground();
  const map = bloomMap();
  const glow = (star: THREE.Mesh, color: THREE.ColorRepresentation, opacity: number) => {
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map, color, opacity, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending, toneMapped: false,
    }));
    sprite.scale.set(3.38, 3.38, 1);
    sprite.position.z = -.26;
    star.add(sprite);
    return sprite;
  };
  const coreGlow = glow(protostar, 0xffb875, .48);
  const solarGlow = glow(solar, 0xffc892, .41);
  const massiveGlow = glow(massive, 0x9fbdff, .49);
  glow(dwarf, 0xc6ddff, .42);
  glow(neutron, 0xa0c6ff, .56);
  const gasUniforms = (gas.material as THREE.ShaderMaterial).uniforms;
  const shellUniforms = (shell.material as THREE.ShaderMaterial).uniforms;
  const solarUniforms = solar.material.uniforms;
  const massiveUniforms = massive.material.uniforms;
  const solarWarm = new THREE.Color(0xffe8ca);
  const solarGiant = new THREE.Color(0xf07b49);
  const massiveHot = new THREE.Color(0xb8d5ff);
  const massiveGiant = new THREE.Color(0xf6a67c);

  gas.position.set(0, 1.01, -.22);
  gas.rotation.set(.08, -.18, .12);
  gasUniforms.uEdgeFade.value = .38;
  gas.renderOrder = 1;
  protostar.position.set(0, 1.01, .06);
  solar.position.set(-2.44, -.76, 0);
  massive.position.set(2.44, -.76, 0);
  shell.position.set(-2.44, -.76, -.12);
  shellUniforms.uMode.value = 1;
  shellUniforms.uEdgeFade.value = .34;
  shellUniforms.uShell.value = .63;
  shell.renderOrder = 1;
  dwarf.position.set(-2.44, -.76, .06);
  dwarf.scale.setScalar(.23);
  dwarf.material.uniforms.uIntensity.value = 1.30;
  neutron.position.set(1.76, -.76, .04);
  neutron.scale.setScalar(.16);
  neutron.material.uniforms.uIntensity.value = 1.52;
  blackHole.position.set(3.13, -.76, .02);
  group.add(background, gas, protostar, solar, massive, shell, dwarf, neutron, blackHole);

  return {
    group,
    camera: [0, 0, 7],
    quality(mode, width) {
      const steps = mode === 'low' ? 16 : width < 640 ? 23 : 34;
      gasUniforms.uSteps.value = steps;
      shellUniforms.uSteps.value = steps;
    },
    update({ value }) {
      const collapse = THREE.MathUtils.smoothstep(value, 0, .30);
      const birth = THREE.MathUtils.smoothstep(value, .05, .30);
      const giant = THREE.MathUtils.smoothstep(value, .42, .715);
      const remnant = THREE.MathUtils.smoothstep(value, .72, 1);
      const ended = value >= .72;
      gas.scale.set(1.93 - 1.12 * collapse, .71 - .40 * collapse, .72 - .38 * collapse);
      gasUniforms.uOpacity.value = .92 - .65 * collapse;
      gas.rotation.z = .12 + .26 * collapse;
      protostar.visible = birth > 0;
      protostar.scale.setScalar(.09 + .33 * birth);
      protostar.material.uniforms.uIntensity.value = .44 + .81 * birth;
      coreGlow.material.opacity = .48 * birth;

      solar.visible = massive.visible = !ended;
      solar.scale.setScalar(.31 + .16 * birth + .30 * giant);
      massive.scale.setScalar(.44 + .26 * birth + .19 * giant);
      solar.rotation.y = value * .75;
      massive.rotation.y = value * .42;
      solarUniforms.uColor.value.lerpColors(solarWarm, solarGiant, giant);
      massiveUniforms.uColor.value.lerpColors(massiveHot, massiveGiant, giant);
      solarGlow.material.color.copy(solarUniforms.uColor.value);
      massiveGlow.material.color.copy(massiveUniforms.uColor.value);
      solarUniforms.uIntensity.value = 1.14 + .12 * birth;
      massiveUniforms.uIntensity.value = 1.22 + .14 * birth;
      shell.visible = dwarf.visible = neutron.visible = blackHole.visible = ended;
      shell.scale.set(.61 + .19 * remnant, .49 + .20 * remnant, .51 + .18 * remnant);
      shellUniforms.uOpacity.value = .73 - .28 * remnant;
      (blackHole.material as THREE.ShaderMaterial).uniforms.uPhase.value = remnant;
    },
  };
}
