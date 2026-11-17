export interface StoryPhase { at:number; label:string; say:string }
export interface Story { title:string; short:string; lede:string; phases:StoryPhase[]; limit:string }
export const STORIES:Record<string,Story>={
 'galaxias-e-nebulosas':{
  title:'Uma casa dentro de outra',short:'Nosso endereço cósmico',lede:'Afaste o olhar: o que parecia enorme passa a fazer parte de algo maior.',
  phases:[{at:0,label:'Nossa casa',say:'A Terra orbita o Sol. O Sistema Solar é só uma pequena parte da nossa galáxia.'},{at:.34,label:'Nossa galáxia',say:'A Via Láctea reúne estrelas, gás e poeira. O Sol fica longe do centro.'},{at:.7,label:'A grande teia',say:'Galáxias se agrupam em fios e conjuntos maiores, separados por regiões menos povoadas.'}],
  limit:'Saltos de escala ilustrativos. A Terra, a galáxia e os filamentos são ilustrações em três escalas independentes.'
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
  limit:'Limites aproximados; o perfil de altitude está ampliado. A régua vai até 120 km; a atmosfera continua muito acima dessa altura.'
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
const ivory='#fff6e9', copper='#ffc996', ice='#a5d6ef', muted='#c7d0d4';
const esc=(value:string)=>value.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const n=(value:number,d=1)=>value.toFixed(d).replace('.',',');
const pt=(x:number)=>x.toFixed(2);

type ResolveImage=(path:string)=>string;
interface Plane {src:string;x:number;y:number;w:number;h:number;opacity:number;fit:'slice'|'meet'}
const plate=(src:string,x=0,y=0,w=960,h=540,opacity=1,fit:Plane['fit']='slice'):Plane=>({src,x,y,w,h,opacity,fit});
const render=(name:string)=>'/renders/'+name+'.webp';
const planet=(name:string)=>'/models/portraits/'+name+'.webp';
const matte='/media/stories/solar-disc.webp';
const type=(x:number,y:number,label:string,size:number,fill=ivory,extra='')=>`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" ${extra}>${esc(label)}</text>`;
const stroke=(d:string,color:string,width=2,extra='')=>`<path d="${d}" fill="none" stroke="${color}" stroke-width="${width}" ${extra}/>`;
const label=(x:number,y:number,s:string,size=28,fill=ivory)=>type(x,y,s,size,fill,'font-weight="600"');
const hero=(title:string,detail:string)=>label(44,439,title,60)+type(46,490,detail,28,muted);
function closer(src:string,zoom:number):Plane {const w=960*zoom,h=540*zoom;return plate(src,(960-w)*.54,(540-h)*.42,w,h);}

export function storyComposition(id:string,progress:number){
 const state=sampleStory(id,progress),p=state.progress,k=state.phase,planes:Plane[]=[];
 let overlay='',shade:'foot'|'left'|'split'|'none'='foot';
 if(id==='galaxias-e-nebulosas'){
  if(k===0){
   const size=526-110*p;
   planes.push(plate('/media/stories/studio-field.webp'),plate(planet('terra'),552-size*.32,245-size*.51,size,size,1,'meet'));
   overlay=hero('Terra','Um planeta do Sistema Solar');
  }else if(k===1){
   planes.push(closer(render('milky-way'),1.13-(p-.34)*.25));
   overlay=hero('Via Láctea','O Sol fica no disco galáctico');
  }else{
   planes.push(closer(render('cosmic-web'),1.19-(p-.7)*.58));
   overlay=hero('Teia cósmica','Filamentos, aglomerados e vazios');
  }
 }else if(id==='origem-do-universo'){
  planes.push(plate(render('galaxies'),400,-6,610,550,.85));
  shade='left';
  const wave=(baseline:number,period:number)=>Array.from({length:130},(_,i)=>{
   const x=i*4;return (i?'L':'M')+pt(48+x)+','+pt(baseline-20*Math.sin(x*Math.PI*2/period));
  }).join('');
  const width=62*(1+p);
  overlay=label(44,96,'Luz em expansão',44)+type(46,155,'Na emissão',25,muted)+label(46,200,'400 nm',38,ice)
    +stroke(wave(251,62),ice,3)+type(46,322,'No trajeto',25,muted)+label(46,367,n(state.wavelength,0)+' nm',38,copper)
    +stroke(wave(420,width),copper,3)+stroke(`M${pt(48+width/4)} 453v10m0 -5h${pt(width)}m0 -5v10`,copper,2)
    +type(46,503,'Fator de escala  '+n(state.scale,2)+' ×',26,ivory);
 }else if(id==='misterios-do-cosmos'){
  shade='split';
  planes.push(plate(render('milky-way'),-142,15,680,510,.94),plate(render('dark-matter'),-142,15,680,510,p*.76));
  const curve=(withHalo:boolean)=>Array.from({length:70},(_,i)=>{
   const r=.012+i*.988/69,stars=r<.3?r/.3:Math.sqrt(.3/r),halo=.95*(1-Math.exp(-r/.22));
   return (i?'L':'M')+pt(486+r*417)+','+pt(363-Math.hypot(stars,withHalo?Math.sqrt(p)*halo:0)*143);
  }).join('');
  overlay=label(474,84,'Curva de rotação',39)+type(477,135,'Velocidade relativa',25,muted)
    +stroke('M486 160V364H908','#87939a',1.5)+stroke(curve(false),ice,4,'stroke-dasharray="10 7"')+stroke(curve(true),copper,4)
    +type(895,400,'Raio galáctico →',23,muted,'text-anchor="end"')
    +stroke('M484 450h38',ice,3,'stroke-dasharray="6 4"')+type(539,459,'Matéria visível',24)
    +stroke('M484 491h38',copper,4)+type(539,500,'Modelo com halo',24);
 }else if(id==='vida-das-estrelas'){
  if(k===0){
   planes.push(closer('/models/stellar/orion-detail.webp',1+p*.55));
   overlay=hero('Berçário estelar','Nebulosa de Órion · Hubble');
  }else if(k===1){
   planes.push(closer(render('star'),1.02+(p-.3)*.22));
   overlay=hero('Fusão nuclear','A estrela transforma seu combustível');
  }else{
   planes.push(closer('/media/stories/stellar-remnants.webp',1.01+(p-.72)*.08));
   overlay=hero('Remanescentes','Anã branca · estrela de nêutrons · buraco negro');
  }
 }else if(id==='sistema-solar'){
  shade='none';
  const cx=530,cy=281,radii=[95,191,299],flatten=.51,names=['Mercúrio','Terra','Marte'],bodies=['mercurio','terra','marte'];
  // Render order follows the projected depth, including occultations by the Sun.
  const bodiesInDepth:{depth:number;plane:Plane}[]=[];
  for(let i=0;i<3;i++){
   const a=.40+i*1.8+p*Math.PI*2/state.periods[i],r=radii[i],x=cx+r*Math.cos(a),y=cy+r*flatten*Math.sin(a),sz=[32,46,36][i];
   bodiesInDepth.push({depth:Math.sin(a),plane:plate(planet(bodies[i]),x-sz/2,y-sz/2,sz,sz,1,'meet')});
  }
  bodiesInDepth.push({depth:0,plane:plate(matte,cx-47,cy-47,94,94,1,'meet')});
  planes.push(...bodiesInDepth.sort((a,b)=>a.depth-b.depth).map(v=>v.plane));
  overlay=label(44,76,'Períodos orbitais',46);
  for(let i=0;i<3;i++){
   const x=46+314*i;
   overlay+=type(x,452,names[i],29,ivory)+type(x,493,n(state.periods[i],2)+' ano'+(state.periods[i]>1?'s':''),26,muted);
  }
 }else if(id==='terra-e-atmosfera'){
  planes.push(plate('/media/stories/limbo-terrestre.webp',-110,-50+p*14,1080,650));
  shade='split';
  const stages=['Troposfera','Estratosfera','Mesosfera','Termosfera'],edges=[0,12,50,85,120],h=state.altitude,at=(v:number)=>427-2.56*v;
  overlay=label(444,72,'Perfil da atmosfera',38);
  for(let i=0;i<4;i++){
   const y=at(edges[i]),t=at(edges[i+1]);
   overlay+=stroke(`M530 ${pt(y)}H907`,'#586d78',1)+type(567,(y+t)/2+8,stages[i],25,ivory);
  }
  for(const h of edges)overlay+=type(511,at(h)+7,String(h),21,muted,'text-anchor="end"');
  overlay+=stroke('M530 119.8V427','#8e9da3',2)+stroke(`M525 ${pt(at(h))}H913`,copper,3)
    +label(446,498,'Altitude   '+n(h,0)+' km',33,copper);
 }
 const grid=id==='sistema-solar'?[95,191,299].map(r=>`<ellipse cx="530" cy="281" rx="${r}" ry="${pt(r*.51)}" fill="none" stroke="#788995" stroke-width="1.5" opacity=".62"/>`).join(''):'';
 return {state,planes,overlay,shade,grid};
}

export function renderStory(id:string,progress:number,uid:string,resolve:ResolveImage=p=>p):string {
 const {state,planes,overlay,shade,grid}=storyComposition(id,progress),key=esc(uid+'-'+id),story=STORIES[id];
 const stops=(pairs:[string,number][])=>pairs.map(([offset,opacity])=>`<stop offset="${offset}" stop-color="#03060a" stop-opacity="${opacity}"/>`).join('');
 const gradients=`<defs><linearGradient id="${key}-foot" x1="0%" y1="0%" x2="0%" y2="100%" gradientUnits="objectBoundingBox">${stops([['0',.06],['.46',0],['.75',.3],['1',.84]])}</linearGradient><linearGradient id="${key}-left">${stops([['0',1],['.43',.95],['.61',.54],['1',.06]])}</linearGradient><linearGradient id="${key}-split">${stops([['0',.02],['.36',.08],['.53',.94],['1',.99]])}</linearGradient></defs>`;
 const field=id==='sistema-solar' ? `<image width="960" height="540" href="${esc(resolve('/media/stories/studio-field.webp'))}" xlink:href="${esc(resolve('/media/stories/studio-field.webp'))}"/>` : '';
 const imgs=planes.map(layer=>`<image x="${pt(layer.x)}" y="${pt(layer.y)}" width="${pt(layer.w)}" height="${pt(layer.h)}" opacity="${pt(layer.opacity)}" preserveAspectRatio="xMidYMid ${layer.fit}" href="${esc(resolve(layer.src))}" xlink:href="${esc(resolve(layer.src))}"/>`).join('');
 return `<svg class="story-graphic" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 960 540" role="img" aria-labelledby="${key}-title ${key}-desc"><title id="${key}-title">${esc(story.short)}</title><desc id="${key}-desc">${esc(story.phases[state.phase].say)}</desc>${gradients}<rect width="960" height="540" fill="#06090e"/>${field}${grid}<g data-story-planes="">${imgs}</g><rect width="960" height="540" fill="${shade==='none'?'none':'url(#'+key+'-'+shade+')'}"/><g data-story-overlay="" font-family="Arial, Helvetica, sans-serif">${overlay}</g></svg>`;
}
