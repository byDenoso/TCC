'use client';
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { rad, orbitPoint, orbitRadius } from './explorer-data';
import type { CameraView, Orbit } from './explorer-data';
import { ink, makeField } from './explorer-geometry';

export interface SceneProps {
  station: string;
  cameraView: CameraView;
  orbits: Orbit[];
  selected: number;
  linear: boolean;
  day: number;
  reduced: boolean;
  onSelect: (i: number) => void;
  onFailure: () => void;
}

const grainVertex = `
attribute float aWidth;
attribute vec3 aTint;
uniform float uPixel;
varying vec3 vTint;
void main(){
  vTint=aTint;
  gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);
  gl_PointSize=clamp(aWidth*uPixel,1.,18.);
}`;
const grainFragment = `
varying vec3 vTint;
void main(){
  vec2 uv=gl_PointCoord*2.-1.;
  float q=dot(uv,uv);
  if(q>1.) discard;
  float a=exp(-q*3.)*(1.-smoothstep(.65,1.,q));
  gl_FragColor=vec4(vTint,a*.92);
}`;
const cloudVertex = `
varying vec3 startAt;
varying vec3 localDirection;
void main(){
  startAt=position;
  localDirection=normalize((vec4(0.,0.,-1.,0.)*modelViewMatrix).xyz);
  gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);
}`;
const cloudFragment = `
varying vec3 startAt;
varying vec3 localDirection;
float hash(vec3 p) { return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453); }
float noise3(vec3 p) {
  vec3 c=floor(p), s=fract(p); s=s*s*(3.-2.*s);
  return mix(mix(mix(hash(c),hash(c+vec3(1,0,0)),s.x),mix(hash(c+vec3(0,1,0)),hash(c+vec3(1,1,0)),s.x),s.y),
             mix(mix(hash(c+vec3(0,0,1)),hash(c+vec3(1,0,1)),s.x),mix(hash(c+vec3(0,1,1)),hash(c+vec3(1,1,1)),s.x),s.y),s.z);
}
void main(){
  vec3 ray=normalize(localDirection);
  vec3 p=startAt+ray*.006;
  vec4 sum=vec4(0.);
  for(int i=0;i<48;i++){
    if(any(greaterThan(abs(p),vec3(2.85,1.45,1.85)))) break;
    float wave=sin(p.x*1.30+.5)*.69;
    float body=exp(-.36*p.x*p.x-2.8*(p.y-wave)*(p.y-wave)-.94*p.z*p.z);
    float wisps=noise3(p*2.8)+.47*noise3(p*6.9);
    float d=body*smoothstep(.46,1.09,wisps)*.087;
    vec3 col=mix(vec3(.11,.35,.72),vec3(.96,.42,.27),smoothstep(-.75,.8,p.y-p.z*.44));
    sum.rgb+=(1.-sum.a)*d*col; sum.a+=(1.-sum.a)*d;
    if(sum.a>.94)break;
    p+=ray*.101;
  }
  if(sum.a<.002)discard;
  gl_FragColor=vec4(sum.rgb/max(sum.a,.001),sum.a);
}`;

function DataCloud({ id }: { id: string }) {
  const material = useRef<THREE.ShaderMaterial>(null);
  const { gl } = useThree();
  const buffers = useMemo(() => {
    const { grains, wires } = makeField(id);
    const points = new Float32Array(grains.length * 3);
    const colors = new Float32Array(grains.length * 3);
    const widths = new Float32Array(grains.length);
    const rgb = ink.map((c) => new THREE.Color(c));
    grains.forEach(({ p, tone, width }, i) => {
      points.set(p, i * 3);
      rgb[tone].toArray(colors, i * 3);
      widths[i] = width;
    });
    return { points, colors, widths, lines: new Float32Array(wires.flatMap((w) => [...w.a, ...w.b])) };
  }, [id]);
  const uniforms = useMemo(() => ({ uPixel: { value: gl.getPixelRatio() } }), [gl]);
  useFrame(() => {
    if (material.current) material.current.uniforms.uPixel.value = gl.getPixelRatio();
  });
  return (
    <>
      {id === 'orion' && (
        <mesh renderOrder={-2}>
          <boxGeometry args={[5.7, 2.9, 3.7]} />
          <shaderMaterial
            vertexShader={cloudVertex}
            fragmentShader={cloudFragment}
            transparent
            depthWrite={false}
          />
        </mesh>
      )}
      {buffers.lines.length > 0 && (
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[buffers.lines, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#5d8bd0" opacity={0.28} transparent />
        </lineSegments>
      )}
      <points frustumCulled={false}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[buffers.points, 3]} />
          <bufferAttribute attach="attributes-aWidth" args={[buffers.widths, 1]} />
          <bufferAttribute attach="attributes-aTint" args={[buffers.colors, 3]} />
        </bufferGeometry>
        <shaderMaterial
          ref={material}
          uniforms={uniforms}
          vertexShader={grainVertex}
          fragmentShader={grainFragment}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </points>
    </>
  );
}

function OrbitTrack({ radius, color, selected }: { radius: number; color: string; selected: boolean }) {
  const p = useMemo(() => {
    const data: number[] = [];
    for (let i = 0; i < 160; i++) {
      const a = (i * Math.PI) / 80,
        b = ((i + 1) * Math.PI) / 80;
      data.push(
        Math.cos(a) * radius,
        0,
        Math.sin(a) * radius,
        Math.cos(b) * radius,
        0,
        Math.sin(b) * radius
      );
    }
    return new Float32Array(data);
  }, [radius]);
  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[p, 3]} />
      </bufferGeometry>
      <lineBasicMaterial
        color={selected ? color : '#6a8dba'}
        transparent
        opacity={selected ? 0.9 : 0.37}
      />
    </lineSegments>
  );
}

const starVertex = `varying vec2 vUv;void main(){vUv=uv;vec4 c=modelViewMatrix*vec4(0.,0.,0.,1.);c.xy+=position.xy;gl_Position=projectionMatrix*c;}`;
const starFragment = `uniform vec3 uColor;varying vec2 vUv;void main(){vec2 u=(vUv-.5)*2.;float d=length(u);float a=exp(-d*d*5.)*(1.-smoothstep(.5,1.,d));gl_FragColor=vec4(uColor,a*.67);}`;

function Solar({ orbits, selected, linear, day, onSelect, station }: SceneProps) {
  const max = orbits[orbits.length - 1].a;
  const tint = station === 'solar' ? '#ffbb66' : '#ff8657';
  const glow = useMemo(() => ({ uColor: { value: new THREE.Color(tint) } }), [tint]);
  return (
    <>
      <ambientLight intensity={1.45} />
      <directionalLight position={[3, 4, 6]} intensity={1.65} color="#ffecd5" />
      <mesh renderOrder={-1}>
        <planeGeometry args={[0.8, 0.8]} />
        <shaderMaterial
          uniforms={glow}
          vertexShader={starVertex}
          fragmentShader={starFragment}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.105, 24, 18]} />
        <meshBasicMaterial color={tint} />
      </mesh>
      {orbits.map((ob, i) => {
        const chosen = i === selected,
          r = ob.symbolSize,
          p = orbitPoint(ob, max, linear, day);
        return (
          <group key={ob.name}>
            <OrbitTrack radius={orbitRadius(ob.a, max, linear)} color={ob.color} selected={chosen} />
            <group
              position={p}
              onClick={(e) => {
                e.stopPropagation();
                onSelect(i);
              }}
            >
              <mesh>
                <sphereGeometry args={[r, 24, 16]} />
                <meshStandardMaterial color={ob.color} metalness={0} roughness={0.84} />
              </mesh>
              {ob.name === 'Saturno' && (
                <mesh rotation={[1.11, 0, 0.24]}>
                  <ringGeometry args={[r * 1.24, r * 1.8, 48]} />
                  <meshBasicMaterial
                    color="#dbba8f"
                    side={THREE.DoubleSide}
                    transparent
                    opacity={0.86}
                  />
                </mesh>
              )}
              {chosen && (
                <mesh>
                  <sphereGeometry args={[r * 1.55, 14, 9]} />
                  <meshBasicMaterial color={ob.color} transparent opacity={0.32} wireframe />
                </mesh>
              )}
            </group>
          </group>
        );
      })}
    </>
  );
}

function Universe(props: SceneProps) {
  const group = useRef<THREE.Group>(null);
  const { camera, size, invalidate, gl } = useThree();
  const view = props.cameraView;
  useLayoutEffect(() => {
    const lens = camera as THREE.OrthographicCamera;
    const aspect = Math.max(0.05, size.width / Math.max(size.height, 1));
    const width = Math.max(7.4, 4.35 * aspect);
    lens.left = -width / 2;
    lens.right = width / 2;
    lens.top = width / (2 * aspect);
    lens.bottom = -width / (2 * aspect);
    lens.updateProjectionMatrix();
    invalidate();
  }, [camera, size, invalidate]);
  useEffect(() => {
    const canvas = gl.domElement;
    const fail = (e: Event) => {
      e.preventDefault();
      props.onFailure();
    };
    canvas.addEventListener('webglcontextlost', fail);
    return () => canvas.removeEventListener('webglcontextlost', fail);
  }, [gl, props.onFailure]);
  const axis = useMemo(() => new THREE.Euler(0, 0, 0, 'XYZ'), []);
  const desired = useMemo(() => new THREE.Quaternion(), []);
  useFrame((_, dt) => {
    const g = group.current;
    if (!g) return;
    axis.set(view.tilt * rad, view.azimuth * rad, 0, 'XYZ');
    desired.setFromEuler(axis);
    const alpha = props.reduced ? 1 : 1 - Math.exp(-Math.min(Math.max(dt, 1 / 120), 0.09) * 18);
    g.quaternion.slerp(desired, alpha);
    const z = THREE.MathUtils.lerp(g.scale.x, view.zoom, alpha);
    g.scale.setScalar(z);
    if (g.quaternion.angleTo(desired) > 0.0015 || Math.abs(z - view.zoom) > 0.001) invalidate();
  });
  return (
    <group ref={group}>
      {props.orbits.length ? <Solar {...props} /> : <DataCloud id={props.station} />}
    </group>
  );
}
export default function ExpoScene(props: SceneProps) {
  return (
    <Canvas
      orthographic
      camera={{ position: [0, 0, 9], near: 0.1, far: 30 }}
      frameloop="demand"
      dpr={[1, 1.6]}
      gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
      fallback="Mapa astronômico em três dimensões."
      aria-label="Cena tridimensional do explorador"
    >
      <Universe {...props} />
    </Canvas>
  );
}
