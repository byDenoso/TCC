import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { styleEarth } from '../src/scripts/visual/world-view';

export async function renderEarthPortrait(): Promise<string> {
  const model = await new GLTFLoader().loadAsync('/models/mundos.glb');
  const earth = model.scene.getObjectByName('terra')!.clone(true);
  const globe = new THREE.Group(); globe.add(earth); styleEarth(globe); globe.rotation.y = -1.8;
  const scene = new THREE.Scene(); scene.add(globe);
  scene.add(new THREE.AmbientLight(0xffffff, .48));
  const key = new THREE.DirectionalLight(0xffffff, 3.4); key.position.set(-5,4,6); scene.add(key);
  const fill = new THREE.DirectionalLight(0x699bd9, .25); fill.position.set(4,-1,-4); scene.add(fill);
  const camera = new THREE.PerspectiveCamera(37,1,.02,30); camera.position.set(0,.35,4); camera.lookAt(0,0,0);
  const renderer = new THREE.WebGLRenderer({ alpha:true, antialias:true, preserveDrawingBuffer:true });
  renderer.setPixelRatio(1); renderer.setSize(768,768); renderer.setClearColor(0x000000,0);
  renderer.outputColorSpace=THREE.SRGBColorSpace; renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.18;
  renderer.render(scene,camera);
  return renderer.domElement.toDataURL('image/webp',.94);
}
