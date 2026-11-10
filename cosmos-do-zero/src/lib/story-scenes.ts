export interface StoryPhase { at:number; label:string; say:string }
export interface Story { title:string; short:string; lede:string; phases:StoryPhase[]; limit:string }
export const STORIES:Record<string,Story>={
 'galaxias-e-nebulosas':{
  title:'Do Sistema Solar à teia cósmica',short:'A Via Láctea em diferentes escalas',lede:'Compare o tamanho do Sistema Solar com o da Via Láctea e a escala dos agrupamentos de galáxias.',
  phases:[{at:0,label:'Sistema Solar',say:'A Terra orbita o Sol. O Sistema Solar é só uma pequena parte da nossa galáxia.'},{at:.34,label:'Via Láctea',say:'A Via Láctea reúne estrelas, gás e poeira. O Sol fica longe do centro.'},{at:.7,label:'Teia cósmica',say:'Galáxias se agrupam em fios e conjuntos maiores, separados por regiões menos povoadas.'}],
  limit:'Terra com mapa MODIS. A Via Láctea e a teia cósmica são modelos ilustrativos, com saltos de escala.'
 },
 'origem-do-universo':{
  title:'O efeito da expansão sobre a luz',short:'Comprimento de onda e expansão',lede:'Compare uma onda quando foi emitida e depois de atravessar um espaço em expansão.',
  phases:[{at:0,label:'Luz emitida',say:'A onda começa com 400 nanômetros. A distância entre duas cristas é seu comprimento de onda.'},{at:.2,label:'Espaço crescendo',say:'Enquanto o espaço se expande, as cristas se separam. A onda fica mais comprida na mesma proporção.'},{at:.8,label:'Luz recebida',say:'Se o espaço duplica, 400 nm passam a 800 nm: infravermelho, fora da nossa visão.'}],
  limit:'As ondas representam o campo elétrico. Amplitudes e comprimentos foram ampliados. A faixa de cor é ilustrativa.'
 },
 'misterios-do-cosmos':{
  title:'Rotação das galáxias',short:'Curvas de rotação com e sem halo',lede:'O movimento das estrelas revela a gravidade que age sobre elas.',
  phases:[{at:0,label:'Matéria visível',say:'Começamos com uma curva de giro que considera apenas a matéria visível do modelo.'},{at:.3,label:'Padrão de rotação',say:'Em muitas galáxias, as regiões externas giram mais depressa do que essa previsão simples.'},{at:.75,label:'Modelo com halo',say:'Um halo de matéria escura acrescenta gravidade e ajuda a explicar o padrão. Outras evidências também entram na investigação.'}],
  limit:'Curvas de um modelo ilustrativo, sem medições de uma galáxia real. A comparação isolada não estabelece uma explicação única.'
 },
 'vida-das-estrelas':{
  title:'Evolução estelar em duas massas',short:'Da fusão ao remanescente',lede:'Uma estrela nasce do colapso de uma nuvem. Sua massa ajuda a definir o que vem depois.',
  phases:[{at:0,label:'Colapso da nuvem',say:'A gravidade concentra gás. O centro aquece até a fusão sustentar uma estrela.'},{at:.3,label:'Fusão nuclear',say:'A fusão libera energia. Estrelas mais massivas gastam seu combustível mais depressa.'},{at:.72,label:'Remanescentes',say:'Uma estrela como o Sol termina como anã branca. Estrelas muito massivas podem deixar uma estrela de nêutrons ou um buraco negro.'}],
  limit:'Caminhos simplificados, com tamanhos e durações fora de escala. Massa, composição e companheiras influenciam a evolução.'
 },
 'sistema-solar':{
  title:'Períodos das órbitas planetárias',short:'Distância ao Sol e período orbital',lede:'Compare quantas voltas Mercúrio, a Terra e Marte completam no mesmo intervalo de tempo.',
  phases:[{at:0,label:'Órbitas planetárias',say:'Os planetas seguem órbitas ao redor do Sol. Cada órbita tem seu próprio tamanho.'},{at:.25,label:'Períodos orbitais',say:'Um planeta mais próximo completa sua volta antes de um planeta mais distante.'},{at:.72,label:'Lei de Kepler',say:'Na aproximação de Kepler, o quadrado do período é proporcional ao cubo do tamanho da órbita.'}],
  limit:'Órbitas circulares e coplanares para comparar períodos. Raios desenhados e tamanhos dos planetas são ilustrativos.'
 },
 'terra-e-atmosfera':{
  title:'O ar muda conforme você sobe',short:'Uma atmosfera, várias camadas',lede:'Suba do solo até 120 km e acompanhe onde ficam as camadas do ar.',
  phases:[{at:0,label:'Perto do chão',say:'A troposfera reúne a maior parte do ar e quase todo o tempo que sentimos: nuvens, chuva e ventos.'},{at:.1,label:'Mais acima',say:'Na estratosfera, o ozônio absorve parte da radiação ultravioleta que vem do Sol.'},{at:.42,label:'Ar cada vez mais rarefeito',say:'Acima vêm a mesosfera e a termosfera. O ar continua ficando menos denso; as camadas não têm bordas rígidas.'}],
  limit:'Terra com mapa MODIS e nuvens ilustrativas. A régua mostra limites aproximados até 120 km. A atmosfera continua acima dessa altura.'
 }
};

const clamp=(v:number)=>Math.max(0,Math.min(1,v));
/** O filme deixa três segundos para ler o começo e cinco para a conclusão. */
export function storyProgress(seconds:number):number {return clamp(Number(((seconds-3)/12).toFixed(12)));}
export function sampleStory(id:string,progress:number){
 const p=clamp(progress),story=STORIES[id];
 const axes=[.387,1,1.524],periods=axes.map(a=>a**1.5);
 return {progress:p,phase:story.phases.reduce((at,s,i)=>p>=s.at?i:at,0),scale:1+p,wavelength:400*(1+p),redshift:p,galaxyRadius:9,axes,periods,altitude:120*p};
}
const C={bg:'#031226',surface:'#08233d',line:'#254661',ink:'#eef6ff',muted:'#aec7db',cyan:'#74dceb',blue:'#83b6ff',gold:'#f3ce83'};
const esc=(s:string)=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const num=(v:number,n=1)=>v.toFixed(n).replace('.',',');
const text=(x:number,y:number,s:string,size=20,color:string=C.ink,extra='')=>`<text x="${x}" y="${y}" font-size="${size}" fill="${color}" ${extra}>${esc(s)}</text>`;
const circle=(x:number,y:number,r:number,fill:string,extra='')=>`<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="${r}" fill="${fill}" ${extra}/>`;
const path=(d:string,stroke:string,width=2,extra='')=>`<path d="${d}" fill="none" stroke="${stroke}" stroke-width="${width}" ${extra}/>`;
const line=(x:number,y:number,x2:number,y2:number,stroke:string,extra='')=>`<line x1="${x}" y1="${y}" x2="${x2}" y2="${y2}" stroke="${stroke}" ${extra}/>`;
function galaxies(p:number){
 const phase=sampleStory('galaxias-e-nebulosas',p).phase;
 const header=text(38,81,['01 · Sistema Solar','02 · Via Láctea','03 · Estrutura em grande escala'][phase],17,C.muted);
 if(phase===0)return header+text(430,462,'Terra',24,C.ink,'text-anchor="middle"')+text(730,249,'Sol',19,C.gold,'text-anchor="middle"');
 if(phase===1)return header+path('M605 271L650 363H667',C.cyan,1.5)+text(673,370,'Região do Sol',17,C.cyan)+text(480,485,'Via Láctea · representação',21,C.ink,'text-anchor="middle"');
 return header+text(480,492,'Teia cósmica · modelo ilustrativo',21,C.ink,'text-anchor="middle"');
}

function redshift(p:number,vectorFallback=false){
 const a=1+p;
 const box=(y:number)=>`<rect x="36" y="${y}" width="888" height="128" rx="14" fill="none" stroke="${C.line}"/>`;
 let body=box(96)+box(250)+text(60,126,'NA EMISSÃO',16,C.blue,'font-weight="700"')+text(898,126,'400 nm',22,C.blue,'text-anchor="end"');
 body+=path('M78 209v7 M78 213H150 M150 209v7',C.blue,2);
 body+=text(60,280,'DURANTE A EXPANSÃO',16,C.cyan,'font-weight="700"')+text(898,280,`${num(400*a,0)} nm`,22,C.cyan,'text-anchor="end"');
 body+=path(`M${60+18*a} 361v7 M${60+18*a} 365H${60+90*a} M${60+90*a} 361v7`,C.cyan,2);
 if(vectorFallback){
  const wave=(y:number,spacing:number)=>Array.from({length:169},(_,i)=>{
   const x=i*5;
   return `${i?'L':'M'}${60+x},${(y-25*Math.sin(2*Math.PI*x/spacing)).toFixed(2)}`;
  }).join(' ');
  body+=`<g class="story-wave-fallback">${path(wave(173,72),C.blue,3)}${path(wave(327,72*a),C.cyan,3)}</g>`;
 }
 body+=text(60,421,'Espaço',16,C.muted)+text(60,457,`${num(a,2)} ×`,30,C.cyan,'font-weight="700"');
 body+=text(365,421,'Comprimento de onda',16,C.muted)+text(365,457,`${num(400*a,0)} nm`,30,C.ink,'font-weight="700"');
 body+=text(700,421,'Desvio para o vermelho',16,C.muted)+text(700,457,`z = ${num(p,2)}`,30,C.ink,'font-weight="700"');
 return body+text(480,503,p>.75?'A onda fica maior na mesma proporção que o espaço.':'Compare a distância entre duas cristas.',19,C.muted,'text-anchor="middle"');
}

export function storyRotationVelocity(radius:number,strength:number):number {
 const visible=radius<.3?radius/.3:Math.sqrt(.3/radius);
 return Math.hypot(visible,Math.sqrt(strength)*.95*(1-Math.exp(-radius/.22)));
}

function rotation(p:number){
 const curve=(strength:number)=>Array.from({length:60},(_,i)=>{
  const r=.025+i/59*.975;
  return `${i?'L':'M'}${480+r*390},${(420-storyRotationVelocity(r,strength)*190).toFixed(2)}`;
 }).join(' ');
 let body=path('M480 150V420H890',C.line,2)+path(curve(p),C.cyan,4)+path(curve(0),C.blue,3,'stroke-dasharray="6 7"');
 body+=text(480,118,'Rapidez de giro',18,C.muted)+text(880,453,'Distância ao centro',17,C.muted,'text-anchor="end"');
 body+=line(90,480,125,480,C.blue,'stroke-width="3" stroke-dasharray="5 5"')+text(135,486,'Só matéria visível',17,C.blue);
 body+=line(480,480,515,480,C.cyan,'stroke-width="4"')+text(525,486,'Modelo com halo',17,C.cyan);
 return body;
}

function stars(p:number){
 if(p>=.72){
  return text(235,452,'Anã branca',22,C.ink,'text-anchor="middle"')+
   text(656,452,'Estrela de nêutrons',18,C.ink,'text-anchor="middle"')+
   text(725,348,'ou',19,C.muted,'text-anchor="middle"')+
   text(810,481,'Buraco negro',18,C.ink,'text-anchor="middle"');
 }
 return text(480,84,p<.3?'Uma nuvem se concentra':'Uma estrela começa a brilhar',21,C.ink,'text-anchor="middle"')+
  text(235,472,'Como o Sol',22,C.ink,'text-anchor="middle"')+
  text(725,472,'Muito mais massiva',22,C.ink,'text-anchor="middle"');
}

function solar(p:number){
 const {periods}=sampleStory('sistema-solar',p);
 const names=['Mercúrio','Terra','Marte'],colors=[C.gold,C.cyan,'#e4a187'];
 return text(480,86,'O mesmo tempo passa para todos',21,C.ink,'text-anchor="middle"')+
  periods.map((period,i)=>circle(192+i*260,462,4,colors[i])+text(207+i*260,468,names[i],20,C.ink)+text(207+i*260,498,`${num(period,2)} ano`,17,C.muted)).join('');
}

function atmosphere(p:number){
 const h=120*p,y=448-h/120*300;
 const layers=[{a:0,b:12,name:'Troposfera',fill:'#276d91'},{a:12,b:50,name:'Estratosfera',fill:'#205578'},{a:50,b:85,name:'Mesosfera',fill:'#173d61'},{a:85,b:120,name:'Termosfera',fill:'#102e50'}];
 let body='';
 for(const layer of layers){const top=448-layer.b/120*300,height=(layer.b-layer.a)/120*300;body+=`<rect x="490" y="${top}" width="320" height="${height}" fill="${layer.fill}" opacity=".7"/>`;body+=text(820,top+height/2+5,layer.name,16,C.muted);}
 body+=line(490,148,490,448,C.line,'stroke-width="2"');
 for(const height of [0,12,50,85,120]){const at=448-height/120*300;body+=line(482,at,490,at,C.muted)+text(468,at+5,`${height}`,16,C.muted,'text-anchor="end"');}
 body+=line(490,y,807,y,C.cyan,'stroke-width="2"')+circle(520,y,7,C.ink)+text(650,107,`${num(h,0)} km`,32,C.cyan,'font-weight="700" text-anchor="middle"');
 body+=text(260,502,'Terra · MODIS',24,C.ink,'text-anchor="middle"')+text(650,490,'Altitude acima do solo',18,C.muted,'text-anchor="middle"');
 return body;
}

/** Régua, unidades e legendas de leitura sobre a cena 3D e seus quadros de referência. */
export function renderStory(id:string,progress:number,uid:string,vectorFallback=false):string {
 const state=sampleStory(id,progress),story=STORIES[id],key=esc(`${uid}-${id}`);
 const scenes:Record<string,(p:number)=>string>={'galaxias-e-nebulosas':galaxies,'origem-do-universo':p=>redshift(p,vectorFallback),'misterios-do-cosmos':rotation,'vida-das-estrelas':stars,'sistema-solar':solar,'terra-e-atmosfera':atmosphere};
 return `<svg class="story-graphic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" role="img" aria-labelledby="${key}-title ${key}-desc"><title id="${key}-title">${esc(story.short)}</title><desc id="${key}-desc">${esc(story.phases[state.phase].say)}</desc><style>.story-graphic text{font-family:Arial,Helvetica,sans-serif}</style>${text(38,45,story.short.toLocaleUpperCase('pt-BR'),15,C.cyan,'letter-spacing="1.4" font-weight="700"')}${scenes[id](state.progress)}</svg>`;
}
