import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type * as THREE from 'three';

/**
 * Pontos da teia cósmica gerada no Blender pela aproximação de Zel'dovich (caixa de 160 Mpc,
 * esfera de 62 Mpc de raio), lidos do mesmo GLB da viagem. Usado pelo Explorador (fatias e volume)
 * para que toda a escola mostre a mesma estrutura.
 */
export type TeiaDados = { posicoes: Float32Array; cores: Float32Array; raios: Float32Array; raioMpc: number };

let promessa: Promise<TeiaDados> | null = null;

export function carregarTeia(): Promise<TeiaDados> {
  if (!promessa) {
    promessa = new GLTFLoader().loadAsync('/viagem/teia-cosmica-m.glb').then((gltf) => {
      const pts = gltf.scene.getObjectByName('teia') as THREE.Points;
      const g = pts.geometry;
      const pos = g.getAttribute('position').array as Float32Array;
      const cor = g.getAttribute('color');
      const n = pos.length / 3;
      const cores = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        cores[i * 3] = cor.getX(i);
        cores[i * 3 + 1] = cor.getY(i);
        cores[i * 3 + 2] = cor.getZ(i);
      }
      const raios = (g.getAttribute('_radius')?.array as Float32Array) ?? new Float32Array(n).fill(0.1);
      return { posicoes: pos, cores, raios, raioMpc: 62 };
    });
    promessa.catch(() => {
      promessa = null;
    });
  }
  return promessa;
}
