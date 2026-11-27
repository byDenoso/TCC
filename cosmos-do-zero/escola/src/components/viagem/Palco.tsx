import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useLoader, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import cenas from './cenas.json';
import { estacoes, PLANETAS } from './estacoes';
import { corCorpoNegro, periodoAnos, raioOrbitaVisual, temperaturaCmb } from './fisica';
import { atualizarBuracoNegro, criarBuracoNegro } from './buracoNegro';

type Cfg = { camera: { pos: number[]; alvo: number[]; fov: number }; sol?: number[]; [k: string]: unknown };
const CFG = cenas.estacoes as Record<string, Cfg>;
const url = (id: string) => `/viagem/${id}.glb`;

export type PalcoProps = {
  id: string;
  valor: number;
  movimento: boolean;
  deslocamento: number;
  onPronto: (id: string) => void;
};

/* ------------------------------------------------------------ pontos */

const vertexPontos = /* glsl */ `
attribute float _radius;
attribute vec4 color;
uniform float escala;
varying vec3 vCor;
void main() {
  vCor = color.rgb;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = clamp(2.0 * _radius * escala / -mv.z, 1.4, 36.0);
}`;
const fragmentPontos = /* glsl */ `
uniform float ganho;
uniform float opacidade;
varying vec3 vCor;
void main() {
  vec2 p = gl_PointCoord * 2.0 - 1.0;
  float r2 = dot(p, p);
  if (r2 > 1.0) discard;
  // disco nítido com borda suavizada por um pixel e núcleo um pouco mais brilhante
  float r = sqrt(r2);
  float borda = 1.0 - smoothstep(1.0 - 2.0 * fwidth(r), 1.0, r);
  gl_FragColor = vec4(vCor * ganho, borda * (0.55 + 0.45 * exp(-5.0 * r2)) * opacidade);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const GANHO: Record<string, [number, number]> = {
  // [brilho, multiplicador de tamanho]
  estrelas: [1.6, 2.2],
  galaxias: [1.25, 2.4],
  'teia-cosmica': [0.62, 1.9],
  expansao: [1.5, 2.2],
};

function materialPontos(id: string) {
  const [ganho] = GANHO[id] ?? [1, 2];
  return new THREE.ShaderMaterial({
    uniforms: { escala: { value: 400 }, ganho: { value: ganho }, opacidade: { value: 1 } },
    vertexShader: vertexPontos,
    fragmentShader: fragmentPontos,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true,
  });
}

/** Clona a cena do GLB e ajusta materiais que o glTF não descreve (pontos, transparência). */
function preparar(original: THREE.Object3D, id: string) {
  const raiz = original.clone(true);
  raiz.traverse((o) => {
    const obj = o as THREE.Mesh | THREE.Points;
    if (!('material' in obj) || !obj.material) return;
    if ((obj as THREE.Points).isPoints) {
      obj.material = materialPontos(id);
      obj.frustumCulled = false;
      return;
    }
    const m = (obj.material as THREE.MeshStandardMaterial).clone();
    if (m.transparent || /aneis|nuvens|disco/.test(obj.name)) {
      m.transparent = true;
      m.depthWrite = false;
      m.side = THREE.DoubleSide;
    }
    // superfícies que emitem a própria luz: cor fiel, sem compressão do tone mapping
    if (/^(sol|estrela|cmb)$/.test(obj.name)) {
      m.toneMapped = false;
      m.emissiveIntensity = 1;
    }
    obj.material = m;
  });
  return raiz;
}

/** Escurecimento do limbo em materiais emissivos (estrela e Sol). */
function limbo(m: THREE.MeshStandardMaterial, k = 0.62) {
  m.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <emissivemap_fragment>',
      `#include <emissivemap_fragment>
       float mu = clamp(dot(normalize(vNormal), normalize(vViewPosition)), 0.0, 1.0);
       totalEmissiveRadiance *= 1.0 - ${k.toFixed(2)} * (1.0 - mu);`,
    );
  };
  m.needsUpdate = true;
}

/* ------------------------------------------------------------ câmera */

function Camera({ id, movimento, deslocamento }: { id: string; movimento: boolean; deslocamento: number }) {
  const { camera, size } = useThree();
  const cam = camera as THREE.PerspectiveCamera;
  const alvo = useRef(new THREE.Vector3());
  const destino = useRef(new THREE.Vector3());
  const t = useRef(1);
  const origem = useRef(new THREE.Vector3());
  const alvoOrigem = useRef(new THREE.Vector3());
  const alvoDestino = useRef(new THREE.Vector3());
  const ultimo = useRef('');

  useLayoutEffect(() => {
    const c = CFG[id].camera;
    alvoDestino.current.fromArray(c.alvo);
    destino.current.fromArray(c.pos);
    // afasta ou aproxima a câmera para o conteúdo caber no palco, qualquer que seja a proporção
    const enq = CFG[id].enquadramento as number | undefined;
    if (enq) {
      const meiaV = (c.fov * Math.PI) / 360;
      const meiaH = Math.atan(Math.tan(meiaV) * (size.width / Math.max(1, size.height)));
      const d = enq / Math.tan(Math.min(meiaV, meiaH));
      destino.current.sub(alvoDestino.current).setLength(d).add(alvoDestino.current);
    }
    cam.fov = c.fov;
    cam.near = 0.05;
    cam.far = 4000;
    const novo = ultimo.current !== id;
    ultimo.current = id;
    if (movimento && novo) {
      // chega de mais longe, na mesma direção: a viagem entre estações
      origem.current.copy(destino.current).sub(alvoDestino.current).multiplyScalar(1.7).add(alvoDestino.current);
      alvoOrigem.current.copy(alvoDestino.current);
      t.current = 0;
    } else if (!movimento) {
      t.current = 1;
    }
    cam.updateProjectionMatrix();
  }, [id, movimento, cam, size.width, size.height]);

  useEffect(() => {
    const w = size.width;
    const h = size.height;
    if (deslocamento) cam.setViewOffset(w, h, -w * deslocamento, 0, w, h);
    else cam.clearViewOffset();
    cam.updateProjectionMatrix();
  }, [size, deslocamento, cam]);

  useFrame((_, dt) => {
    if (t.current < 1) t.current = Math.min(1, t.current + dt / 1.6);
    const e = 1 - Math.pow(1 - t.current, 3);
    cam.position.lerpVectors(origem.current, destino.current, t.current >= 1 ? 1 : e);
    alvo.current.lerpVectors(alvoOrigem.current, alvoDestino.current, e);
    cam.lookAt(alvo.current);
  });
  return null;
}

/* ------------------------------------------------------------ estações */

function useArrasto(grupo: React.RefObject<THREE.Object3D | null>) {
  const { gl } = useThree();
  const giro = useRef({ y: 0, x: 0, vy: 0, ativo: false, px: 0, py: 0 });
  useEffect(() => {
    const el = gl.domElement;
    el.style.touchAction = 'pan-y';
    const down = (e: PointerEvent) => {
      giro.current.ativo = true;
      giro.current.px = e.clientX;
      giro.current.py = e.clientY;
    };
    const move = (e: PointerEvent) => {
      const g = giro.current;
      if (!g.ativo) return;
      const dx = e.clientX - g.px;
      const dy = e.clientY - g.py;
      g.px = e.clientX;
      g.py = e.clientY;
      g.y += dx * 0.006;
      g.vy = dx * 0.006;
      if (e.pointerType === 'mouse') g.x = Math.max(-0.5, Math.min(0.5, g.x + dy * 0.004));
    };
    const up = () => (giro.current.ativo = false);
    el.addEventListener('pointerdown', down);
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => {
      el.removeEventListener('pointerdown', down);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
  }, [gl]);
  useFrame(() => {
    const g = giro.current;
    if (!g.ativo) {
      g.y += g.vy;
      g.vy *= 0.92;
    }
    if (grupo.current) {
      grupo.current.rotation.y = g.y;
      grupo.current.rotation.x = g.x;
    }
  });
}

function linhaCirculo(raio: number, cor: string, opacidade = 0.8, segmentos = 256) {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i < segmentos; i++) {
    const a = (i / segmentos) * Math.PI * 2;
    pts.push(new THREE.Vector3(raio * Math.cos(a), 0, raio * Math.sin(a)));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color: cor, transparent: true, opacity: opacidade, depthWrite: false });
  return new THREE.LineLoop(geo, mat);
}

function Modelo({ id, valor, movimento, onPronto, software }: Omit<PalcoProps, 'deslocamento'> & { software: boolean }) {
  const gltf = useLoader(GLTFLoader, url(id));
  const { gl } = useThree();
  const cena = useMemo(() => {
    const c = preparar(gltf.scene, id);
    // filtro anisotrópico: texturas nítidas em ângulos rasantes (anéis, disco, limbo)
    const aniso = gl.capabilities.getMaxAnisotropy();
    c.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (!m || !('map' in m)) return;
      for (const t of [m.map, m.emissiveMap, m.normalMap, m.alphaMap, m.roughnessMap]) {
        if (t) {
          t.anisotropy = aniso;
          t.needsUpdate = true;
        }
      }
    });
    return c;
  }, [gltf, id, gl]);
  const grupo = useRef<THREE.Group>(null);
  const extras = useRef<THREE.Group>(null);
  const relogio = useRef(0);
  const { size, viewport, camera } = useThree();
  const cfg = CFG[id];
  const est = estacoes.find((e) => e.id === id)!;
  useArrasto(grupo);

  // buraco negro: traçado de raios em tela cheia com as texturas do GLB (disco e céu)
  const buraco = useMemo(() => {
    if (id !== 'buraco-negro') return null;
    // a geometria do GLB é só referência; quem desenha é o traçado de raios
    cena.visible = false;
    // sem placa de vídeo o traçado fica lento demais: o pôster traçado no Blender permanece
    if (software) return null;
    const mapa = (nome: string) => ((cena.getObjectByName(nome) as THREE.Mesh).material as THREE.MeshStandardMaterial).emissiveMap!;
    const malha = criarBuracoNegro(mapa('disco'), mapa('ceu'));
    cena.visible = false;
    return malha;
  }, [cena, id, software]);
  const setDpr = useThree((s) => s.setDpr);
  useEffect(() => {
    if (!buraco) return;
    // cada pixel integra uma geodésica: resolução um pouco menor mantém a fluidez
    setDpr(Math.min(1.25, window.devicePixelRatio || 1));
    return () => setDpr([1, 2]);
  }, [buraco, setDpr]);

  // escala dos pontos depende da altura do canvas e do campo de visão
  useEffect(() => {
    const fov = ((camera as THREE.PerspectiveCamera).fov * Math.PI) / 180;
    const [, mult] = GANHO[id] ?? [1, 2];
    const escala = ((size.height * viewport.dpr) / (2 * Math.tan(fov / 2))) * mult;
    cena.traverse((o) => {
      const m = (o as THREE.Points).material as THREE.ShaderMaterial | undefined;
      if (m?.uniforms?.escala) m.uniforms.escala.value = escala;
    });
  }, [cena, size, viewport.dpr, camera, id]);

  // objetos de cada estação que dependem do controle
  const dados = useMemo(() => {
    const d: Record<string, unknown> = {};
    if (id === 'sistema-solar') {
      d.planetas = PLANETAS.map(([, a], i) => {
        const nome = ['mercurio', 'venus', 'terra', 'marte', 'jupiter', 'saturno', 'urano', 'netuno'][i];
        const obj = cena.getObjectByName(nome)!;
        const R = Math.hypot(obj.position.x, obj.position.z);
        const fase = Math.atan2(-obj.position.z, obj.position.x);
        return { obj, R, fase, w: (2 * Math.PI) / (8 * periodoAnos(a)) };
      });
      d.aneis = cena.getObjectByName('saturno-aneis');
      const sol = cena.getObjectByName('sol') as THREE.Mesh;
      if (sol) limbo(sol.material as THREE.MeshStandardMaterial, 0.55);
    }
    if (id === 'estrelas') {
      const est = cena.getObjectByName('estrela') as THREE.Mesh;
      limbo(est.material as THREE.MeshStandardMaterial);
    }
    return d;
  }, [cena, id]);

  const sonda = useMemo(() => {
    if (id !== 'sistema-solar') return null;
    const g = new THREE.Group();
    g.add(linhaCirculo(1, '#e9f2ee', 0.85));
    const ponto = new THREE.Mesh(new THREE.SphereGeometry(0.22, 20, 12), new THREE.MeshBasicMaterial({ color: '#f4f7f2' }));
    ponto.name = 'ponto';
    g.add(ponto);
    return g;
  }, [id]);

  const anelGalaxia = useMemo(() => {
    if (id !== 'galaxias') return null;
    const g = new THREE.Group();
    g.add(linhaCirculo(1, '#b9e2df', 0.9));
    const ponto = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 10), new THREE.MeshBasicMaterial({ color: '#ffffff' }));
    ponto.name = 'ponto';
    g.add(ponto);
    return g;
  }, [id]);

  const pulso = useMemo(() => {
    if (id !== 'luz') return null;
    const g = new THREE.Group();
    const bola = new THREE.Mesh(new THREE.SphereGeometry(0.075, 20, 12), new THREE.MeshBasicMaterial({ color: new THREE.Color(2.4, 2.0, 1.3) }));
    bola.name = 'bola';
    const feixe = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1, 8), new THREE.MeshBasicMaterial({ color: new THREE.Color(1.6, 1.25, 0.8) }));
    feixe.name = 'feixe';
    feixe.rotation.z = Math.PI / 2;
    g.add(bola, feixe);
    return g;
  }, [id]);

  const halo = useMemo(() => {
    if (id !== 'estrelas' && id !== 'sistema-solar') return null;
    const c = document.createElement('canvas');
    c.width = c.height = 256;
    const g = c.getContext('2d')!;
    const grad = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    grad.addColorStop(0, 'rgba(255,255,255,0.55)');
    grad.addColorStop(0.32, 'rgba(255,255,255,0.22)');
    grad.addColorStop(0.6, 'rgba(255,255,255,0.05)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 256, 256);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, color: '#ffd9a8' }));
    s.scale.setScalar(id === 'estrelas' ? 3.6 : 7.5);
    s.renderOrder = -1;
    return s;
  }, [id]);

  const regua = useMemo(() => {
    if (id !== 'teia-cosmica') return null;
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-0.5, 0, 0), new THREE.Vector3(0.5, 0, 0),
      new THREE.Vector3(-0.5, -0.02, 0), new THREE.Vector3(-0.5, 0.02, 0),
      new THREE.Vector3(0.5, -0.02, 0), new THREE.Vector3(0.5, 0.02, 0),
    ]);
    return new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: '#f1efe6', depthTest: false, transparent: true }));
  }, [id]);

  const grade = useMemo(() => {
    if (id !== 'expansao') return null;
    const base = cena.getObjectByName('galaxia') as THREE.Points;
    base.visible = false;
    const lado = cfg.lado as number;
    const meio = (lado - 1) / 2;
    const g = new THREE.Group();
    let semente = 7;
    const rnd = () => ((semente = (semente * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < lado; i++)
      for (let j = 0; j < lado; j++)
        for (let k = 0; k < lado; k++) {
          const p = new THREE.Points(base.geometry, base.material);
          p.frustumCulled = false;
          p.userData.comovel = new THREE.Vector3(i - meio, j - meio, k - meio).multiplyScalar(cfg.passo as number);
          p.rotation.set(rnd() * 6.28, rnd() * 6.28, rnd() * 6.28);
          g.add(p);
        }
    const marca = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(1, 0, 0)]),
      new THREE.LineBasicMaterial({ color: '#e9d6a8', transparent: true, opacity: 0.9 }),
    );
    marca.name = 'marca';
    g.add(marca);
    return g;
  }, [cena, cfg, id]);

  // primeiro quadro desenhado com o modelo: a página pode esconder o pôster
  const avisou = useRef(false);
  useFrame(() => {
    if (id === 'buraco-negro' && !buraco) return;
    if (!avisou.current) {
      avisou.current = true;
      requestAnimationFrame(() => onPronto(id));
    }
  });

  useFrame((_, dtReal) => {
    const dt = movimento ? Math.min(dtReal, 0.05) : 0;
    relogio.current += dt;
    const t = relogio.current;
    const v = valor;
    if (id === 'luz') {
      const terra = cena.getObjectByName('terra');
      const nuvens = cena.getObjectByName('nuvens');
      if (terra) terra.rotation.y += dt * 0.05;
      if (nuvens) nuvens.rotation.y += dt * 0.062;
      const lua = (cfg.lua as number[])[0];
      const f = (v - est.controle.min) / (est.controle.max - est.controle.min);
      const x0 = 1.0;
      const x1 = lua - 0.273;
      const x = x0 + (x1 - x0) * f;
      const bola = pulso!.getObjectByName('bola')!;
      const feixe = pulso!.getObjectByName('feixe')!;
      bola.position.set(x, 0, 0);
      feixe.visible = x - x0 > 0.01;
      feixe.scale.set(1, Math.max(0.001, x - x0), 1);
      feixe.position.set((x + x0) / 2, 0, 0);
    }
    if (id === 'sistema-solar') {
      const ps = dados.planetas as { obj: THREE.Object3D; R: number; fase: number; w: number }[];
      for (const p of ps) {
        const a = p.fase + p.w * t;
        p.obj.position.set(p.R * Math.cos(a), 0, -p.R * Math.sin(a));
        p.obj.rotation.y += dt * 0.4;
      }
      const aneis = dados.aneis as THREE.Object3D | undefined;
      const sat = ps[5].obj;
      if (aneis) aneis.position.copy(sat.position);
      const sol = cena.getObjectByName('sol');
      if (sol) sol.rotation.y += dt * 0.03;
      const R = raioOrbitaVisual(v);
      const circ = sonda!.children[0];
      circ.scale.setScalar(R);
      const ponto = sonda!.getObjectByName('ponto')!;
      const a = (2 * Math.PI * t) / (8 * periodoAnos(v));
      ponto.position.set(R * Math.cos(a), 0, -R * Math.sin(a));
    }
    if (id === 'saturno' && grupo.current) {
      const c = CFG[id].camera.pos;
      const elev = Math.atan2(c[1], c[2]);
      cena.rotation.x = (v * Math.PI) / 180 - elev;
      cena.rotation.z = -0.18;
      const globo = cena.getObjectByName('saturno');
      if (globo) globo.rotation.y += dt * 0.08;
    }
    if (id === 'estrelas') {
      const est3 = cena.getObjectByName('estrela') as THREE.Mesh;
      const m = est3.material as THREE.MeshStandardMaterial;
      const [r, g, b] = corCorpoNegro(v);
      const brilho = 1.6 + 0.35 * Math.log10(Math.max(0.05, (v / 5772) ** 4));
      m.emissive.setRGB(r, g, b, THREE.SRGBColorSpace);
      m.emissiveIntensity = Math.min(1.25, Math.max(0.55, 0.45 + 0.35 * brilho));
      if (halo) {
        (halo.material as THREE.SpriteMaterial).color.setRGB(r, g, b, THREE.SRGBColorSpace);
        halo.scale.setScalar(2.6 + 0.5 * Math.max(0, brilho));
      }
      est3.rotation.y += dt * 0.04;
      const campo = cena.getObjectByName('campo');
      if (campo) campo.rotation.y += dt * 0.004;
    }
    if (buraco && grupo.current) {
      // a frequência orbital cai com 1/M; a escala de tempo da cena é logarítmica na massa
      atualizarBuracoNegro(buraco, camera as THREE.PerspectiveCamera, grupo.current, dt, 26 / (1 + 0.55 * v));
    }
    if (id === 'galaxias') {
      const gal = cena.getObjectByName('galaxia');
      if (gal) gal.rotation.y -= dt * 0.03;
      anelGalaxia!.children[0].scale.setScalar(v);
      // curva de rotação plana: velocidade angular ∝ 1/r
      const ponto = anelGalaxia!.getObjectByName('ponto')!;
      const a = -(t * 2.4) / v;
      ponto.position.set(v * Math.cos(a), 0, v * Math.sin(a));
    }
    if (id === 'teia-cosmica') {
      const teia = cena.getObjectByName('teia');
      if (teia) teia.rotation.y += dt * 0.012;
      regua!.scale.set(v, 40, 1);
      regua!.position.set(0, -54, 30);
    }
    if (id === 'expansao' && grade) {
      for (const p of grade.children) {
        const c = p.userData.comovel as THREE.Vector3 | undefined;
        if (c) p.position.copy(c).multiplyScalar(v);
        else if (p.name === 'marca') p.scale.set((cfg.passo as number) * v, 1, 1);
      }
      grade.rotation.y += dt * 0.02;
    }
    if (id === 'luz-fossil') {
      const s = cena.getObjectByName('cmb') as THREE.Mesh;
      s.rotation.y += dt * 0.025;
      const m = s.material as THREE.MeshStandardMaterial;
      const T = temperaturaCmb(v);
      // abaixo de ~800 K (ponto de Draper) a radiação não é visível: cores falsas do mapa
      const f = Math.min(1, Math.max(0, (T - 800) / 2200));
      const [r, g, b] = corCorpoNegro(Math.max(1000, T));
      m.emissive.setRGB(1 + (r * 2.2 - 1) * f, 1 + (g * 2.2 - 1) * f, 1 + (b * 2.2 - 1) * f, THREE.SRGBColorSpace);
      m.emissiveIntensity = 1 + 0.6 * f;
    }
  });

  const luzSol = cfg.sol as number[] | undefined;
  return (
    <>
      {luzSol && <directionalLight position={[luzSol[0] * 20, luzSol[1] * 20, luzSol[2] * 20]} intensity={2.8} />}
      {id === 'sistema-solar' && <pointLight position={[0, 0, 0]} intensity={2.6} decay={0} distance={0} />}
      <ambientLight intensity={id === 'luz' || id === 'saturno' || id === 'sistema-solar' ? 0.05 : 0} />
      <group ref={grupo}>
        <primitive object={cena} />
        <group ref={extras}>
          {sonda && <primitive object={sonda} />}
          {anelGalaxia && <primitive object={anelGalaxia} />}
          {pulso && <primitive object={pulso} />}
          {grade && <primitive object={grade} />}
          {halo && <primitive object={halo} />}
        </group>
      </group>
      {regua && <primitive object={regua} />}
      {buraco && <primitive object={buraco} />}
    </>
  );
}

/** Renderizador por software (sem placa de vídeo): meia resolução e 8 quadros por segundo. */
function useSoftware() {
  const gl = useThree((s) => s.gl);
  const setDpr = useThree((s) => s.setDpr);
  const setFrameloop = useThree((s) => s.setFrameloop);
  const invalidate = useThree((s) => s.invalidate);
  const [software, setSoftware] = useState(false);
  useEffect(() => {
    const ctx = gl.getContext();
    const ext = ctx.getExtension('WEBGL_debug_renderer_info');
    const nome = ext ? String(ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : '';
    if (!/swiftshader|llvmpipe|software|basic render/i.test(nome)) return;
    setSoftware(true);
    setDpr(0.5);
    setFrameloop('demand');
    const t = setInterval(() => invalidate(), 125);
    return () => clearInterval(t);
  }, [gl, setDpr, setFrameloop, invalidate]);
  return software;
}

function Conteudo(props: PalcoProps & { vizinhos: string[] }) {
  const software = useSoftware();
  return (
    <>
      <Camera id={props.id} movimento={props.movimento} deslocamento={props.deslocamento} />
      <Suspense fallback={null}>
        <Modelo key={props.id} id={props.id} valor={props.valor} movimento={props.movimento} onPronto={props.onPronto} software={software} />
      </Suspense>
      <Precarregar ids={props.vizinhos} />
    </>
  );
}

function Precarregar({ ids }: { ids: string[] }) {
  useEffect(() => {
    const t = setTimeout(() => ids.forEach((i) => useLoader.preload(GLTFLoader, url(i))), 900);
    return () => clearTimeout(t);
  }, [ids]);
  return null;
}

export default function Palco({ id, valor, movimento, deslocamento, onPronto }: PalcoProps) {
  const i = estacoes.findIndex((e) => e.id === id);
  const vizinhos = [estacoes[i + 1]?.id, estacoes[i - 1]?.id].filter(Boolean) as string[];
  return (
    <Canvas
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true, toneMapping: THREE.AgXToneMapping, powerPreference: 'high-performance' }}
      camera={{ fov: 40, position: [0, 0, 10] }}
      frameloop="always"
      onCreated={({ gl }) => gl.setClearColor(0x000000, 0)}
    >
      <Conteudo id={id} valor={valor} movimento={movimento} deslocamento={deslocamento} onPronto={onPronto} vizinhos={vizinhos} />
    </Canvas>
  );
}
