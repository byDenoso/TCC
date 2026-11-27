import * as THREE from 'three';

/*
 * Galáxia espiral com rotação diferencial e braços de onda de densidade (Lin e Shu).
 *
 * Cada estrela gira em torno do centro com a curva de rotação v(r) = V r / √(r² + r_c²): sobe
 * no centro e fica plana além de r_c, como nas espirais observadas. A velocidade angular
 * ω = v/r cai com o raio, então as estrelas de dentro dão mais voltas que as de fora.
 * Os braços não acompanham as estrelas: são um padrão que gira rígido com Ω_p. As estrelas jovens
 * e as regiões HII acendem quando passam por eles e apagam ao sair, por isso os braços persistem
 * enquanto as estrelas se movem. A barra gira rígida com o padrão.
 * Tipos (atributo _tipo, gravado pelo Blender): 0 disco antigo, 1 disco jovem, 2 barra, 3 bojo, 4 HII.
 */

const vertex = /* glsl */ `
attribute float _radius;
attribute float _tipo;
attribute vec4 color;
uniform float escala;
uniform float tempo;
uniform float kpc;
uniform float raioMarcado;
uniform float omegaP;
varying vec3 vCor;
const float RC = 1.2;
const float PITCH = 0.2867453; // tan(16°)
float omega(float r) { return 1.0 / sqrt(r * r + RC * RC); }
float pertoDoBraco(float r, float phi) {
  float bracos = log(max(r, 0.3) / 4.2) / PITCH - omegaP * tempo;
  float d = mod(phi - bracos + 1.5707963, 3.1415927) - 1.5707963;
  return exp(-d * d / (2.0 * 0.26 * 0.26));
}
void main() {
  vec3 p = position / kpc;
  float r = length(p.xz);
  float phi0 = atan(p.z, p.x);
  bool barra = _tipo > 1.5 && _tipo < 2.5;
  float phi = phi0 - (barra ? omegaP : omega(r)) * tempo;
  vec3 q = vec3(r * cos(phi), p.y, r * sin(phi)) * kpc;
  float braco = pertoDoBraco(r, phi);
  float brilho = 1.0;
  if (_tipo < 0.5) brilho = 0.8 + 0.35 * braco;
  else if (_tipo < 1.5) brilho = 0.2 + 1.15 * braco;
  else if (_tipo < 2.5) brilho = 0.55;
  else if (_tipo < 3.5) brilho = 0.45;
  else brilho = 0.04 + 1.5 * braco;
  vec3 cor = color.rgb * brilho;
  // estrelas no raio escolhido ficam destacadas: dá para seguir a órbita delas
  float marca = 0.0;
  if (raioMarcado > 0.0 && _tipo < 2.5) marca = 1.0 - smoothstep(0.25, 0.55, abs(r - raioMarcado));
  cor = mix(cor, vec3(0.45, 1.0, 0.88) * 2.4, 0.9 * marca);
  vCor = cor;
  vec4 mv = modelViewMatrix * vec4(q, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = clamp(2.0 * _radius * escala / -mv.z * (1.0 + 0.6 * marca), 1.4, 36.0);
}`;

const fragment = /* glsl */ `
uniform float ganho;
uniform float opacidade;
varying vec3 vCor;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float r2 = dot(p, p);
  if (r2 > 1.0) discard;
  float r = sqrt(r2);
  float borda = 1.0 - smoothstep(1.0 - 2.0 * fwidth(r), 1.0, r);
  gl_FragColor = vec4(vCor * ganho, borda * (0.55 + 0.45 * exp(-5.0 * r2)) * opacidade);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/** Ω(r) da mesma curva de rotação, em rad por unidade de tempo da cena (V = 1). */
export const omegaGalaxia = (rKpc: number) => 1 / Math.sqrt(rKpc * rKpc + 1.2 * 1.2);
/** Padrão dos braços com corrotação perto de 8,8 kpc. */
export const OMEGA_P = omegaGalaxia(8.8);

export function materialGalaxia(ganho: number, kpc = 1) {
  return new THREE.ShaderMaterial({
    uniforms: {
      escala: { value: 400 },
      ganho: { value: ganho },
      opacidade: { value: 1 },
      tempo: { value: 0 },
      kpc: { value: kpc },
      raioMarcado: { value: -1 },
      omegaP: { value: OMEGA_P },
    },
    vertexShader: vertex,
    fragmentShader: fragment,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true,
  });
}
