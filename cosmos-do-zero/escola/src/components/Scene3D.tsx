import { Canvas, useFrame, useThree } from '@react-three/fiber';
import {
  BufferAttribute,
  BufferGeometry,
  Color,
  DynamicDrawUsage,
  InstancedMesh,
  Matrix4,
  OrthographicCamera,
  WebGLRenderer,
} from 'three';
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

import { orbitGuide } from '../lib/model';
const guide = new Float32Array(orbitGuide.flat());
type Geo = {
  dots: number[][];
  segments: number[][];
  referenceOrbit: number[][];
  orbital: boolean;
  center: number;
  turn: number;
  resetView: number;
};
const gold = new Color('#ffbb54'),
  ice = new Color('#64d8ff');

function Geometry({ dots, segments, referenceOrbit, orbital, center, turn, resetView }: Geo) {
  const lines = useMemo(() => new BufferGeometry(), []);
  const referencePositions = useMemo(() => new Float32Array(referenceOrbit.flat()), [referenceOrbit]);
  const markers = useRef<InstancedMesh>(null);
  const matrix = useMemo(() => new Matrix4(), []);
  const { camera, gl, size, invalidate, setDpr } = useThree();
  const slowFrames = useRef(0);
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
    if (orbital && camera instanceof OrthographicCamera) {
      const px = Math.min(size.width / 6, size.height / 5.15);
      camera.left = -size.width / (2 * px);
      camera.right = -camera.left;
      camera.top = size.height / (2 * px);
      camera.bottom = -camera.top;
      camera.updateProjectionMatrix();
    }
    invalidate();
  }, [camera, orbital, size, resetView, invalidate]);
  useLayoutEffect(() => {
    const count = segments.length * 2;
    let pos = lines.getAttribute('position') as BufferAttribute | undefined;
    if (!pos || pos.count < count) {
      if (pos) lines.dispose();
      pos = new BufferAttribute(new Float32Array(Math.max(2, count) * 3), 3).setUsage(DynamicDrawUsage);
      lines.setAttribute('position', pos);
    }
    for (let i = 0; i < segments.length; i++) pos.array.set(segments[i], i * 6);
    pos.needsUpdate = true;
    lines.setDrawRange(0, count);
    const mesh = markers.current;
    if (mesh) {
      dots.forEach(([x, y, z], i) => {
        const scale = Math.min(size.width / 6, size.height / 5.15) || 1;
        const separation = orbital ? Math.hypot(...dots[1]) : 0;
        const r = orbital
          ? Math.min(
              i === 0 ? separation * 0.45 : separation * 0.32,
              Math.max(i === 0 ? 0.102 : 0.072, (i === 0 ? 8 : 5.5) / scale)
            )
          : dots.length > 12
            ? 0.024
            : 0.065;
        mesh.setMatrixAt(i, matrix.makeScale(r, r, r).setPosition(x, y, z));
        mesh.setColorAt(i, i % 3 === 0 ? gold : ice);
      });
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }
    invalidate();
  }, [dots, segments, lines, orbital, matrix, size, invalidate]);
  useEffect(() => () => lines.dispose(), [lines]);
  return (
    <>
      <ambientLight intensity={1.15} />
      <directionalLight position={[-2, 3, 4]} intensity={2.2} />
      <group rotation={[0, turn, 0]}>
        <group position={[center, 0, 0]}>
          <lineSegments geometry={lines} frustumCulled={false}>
            <lineBasicMaterial color={orbital ? '#79bcdb' : '#9bdcfa'} />
          </lineSegments>
          {orbital && (
            <lineSegments>
              <bufferGeometry>
                <bufferAttribute attach="attributes-position" args={[guide, 3]} />
              </bufferGeometry>
              <lineBasicMaterial color="#425c76" />
            </lineSegments>
          )}
          {referencePositions.length > 0 && (
            <lineSegments>
              <bufferGeometry>
                <bufferAttribute attach="attributes-position" args={[referencePositions, 3]} />
              </bufferGeometry>
              <lineBasicMaterial color="#ffbb79" />
            </lineSegments>
          )}
          <instancedMesh
            key={dots.length}
            args={[undefined, undefined, dots.length]}
            ref={markers}
            frustumCulled={false}
          >
            <sphereGeometry args={[1, 20, 14]} />
            <meshStandardMaterial roughness={0.82} />
          </instancedMesh>
          {orbital && (
            <mesh>
              <sphereGeometry args={[0.14, 24, 16]} />
              <meshBasicMaterial color="#ffb74b" transparent opacity={0.14} depthWrite={false} />
            </mesh>
          )}
        </group>
        {!orbital && <gridHelper args={[4, 8, '#304257', '#1c2a3c']} position={[0, -1.45, 0]} />}
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
        frameloop="demand"
        dpr={[1, 1.5]}
        orthographic={scene.orbital}
        camera={
          scene.orbital
            ? { position: [0.7, -2.1, 4.6], near: 0.1, far: 60, manual: true }
            : { position: [2.1, 1.7, 4.2], fov: 40 }
        }
        gl={async (props) => {
          const canvas = props.canvas as HTMLCanvasElement;
          const gpu = (navigator as Navigator & { gpu?: { requestAdapter(): Promise<unknown> } }).gpu;
          if (gpu) {
            try {
              if (await gpu.requestAdapter()) {
                const { WebGPURenderer } = await import('three/webgpu');
                const r = new WebGPURenderer({ canvas, antialias: true });
                await r.init();
                return r;
              }
            } catch {
              /* Continue with WebGL2. */
            }
          }
          return new WebGLRenderer({ canvas, antialias: true, alpha: false });
        }}
      >
        <color attach="background" args={['#0a1425']} />
        <Geometry {...scene} />
      </Canvas>
    </div>
  );
}
