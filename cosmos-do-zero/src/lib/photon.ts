import { C_KMS,E2,GYR_PER_INV_H0,type Cosmos } from './cosmology';
/** Geodésica radial FLRW: dχ = c da/(a²H), dt = da/(aH). Tabela criada por evento. */
export function photonTable(z:number,p:Cosmos,n=1200):{a:number[];time:number[];chi:number[];totalMpc:number;totalGyr:number}{
 const emission=1/(1+Math.max(0,z)),a=[emission],time=[0],chi=[0];
 if(z<=0)return {a:[1,1],time:[0,1],chi:[0,0],totalMpc:0,totalGyr:0};
 const step=-Math.log(emission)/n;
 const tIntegrand=(aa:number)=>1/Math.sqrt(E2(aa,p));
 const dIntegrand=(aa:number)=>1/(aa*Math.sqrt(E2(aa,p)));
 for(let i=1;i<=n;i++){
  const next=emission*Math.exp(step*i),prev=a[i-1];a.push(next);
  time.push(time[i-1]+step*(tIntegrand(prev)+tIntegrand(next))/2*GYR_PER_INV_H0/p.h0);
  chi.push(chi[i-1]+step*(dIntegrand(prev)+dIntegrand(next))/2*C_KMS/p.h0);
 }
 const totalGyr=time.at(-1)!,totalMpc=chi.at(-1)!;
 return {a,time:time.map(t=>t/totalGyr),chi:chi.map(c=>1-c/totalMpc),totalMpc,totalGyr};
}
export function photonAt(table:ReturnType<typeof photonTable>,fraction:number):{a:number;chi:number}{
 const t=Math.max(0,Math.min(1,fraction));let lo=0,hi=table.time.length-1;
 while(hi-lo>1){const mid=(lo+hi)>>1;if(table.time[mid]<t)lo=mid;else hi=mid;}
 const k=(t-table.time[lo])/(table.time[hi]-table.time[lo]||1);
 return {a:table.a[lo]+k*(table.a[hi]-table.a[lo]),chi:table.chi[lo]+k*(table.chi[hi]-table.chi[lo])};
}
