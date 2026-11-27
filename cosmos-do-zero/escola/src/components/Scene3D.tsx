import { Canvas, useFrame, useLoader, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { Suspense, useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { orbitGuide } from '../lib/model';
import { materialGalaxia } from './viagem/galaxia';
import { atualizarBuracoNegro, criarBuracoNegro } from './viagem/buracoNegro';

/*
 * Cena 3D das bancadas, no mesmo padrão da viagem da página inicial: fundo do palco (#0c1517),
 * tone mapping AgX, esferas em alta resolução, estrelas com brilho próprio e, quando a bancada
 * trata de um objeto que a viagem já modelou no Blender, esse modelo como cena de fundo
 * (Sol, galáxia em rotação, teia cósmica, galáxias da expansão, buraco negro por traçado de raios).
 * Os pontos e segmentos continuam vindo do modelo físico da bancada (src/lib/model.ts).
 */

const guide = new Float32Array(orbitGuide.flat());
type Geo = {
  lab: string;
  dots: number[][];
  segments: number[][];
  referenceOrbit: number[][];
  orbital: boolean;
  center: number;
  turn: number;
  resetView: number;
};

const FUNDO = '#0c1517';
const ESTRELA = new THREE.Color('#ffbb54');
const CORPO = new THREE.Color('#64d8ff');
const modelo = (nome: string) => `/viagem/${nome}-m.glb`;

/** Fundos com movimento próprio pedem quadros contínuos; os demais só redesenham quando algo muda. */
const ANIMADOS = new Set(['rotacao', 'buracos-negros']);

let texturaHalo: THREE.Texture | null = null;
function halo() {
  if (texturaHalo) return texturaHalo;
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d')!;
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, 'rgba(255,255,255,0.75)');
  grad.addColorStop(0.3, 'rgba(255,255,255,0.25)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  texturaHalo = new THREE.CanvasTexture(c);
  texturaHalo.colorSpace = THREE.SRGBColorSpace;
  return texturaHalo;
}

/** Pontos com brilho suave e tamanho físico (mesmo desenho da viagem). */
function materialPontos(ganho: number, opacidade = 1) {
  return new THREE.ShaderMaterial({
    uniforms: { escala: { value: 400 }, ganho: { value: ganho }, opacidade: { value: opacidade } },
    vertexShader: /* glsl */ `
      attribute float _radius;
      attribute vec4 color;
      uniform float escala;
      varying vec3 vCor;
      void main() {
        vCor = color.rgb;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = clamp(2.0 * _radius * escala / -mv.z, 1.0, 24.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform float ganho;
      uniform float opacidade;
      varying vec3 vCor;
      void main() {
        vec2 p = gl_PointCoord * 2.0 - 1.0;
        float r2 = dot(p, p);
        if (r2 > 1.0) discard;
        gl_FragColor = vec4(vCor * ganho, exp(-3.0 * r2) * opacidade);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true,
  });
}

/** Escala dos pontos: pixels por unidade a 1 unidade de distância, vezes a escala do objeto. */
function useEscalaPontos(materiais: THREE.ShaderMaterial[], escalaObjeto: number, mult = 2) {
  const { size, viewport, camera } = useThree();
  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera;
    const fov = ((cam.isPerspectiveCamera ? cam.fov : 40) * Math.PI) / 180;
    const e = ((size.height * viewport.dpr) / (2 * Math.tan(fov / 2))) * escalaObjeto * mult;
    materiais.forEach((m) => (m.uniforms.escala.value = e));
  }, [materiais, escalaObjeto, mult, size, viewport.dpr, camera]);
}

/* ------------------------------------------------------------ fundos */

function FundoGalaxia() {
  const gltf = useLoader(GLTFLoader, modelo('galaxias'));
  const { pontos, material } = useMemo(() => {
    const src = gltf.scene.getObjectByName('galaxia') as THREE.Points;
    const material = materialGalaxia(1.1, 1);
    const pontos = new THREE.Points(src.geometry, material);
    pontos.frustumCulled = false;
    return { pontos, material };
  }, [gltf]);
  const lista = useMemo(() => [material], [material]);
  // os traçadores da bancada ficam em r/18 no plano inclinado de orbitPlane
  useEscalaPontos(lista, 1 / 18, 5);
  useFrame((_, dt) => {
    material.uniforms.tempo.value -= Math.min(dt, 0.05) * 0.9;
  });
  return <primitive object={pontos} scale={1 / 18} rotation={[-0.5707, 0, 0]} />;
}

function FundoTeia() {
  const gltf = useLoader(GLTFLoader, modelo('teia-cosmica'));
  const { pontos, material } = useMemo(() => {
    const src = gltf.scene.getObjectByName('teia') as THREE.Points;
    const material = materialPontos(0.28, 0.7);
    const pontos = new THREE.Points(src.geometry, material);
    pontos.frustumCulled = false;
    return { pontos, material };
  }, [gltf]);
  const lista = useMemo(() => [material], [material]);
  useEscalaPontos(lista, 2.1 / 62, 1.6);
  return <primitive object={pontos} scale={2.1 / 62} />;
}

function GalaxiasNosPontos({ dots }: { dots: number[][] }) {
  const gltf = useLoader(GLTFLoader, modelo('expansao'));
  const { grupo, material } = useMemo(() => {
    const src = gltf.scene.getObjectByName('galaxia') as THREE.Points;
    const material = materialGalaxia(0.16, 0.24);
    const grupo = new THREE.Group();
    let semente = 11;
    const rnd = () => ((semente = (semente * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 64; i++) {
      const p = new THREE.Points(src.geometry, material);
      p.frustumCulled = false;
      p.rotation.set(rnd() * 6.28, rnd() * 6.28, rnd() * 6.28);
      p.scale.setScalar(0.026);
      p.visible = false;
      grupo.add(p);
    }
    return { grupo, material };
  }, [gltf]);
  const lista = useMemo(() => [material], [material]);
  useEscalaPontos(lista, 0.026, 0.9);
  useLayoutEffect(() => {
    grupo.children.forEach((g, i) => {
      // o primeiro ponto é o observador; as galáxias ocupam os demais
      const d = dots[i + 1];
      g.visible = Boolean(d);
      if (d) g.position.set(d[0], d[1], d[2]);
    });
  }, [dots, grupo]);
  return <primitive object={grupo} />;
}

function FundoBuracoNegro({ dots, grupo }: { dots: number[][]; grupo: React.RefObject<THREE.Group | null> }) {
  const gltf = useLoader(GLTFLoader, modelo('buraco-negro'));
  const { camera } = useThree();
  // a bancada desenha o horizonte com raio `scale` e o raio emitido até (u + 4) scale = 1,65
  const escala = dots[0] ? (1.65 - dots[0][0]) / 4 : 0.3;
  const malha = useMemo(() => {
    const mapa = (nome: string) =>
      ((gltf.scene.getObjectByName(nome) as THREE.Mesh).material as THREE.MeshStandardMaterial).emissiveMap!;
    return criarBuracoNegro(mapa('disco'), mapa('ceu'), 1);
  }, [gltf]);
  useEffect(() => {
    (malha.material as THREE.ShaderMaterial).uniforms.escalaRs.value = escala;
  }, [malha, escala]);
  useFrame((_, dt) => {
    if (grupo.current) atualizarBuracoNegro(malha, camera as THREE.PerspectiveCamera, grupo.current, Math.min(dt, 0.05), 6);
  });
  return <primitive object={malha} />;
}

function SolNoCentro({ posicao, raio }: { posicao: number[]; raio: number }) {
  const gltf = useLoader(GLTFLoader, modelo('sistema-solar'));
  const { sol, brilho } = useMemo(() => {
    const src = gltf.scene.getObjectByName('sol') as THREE.Mesh;
    const mapa = (src.material as THREE.MeshStandardMaterial).emissiveMap;
    const sol = new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 32),
      new THREE.MeshBasicMaterial({ map: mapa, color: new THREE.Color(1.15, 0.95, 0.8), toneMapped: false }),
    );
    const brilho = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: halo(), color: '#ffc27a', blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }),
    );
    return { sol, brilho };
  }, [gltf]);
  useFrame((_, dt) => {
    sol.rotation.y += Math.min(dt, 0.05) * 0.15;
  });
  return (
    <group position={[posicao[0], posicao[1], posicao[2]]}>
      <primitive object={sol} scale={raio * 1.04} />
      <primitive object={brilho} scale={raio * 4.2} />
    </group>
  );
}

/* ------------------------------------------------------------ cena */

function Geometry({ lab, dots, segments, referenceOrbit, orbital, center, turn, resetView }: Geo) {
  const lines = useMemo(() => new THREE.BufferGeometry(), []);
  const referencePositions = useMemo(() => new Float32Array(referenceOrbit.flat()), [referenceOrbit]);
  const estrelas = useRef<THREE.InstancedMesh>(null);
  const corpos = useRef<THREE.InstancedMesh>(null);
  const halos = useRef<THREE.Group>(null);
  const giro = useRef<THREE.Group>(null);
  const matrix = useMemo(() => new THREE.Matrix4(), []);
  const { camera, gl, size, invalidate, setDpr } = useThree();
  const slowFrames = useRef(0);
  const comSol = orbital;
  const galaxiasNosPontos = lab === 'expansao';

  useFrame((_, dt) => {
    if (dt < 0.14 && dt > 0.036) {
      if (++slowFrames.current === 16 && gl.getPixelRatio() > 1) setDpr(1);
    } else slowFrames.current = 0;
  });
  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    controls.enablePan = false;
    controls.minDistance = 2;
    controls.maxDistance = 12;
    controls.minZoom = 0.7;
    controls.maxZoom = 4;
    controls.saveState();
    const redraw = () => invalidate();
    controls.addEventListener('change', redraw);
    return () => {
      controls.removeEventListener('change', redraw);
      controls.reset();
      controls.dispose();
    };
  }, [camera, gl, invalidate, resetView]);
  useLayoutEffect(() => {
    if (orbital && camera instanceof THREE.OrthographicCamera) {
      const px = Math.min(size.width / 6, size.height / 5.15);
      camera.left = -size.width / (2 * px);
      camera.right = -camera.left;
      camera.top = size.height / (2 * px);
      camera.bottom = -camera.top;
      camera.updateProjectionMatrix();
    }
    invalidate();
  }, [camera, orbital, size, resetView, invalidate]);

  const raio = (i: number) => {
    const scale = Math.min(size.width / 6, size.height / 5.15) || 1;
    const separation = orbital ? Math.hypot(...(dots[1] as [number, number, number])) : 0;
    return orbital
      ? Math.min(i === 0 ? separation * 0.45 : separation * 0.32, Math.max(i === 0 ? 0.102 : 0.072, (i === 0 ? 8 : 5.5) / scale))
      : dots.length > 12
        ? 0.024
        : 0.065;
  };
  const indicesEstrelas = useMemo(() => dots.map((_, i) => i).filter((i) => i % 3 === 0), [dots]);
  const indicesCorpos = useMemo(() => dots.map((_, i) => i).filter((i) => i % 3 !== 0), [dots]);

  useLayoutEffect(() => {
    const count = segments.length * 2;
    let pos = lines.getAttribute('position') as THREE.BufferAttribute | undefined;
    if (!pos || pos.count < count) {
      if (pos) lines.dispose();
      pos = new THREE.BufferAttribute(new Float32Array(Math.max(2, count) * 3), 3).setUsage(THREE.DynamicDrawUsage);
      lines.setAttribute('position', pos);
    }
    for (let i = 0; i < segments.length; i++) (pos.array as Float32Array).set(segments[i], i * 6);
    pos.needsUpdate = true;
    lines.setDrawRange(0, count);
    const preencher = (mesh: THREE.InstancedMesh | null, indices: number[], cor: THREE.Color) => {
      if (!mesh) return;
      // sem pontos deste tipo, nenhuma instância é desenhada (a instância reserva teria escala 1)
      mesh.count = indices.length;
      indices.forEach((i, k) => {
        const [x, y, z] = dots[i];
        // o Sol do Blender cobre o marcador do centro (que fica visível enquanto o modelo carrega);
        // nas galáxias da expansão, os pontos ficam pequenos
        const r = galaxiasNosPontos && i > 0 ? raio(i) * 0.35 : raio(i);
        mesh.setMatrixAt(k, matrix.makeScale(r, r, r).setPosition(x, y, z));
        mesh.setColorAt(k, cor);
      });
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    };
    preencher(estrelas.current, indicesEstrelas, ESTRELA);
    preencher(corpos.current, indicesCorpos, CORPO);
    if (halos.current) {
      halos.current.children.forEach((s, k) => {
        const i = indicesEstrelas[k];
        s.visible = i !== undefined && !(comSol && i === 0) && !galaxiasNosPontos;
        if (i !== undefined) {
          s.position.set(dots[i][0], dots[i][1], dots[i][2]);
          s.scale.setScalar(raio(i) * 5);
        }
      });
    }
    invalidate();
  }, [dots, segments, lines, orbital, matrix, size, invalidate, indicesEstrelas, indicesCorpos, comSol, galaxiasNosPontos]);
  useEffect(() => () => lines.dispose(), [lines]);

  const spritesHalo = useMemo(
    () =>
      Array.from({ length: 24 }, () => {
        const s = new THREE.Sprite(
          new THREE.SpriteMaterial({ map: halo(), color: '#ffb35c', blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }),
        );
        s.visible = false;
        return s;
      }),
    [],
  );

  return (
    <>
      <ambientLight intensity={0.35} />
      <directionalLight position={[-2, 3, 4]} intensity={2.4} />
      <group ref={giro} rotation={[0, turn, 0]}>
        <Suspense fallback={null}>
          {lab === 'rotacao' && <FundoGalaxia />}
          {lab === 'estruturas' && <FundoTeia />}
          {lab === 'buracos-negros' && <FundoBuracoNegro dots={dots} grupo={giro} />}
        </Suspense>
        <group position={[center, 0, 0]}>
          <Suspense fallback={null}>
            {comSol && dots[0] && <SolNoCentro posicao={dots[0]} raio={raio(0)} />}
            {galaxiasNosPontos && <GalaxiasNosPontos dots={dots} />}
          </Suspense>
          <lineSegments geometry={lines} frustumCulled={false}>
            <lineBasicMaterial color={orbital ? '#7fb7b0' : '#8fd0c6'} transparent opacity={0.85} />
          </lineSegments>
          {orbital && (
            <lineSegments>
              <bufferGeometry>
                <bufferAttribute attach="attributes-position" args={[guide, 3]} />
              </bufferGeometry>
              <lineBasicMaterial color="#2f4a49" />
            </lineSegments>
          )}
          {referencePositions.length > 0 && (
            <lineSegments>
              <bufferGeometry>
                <bufferAttribute attach="attributes-position" args={[referencePositions, 3]} />
              </bufferGeometry>
              <lineBasicMaterial color="#e8b779" />
            </lineSegments>
          )}
          <instancedMesh key={'e' + indicesEstrelas.length} args={[undefined, undefined, Math.max(1, indicesEstrelas.length)]} ref={estrelas} frustumCulled={false}>
            <sphereGeometry args={[1, 48, 32]} />
            <meshBasicMaterial toneMapped={false} />
          </instancedMesh>
          <instancedMesh key={'c' + indicesCorpos.length} args={[undefined, undefined, Math.max(1, indicesCorpos.length)]} ref={corpos} frustumCulled={false}>
            <sphereGeometry args={[1, 48, 32]} />
            <meshStandardMaterial roughness={0.55} metalness={0} emissive="#1a5f73" emissiveIntensity={0.9} toneMapped={false} />
          </instancedMesh>
          <group ref={halos}>
            {spritesHalo.map((s, i) => (
              <primitive key={i} object={s} />
            ))}
          </group>
        </group>
        {!orbital && lab !== 'buracos-negros' && (
          <polarGridHelper args={[2.2, 12, 6, 64, '#1d3233', '#162728']} position={[0, -1.45, 0]} />
        )}
      </group>
    </>
  );
}

export default function Scene3D({ onFail, ...scene }: Geo & { onFail: () => void }) {
  const frame = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const wrap = frame.current;
    function onLoss(e: Event) {
      e.preventDefault();
      onFail();
    }
    wrap?.addEventListener('webglcontextlost', onLoss, true);
    return () => wrap?.removeEventListener('webglcontextlost', onLoss, true);
  }, [onFail]);
  return (
    <div ref={frame} className="lab-webgl">
      <Canvas
        frameloop={ANIMADOS.has(scene.lab) ? 'always' : 'demand'}
        dpr={[1, 2]}
        orthographic={scene.orbital}
        camera={
          scene.orbital
            ? { position: [0.7, -2.1, 4.6], near: 0.1, far: 60, manual: true }
            : { position: [2.1, 1.7, 4.2], fov: 40 }
        }
        gl={{ antialias: true, alpha: false, toneMapping: THREE.AgXToneMapping }}
      >
        <color attach="background" args={[FUNDO]} />
        <Geometry {...scene} />
      </Canvas>
    </div>
  );
}
