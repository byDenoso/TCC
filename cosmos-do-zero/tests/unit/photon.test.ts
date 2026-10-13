import {it,expect} from 'vitest';
import { PLANCK,comovingMpc,lookbackGyr } from '../../src/lib/cosmology';
import { photonTable,photonAt } from '../../src/lib/photon';
it('luz local em z=0 tem caminho e tempo nulos em todo o transporte',()=>{
 const table=photonTable(0,PLANCK);
 expect(table.totalGyr).toBe(0);expect(table.totalMpc).toBe(0);
 for(const t of [0,.3,1])expect(photonAt(table,t)).toEqual({a:1,chi:0});
});
it('trajetória radial FLRW concorda com integrais centrais, inclusive na primeira luz',()=>{
 for(const z of [.001,.5,2,20,1090]){
  const table=photonTable(z,PLANCK);
  expect(Math.abs(table.totalMpc/comovingMpc(z,PLANCK)-1)).toBeLessThan(.00002);
  expect(Math.abs(table.totalGyr/lookbackGyr(z,PLANCK)-1)).toBeLessThan(.00002);
  expect(photonAt(table,0).chi).toBe(1);expect(photonAt(table,1).chi).toBe(0);
  expect(photonAt(table,1).a).toBeCloseTo(1,12);
  for(let t=.1;t<1;t+=.1){const state=photonAt(table,t);expect(state.a).toBeGreaterThanOrEqual(1/(1+z));expect(state.chi).toBeGreaterThan(0);}
 }
});
