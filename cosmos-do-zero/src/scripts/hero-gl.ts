/**
 * Abertura em WebGL (Three.js): nebulosa volumétrica em GLSL (fbm com distorção de domínio)
 * e um campo de estrelas em profundidade que reage ao ponteiro e à rolagem.
 * Decorativo: aria-hidden, pausa fora da tela, com o céu pausado ou com movimento reduzido
 * (aí desenha um único quadro parado). Sem WebGL, a abertura em CSS continua igual.
 */
import { motionPreference, motionFactor } from './motion-preference';

export async function initHeroGl(): Promise<void> {
  const hero = document.querySelector<HTMLElement>('.hero-shell');
  if (!hero || hero.querySelector('.hero-gl')) return;
  // Sem GPU de verdade (renderização por software), o fundo animado não entra: a abertura em CSS fica.
  const force = new URLSearchParams(location.search).has('gl');
  const probe = document.createElement('canvas');
  const opts = { failIfMajorPerformanceCaveat: !force };
  if (!(probe.getContext('webgl2', opts) || probe.getContext('webgl', opts))) return;
  const THREE = await import('three');

  const canvas = document.createElement('canvas');
  canvas.className = 'hero-gl';
  canvas.setAttribute('aria-hidden', 'true');
  hero.prepend(canvas);
  let renderer: import('three').WebGLRenderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: 'low-power', failIfMajorPerformanceCaveat: !force }); }
  catch { canvas.remove(); return; }
  // O fundo é difuso: renderizar em resolução reduzida custa ~4× menos GPU sem perda visível.
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1) * (innerWidth < 700 ? 0.5 : 0.65));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
  camera.position.z = 6;

  // ── nebulosa: plano de fundo em tela cheia com fbm e distorção de domínio ──
  const nebula = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
    depthWrite: false, depthTest: false, transparent: true,
    uniforms: { uTime: { value: 0 }, uPointer: { value: new THREE.Vector2(0.6, 0.4) }, uAspect: { value: 1 }, uScroll: { value: 0 } },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.999, 1.0); }',
    fragmentShader: `
      precision highp float;
      varying vec2 vUv; uniform float uTime; uniform vec2 uPointer; uniform float uAspect; uniform float uScroll;
      float hash(vec2 p){ p = fract(p*vec2(123.34, 456.21)); p += dot(p, p+45.32); return fract(p.x*p.y); }
      float noise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.0-2.0*f);
        return mix(mix(hash(i),hash(i+vec2(1,0)),u.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x), u.y); }
      float fbm(vec2 p){ float v=0.0, a=0.5; mat2 r=mat2(0.8,0.6,-0.6,0.8); for(int i=0;i<5;i++){ v+=a*noise(p); p=r*p*2.02+3.1; a*=0.5; } return v; }
      void main(){
        vec2 p = vec2((vUv.x-0.5)*uAspect, vUv.y-0.5) * 2.2;
        p.y += uScroll * 0.6;
        float t = uTime * 0.035;
        vec2 m = vec2((uPointer.x-0.5)*uAspect, uPointer.y-0.5) * 2.2;
        vec2 q = vec2(fbm(p + t), fbm(p + vec2(5.2, 1.3) - t));
        vec2 r = vec2(fbm(p + 3.5*q + vec2(1.7, 9.2) + 0.6*t), fbm(p + 3.5*q + vec2(8.3, 2.8) - 0.4*t));
        float f = fbm(p + 3.0*r);
        float glow = exp(-2.6 * length(p - m));
        vec3 deep = vec3(0.012, 0.071, 0.149);
        vec3 ocean = vec3(0.04, 0.16, 0.30);
        vec3 teal = vec3(0.04, 0.28, 0.39);
        vec3 ice = vec3(0.32, 0.65, 0.78);
        vec3 col = mix(deep, ocean, smoothstep(0.25, 0.9, f));
        col = mix(col, teal, smoothstep(0.35, 0.95, length(q)) * 0.55);
        col += ice * pow(smoothstep(0.55, 1.0, f*f*1.6), 2.0) * 0.55;
        col += vec3(0.22, 0.55, 0.80) * glow * 0.22;
        float vign = smoothstep(1.55, 0.25, length(vec2((vUv.x-0.68)*1.25, vUv.y-0.55)));
        float alpha = (0.18 + 0.82 * f) * (0.35 + 0.65 * vign);
        gl_FragColor = vec4(col, alpha * 0.92);
      }`,
  }));
  nebula.frustumCulled = false;
  scene.add(nebula);

  // ── estrelas: pontos com profundidade, cor por temperatura e cintilação no shader ──
  const N = innerWidth < 700 ? 1400 : 3200;
  const pos = new Float32Array(N * 3), col = new Float32Array(N * 3), size = new Float32Array(N), seed = new Float32Array(N);
  let s = 20261101;
  const rnd = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
  const palette = [[0.75, 0.82, 1.0], [0.95, 0.93, 1.0], [1.0, 0.9, 0.78], [0.85, 0.75, 1.0]];
  for (let i = 0; i < N; i++) {
    pos[i * 3] = (rnd() - 0.5) * 22; pos[i * 3 + 1] = (rnd() - 0.5) * 14; pos[i * 3 + 2] = -rnd() * 26 + 3;
    const c = palette[Math.floor(rnd() * palette.length)];
    col.set(c, i * 3); size[i] = 0.6 + Math.pow(rnd(), 6) * 4.5; seed[i] = rnd() * 6.283;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  geo.setAttribute('size', new THREE.BufferAttribute(size, 1));
  geo.setAttribute('seed', new THREE.BufferAttribute(seed, 1));
  const starMat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, uPx: { value: renderer.getPixelRatio() } },
    vertexShader: `
      attribute float size; attribute float seed; attribute vec3 color; varying vec3 vColor; varying float vTw;
      uniform float uTime; uniform float uPx;
      void main(){
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mv;
        vTw = 0.55 + 0.45 * sin(uTime * (0.8 + fract(seed) * 2.2) + seed * 7.0);
        vColor = color;
        gl_PointSize = size * uPx * (14.0 / -mv.z);
      }`,
    fragmentShader: `
      varying vec3 vColor; varying float vTw;
      void main(){
        vec2 d = gl_PointCoord - 0.5; float r = length(d);
        float core = smoothstep(0.5, 0.0, r);
        float spike = max(0.0, 1.0 - abs(d.x) * 14.0) * max(0.0, 1.0 - abs(d.y) * 2.2) + max(0.0, 1.0 - abs(d.y) * 14.0) * max(0.0, 1.0 - abs(d.x) * 2.2);
        float a = (core * core + spike * 0.25) * vTw;
        if (a < 0.01) discard;
        gl_FragColor = vec4(vColor * a, a);
      }`,
  });
  const stars = new THREE.Points(geo, starMat);
  scene.add(stars);
  hero.classList.add('has-gl');

  // ── ciclo: só roda visível, com o céu ativo e sem movimento reduzido ──
  const pointer = { x: 0.62, y: 0.42, tx: 0.62, ty: 0.42 };
  let visible = true, frame = 0, t0 = performance.now(), elapsed = 0, scroll = 0;
  const paused = () => hero.dataset.ambientPaused === 'true' || motionPreference.matches || document.hidden;
  const resize = () => {
    const w = hero.clientWidth, h = hero.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    (nebula.material as import('three').ShaderMaterial).uniforms.uAspect.value = w / h;
  };
  const draw = (dt: number) => {
    const k = motionFactor();
    elapsed += dt * k;
    pointer.x += (pointer.tx - pointer.x) * 0.04; pointer.y += (pointer.ty - pointer.y) * 0.04;
    const neb = (nebula.material as import('three').ShaderMaterial).uniforms;
    neb.uTime.value = elapsed; neb.uPointer.value.set(pointer.x, pointer.y); neb.uScroll.value = scroll;
    starMat.uniforms.uTime.value = elapsed;
    stars.rotation.z = elapsed * 0.006;
    stars.position.z = (elapsed * 0.25) % 6 - scroll * 3;
    camera.position.x = (pointer.x - 0.5) * 0.9; camera.position.y = -(pointer.y - 0.5) * 0.6 - scroll * 1.2;
    camera.lookAt(0, -scroll * 1.2, -8);
    renderer.render(scene, camera);
  };
  let slow = 0, frames = 0, tooSlow = false;
  const loop = (now: number) => {
    frame = 0;
    if (!visible || paused() || tooSlow) return;
    const raw = (now - t0) / 1000, dt = Math.min(0.05, raw); t0 = now;
    // Guarda de desempenho: se a GPU não acompanha (quadros > 45 ms), congela num quadro bonito.
    if (++frames > 20 && frames < 140) { slow = raw > 0.045 ? slow + 1 : Math.max(0, slow - 1); if (slow > 25 && !force) { tooSlow = true; return; } }
    draw(dt);
    frame = requestAnimationFrame(loop);
  };
  const kick = () => { if (!frame && visible && !paused()) { t0 = performance.now(); frame = requestAnimationFrame(loop); } else if (paused()) draw(0); };
  resize(); draw(0); kick();
  new ResizeObserver(() => { resize(); draw(0); }).observe(hero);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }).observe(hero);
  new MutationObserver(kick).observe(hero, { attributes: true, attributeFilter: ['data-ambient-paused'] });
  motionPreference.addEventListener('change', kick);
  document.addEventListener('visibilitychange', kick);
  hero.addEventListener('pointermove', (e) => { const r = hero.getBoundingClientRect(); pointer.tx = (e.clientX - r.left) / r.width; pointer.ty = 1 - (e.clientY - r.top) / r.height; });
  addEventListener('scroll', () => { scroll = Math.min(1, scrollY / Math.max(1, hero.offsetHeight)); }, { passive: true });
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); cancelAnimationFrame(frame); frame = 0; canvas.remove(); hero.classList.remove('has-gl'); });
}
