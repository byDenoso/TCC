import { describe, it, expect } from 'vitest';
import * as expansion from '../../src/lib/expansion';
describe('enquadramento didático da expansão',()=>{
 it('mantém todas as galáxias na cena até 2,5 vezes para cada observador',()=>{
  expect(expansion).toHaveProperty('projectExpansion');
  for(let observer=0;observer<3;observer++)for(let i=0;i<expansion.expansionPositions.length;i++){
   const [x,y]=expansion.projectExpansion(i,observer,2.5);
   expect(x).toBeGreaterThanOrEqual(40);expect(x).toBeLessThanOrEqual(600);
   expect(y).toBeGreaterThanOrEqual(30);expect(y).toBeLessThanOrEqual(350);
  }
 });
});
