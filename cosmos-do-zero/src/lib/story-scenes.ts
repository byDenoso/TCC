export interface StoryPhase { at:number; label:string; say:string }
export interface Story { title:string; short:string; lede:string; phases:StoryPhase[]; limit:string }
export const STORIES:Record<string,Story>={
 'galaxias-e-nebulosas':{
  title:'Uma casa dentro de outra',short:'Nosso endereço cósmico',lede:'Afaste o olhar: o que parecia enorme passa a fazer parte de algo maior.',
  phases:[{at:0,label:'Nossa casa',say:'A Terra orbita o Sol. O Sistema Solar é só uma pequena parte da nossa galáxia.'},{at:.34,label:'Nossa galáxia',say:'A Via Láctea reúne estrelas, gás e poeira. O Sol fica longe do centro.'},{at:.7,label:'A grande teia',say:'Galáxias se agrupam em fios e conjuntos maiores, separados por regiões menos povoadas.'}],
  limit:'Saltos de escala ilustrativos. O desenho não representa um zoom contínuo nem um mapa observado.'
 },
 'origem-do-universo':{
  title:'A luz traz uma pista',short:'O espaço cresce, a onda se alonga',lede:'Compare uma onda quando foi emitida e depois de atravessar um espaço em expansão.',
  phases:[{at:0,label:'Luz emitida',say:'A onda começa com 400 nanômetros. A distância entre duas cristas é seu comprimento de onda.'},{at:.2,label:'Espaço crescendo',say:'Enquanto o espaço se expande, as cristas se separam. A onda fica mais comprida na mesma proporção.'},{at:.8,label:'Luz recebida',say:'Se o espaço duplica, 400 nm passam a 800 nm: infravermelho, fora da nossa visão.'}],
  limit:'Exemplo ilustrativo. As cores distinguem as duas curvas; os tempos e comprimentos desenhados estão ampliados.'
 },
 'misterios-do-cosmos':{
  title:'Uma pista no giro das galáxias',short:'Compare a previsão com o padrão',lede:'O movimento das estrelas revela a gravidade que age sobre elas.',
  phases:[{at:0,label:'O que enxergamos',say:'Começamos com uma curva de giro que considera apenas a matéria visível do modelo.'},{at:.3,label:'A pista do movimento',say:'Em muitas galáxias, as regiões externas giram mais depressa do que essa previsão simples.'},{at:.75,label:'Uma explicação',say:'Um halo de matéria escura acrescenta gravidade e ajuda a explicar o padrão. Outras evidências também entram na investigação.'}],
  limit:'Curvas de um modelo ilustrativo, sem medições de uma galáxia real. A comparação isolada não estabelece uma explicação única.'
 },
 'vida-das-estrelas':{
  title:'Um começo parecido, dois caminhos',short:'A massa muda a história',lede:'Uma estrela nasce do colapso de uma nuvem. Sua massa ajuda a definir o que vem depois.',
  phases:[{at:0,label:'Nascer',say:'A gravidade concentra gás. O centro aquece até a fusão sustentar uma estrela.'},{at:.3,label:'Brilhar',say:'A fusão libera energia. Estrelas mais massivas gastam seu combustível mais depressa.'},{at:.72,label:'Transformar',say:'Uma estrela como o Sol termina como anã branca. Estrelas muito massivas podem deixar uma estrela de nêutrons ou um buraco negro.'}],
  limit:'Caminhos simplificados, com tamanhos e durações fora de escala. Massa, composição e companheiras influenciam a evolução.'
 },
 'sistema-solar':{
  title:'Cada órbita tem seu ritmo',short:'Mais longe, uma volta demora mais',lede:'Observe três planetas. Eles avançam juntos no tempo, mas completam voltas em ritmos diferentes.',
  phases:[{at:0,label:'Mesmo Sol',say:'Os planetas seguem órbitas ao redor do Sol. Cada órbita tem seu próprio tamanho.'},{at:.25,label:'Ritmos diferentes',say:'Um planeta mais próximo completa sua volta antes de um planeta mais distante.'},{at:.72,label:'Uma relação',say:'Na aproximação de Kepler, o quadrado do período é proporcional ao cubo do tamanho da órbita.'}],
  limit:'Órbitas circulares e coplanares para comparar períodos. Raios desenhados e tamanhos dos planetas são ilustrativos.'
 },
 'terra-e-atmosfera':{
  title:'O ar muda conforme você sobe',short:'Uma atmosfera, várias camadas',lede:'Suba do solo até 120 km e acompanhe onde ficam as camadas do ar.',
  phases:[{at:0,label:'Perto do chão',say:'A troposfera reúne a maior parte do ar e quase todo o tempo que sentimos: nuvens, chuva e ventos.'},{at:.1,label:'Mais acima',say:'Na estratosfera, o ozônio absorve parte da radiação ultravioleta que vem do Sol.'},{at:.42,label:'Ar cada vez mais rarefeito',say:'Acima vêm a mesosfera e a termosfera. O ar continua ficando menos denso; as camadas não têm bordas rígidas.'}],
  limit:'Limites aproximados e desenho ampliado. A régua vai até 120 km; a atmosfera continua muito acima dessa altura.'
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
const starfield=()=>Array.from({length:45},(_,i)=>circle(35+(i*173)%890,105+(i*89)%365,i%9===0?1.7:1,C.ink,`opacity="${.12+(i%5)*.07}"`)).join('');

function galaxies(p:number){
 const phase=p<.34?0:p<.7?1:2;
 let body='';
 if(phase===0){
  body=circle(480,278,88,'#126c94')+`<ellipse cx="480" cy="278" rx="90" ry="25" fill="none" stroke="${C.cyan}" opacity=".6"/>`;
  body+=path('M430 218Q475 201 500 235L480 265L520 278L496 318L460 294L437 270Z','#6ed8b6',18,'stroke-linejoin="round"');
  body+=text(480,424,'Terra',28,C.ink,'text-anchor="middle" font-weight="700"')+text(480,456,'Nosso ponto de partida',20,C.muted,'text-anchor="middle"');
  body+=circle(745,185,18,C.gold)+path('M600 270Q675 190 724 187',C.line,2,'stroke-dasharray="6 7"')+text(745,226,'Sol',20,C.gold,'text-anchor="middle"');
 }else if(phase===1){
  body+=`<ellipse cx="480" cy="277" rx="275" ry="95" fill="#123d61" opacity=".45"/>`;
  for(let i=0;i<360;i++){const a=i*.23,r=12+(i%90)*2.8,arm=i%4*Math.PI/2;body+=circle(480+Math.cos(a*.2+arm)*r,277+Math.sin(a*.2+arm)*r*.39,.9+(i%3)*.35,i%9===0?C.gold:C.blue,`opacity="${.35+(i%5)*.1}"`);}
  body+=circle(480,277,18,C.gold)+circle(640,300,6,C.cyan)+line(640,312,665,368,C.cyan)+text(668,392,'Sistema Solar',19,C.cyan)+text(480,464,'Via Láctea',28,C.ink,'text-anchor="middle" font-weight="700"');
 }else{
  const nodes=[[110,185],[275,125],[460,235],[660,150],[838,230],[720,389],[480,418],[240,346]];
  const links=[[0,1],[0,7],[1,2],[1,3],[2,3],[2,6],[3,4],[4,5],[5,6],[6,7],[2,7]];
  for(const [a,b]of links){const A=nodes[a],B=nodes[b];body+=line(A[0],A[1],B[0],B[1],'#285976','stroke-width="13" opacity=".2"');for(let j=0;j<18;j++){const q=j/17,off=Math.sin(j*7.1+a)*11;body+=circle(A[0]+(B[0]-A[0])*q+off,A[1]+(B[1]-A[1])*q+off*.6,1.8,C.blue,'opacity=".6"');}}
  for(const n of nodes)body+=circle(n[0],n[1],10,C.gold)+circle(n[0]+8,n[1]-6,4,C.cyan)+circle(n[0]-11,n[1]+7,3,C.blue);
  body+=text(480,490,'Galáxias também se agrupam',24,C.ink,'text-anchor="middle"');
 }
 return body+text(40,88,['1 · Uma casa','2 · Uma galáxia','3 · Uma teia'][phase],17,C.cyan,'font-weight="700"');
}

function redshift(p:number){
 const a=1+p,period=72;
 const wave=(cy:number,k:number)=>Array.from({length:421},(_,i)=>{const x=i*2;return`${i?'L':'M'}${60+x},${(cy-25*Math.sin(2*Math.PI*x/(period*k))).toFixed(2)}`;}).join(' ');
 const box=(y:number)=>`<rect x="36" y="${y}" width="888" height="128" rx="14" fill="${C.surface}"/>`;
 let body=box(96)+box(250)+text(60,126,'NA EMISSÃO',16,C.blue,'font-weight="700"')+text(898,126,'400 nm',22,C.blue,'text-anchor="end"');
 body+=path(wave(173,1),C.blue,3)+path('M78 209v7 M78 213H150 M150 209v7',C.blue,2);
 body+=text(60,280,'DURANTE A EXPANSÃO',16,C.cyan,'font-weight="700"')+text(898,280,`${num(400*a,0)} nm`,22,C.cyan,'text-anchor="end"')+path(wave(327,a),C.cyan,3);
 body+=path(`M${60+18*a} 361v7 M${60+18*a} 365H${60+90*a} M${60+90*a} 361v7`,C.cyan,2);
 body+=text(60,421,'Espaço',16,C.muted)+text(60,457,`${num(a,2)} ×`,30,C.cyan,'font-weight="700"');
 body+=text(365,421,'Comprimento de onda',16,C.muted)+text(365,457,`${num(400*a,0)} nm`,30,C.ink,'font-weight="700"');
 body+=text(700,421,'Desvio para o vermelho',16,C.muted)+text(700,457,`z = ${num(p,2)}`,30,C.ink,'font-weight="700"');
 return body+text(480,503,p>.75?'A onda fica maior na mesma proporção que o espaço.':'Compare a distância entre duas cristas.',19,C.muted,'text-anchor="middle"');
}

function rotation(p:number){
 const k=p,points=Array.from({length:60},(_,i)=>{const r=.025+i/59*.975,visible=r<.3?r/.3:Math.sqrt(.3/r),halo=.95*(1-Math.exp(-r/.22));return {r,visible,model:Math.sqrt(visible**2+k*halo**2)};});
 const curve=(key:'visible'|'model')=>points.map((q,i)=>`${i?'L':'M'}${480+q.r*390},${(420-q[key]*190).toFixed(2)}`).join(' ');
 let body=starfield()+`<ellipse cx="240" cy="275" rx="160" ry="95" fill="#15466d" opacity=".28"/>`;
 for(let i=0;i<120;i++){const r=24+(i%30)*4.4,a=i*2.399+p*(2.3/(1+r/55));body+=circle(240+Math.cos(a)*r,275+Math.sin(a)*r*.62,1.7,i%7?C.blue:C.gold,'opacity=".75"');}
 body+=circle(240,275,18,C.gold)+`<ellipse cx="240" cy="275" rx="190" ry="124" fill="none" stroke="${C.cyan}" stroke-width="2" opacity="${k*.7}" stroke-dasharray="5 7"/>`;
 body+=path('M480 150V420H890',C.line,2)+path(curve('visible'),C.blue,3,'stroke-dasharray="6 7"')+path(curve('model'),C.cyan,4);
 body+=text(480,118,'Rapidez de giro',18,C.muted)+text(880,453,'Distância ao centro',17,C.muted,'text-anchor="end"');
 body+=line(90,480,125,480,C.blue,'stroke-width="3" stroke-dasharray="5 5"')+text(135,486,'Só matéria visível',17,C.blue);
 body+=line(480,480,515,480,C.cyan,'stroke-width="4"')+text(525,486,'Modelo com halo',17,C.cyan);
 return body;
}

function stars(p:number){
 const born=p<.3,bloom=Math.min(1,p/.3),late=Math.max(0,(p-.55)/.45);
 let body=starfield()+path('M480 220V275M480 275L235 340M480 275L725 340',C.line,3);
 if(born){for(let i=0;i<70;i++){const a=i*2.4,r=(15+(i%18)*5)*(1-bloom*.55);body+=circle(480+Math.cos(a)*r,215+Math.sin(a)*r*.55,4+i%4,C.blue,'opacity=".18"');}}
 body+=circle(480,215,20+bloom*16,C.gold)+text(480,136,born?'Uma nuvem se concentra':'Uma estrela começa a brilhar',24,C.ink,'text-anchor="middle"');
 body+=circle(235,350,24+late*28,'#ecba6b')+circle(725,350,34+late*23,'#9acbff');
 body+=text(235,430,'Como o Sol',23,C.ink,'text-anchor="middle"')+text(725,430,'Muito mais massiva',23,C.ink,'text-anchor="middle"');
 if(p>.7){body+=path('M235 446V459 M725 446V459',C.line,2)+circle(235,480,9,'#e5f6ff')+circle(695,480,8,C.cyan)+circle(755,480,11,'#010813',`stroke="${C.blue}" stroke-width="3"`);body+=text(235,520,'Anã branca',17,C.muted,'text-anchor="middle"')+text(725,520,'Nêutrons ou buraco negro',17,C.muted,'text-anchor="middle"');}
 return body;
}

function solar(p:number){
 const {axes,periods}=sampleStory('sistema-solar',p),radii=[76,135,195],names=['Mercúrio','Terra','Marte'],colors=[C.gold,C.cyan,'#e4a187'];
 let body=starfield()+circle(480,275,25,C.gold);
 axes.forEach((_a,i)=>{const period=periods[i],angle=-Math.PI/2+p*4*Math.PI*2/period;body+=`<ellipse cx="480" cy="275" rx="${radii[i]}" ry="${radii[i]*.7}" fill="none" stroke="${C.line}" stroke-width="2"/>`;body+=circle(480+Math.cos(angle)*radii[i],275+Math.sin(angle)*radii[i]*.7,[6,9,7][i],colors[i]);body+=circle(220+i*265,455,5,colors[i])+text(235+i*265,462,names[i],19,C.ink)+text(235+i*265,490,`${num(period,2)} ano`,17,C.muted);});
 return body+text(480,104,'O mesmo tempo passa para todos',24,C.ink,'text-anchor="middle"');
}

function atmosphere(p:number){
 const h=120*p,y=448-h/120*300;
 const layers=[{a:0,b:12,name:'Troposfera',fill:'#276d91'},{a:12,b:50,name:'Estratosfera',fill:'#205578'},{a:50,b:85,name:'Mesosfera',fill:'#173d61'},{a:85,b:120,name:'Termosfera',fill:'#102e50'}];
 let body=circle(260,350,105,'#0d7292')+`<ellipse cx="260" cy="350" rx="118" ry="118" fill="none" stroke="${C.cyan}" stroke-width="14" opacity=".16"/>`;
 body+=path('M212 286L255 278L277 315L248 338L274 373L247 412L207 370Z','#6cc7ae',16,'stroke-linejoin="round"');
 for(const layer of layers){const top=448-layer.b/120*300,height=(layer.b-layer.a)/120*300;body+=`<rect x="490" y="${top}" width="320" height="${height}" fill="${layer.fill}" opacity=".7"/>`;body+=text(820,top+height/2+5,layer.name,16,C.muted);}
 body+=line(490,148,490,448,C.line,'stroke-width="2"');
 for(const height of [0,12,50,85,120]){const at=448-height/120*300;body+=line(482,at,490,at,C.muted)+text(468,at+5,`${height}`,16,C.muted,'text-anchor="end"');}
 body+=line(490,y,807,y,C.cyan,'stroke-width="2"')+circle(520,y,7,C.ink)+text(650,107,`${num(h,0)} km`,32,C.cyan,'font-weight="700" text-anchor="middle"');
 body+=text(260,490,'Terra',24,C.ink,'text-anchor="middle"')+text(650,490,'Altitude acima do solo',18,C.muted,'text-anchor="middle"');
 return body;
}

/** SVG server-rendered e quadros de filme usam exatamente a mesma geometria. */
export function renderStory(id:string,progress:number,uid:string):string {
 const state=sampleStory(id,progress),story=STORIES[id],key=esc(`${uid}-${id}`);
 const scenes:Record<string,(p:number)=>string>={'galaxias-e-nebulosas':galaxies,'origem-do-universo':redshift,'misterios-do-cosmos':rotation,'vida-das-estrelas':stars,'sistema-solar':solar,'terra-e-atmosfera':atmosphere};
 return `<svg class="story-graphic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" role="img" aria-labelledby="${key}-title ${key}-desc"><title id="${key}-title">${esc(story.short)}</title><desc id="${key}-desc">${esc(story.phases[state.phase].say)}</desc><defs><radialGradient id="${key}-bg" cx=".65" cy=".25" r=".9"><stop stop-color="#0b304d"/><stop offset="1" stop-color="${C.bg}"/></radialGradient></defs><style>.story-graphic text{font-family:Arial,Helvetica,sans-serif}</style><rect width="960" height="540" fill="url(#${key}-bg)"/>${text(38,45,story.short.toLocaleUpperCase('pt-BR'),15,C.cyan,'letter-spacing="1.4" font-weight="700"')}${scenes[id](state.progress)}</svg>`;
}
