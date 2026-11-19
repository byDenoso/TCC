import { Canvas, useFrame } from '@react-three/fiber';
import { BufferAttribute, BufferGeometry, Color, Vector3, WebGLRenderer } from 'three';
import { useEffect, useMemo, useRef } from 'react';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useThree } from '@react-three/fiber';
type Geo = { dots: number[][]; segments: number[][] };
function Geometry({ dots, segments }: Geo) {
  const p = useMemo(() => new BufferGeometry(), []),
    l = useMemo(() => new BufferGeometry(), []);
  useEffect(() => {
    p.setAttribute('position', new BufferAttribute(new Float32Array(dots.flat()), 3));
    p.computeBoundingSphere();
    l.setAttribute('position', new BufferAttribute(new Float32Array(segments.flat()), 3));
    l.computeBoundingSphere();
  }, [dots, segments, p, l]);
  useEffect(
    () => () => {
      p.dispose();
      l.dispose();
    },
    [p, l]
  );
  const { gl, camera } = useThree();
  const c = useMemo(() => {
    const o = new OrbitControls(camera, gl.domElement);
    o.enableDamping = true;
    o.minDistance = 2;
    o.maxDistance = 12;
    o.enablePan = false;
    return o;
  }, [camera, gl]);
  useEffect(() => () => c.dispose(), [c]);
  useFrame(() => c.update());
  return (
    <>
      <points geometry={p}>
        <pointsMaterial size={0.075} color="#ffd39d" sizeAttenuation />
      </points>
      <lineSegments geometry={l}>
        <lineBasicMaterial color="#9bdcfa" />
      </lineSegments>
      <gridHelper args={[5, 10, '#31435c', '#222d41']} position={[0, -1.45, 0]} />
    </>
  );
}
export default function Scene3D({
  dots,
  segments,
  onFail,
  turn = 0,
}: {
  dots: number[][];
  segments: number[][];
  onFail: () => void;
  turn?: number;
}) {
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
        dpr={[1, 1.5]}
        performance={{ min: 0.5 }}
        fallback={<p>Use a projeção 2D.</p>}
        camera={{ position: [2.1, 1.7, 4.2], fov: 40 }}
        gl={async (props) => {
          if (typeof navigator !== 'undefined' && 'gpu' in navigator) {
            try {
              const gpu = (navigator as unknown as { gpu: { requestAdapter: () => Promise<unknown> } })
                .gpu;
              if (gpu && (await gpu.requestAdapter())) {
                const { WebGPURenderer } = await import('three/webgpu');
                const r = new WebGPURenderer({
                  canvas: props.canvas as HTMLCanvasElement,
                  antialias: true,
                });
                await r.init();
                return r;
              }
            } catch {
              /* WebGL2 covers incompatible drivers. */
            }
          }
          return new WebGLRenderer({
            canvas: props.canvas as HTMLCanvasElement,
            antialias: true,
            alpha: false,
          });
        }}
        onCreated={({ scene, camera }) => {
          scene.background = new Color('#0a1425');
          camera.lookAt(new Vector3(0, 0, 0));
        }}
      >
        <group rotation={[0, turn, 0]}>
          <Geometry dots={dots} segments={segments} />
        </group>
        <Quality />
      </Canvas>
    </div>
  );
}
function Quality() {
  const set = useThree((s) => s.setDpr),
    slow = useRef(0);
  useFrame((_, dt) => {
    slow.current = dt > 0.036 ? slow.current + 1 : Math.max(0, slow.current - 1);
    if (slow.current === 16) set(1);
  });
  return null;
}
