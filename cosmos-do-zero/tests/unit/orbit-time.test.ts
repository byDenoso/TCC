import {it,expect} from 'vitest';
import {trajectory,trajectoryAt,ORBIT_DRAWN_CENTRAL_RADIUS} from '../../src/scripts/micro/sistema';
it('órbitas classificam queda, círculo e escape nos mesmos controles',()=>{
 expect(trajectory(.2).kind).toBe('cai');expect(trajectory(1).kind).toBe('orbita');expect(trajectory(1.6).kind).toBe('escapa');expect(()=>trajectory(NaN)).toThrow();
});
it('período numérico da elipse concorda com Kepler e acelera no periélio',()=>{
 const v=.75,path=trajectory(v),a=1/(2-v*v),period=path.times.at(-1)!;
 expect(Math.abs(period/(2*Math.PI*a**1.5)-1)).toBeLessThan(.003);
 const speed=(t:number)=>{const delta=.0005,p=trajectoryAt(path,t).position,q=trajectoryAt(path,t+delta).position;return Math.hypot(q[0]-p[0],q[1]-p[1])/(delta*period);};
 const apo=speed(0),peri=speed(.5),rPeri=v*v/(2-v*v);
 expect(Math.abs(peri/apo*rPeri-1)).toBeLessThan(.03);
});
it('áreas varridas em quartos de tempo físico são iguais na elipse',()=>{
 const path=trajectory(.75),areas:number[]=[];
 for(let quarter=0;quarter<4;quarter++){let area=0;for(let j=0;j<100;j++){
 const t=quarter/4+j/400,p=trajectoryAt(path,t).position,q=trajectoryAt(path,t+1/400).position;area+=(p[0]*q[1]-q[0]*p[1])/2;
 }areas.push(area);}
 expect((Math.max(...areas)-Math.min(...areas))/areas[0]).toBeLessThan(.005);
});

it('limite central concorda com periélio analítico por energia e momento angular',()=>{
 // GM=r0=1, lançamento tangencial: a=1/(2-v²), e=1-v² => rp=v²/(2-v²).
 const peri=(v:number)=>v*v/(2-v*v),R=ORBIT_DRAWN_CENTRAL_RADIUS;
 expect(peri(.2)).toBeCloseTo(.0204081632653,11);expect(peri(.5)).toBeCloseTo(.142857142857,11);
 expect(peri(.2)).toBeLessThan(R);expect(peri(.5)).toBeGreaterThan(R);
 expect(trajectory(.2).kind).toBe('cai');expect(trajectory(.5).kind).toBe('orbita');
 const threshold=Math.sqrt(2*R/(1+R));expect(threshold).toBeCloseTo(.495595,5);
 expect(trajectory(threshold-.01).kind).toBe('cai');expect(trajectory(threshold+.01).kind).toBe('orbita');
});
