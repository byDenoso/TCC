/**
 * Teia cósmica em 3D (Three.js, carregado só quando a cena aparece).
 * Cada partícula tem posição inicial quase uniforme e posição final num nó, num filamento ou num vazio;
 * o shader interpola pelas duas com o quanto a gravidade já agiu (k). Esquemático: não integra a gravidade.
 * Pausa fora da tela/aba oculta; sem WebGL devolve null e a cena fica no desenho em SVG.
 */
import type * as THREE_NS from 'three';

export interface Web3D {
  set(k: number): void;
  dispose(): void;
}

const N = 14000;

export async function mountWeb3D(stage: HTMLElement, reduced: () => boolean): Promise<Web3D | null> {
  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) return null;
  const THREE: typeof THREE_NS = await import('three');
  const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');

  const canvas = document.createElement('canvas');
  canvas.className = 'mx-gl';
  canvas.setAttribute('aria-hidden', 'true');
  stage.prepend(canvas);
  let renderer: THREE_NS.WebGLRenderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'low-power' }); }
  catch { canvas.remove(); return null; }
  renderer.setClearColor(0x04060b, 1);
  stage.classList.add('mx-stage--gl');

  // estrutura final: nós ligados aos 3 vizinhos mais próximos (semente fixa: mesmo desenho sempre)
  let s = 7;
  const rnd = () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296);
  const gauss = () => Math.sqrt(-2 * Math.log(1 - rnd())) * Math.cos(2 * Math.PI * rnd());
  const nodes = Array.from({ length: 18 }, () => new THREE.Vector3((rnd() - 0.5) * 2, (rnd() - 0.5) * 1.3, (rnd() - 0.5) * 2));
  const links: [number, number][] = [];
  nodes.forEach((a, i) => nodes.map((b, j) => ({ j, d: a.distanceTo(b) })).filter((o) => o.j !== i).sort((x, y) => x.d - y.d).slice(0, 3)
    .forEach(({ j }) => { if (!links.some(([p, q]) => (p === j && q === i) || (p === i && q === j))) links.push([i, j]); }));

  const start = new Float32Array(N * 3), end = new Float32Array(N * 3), dens = new Float32Array(N), seed = new Float32Array(N);
  const v = new THREE.Vector3();
  for (let i = 0; i < N; i++) {
    const r = rnd();
    let d: number;
    if (r < 0.28) { // nó (aglomerado)
      const n = nodes[Math.floor(rnd() * nodes.length)];
      const sc = 0.035 + 0.05 * rnd() ** 2;
      v.set(n.x + gauss() * sc, n.y + gauss() * sc, n.z + gauss() * sc); d = 1;
    } else if (r < 0.9) { // filamento: mais denso perto dos nós
      const [a, b] = links[Math.floor(rnd() * links.length)];
      const t = rnd(), w = 0.018 + 0.012 * Math.sin(Math.PI * t);
      v.lerpVectors(nodes[a], nodes[b], t).add(new THREE.Vector3(gauss() * w, gauss() * w, gauss() * w)); d = 0.55;
    } else { // poucas galáxias sobram nos vazios
      v.set((rnd() - 0.5) * 2.2, (rnd() - 0.5) * 1.5, (rnd() - 0.5) * 2.2); d = 0.15;
    }
    end.set([v.x, v.y, v.z], i * 3);
    // início: quase uniforme, levemente deslocado na direção de onde vai cair (as "sementes" de densidade)
    const u = new THREE.Vector3((rnd() - 0.5) * 2.2, (rnd() - 0.5) * 1.5, (rnd() - 0.5) * 2.2);
    u.lerp(v, 0.12);
    start.set([u.x, u.y, u.z], i * 3);
    dens[i] = d; seed[i] = rnd();
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(end, 3)); // caixa de contorno; o shader usa start/end
  geo.setAttribute('aStart', new THREE.BufferAttribute(start, 3));
  geo.setAttribute('aDens', new THREE.BufferAttribute(dens, 1));
  geo.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));

  const uniforms = { uK: { value: 0 }, uPx: { value: 1 }, uTime: { value: 0 } };
  const mat = new THREE.ShaderMaterial({
    uniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */ `
      attribute vec3 aStart; attribute float aDens; attribute float aSeed;
      uniform float uK; uniform float uPx; uniform float uTime;
      varying vec3 vCol; varying float vA;
      void main() {
        // matéria cai devagar no começo e acelera (crescimento das diferenças)
        float k = uK * uK * (3.0 - 2.0 * uK);
        vec3 p = mix(aStart, position, k);
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        float tw = 0.85 + 0.15 * sin(uTime * 1.3 + aSeed * 40.0);
        gl_PointSize = uPx * (2.0 + 2.4 * aDens * k) * tw * (3.2 / -mv.z);
        vec3 cold = vec3(0.45, 0.58, 0.85), fil = vec3(0.62, 0.78, 1.0), hot = vec3(1.0, 0.82, 0.55);
        vCol = mix(cold, mix(fil, hot, smoothstep(0.5, 1.0, aDens)), k);
        vA = mix(0.8, 0.5 + 0.5 * aDens, k);
      }`,
    fragmentShader: /* glsl */ `
      varying vec3 vCol; varying float vA;
      void main() {
        vec2 q = gl_PointCoord - 0.5; float r = length(q);
        float a = smoothstep(0.5, 0.0, r); a *= a;
        gl_FragColor = vec4(vCol * a * vA, a * vA);
      }`
  });
  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  const scene = new THREE.Scene();
  scene.add(points);
  const camera = new THREE.PerspectiveCamera(42, 16 / 9, 0.05, 50);
  camera.position.set(0.3, 0.7, 2.3);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true; controls.enablePan = false; controls.enableZoom = false;
  controls.autoRotate = !reduced(); controls.autoRotateSpeed = 0.45;

  // rótulos em HTML (acompanham a rotação sem mexer no SVG da cena)
  const mk = (t: string) => { const e = document.createElement('span'); e.className = 'mx-gl-label'; e.textContent = t; e.hidden = true; stage.append(e); return e; };
  const big = nodes.reduce((best, n, i) => (links.filter(([a, b]) => a === i || b === i).length > links.filter(([a, b]) => a === best || b === best).length ? i : best), 0);
  const [la, lb] = links.filter(([a, b]) => a !== big && b !== big).sort(([a, b], [c, d]) => nodes[d].distanceTo(nodes[c]) - nodes[b].distanceTo(nodes[a]))[0] ?? links[0];
  const lab = { node: mk('aglomerado'), fil: mk('filamento'), void: mk('vazio') };
  const anchor = { node: nodes[big], fil: new THREE.Vector3().lerpVectors(nodes[la], nodes[lb], 0.5), void: new THREE.Vector3() };
  // vazio: ponto da caixa mais distante de qualquer filamento (amostragem simples)
  let bestD = -1;
  for (let i = 0; i < 400; i++) {
    const c = new THREE.Vector3((rnd() - 0.5) * 1.6, (rnd() - 0.5) * 0.9, (rnd() - 0.5) * 1.6);
    const d = Math.min(...links.map(([a, b]) => { const ab = nodes[b].clone().sub(nodes[a]); const t = Math.max(0, Math.min(1, c.clone().sub(nodes[a]).dot(ab) / ab.lengthSq())); return c.distanceTo(nodes[a].clone().addScaledVector(ab, t)); }));
    if (d > bestD) { bestD = d; anchor.void.copy(c); }
  }
  const tmp = new THREE.Vector3();
  const place = (e: HTMLElement, p: THREE_NS.Vector3, show: boolean) => {
    tmp.copy(p).project(camera);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const x = Math.min(Math.max((tmp.x * 0.5 + 0.5) * w - e.offsetWidth / 2, 6), w - e.offsetWidth - 6);
    const y = Math.min(Math.max((-tmp.y * 0.5 + 0.5) * h - e.offsetHeight - 10, 6), h - e.offsetHeight - 30);
    e.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    e.hidden = !show || tmp.z > 1;
  };

  let k = 0, frame = 0, visible = true, alive = true;
  const render = (now: number) => {
    uniforms.uK.value = k; uniforms.uTime.value = now / 1000;
    controls.update();
    renderer.render(scene, camera);
    const show = k > 0.9;
    place(lab.node, anchor.node, show); place(lab.fil, anchor.fil, show); place(lab.void, anchor.void, show);
  };
  const loop = (now: number) => {
    if (!alive || !visible || document.hidden) { frame = 0; return; }
    render(now);
    frame = requestAnimationFrame(loop);
  };
  const wake = () => { if (!frame && alive) frame = requestAnimationFrame(loop); };
  const resize = () => {
    const w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, w < 600 ? 1.5 : 2));
    renderer.setSize(w, h, false);
    uniforms.uPx.value = renderer.getPixelRatio() * h / 300;
    camera.aspect = w / h; camera.position.setLength(2.3); camera.updateProjectionMatrix();
    render(performance.now());
  };
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) wake(); }, { threshold: 0.05 });
  io.observe(stage);
  const onVis = () => { if (!document.hidden) wake(); };
  document.addEventListener('visibilitychange', onVis);
  const ro = new ResizeObserver(resize); ro.observe(stage);
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); alive = false; cancelAnimationFrame(frame); stage.classList.remove('mx-stage--gl'); canvas.remove(); Object.values(lab).forEach((l) => l.remove()); stage.dispatchEvent(new CustomEvent('mx:gl-lost')); });
  resize(); wake();

  return {
    set(next) { k = next; if (!frame) render(performance.now()); },
    dispose() { alive = false; cancelAnimationFrame(frame); io.disconnect(); ro.disconnect(); document.removeEventListener('visibilitychange', onVis); controls.dispose(); renderer.dispose(); geo.dispose(); mat.dispose(); canvas.remove(); Object.values(lab).forEach((l) => l.remove()); stage.classList.remove('mx-stage--gl'); }
  };
}
