/**
 * Máquina do tempo em 3D (Three.js, carregado só quando a cena aparece).
 * Uma rede de galáxias (o espaço) cresce enquanto a luz viaja de uma galáxia distante até nós.
 * A onda da luz cresce na mesma proporção que a rede. Na tela, o crescimento é comprimido (até ×6);
 * o valor real fica nos rótulos. Pausa fora da tela/aba oculta; sem WebGL, a página mantém o desenho em SVG.
 */
import type * as THREE_NS from 'three';

export interface Tempo3D {
  /** Atualiza o redshift z e reinicia a viagem da luz. */
  set(z: number, lamNm: number): void;
  dispose(): void;
}

const Z_MAX = 1100;
const SPAN = 9; // meia-largura da rede em unidades da cena (hoje)

export async function mountTempo3D(host: HTMLElement, reduced: () => boolean): Promise<Tempo3D | null> {
  // WebGL disponível?
  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) return null;
  const THREE: typeof THREE_NS = await import('three');
  const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');

  const canvas = document.createElement('canvas');
  canvas.className = 'obs3d-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  host.prepend(canvas);
  const labels = {
    us: host.querySelector<HTMLElement>('[data-3d-us]')!,
    src: host.querySelector<HTMLElement>('[data-3d-src]')!,
    wave: host.querySelector<HTMLElement>('[data-3d-wave]')!
  };

  let renderer: THREE_NS.WebGLRenderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'low-power' }); }
  catch { canvas.remove(); return null; }
  renderer.setClearColor(0x05070f, 1);
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x05070f, 0.035);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 200);
  camera.position.set(2, 6.5, 21);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true; controls.enablePan = false; controls.minDistance = 12; controls.maxDistance = 34;
  controls.autoRotate = !reduced(); controls.autoRotateSpeed = 0.35;
  controls.target.set(-2, 0, 0);

  // textura de brilho circular para as galáxias
  const glowTex = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const g = c.getContext('2d')!; const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.25, 'rgba(255,220,180,.85)'); grd.addColorStop(1, 'rgba(255,200,150,0)');
    g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();

  // rede de galáxias: posições comóveis fixas (pequeno desvio da grade para parecer natural)
  const comoving: number[] = [];
  let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = -4; i <= 4; i++) for (let j = -2; j <= 2; j++) for (let k = -4; k <= 4; k++) {
    if (i === 0 && j === 0 && k === 0) continue;
    comoving.push((i + (rnd() - 0.5) * 0.5) * (SPAN / 4), (j + (rnd() - 0.5) * 0.5) * (SPAN / 4) * 0.7, (k + (rnd() - 0.5) * 0.5) * (SPAN / 4));
  }
  const n = comoving.length / 3;
  const posAttr = new THREE.Float32BufferAttribute(new Float32Array(comoving.length), 3);
  const colors = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { const w = 0.75 + rnd() * 0.25; colors.set([w, w * (0.82 + rnd() * 0.12), w * (0.7 + rnd() * 0.25)], i * 3); }
  const galGeo = new THREE.BufferGeometry();
  galGeo.setAttribute('position', posAttr);
  galGeo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  const galMat = new THREE.PointsMaterial({ size: 0.6, map: glowTex, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
  const galaxies = new THREE.Points(galGeo, galMat);
  scene.add(galaxies);

  // grade comóvel (o próprio espaço): linhas finas no plano das galáxias
  const gridPts: number[] = [];
  for (let i = -4; i <= 4; i++) { const v = i * (SPAN / 4); gridPts.push(v, 0, -SPAN, v, 0, SPAN, -SPAN, 0, v, SPAN, 0, v); }
  const gridBase = new Float32Array(gridPts);
  const gridGeo = new THREE.BufferGeometry();
  gridGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(gridPts.length), 3));
  const grid = new THREE.LineSegments(gridGeo, new THREE.LineBasicMaterial({ color: 0x3a4a78, transparent: true, opacity: 0.55 }));
  grid.position.y = -2.2;
  scene.add(grid);

  // nós (Via Láctea) e a fonte
  const usMesh = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0x8db3e8, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  usMesh.scale.setScalar(1.6); scene.add(usMesh);
  const srcComoving = new THREE.Vector3(-SPAN * 0.9, 0.6, -SPAN * 0.35);
  const usComoving = new THREE.Vector3(SPAN * 0.45, 0, SPAN * 0.3); // nós fora do centro da tela: não há centro
  usMesh.position.copy(usComoving);
  const srcMesh = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xffb27a, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  srcMesh.scale.setScalar(1.5); scene.add(srcMesh);

  // onda da luz: fita (malha fina) ao longo do caminho fonte → nós
  const SEG = 420;
  const waveGeo = new THREE.BufferGeometry();
  const wavePos = new Float32Array((SEG + 1) * 2 * 3);
  waveGeo.setAttribute('position', new THREE.BufferAttribute(wavePos, 3));
  const idx: number[] = [];
  for (let i = 0; i < SEG; i++) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
  waveGeo.setIndex(idx);
  const waveMat = new THREE.MeshBasicMaterial({ color: 0xff5a4f, transparent: true, opacity: 0.95, side: THREE.DoubleSide, depthWrite: false });
  const waveMesh = new THREE.Mesh(waveGeo, waveMat);
  scene.add(waveMesh);

  let prevVC = true;
  let z = 0, lam = 656.28, t = 0, playing = !reduced(), frame = 0, last = 0, visible = true, alive = true;
  const growOf = (zz: number) => Math.pow(1 + zz, Math.log(6) / Math.log(1 + Z_MAX));

  const layout = (scale: number) => {
    const p = posAttr.array as Float32Array;
    for (let i = 0; i < comoving.length; i++) p[i] = comoving[i] * scale;
    posAttr.needsUpdate = true;
    const g = gridGeo.getAttribute('position') as THREE_NS.BufferAttribute;
    for (let i = 0; i < gridBase.length; i++) (g.array as Float32Array)[i] = gridBase[i] * scale;
    g.needsUpdate = true;
    srcMesh.position.copy(srcComoving).multiplyScalar(scale);
    usMesh.position.copy(usComoving).multiplyScalar(scale);
  };

  const tmp = new THREE.Vector3();
  const place = (el: HTMLElement, v: THREE_NS.Vector3, dy = 0) => {
    tmp.copy(v).project(camera);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const x = (tmp.x * 0.5 + 0.5) * w, y = (-tmp.y * 0.5 + 0.5) * h + dy;
    el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -100%)`;
    el.hidden = tmp.z > 1;
  };

  const render = () => {
    const G = growOf(z);
    const k = z < 0.005 ? 1 : Math.min(1, t); // fração da viagem
    const ease = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    // fator de escala na tela ao longo da viagem: de 1/G (quando a luz saiu) até 1 (hoje)
    const s = 1 / G + (1 - 1 / G) * ease;
    layout(s);
    // caminho da luz: da fonte (posição comóvel × s) até nós; a frente da onda avança com ease
    const src = srcComoving.clone().multiplyScalar(s);
    const dir = new THREE.Vector3().subVectors(usMesh.position, src);
    const len = dir.length(); dir.normalize();
    const side = new THREE.Vector3().crossVectors(dir, camera.up).normalize();
    const up = new THREE.Vector3().crossVectors(side, dir).normalize();
    const lamScene = 0.7 * (G * s); // comprimento de onda na tela cresce junto com a rede
    const head = z < 0.005 ? len : len * ease;
    const tail = Math.max(0, head - len);
    const amp = 0.62, halfW = 0.085;
    for (let i = 0; i <= SEG; i++) {
      const d = tail + ((head - tail) * i) / SEG;
      const env = Math.min(1, (d - tail) / 1.2) * Math.min(1, (head - d) / 0.6 + 0.02);
      const yv = amp * env * Math.sin(((d - head) / lamScene) * Math.PI * 2);
      const px = src.x + dir.x * d + up.x * yv, py = src.y + dir.y * d + up.y * yv, pz = src.z + dir.z * d + up.z * yv;
      wavePos.set([px + side.x * halfW, py + side.y * halfW, pz + side.z * halfW, px - side.x * halfW, py - side.y * halfW, pz - side.z * halfW], i * 6);
    }
    (waveGeo.getAttribute('position') as THREE_NS.BufferAttribute).needsUpdate = true;
    waveGeo.computeBoundingSphere();
    // cor: visível (vermelho) enquanto λ < 750 nm; depois, traço neutro e translúcido (invisível aos olhos)
    const lamAt = 656.28 * s * G;
    const invisible = lamAt >= 750;
    // antes das primeiras galáxias (z > ~20) não havia galáxias: os pontos viram gás difuso
    const early = z > 20;
    galMat.size = early ? 1.25 : 0.6; galMat.opacity = early ? 0.6 : 1; galMat.color.set(early ? 0x9fb8e6 : 0xffffff);
    galMat.vertexColors = !early; galMat.needsUpdate = galMat.vertexColors !== prevVC; prevVC = galMat.vertexColors;
    labels.src.textContent = early ? 'região de onde a luz saiu' : 'galáxia de onde a luz saiu';
    waveMat.color.set(invisible ? 0xd9dde8 : 0xff5a4f);
    waveMat.opacity = invisible ? 0.55 + 0.25 * Math.sin(performance.now() / 300) : 0.95;
    controls.update();
    renderer.render(scene, camera);
    place(labels.us, usMesh.position, -14);
    place(labels.src, srcMesh.position, -14);
    labels.src.hidden = labels.src.hidden || z < 0.005;
    const front = src.clone().addScaledVector(dir, Math.max(0.5, head));
    place(labels.wave, front, 26);
    labels.wave.style.transform += ' translate(0, 100%)';
    labels.wave.textContent = z < 0.005 ? '' : invisible ? 'luz (invisível aos olhos)' : 'luz vermelha';
    labels.wave.hidden = labels.wave.hidden || z < 0.005;
    void lam;
  };

  const resize = () => {
    const w = host.clientWidth, h = Math.max(220, host.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, w < 600 ? 1.5 : 2));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.position.setLength(w < 520 ? 16.5 : 21);
    camera.updateProjectionMatrix();
    render();
  };
  const tick = (now: number) => {
    if (!alive) return;
    const dt = last ? Math.min(now - last, 50) : 16; last = now;
    if (playing && z >= 0.005) { t += dt / 5200; if (t > 1.35) t = 0; } // viagem de ~5 s, pausa e repete
    render();
    frame = visible && !document.hidden ? requestAnimationFrame(tick) : 0;
  };
  const wake = () => { if (!frame && alive && visible && !document.hidden) { last = 0; frame = requestAnimationFrame(tick); } };
  const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) wake(); }, { threshold: 0.1 });
  io.observe(host);
  const onVis = () => wake();
  document.addEventListener('visibilitychange', onVis);
  const ro = new ResizeObserver(resize); ro.observe(host);
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); alive = false; cancelAnimationFrame(frame); host.dataset.webgl = 'lost'; host.dispatchEvent(new CustomEvent('obs3d:lost', { bubbles: true })); });
  controls.addEventListener('start', () => { controls.autoRotate = false; });

  resize(); wake();
  return {
    set(zz, l) { z = zz; lam = l; t = reduced() ? 1 : 0; playing = !reduced(); controls.autoRotate = !reduced() && controls.autoRotate; render(); wake(); },
    dispose() { alive = false; cancelAnimationFrame(frame); io.disconnect(); ro.disconnect(); document.removeEventListener('visibilitychange', onVis); controls.dispose(); renderer.dispose(); galGeo.dispose(); gridGeo.dispose(); waveGeo.dispose(); glowTex.dispose(); canvas.remove(); }
  };
}
