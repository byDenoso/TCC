import * as THREE from 'three';
import type { Exhibit } from './runtime';

/** A curva representa a componente transversal do campo elétrico. */
export function createRedshiftStory(): Exhibit {
  const group = new THREE.Group();
  const geometry = new THREE.TubeGeometry(
    new THREE.LineCurve3(new THREE.Vector3(-4.2, 0, 0), new THREE.Vector3(4.2, 0, 0)),
    420, 0.022, 8
  );
  const wave = (y: number) => {
    const material = new THREE.ShaderMaterial({
      uniforms: { spacing: { value: .72 }, tint: { value: new THREE.Color(0xa4bfff) } },
      vertexShader: `
        uniform float spacing;
        varying vec3 vNormal;
        void main() {
          vec3 p = position;
          float angle = 6.2831853 * (p.x + 4.2) / spacing;
          float slope = .25 * 6.2831853 / spacing * cos(angle);
          p.y += .25 * sin(angle);
          vNormal = normalize(normalMatrix * vec3(normal.x - slope * normal.y, normal.y, normal.z));
          gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.);
        }`,
      fragmentShader: `
        uniform vec3 tint;
        varying vec3 vNormal;
        void main() {
          float diffuse = .6 + .4 * max(dot(normalize(vNormal), normalize(vec3(-.2,.6,1.))), 0.);
          gl_FragColor = vec4(tint * diffuse, 1.);
          #include <colorspace_fragment>
        }`
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.y = y;
    group.add(mesh);
    return material.uniforms;
  };
  wave(.97);
  const observed = wave(-.57);
  const blue = new THREE.Color(0xa4bfff);
  const infrared = new THREE.Color(0xff825d);
  return {
    group, camera: [0, 0, 8], orthographicHeight: () => 5.4,
    update({ value }) {
      observed.spacing.value = .72 * (1 + value);
      observed.tint.value.copy(blue).lerp(infrared, value);
    }
  };
}
