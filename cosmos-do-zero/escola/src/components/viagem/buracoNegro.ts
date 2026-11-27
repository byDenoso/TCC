import * as THREE from 'three';

/*
 * Traçado de raios na geometria de Schwarzschild, em unidades do raio do horizonte (r_s = 1).
 *
 * Em coordenadas espaciais planas, a trajetória da luz obedece a x'' = -1,5 h² x / r⁵, com
 * h = |x × v| conservado (a mesma equação de órbita de Binet, u'' + u = 1,5 u², escrita em 3D).
 * Cada pixel lança um raio da câmera para trás e o integra com Verlet de passo proporcional a r.
 * Ao cruzar o plano do disco entre 3 r_s (última órbita estável) e 12 r_s, soma a emissão do
 * disco com o fator g = 1 / [u^t (1 − Ω L_y)]: desvio gravitacional e Doppler da órbita
 * kepleriana, Ω = √(M/r³) com M = 1/2. A intensidade escala com g³. Raios que escapam leem o
 * céu na direção final, já deformado pela lente; os que atravessam r = 1 ficam negros (sombra).
 * O mesmo cálculo gera o pôster em assets/source/viagem/build_viagem.py.
 */

const vertex = /* glsl */ `
varying vec2 vNdc;
void main() {
  vNdc = position.xy;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}`;

const fragment = /* glsl */ `
uniform mat4 invProj;
uniform mat4 camMundo;
uniform mat3 paraBH;
uniform vec3 camPos;
uniform sampler2D disco;
uniform sampler2D ceu;
uniform float tempo;
uniform float brilho;
uniform vec3 fundo;
varying vec2 vNdc;
const float RIN = 3.0;
const float ROUT = 12.0;
const float TAU = 6.28318530718;

void main() {
  vec4 pv = invProj * vec4(vNdc, 1.0, 1.0);
  pv /= pv.w;
  vec3 dirMundo = normalize((camMundo * vec4(pv.xyz, 0.0)).xyz);
  vec3 x = paraBH * camPos;
  vec3 v = paraBH * dirMundo;
  float Ly = cross(x, -v).y;
  vec3 hv = cross(x, v);
  float h2 = dot(hv, hv);
  vec3 cor = vec3(0.0);
  float a = 0.0;
  bool caiu = false;
  for (int i = 0; i < 360; i++) {
    float r = length(x);
    if (r < 1.0) { caiu = true; break; }
    if (r > 80.0 && dot(x, v) > 0.0) break;
    float dt = clamp(0.07 * r, 0.02, 3.0);
    vec3 a0 = -1.5 * h2 * x / pow(r, 5.0);
    vec3 xn = x + v * dt + 0.5 * a0 * dt * dt;
    vec3 a1 = -1.5 * h2 * xn / pow(length(xn), 5.0);
    v += 0.5 * (a0 + a1) * dt;
    if (x.y * xn.y < 0.0) {
      float t = x.y / (x.y - xn.y);
      vec3 p = mix(x, xn, t);
      float rc = length(p.xz);
      if (rc > RIN && rc < ROUT) {
        float om = sqrt(0.5 / (rc * rc * rc));
        float ang = atan(-p.z, p.x) - om * tempo;
        vec4 tx = texture2D(disco, vec2((rc - RIN) / (ROUT - RIN), fract(ang / TAU)));
        float ut = 1.0 / sqrt(1.0 - 1.5 / rc);
        float g = 1.0 / (ut * (1.0 - om * Ly));
        vec3 c = tx.rgb * pow(g, 3.0) * vec3(pow(g, -0.5), 1.0, pow(g, 0.7)) * brilho;
        cor += (1.0 - a) * tx.a * c;
        a += (1.0 - a) * tx.a;
        if (a > 0.98) break;
      }
    }
    x = xn;
  }
  if (!caiu && a < 0.98) {
    vec3 d = normalize(v);
    vec2 uv = vec2(atan(d.z, d.x) / TAU + 0.5, acos(clamp(d.y, -1.0, 1.0)) / 3.14159265);
    cor += (1.0 - a) * texture2D(ceu, uv).rgb;
  }
  // compressão suave dos realces e saída em sRGB; o céu vazio termina na cor exata do palco
  cor = cor / (1.0 + 0.35 * cor);
  vec3 srgb = pow(clamp(cor, 0.0, 1.0), vec3(1.0 / 2.2));
  gl_FragColor = vec4(fundo + (1.0 - fundo) * srgb, 1.0);
}`;

export function criarBuracoNegro(disco: THREE.Texture, ceu: THREE.Texture) {
  disco.wrapS = THREE.ClampToEdgeWrapping;
  disco.wrapT = THREE.RepeatWrapping;
  ceu.wrapS = THREE.RepeatWrapping;
  ceu.wrapT = THREE.ClampToEdgeWrapping;
  disco.needsUpdate = true;
  ceu.needsUpdate = true;
  const material = new THREE.ShaderMaterial({
    uniforms: {
      invProj: { value: new THREE.Matrix4() },
      camMundo: { value: new THREE.Matrix4() },
      paraBH: { value: new THREE.Matrix3() },
      camPos: { value: new THREE.Vector3() },
      disco: { value: disco },
      ceu: { value: ceu },
      tempo: { value: 0 },
      brilho: { value: 1.7 },
      fundo: { value: new THREE.Vector3(12 / 255, 21 / 255, 23 / 255) }, // #0c1517 em sRGB
    },
    vertexShader: vertex,
    fragmentShader: fragment,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
  });
  const malha = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
  malha.frustumCulled = false;
  malha.renderOrder = -10;
  return malha;
}

const m3 = new THREE.Matrix3();

/** Atualiza a câmera e a orientação do buraco negro (o arrasto gira o grupo, não a câmera). */
export function atualizarBuracoNegro(
  malha: THREE.Mesh,
  camera: THREE.PerspectiveCamera,
  grupo: THREE.Object3D,
  dt: number,
  velocidade: number,
) {
  const u = (malha.material as THREE.ShaderMaterial).uniforms;
  camera.updateMatrixWorld();
  grupo.updateMatrixWorld();
  u.invProj.value.copy(camera.projectionMatrixInverse);
  u.camMundo.value.copy(camera.matrixWorld);
  u.camPos.value.copy(camera.position);
  u.paraBH.value.copy(m3.setFromMatrix4(grupo.matrixWorld).transpose());
  u.tempo.value += dt * velocidade;
}
