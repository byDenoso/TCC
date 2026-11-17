import * as THREE from 'three';
import type { Exhibit } from './runtime';
import { createGalaxyFactory } from './galaxy';
import type { EmissionSize } from './galaxy-emission';

/** Interpolação de densidade para leitura dos vazios e nós; posições ilustrativas. */
export function cosmicWeb(initialSize: EmissionSize = 1536, sharedFactory?: ReturnType<typeof createGalaxyFactory>): Exhibit {
  const galaxy = sharedFactory ?? createGalaxyFactory(initialSize);
  const group = new THREE.Group();
  let seed = 41;
  const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
  const normal = () => Math.sqrt(-2 * Math.log(Math.max(1e-6, random()))) * Math.cos(2 * Math.PI * random());
  // Unequal cells leave the empty regions visible from an oblique camera.
  const corners = [
    [-3.2,.00,1.1], [-2.1,.82,-.68], [-1.4,-.65,1.75], [-.22,.42,1.45], [.58,.87,-.23],
    [1.95,.1,1.6], [3.25,.36,.18], [-3.1,-.55,-1.12], [-1.65,-.1,-2.32], [-.35,-1.04,-1.03],
    [.55,.13,-2.4], [2.3,-.88,-1.28], [3.1,.63,-2.35], [-1.16,1.3,.18], [1,-.99,.22],
    [-2.3,-.78,.42], [2.13,1.18,-.55]
  ].map(p => new THREE.Vector3(...p));
  const links = [
    [0,1],[0,2],[0,15],[1,8],[1,13],[1,7],[2,3],[2,15],[3,13],[3,4],[3,5],[4,10],[4,16],
    [5,6],[5,14],[6,11],[6,16],[7,8],[7,15],[8,9],[8,10],[9,14],[10,11],[11,12],[12,16],[11,14],[13,4]
  ];
  const count = 28000;
  const start = new Float32Array(count * 3), end = new Float32Array(count * 3);
  const grain = new Float32Array(count * 2);
  const point = new THREE.Vector3();
  const filaments = links.map(([a,b]) => {
    const c1 = corners[a].clone().lerp(corners[b], .33);
    const c2 = corners[a].clone().lerp(corners[b], .67);
    c1.add(new THREE.Vector3(normal()*.18, normal()*.18, normal()*.18));
    c2.add(new THREE.Vector3(normal()*.18, normal()*.18, normal()*.18));
    return new THREE.CubicBezierCurve3(corners[a], c1, c2, corners[b]);
  });
  for (let i=0; i<count; i++) {
    const edge = Math.floor(random() * filaments.length);
    const t = random(), kind = random();
    let width: number, heat: number;
    if (kind < .23) {
      point.copy(corners[links[edge][t < .5 ? 0 : 1]]);
      width = .019 + Math.pow(random(), 2) * .24;
      heat = .76 + random() * .24;
    } else {
      filaments[edge].getPoint(t, point);
      const twist = t * Math.PI * 4 + edge;
      // Coherent subfilaments run inside a more diffuse surrounding envelope.
      const strand = ((i % 3) - 1) * Math.sin(Math.PI * t) * .15;
      point.y += Math.cos(twist) * strand;
      point.z += Math.sin(twist) * strand;
      width = kind > .88 ? .21 : .018 + .048 * Math.pow(Math.sin(Math.PI*t),2);
      heat = .12 + .46 * Math.pow(Math.abs(2*t - 1),2) + .15 * random();
    }
    point.x += normal()*width; point.y += normal()*width; point.z += normal()*width;
    point.toArray(end, 3*i);
    start.set([(random()-.5)*6.8,(random()-.5)*2.75,(random()-.5)*4.9], 3*i);
    grain.set([heat, Math.pow(random(),3)], 2*i);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(end,3));
  geometry.setAttribute('aStart', new THREE.BufferAttribute(start,3));
  geometry.setAttribute('aGrain', new THREE.BufferAttribute(grain,2));
  const material = new THREE.ShaderMaterial({
    uniforms: {uGrowth:{value:0}, uHeight:{value:320}}, toneMapped:false, transparent:true,
    depthWrite:false, blending:THREE.AdditiveBlending,
    vertexShader: `
      attribute vec3 aStart; attribute vec2 aGrain;
      uniform float uGrowth,uHeight; varying float vHeat,vGrain,vBrightness;
      void main() {
        vec4 eye = modelViewMatrix * vec4(mix(aStart,position,uGrowth),1.);
        gl_Position = projectionMatrix * eye;
        vHeat = aGrain.x*uGrowth;
        vGrain = aGrain.y;
        vBrightness = mix(.22,1.,uGrowth) * clamp(7./-eye.z,.55,1.35);
        gl_PointSize = clamp(uHeight * (.027+.083*vGrain) / -eye.z,1.1,18.);
      }`,
    fragmentShader: `
      varying float vHeat,vGrain,vBrightness;
      void main() {
        vec2 uv = gl_PointCoord*2.-1.;
        float r = dot(uv,uv);
        if(r>1.) discard;
        float glow = exp(-r*5.) * (1.-smoothstep(.65,1.,r));
        vec3 color = mix(vec3(.36,.55,.72),vec3(1.,.81,.57),smoothstep(.28,.98,vHeat));
        gl_FragColor = vec4(color,glow*(.09+.21*vGrain)*vBrightness);
      }`
  });
  const points = new THREE.Points(geometry, material);
  const bufferSize = new THREE.Vector2();
  points.onBeforeRender = renderer => { material.uniforms.uHeight.value = renderer.getDrawingBufferSize(bufferSize).y; };
  group.add(points);
  const galaxies = corners.map((position,i) => {
    const g = galaxy(77+i, i%4===0?'elliptical':i%5===0?'irregular':'spiral', true);
    g.position.copy(position); g.rotation.set(i*.2,i*.7,i*.4); group.add(g); return g;
  });
  return {
    group, ...(!sharedFactory ? galaxy.presentation(group) : {}),
    camera:[.4,2.25,6.9],
    cameraForAspect: aspect => [.4,2.25, Math.max(6.9, 9.2/aspect)],
    update({value}) {
      const growth = THREE.MathUtils.clamp(value,0,1);
      material.uniforms.uGrowth.value = growth;
      const extent = .12 * THREE.MathUtils.smoothstep(growth,.72,1);
      for (const g of galaxies) { g.visible = extent > .001; g.scale.setScalar(extent); }
    }
  };
}
