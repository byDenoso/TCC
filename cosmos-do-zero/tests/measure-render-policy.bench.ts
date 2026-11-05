import { bench, describe } from 'vitest';
import { visualCatalog } from '../src/scripts/visual/exhibits';
import { canUseWebGPU } from '../src/scripts/visual/render-policy';

// Real existing phase scene, no renderer and no GPU. CPU traversal only.
const exhibit=visualCatalog['origem-do-universo-fase-quente'].make({} as HTMLElement);
let nodes=0;exhibit.group.traverse(()=>{nodes++;});
console.log(`scene=origem-do-universo-fase-quente nodes=${nodes} GPU=none`);
describe('CPU material and primitive compatibility scan',()=>{
  bench('existing scene',()=>{if(!canUseWebGPU(exhibit.group))throw new Error('unexpected incompatible material');},{time:1000,warmupTime:200});
});
