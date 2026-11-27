import { useFrame, useLoader } from '@react-three/fiber';
import * as THREE from 'three';
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

/*
 * Camada visual das bancadas: transforma a geometria didática do modelo físico (pontos e
 * segmentos de src/lib/model.ts) em formas legíveis no padrão da viagem — tubos com brilho
 * no lugar de linhas de 1 px, setas sólidas, superfícies contínuas no lugar de malhas de arame,
 * volumes translúcidos no lugar de cubos de arame e corpos com as texturas do Blender.
 * Nada aqui muda a física: as formas são derivadas dos mesmos números que o gráfico usa.
 */

type Seg = number[];
const EPS = 1e-6;
const iguais = (a: number[], i: number, b: number[], j: number) =>
  Math.abs(a[i] - b[j]) < EPS && Math.abs(a[i + 1] - b[j + 1]) < EPS && Math.abs(a[i + 2] - b[j + 2]) < EPS;

/** Assinatura barata do conteúdo: evita reconstruir malhas quando o modelo devolve os mesmos números. */
export function assinatura(segmentos: Seg[]) {
  let h = segmentos.length;
  for (let i = 0; i < segmentos.length; i++) {
    const s = segmentos[i];
    h += (s[0] * 1.31 + s[1] * 7.13 + s[2] * 3.77 + s[3] * 5.19 + s[4] * 2.41 + s[5] * 9.07) * ((i % 17) + 1);
  }
  return segmentos.length + ':' + h.toFixed(5);
}

/** Separa as setas (haste + duas farpas que partem da ponta) do restante dos traços. */
export function separarSetas(segmentos: Seg[]) {
  const setas: { base: THREE.Vector3; ponta: THREE.Vector3 }[] = [];
  const resto: Seg[] = [];
  for (let i = 0; i < segmentos.length; i++) {
    const a = segmentos[i],
      b = segmentos[i + 1],
      c = segmentos[i + 2];
    if (b && c && iguais(a, 3, b, 0) && iguais(a, 3, c, 0) && !iguais(b, 3, c, 3)) {
      setas.push({ base: new THREE.Vector3(a[0], a[1], a[2]), ponta: new THREE.Vector3(a[3], a[4], a[5]) });
      i += 2;
    } else resto.push(a);
  }
  return { setas, resto };
}

/** Agrupa segmentos contíguos em polilinhas. */
export function polilinhas(segmentos: Seg[]): THREE.Vector3[][] {
  const out: THREE.Vector3[][] = [];
  let atual: THREE.Vector3[] = [];
  let anterior: Seg | null = null;
  for (const s of segmentos) {
    if (anterior && iguais(anterior, 3, s, 0)) atual.push(new THREE.Vector3(s[3], s[4], s[5]));
    else {
      if (atual.length > 1) out.push(atual);
      atual = [new THREE.Vector3(s[0], s[1], s[2]), new THREE.Vector3(s[3], s[4], s[5])];
    }
    anterior = s;
  }
  if (atual.length > 1) out.push(atual);
  return out;
}

/** Tubos contínuos para todas as polilinhas, numa só geometria com cor por polilinha. */
export function geometriaTubos(segmentos: Seg[], raio: number, cores: string[]) {
  const partes: THREE.BufferGeometry[] = [];
  const cor = new THREE.Color();
  polilinhas(segmentos).forEach((linha, k) => {
    const fechada = linha.length > 3 && linha[0].distanceTo(linha[linha.length - 1]) < 1e-4;
    const pts = fechada ? linha.slice(0, -1) : linha;
    const curva =
      pts.length > 2 ? new THREE.CatmullRomCurve3(pts, fechada, 'centripetal') : new THREE.LineCurve3(pts[0], pts[1]);
    const n = pts.length > 2 ? Math.min(480, pts.length * 2) : 1;
    const g = new THREE.TubeGeometry(curva, n, raio, 8, fechada);
    cor.set(cores[k % cores.length]);
    const c = new Float32Array(g.getAttribute('position').count * 3);
    for (let i = 0; i < c.length; i += 3) c.set([cor.r, cor.g, cor.b], i);
    g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    partes.push(g);
  });
  if (!partes.length) return new THREE.BufferGeometry();
  const g = mergeGeometries(partes, false) ?? new THREE.BufferGeometry();
  partes.forEach((p) => p.dispose());
  return g;
}

export function Tubos({ segmentos, raio, cores }: { segmentos: Seg[]; raio: number; cores: string[] }) {
  const chave = assinatura(segmentos);
  const ultimo = useRef(segmentos);
  ultimo.current = segmentos;
  const listaCores = cores.join();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const geo = useMemo(() => geometriaTubos(ultimo.current, raio, listaCores.split(',')), [chave, raio, listaCores]);
  useEffect(() => () => geo.dispose(), [geo]);
  return (
    <mesh geometry={geo} frustumCulled={false}>
      <meshBasicMaterial vertexColors toneMapped={false} />
    </mesh>
  );
}

/** Setas sólidas (haste cilíndrica e ponta cônica), instanciadas. */
export function Setas({ setas, cor }: { setas: { base: THREE.Vector3; ponta: THREE.Vector3 }[]; cor: string }) {
  const hastes = useRef<THREE.InstancedMesh>(null);
  const pontas = useRef<THREE.InstancedMesh>(null);
  const geoHaste = useMemo(() => new THREE.CylinderGeometry(1, 1, 1, 12).translate(0, 0.5, 0), []);
  const geoPonta = useMemo(() => new THREE.ConeGeometry(1, 1, 18).translate(0, 0.5, 0), []);
  const n = Math.max(1, setas.length);
  useLayoutEffect(() => {
    const m = new THREE.Matrix4(),
      q = new THREE.Quaternion(),
      s = new THREE.Vector3(),
      d = new THREE.Vector3(),
      y = new THREE.Vector3(0, 1, 0),
      pescoco = new THREE.Vector3();
    setas.forEach(({ base, ponta }, i) => {
      d.subVectors(ponta, base);
      const len = d.length();
      if (len < 1e-6) {
        hastes.current?.setMatrixAt(i, m.makeScale(0, 0, 0));
        pontas.current?.setMatrixAt(i, m.makeScale(0, 0, 0));
        return;
      }
      d.divideScalar(len);
      q.setFromUnitVectors(y, d);
      const cabeca = len * 0.32;
      const r = Math.min(0.016, Math.max(0.0035, len * 0.08));
      s.set(r, len - cabeca, r);
      hastes.current?.setMatrixAt(i, m.compose(base, q, s));
      pescoco.copy(base).addScaledVector(d, len - cabeca);
      const rc = Math.max(r * 2.2, len * 0.16);
      s.set(rc, cabeca, rc);
      pontas.current?.setMatrixAt(i, m.compose(pescoco, q, s));
    });
    [hastes.current, pontas.current].forEach((malha) => {
      if (!malha) return;
      malha.count = setas.length;
      malha.instanceMatrix.needsUpdate = true;
    });
  }, [setas, n]);
  return (
    <>
      <instancedMesh key={'h' + n} ref={hastes} args={[geoHaste, undefined, n]} frustumCulled={false}>
        <meshStandardMaterial color={cor} emissive={cor} emissiveIntensity={0.5} roughness={0.4} />
      </instancedMesh>
      <instancedMesh key={'p' + n} ref={pontas} args={[geoPonta, undefined, n]} frustumCulled={false}>
        <meshStandardMaterial color={cor} emissive={cor} emissiveIntensity={0.65} roughness={0.35} />
      </instancedMesh>
    </>
  );
}

/* ------------------------------------------------------------ superfícies de revolução */

let texturaGrade: THREE.Texture | null = null;
function grade() {
  if (texturaGrade) return texturaGrade;
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d')!;
  g.fillStyle = '#173a3a';
  g.fillRect(0, 0, 512, 512);
  g.strokeStyle = '#9fdcd2';
  g.globalAlpha = 0.7;
  g.lineWidth = 5;
  for (let i = 0; i <= 512; i += 64) {
    g.beginPath();
    g.moveTo(i, 0);
    g.lineTo(i, 512);
    g.stroke();
    g.beginPath();
    g.moveTo(0, i);
    g.lineTo(512, i);
    g.stroke();
  }
  texturaGrade = new THREE.CanvasTexture(c);
  texturaGrade.wrapS = texturaGrade.wrapT = THREE.RepeatWrapping;
  texturaGrade.repeat.set(12, 4);
  texturaGrade.anisotropy = 8;
  texturaGrade.colorSpace = THREE.SRGBColorSpace;
  return texturaGrade;
}

/**
 * Superfície de revolução reconstruída dos segmentos. No eixo y (curvatura) o perfil é a altura
 * média por faixa de raio; no eixo x (espectro) é o maior raio por faixa da posição axial.
 */
export function Superficie({ segmentos, eixo }: { segmentos: Seg[]; eixo: 'y' | 'x' }) {
  const chave = assinatura(segmentos);
  const ultimo = useRef(segmentos);
  ultimo.current = segmentos;
  const geo = useMemo(() => {
    const pares: [number, number][] = [];
    for (const s of ultimo.current)
      for (const k of [0, 3]) {
        const x = s[k],
          y = s[k + 1],
          z = s[k + 2];
        // [chave da faixa, valor]
        pares.push(eixo === 'y' ? [Math.hypot(x, z), y] : [x, Math.hypot(y, z)]);
      }
    if (pares.length < 4) return null;
    let min = Infinity,
      max = -Infinity;
    for (const p of pares) {
      min = Math.min(min, p[0]);
      max = Math.max(max, p[0]);
    }
    const n = 64;
    const soma = new Float64Array(n),
      cont = new Float64Array(n);
    for (const [k, v] of pares) {
      const i = Math.min(n - 1, Math.floor(((k - min) / Math.max(1e-9, max - min)) * n));
      if (eixo === 'y') {
        soma[i] += v;
        cont[i]++;
      } else {
        soma[i] = Math.max(soma[i], v);
        cont[i] = 1;
      }
    }
    const perfil: THREE.Vector2[] = [];
    for (let i = 0; i < n; i++) {
      if (!cont[i]) continue;
      const k = min + ((i + 0.5) / n) * (max - min);
      const v = soma[i] / cont[i];
      perfil.push(eixo === 'y' ? new THREE.Vector2(k, v) : new THREE.Vector2(Math.max(0.002, v), k));
    }
    if (!perfil.length) return null;
    if (eixo === 'y') perfil.unshift(new THREE.Vector2(min, perfil[0].y));
    else {
      perfil.unshift(new THREE.Vector2(0.001, min));
      perfil.push(new THREE.Vector2(0.001, max));
    }
    const g = new THREE.LatheGeometry(perfil, 96);
    if (eixo === 'x') {
      g.rotateZ(-Math.PI / 2);
      // cor ao longo da frequência: vermelho nas baixas, branco quente nas altas
      const pos = g.getAttribute('position');
      const c = new Float32Array(pos.count * 3);
      const cor = new THREE.Color();
      for (let i = 0; i < pos.count; i++) {
        const t = (pos.getX(i) - min) / Math.max(1e-9, max - min);
        cor.setHSL(0.02 + 0.1 * t, 0.85 - 0.45 * t, 0.42 + 0.3 * t);
        c.set([cor.r, cor.g, cor.b], i * 3);
      }
      g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    }
    g.computeVertexNormals();
    return g;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave, eixo]);
  useEffect(() => () => geo?.dispose(), [geo]);
  if (!geo) return null;
  return eixo === 'y' ? (
    <mesh geometry={geo}>
      <meshStandardMaterial map={grade()} roughness={0.55} metalness={0.05} side={THREE.DoubleSide} />
    </mesh>
  ) : (
    <mesh geometry={geo}>
      <meshStandardMaterial
        vertexColors
        emissive="#4a1d08"
        emissiveIntensity={0.6}
        roughness={0.4}
        side={THREE.DoubleSide}
        transparent
        opacity={0.9}
      />
    </mesh>
  );
}

/**
 * Espectro em relevo: a curva B_ν (perfil da malha da bancada no plano z = 0) vira uma placa
 * extrudada, com a cor indo do vermelho escuro nas baixas frequências ao branco quente nas altas.
 */
export function Espectro({ segmentos }: { segmentos: Seg[] }) {
  const chave = assinatura(segmentos);
  const ultimo = useRef(segmentos);
  ultimo.current = segmentos;
  const geo = useMemo(() => {
    let min = Infinity,
      max = -Infinity;
    for (const s of ultimo.current) for (const k of [0, 3]) {
      min = Math.min(min, s[k]);
      max = Math.max(max, s[k]);
    }
    // maior raio em cada abscissa amostrada pelo modelo (as faixas vazias ficam de fora)
    const topo = new Map<string, [number, number]>();
    for (const s of ultimo.current)
      for (const k of [0, 3]) {
        const chaveX = s[k].toFixed(4);
        const r = Math.hypot(s[k + 1], s[k + 2]);
        const atual = topo.get(chaveX);
        if (!atual || r > atual[1]) topo.set(chaveX, [s[k], r]);
      }
    const perfil = [...topo.values()].sort((a, b) => a[0] - b[0]);
    const forma = new THREE.Shape();
    const base = -0.55;
    forma.moveTo(min, base);
    for (const [x, r] of perfil) forma.lineTo(x, base + r * 1.6);
    forma.lineTo(max, base);
    forma.closePath();
    const g = new THREE.ExtrudeGeometry(forma, { depth: 0.36, bevelEnabled: true, bevelSize: 0.012, bevelThickness: 0.012, bevelSegments: 2, curveSegments: 4 });
    g.translate(0, 0, -0.18);
    const pos = g.getAttribute('position');
    const c = new Float32Array(pos.count * 3);
    const cor = new THREE.Color();
    for (let i = 0; i < pos.count; i++) {
      const t = Math.min(1, Math.max(0, (pos.getX(i) - min) / Math.max(1e-9, max - min)));
      cor.setHSL(0.0 + 0.11 * t, 0.85 - 0.5 * t, 0.36 + 0.4 * t);
      c.set([cor.r, cor.g, cor.b], i * 3);
    }
    g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    g.computeVertexNormals();
    return g;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);
  useEffect(() => () => geo.dispose(), [geo]);
  return (
    <mesh geometry={geo}>
      <meshStandardMaterial vertexColors emissive="#3a1406" emissiveIntensity={0.5} roughness={0.5} />
    </mesh>
  );
}

/* ------------------------------------------------------------ volumes translúcidos */

/** Cada grupo de 12 arestas consecutivas vira uma caixa de vidro (matéria em âmbar à esquerda, energia escura em verde-água). */
export function Caixas({ segmentos, bicolor }: { segmentos: Seg[]; bicolor: boolean }) {
  const caixas = useMemo(() => {
    const out: { centro: THREE.Vector3; tamanho: THREE.Vector3 }[] = [];
    for (let i = 0; i + 12 <= segmentos.length; i += 12) {
      const box = new THREE.Box3();
      for (const s of segmentos.slice(i, i + 12)) {
        box.expandByPoint(new THREE.Vector3(s[0], s[1], s[2]));
        box.expandByPoint(new THREE.Vector3(s[3], s[4], s[5]));
      }
      const tamanho = box.getSize(new THREE.Vector3());
      if (tamanho.x < 1e-4 || tamanho.y < 1e-4 || tamanho.z < 1e-4) continue;
      out.push({ centro: box.getCenter(new THREE.Vector3()), tamanho });
    }
    return out;
  }, [segmentos]);
  return (
    <>
      {caixas.map((c, i) => {
        const materia = bicolor && c.centro.x < 0;
        return (
          <mesh key={i} position={c.centro} scale={c.tamanho}>
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial
              color={materia ? '#e8b779' : '#8fd0c6'}
              emissive={materia ? '#6b4316' : '#1d5650'}
              emissiveIntensity={0.6}
              transparent
              opacity={0.3}
              roughness={0.15}
              depthWrite={false}
            />
          </mesh>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------ corpos com textura */

export type Corpo = { indice: number; nome: 'sol' | 'terra' | 'jupiter' | 'marte' | 'saturno'; raio: number };

/** Esferas com as texturas do Blender (do GLB do Sistema Solar) nas posições dos pontos do modelo. */
export function CorposTexturizados({ corpos, dots }: { corpos: Corpo[]; dots: number[][] }) {
  const gltf = useLoader(GLTFLoader, '/viagem/sistema-solar-m.glb');
  const malhas = useMemo(
    () =>
      corpos.map((c) => {
        const src = gltf.scene.getObjectByName(c.nome) as THREE.Mesh | undefined;
        const base = src?.material as THREE.MeshStandardMaterial | undefined;
        const mat =
          c.nome === 'sol'
            ? new THREE.MeshBasicMaterial({
                map: base?.emissiveMap ?? base?.map ?? null,
                color: new THREE.Color(1.15, 0.95, 0.8),
                toneMapped: false,
              })
            : new THREE.MeshStandardMaterial({ map: base?.map ?? null, roughness: 0.85, emissive: '#0b1a22', emissiveIntensity: 0.4 });
        const m = new THREE.Mesh(new THREE.SphereGeometry(1, 64, 32), mat);
        m.scale.setScalar(c.raio);
        return m;
      }),
    [gltf, corpos],
  );
  useLayoutEffect(() => {
    malhas.forEach((m, k) => {
      const d = dots[corpos[k].indice];
      if (d) m.position.set(d[0], d[1], d[2]);
    });
  }, [malhas, dots, corpos]);
  useFrame((_, dt) => malhas.forEach((m) => (m.rotation.y += Math.min(dt, 0.05) * 0.25)));
  return (
    <>
      {malhas.map((m, i) => (
        <primitive key={i} object={m} />
      ))}
    </>
  );
}

/* ------------------------------------------------------------ configuração por bancada */

export type Visual = {
  corpos?: Corpo[];
  superficie?: 'y' | 'x';
  caixas?: 'bicolor' | 'simples';
  tubo?: { raio: number; cores: string[] };
  setas?: string;
  semPontos?: boolean;
  /** índices dos pontos que viram galáxias, com a escala do modelo de galáxia */
  galaxias?: { indices: number[]; escala: number; ganho: number }[];
  /** espectro em relevo no lugar da superfície de revolução */
  espectro?: boolean;
  /** aproximação da câmera (1 = enquadramento padrão) */
  zoom?: number;
  /** galáxias em coordenadas comóveis dentro do cubo */
  galaxiasComoveis?: boolean;
  /** opacidade da malha de arame original (0 a esconde) */
  arame?: number;
};

const LUZ = '#ffd27a';
export const VISUAL: Record<string, Visual> = {
  gravitacao: {
    zoom: 0.62,
    corpos: [{ indice: 0, nome: 'terra', raio: 0.36 }],
    setas: '#e8b779',
    tubo: { raio: 0.006, cores: ['#5d8f8a'] },
    arame: 0,
  },
  'n-corpos': {
    corpos: [
      { indice: 0, nome: 'sol', raio: 0.11 },
      { indice: 1, nome: 'terra', raio: 0.05 },
      { indice: 2, nome: 'jupiter', raio: 0.075 },
    ],
    tubo: { raio: 0.006, cores: ['#64d8ff', '#e8b779'] },
    arame: 0,
  },
  ondas: { zoom: 0.8, tubo: { raio: 0.016, cores: ['#5d9c95', LUZ, '#5d9c95'] }, arame: 0 },
  campos: { zoom: 0.72, tubo: { raio: 0.012, cores: ['#8fd0c6'] }, setas: '#e8b779', arame: 0 },
  relatividade: { zoom: 0.78, tubo: { raio: 0.012, cores: [LUZ, '#cfe5e1', '#cfe5e1'] }, arame: 0 },
  curvatura: { zoom: 0.82, superficie: 'y', arame: 0.18 },
  lentes: {
    zoom: 0.7,
    corpos: [
      { indice: 0, nome: 'terra', raio: 0.09 },
      { indice: 1, nome: 'sol', raio: 0.085 },
    ],
    // a fonte à direita e as duas imagens que o observador vê na direção da lente
    galaxias: [
      { indices: [2], escala: 0.045, ganho: 0.16 },
      { indices: [3, 4], escala: 0.02, ganho: 0.22 },
    ],
    tubo: { raio: 0.007, cores: [LUZ] },
    arame: 0,
  },
  expansao: { setas: '#8fd0c6', arame: 0 },
  'fator-de-escala': { zoom: 0.8, caixas: 'simples', galaxiasComoveis: true, semPontos: true, arame: 0.7 },
  'energia-escura': { caixas: 'bicolor', semPontos: true, arame: 0.55 },
  cmb: { zoom: 0.8, espectro: true, arame: 0 },
};
