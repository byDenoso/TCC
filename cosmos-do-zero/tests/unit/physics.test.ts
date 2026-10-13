import { describe,it,expect } from 'vitest';
import { orbitalPeriodYears,horizonKm,lensSource,pointImages,einsteinAngle,SOLAR_MASS_KG } from '../../src/lib/physics';
import { expansionPositions,separation,expandedPosition } from '../../src/lib/expansion';
describe('demonstrações físicas calculadas',()=>{
  it('órbita de 1 AU e 1 massa solar dura aproximadamente 1 ano',()=>expect(orbitalPeriodYears(1)).toBeCloseTo(1,4));
  it('o período inclui a massa dos dois corpos e cresce como a^1.5',()=>{
    expect(orbitalPeriodYears(4)/orbitalPeriodYears(1)).toBeCloseTo(8,10);
    expect(orbitalPeriodYears(1,1,1)/orbitalPeriodYears(1)).toBeCloseTo(1/Math.sqrt(2),10);
  });
  it('valores orbitais inválidos são recusados',()=>expect(()=>orbitalPeriodYears(0)).toThrow());
  it('horizonte de 8 massas solares é aproximadamente 24 km (NASA)',()=>expect(horizonKm(8)).toBeCloseTo(23.63,1));
  it('imagens pontuais satisfazem a equação da lente para alinhamento e fora do eixo',()=>{
    for(const beta of [0,.1,1,5])for(const theta of pointImages(beta))expect(lensSource(theta,0)[0]).toBeCloseTo(beta,10);
    expect(pointImages(0)).toEqual([1,-1]);
  });
  it('raio de Einstein escala com raiz da massa',()=>{
    const args:[number,number,number]=[1e20,2e20,1e20];
    expect(einsteinAngle(4*SOLAR_MASS_KG,...args)/einsteinAngle(SOLAR_MASS_KG,...args)).toBeCloseTo(2,10);
    expect(()=>einsteinAngle(1,0,1,1)).toThrow();
    expect(einsteinAngle(1,2,1,1)).toBeGreaterThan(0);
  });
});
describe('expansão usa uma única geometria',()=>{
  it('distâncias crescem pelo mesmo fator em qualquer observador',()=>{
    for(let o=0;o<3;o++)for(let i=0;i<expansionPositions.length;i++){
      const p=expandedPosition(i,o,2.5);expect(Math.hypot(...p)).toBeCloseTo(separation(i,o)*2.5,10);
    }
  });
});
