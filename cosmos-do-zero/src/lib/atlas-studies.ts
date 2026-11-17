import type { ChapterId } from '../types';

interface Study {
  key: 'redshift'|'lens'|'star'|'orbit'|'air'; title: string; prediction: string;
  input: string; min:number; max:number; step:number; initial:number;
  unit:string; reading:string; outUnit:string; rule:string; limit:string; result:string;
  reference:string; sample:string;
}

export const studies: Partial<Record<ChapterId, Study>> = {
  'origem-do-universo': {
    key:'redshift', title:'Quanto uma onda se alonga?', prediction:'Uma linha emitida a 500 nm chega a que comprimento de onda quando z vale 1?',
    input:'Redshift z',min:0,max:2,step:.05,initial:0,unit:'', reading:'Comprimento de onda observado',outUnit:'nm',
    rule:'λ observada = 500 nm × (1 + z)',limit:'O modelo considera somente o redshift cosmológico. A cor distingue as curvas. A medida está na separação das cristas.',
    result:'Em z = 1, duas cristas ficam separadas por 1.000 nm. O comprimento de onda dobrou.',reference:'Na emissão',sample:'Na observação'
  },
  'misterios-do-cosmos': {
    key:'lens',title:'Qual é o tamanho do anel de Einstein?',prediction:'Se a massa da lente quadruplicar, o raio angular também quadruplica?',
    input:'Massa relativa',min:.25,max:4,step:.05,initial:1,unit:'M₀',reading:'Raio angular relativo',outUnit:'θ₀',
    rule:'θE / θ₀ = √(M / M₀)',limit:'Lente fina de massa pontual, alinhamento perfeito e distâncias fixas. θ₀ é o raio angular para a massa de referência M₀.',
    result:'Com 4 M₀, o raio chega a 2 θ₀. O crescimento segue a raiz quadrada da massa.',reference:'Anel de referência',sample:'Anel calculado'
  },
  'vida-das-estrelas': {
    key:'star',title:'Quanto irradia uma estrela maior?',prediction:'Se o raio dobrar e a temperatura for mantida, quantas luminosidades solares você espera?',
    input:'Raio estelar',min:.5,max:2.5,step:.05,initial:1,unit:'R☉',reading:'Luminosidade total',outUnit:'L☉',
    rule:'L / L☉ = (R / R☉)²',limit:'Estrela esférica com temperatura efetiva solar fixa. O diâmetro do modelo varia com o raio. A escala numérica mostra a luminosidade total.',
    result:'Com duas vezes o raio solar, a superfície emissora quadruplica. A estrela emite 4 L☉.',reference:'Sol',sample:'Estrela do modelo'
  },
  'sistema-solar': {
    key:'orbit',title:'Quanto dura uma volta?',prediction:'Uma órbita com o dobro do raio da terrestre leva dois anos para completar uma volta?',
    input:'Raio orbital',min:.5,max:2,step:.05,initial:1,unit:'UA',reading:'Período orbital',outUnit:'anos',
    rule:'P (anos) ≈ [a (UA)]³ᐟ²',limit:'Órbita circular em torno de uma massa solar e planeta de massa desprezível. As pistas compartilham a escala de distância. Os corpos estão ampliados.',
    result:'A 2 UA, o planeta leva aproximadamente 2,83 anos. O período cresce mais rápido que o raio orbital.',reference:'Órbita de 1 UA',sample:'Órbita do modelo'
  },
  'terra-e-atmosfera': {
    key:'air',title:'Quanto ar fica acima de você?',prediction:'Ao subir 8 km, que fração da pressão ao nível do mar resta no modelo?',
    input:'Altitude',min:0,max:24,step:.5,initial:0,unit:'km',reading:'Pressão relativa ao nível do mar',outUnit:'%',
    rule:'P / P₀ = exp(−h / H), com H = 8 km',limit:'Atmosfera isotérmica, gravidade constante e altura de escala ilustrativa de 8 km. A altura das barras compara pressões. Ela não representa a espessura da atmosfera.',
    result:'A 8 km, resta 1/e da pressão inicial, cerca de 37%. A cada 8 km adicionais o modelo aplica o mesmo fator.',reference:'Nível do mar',sample:'Na altitude escolhida'
  }
};

export type StudyKey = Study['key'];
export const number = (v:number) => v.toLocaleString('pt-BR',{maximumFractionDigits:2});
export function measurement(key:StudyKey,v:number) {
  switch(key) {
    case 'redshift': return 500*(1+v);
    case 'lens': return Math.sqrt(v);
    case 'star': return v*v;
    case 'orbit': return v**1.5;
    case 'air': return 100*Math.exp(-v/8);
  }
}
export function wave(px:number) {
  return Array.from({length:161},(_,i)=>[(18+i*px/80).toFixed(1),(14*Math.sin(i*Math.PI/40)).toFixed(1)].join(',')).join(' ');
}
