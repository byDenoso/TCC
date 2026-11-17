// Synthetic emissivity fields in world coordinates. The literal colours aid reading.
import { Application, BLEND_ADDITIVEALPHA, Entity, Mesh, MeshInstance, PRIMITIVE_POINTS, SEMANTIC_COLOR, SEMANTIC_POSITION, ShaderMaterial, Vec3 } from 'playcanvas';

function sequence(seed:number) {
  let n=seed;
  const uniform=() => ((n=(Math.imul(n,1664525)+1013904223)>>>0)+1)/4294967297;
  const normal=()=>Math.sqrt(-2*Math.log(uniform()))*Math.cos(2*Math.PI*uniform());
  return {uniform,normal};
}
type Samples = {positions:number[]; colors:number[]};
function point(field:Samples, x:number,y:number,z:number,r:number,g:number,b:number,size:number){
  field.positions.push(x,y,z);field.colors.push(r,g,b,size);
}
function cloud(app:Application, field:Samples, name:string, size:number) {
  const material=new ShaderMaterial({
    uniqueName:'story-emission-kernel-v1',attributes:{aPosition:SEMANTIC_POSITION,aColor:SEMANTIC_COLOR},
    vertexGLSL:`attribute vec3 aPosition; attribute vec4 aColor;
      uniform mat4 matrix_model; uniform mat4 matrix_viewProjection; uniform float angularSize;
      varying vec3 colour; void main(){
        gl_Position=matrix_viewProjection*matrix_model*vec4(aPosition,1.);
        gl_PointSize=clamp(angularSize*aColor.a/max(1.,gl_Position.w),1.2,40.);
        colour=aColor.rgb;}`,
    fragmentGLSL:`precision highp float; varying vec3 colour;
      void main(){vec2 p=gl_PointCoord*2.-1.;float r2=dot(p,p);
      if(r2>1.)discard; gl_FragColor=vec4(colour,exp(-4.2*r2)*(1.-r2));}`
  });
  material.blendType=BLEND_ADDITIVEALPHA;
  material.depthWrite=false;
  material.setParameter('angularSize',size);
  const mesh=new Mesh(app.graphicsDevice);
  mesh.setPositions(field.positions);mesh.setColors(field.colors);mesh.update(PRIMITIVE_POINTS);
  const node=new Entity(name);
  node.addComponent('render',{meshInstances:[new MeshInstance(mesh,material)]});
  return node;
}
export function background(app:Application) {
  const f:Samples={positions:[],colors:[]}, {uniform}=sequence(7369);
  for(let i=0;i<1400;i++){
    const t=2*Math.PI*uniform(), h=2*uniform()-1,r=Math.sqrt(1-h*h), warm=uniform();
    point(f,24*r*Math.cos(t),24*h,24*r*Math.sin(t),.45+warm*.34,.54+warm*.13,.74-warm*.17, .18+uniform()**4*.75);
  }
  return cloud(app,f,'Campo estelar',100);
}
export function cosmicWeb(app:Application) {
  const f:Samples={positions:[],colors:[]}, {uniform,normal}=sequence(120032);
  const nodes=Array.from({length:65},()=>new Vec3((uniform()-.5)*11,(uniform()-.5)*5.2,(uniform()-.5)*6.8));
  const seen=new Set<string>();
  for(const [i,node] of nodes.entries()){
    const others=nodes.map((v,j)=>({j,d:v.distance(node)})).filter(v=>v.j!==i).sort((a,b)=>a.d-b.d).slice(0,4);
    for(const {j,d} of others){
      const key=[Math.min(i,j),Math.max(i,j)].join('-');
      if(seen.has(key)||d>3.75)continue;seen.add(key);
      const end=nodes[j], bx=normal()*.22,by=normal()*.27,bz=normal()*.24;
      for(let k=0;k<350;k++){
        const t=uniform(),bend=Math.sin(Math.PI*t),spread=.018+.049*bend;
        const bright=uniform()**4,warm=.15+bright*.76;
        point(f,node.x+(end.x-node.x)*t+bx*bend+normal()*spread,node.y+(end.y-node.y)*t+by*bend+normal()*spread,node.z+(end.z-node.z)*t+bz*bend+normal()*spread,
          .14+.63*warm,.23+.41*warm,.35+.24*warm,.24+bright*.60);
      }
    }
    const strength=.1+uniform()*.19;
    for(let k=0;k<100;k++){
      const s=strength*(.15+1.7*uniform()**2),bright=uniform()**2;
      point(f,node.x+normal()*s,node.y+normal()*s,node.z+normal()*s,.47+.48*bright,.35+.46*bright,.27+.37*bright,.16+bright*.8);
    }
  }
  return cloud(app,f,'Filamentos e aglomerados',27);
}

export function stellarNursery(app:Application) {
  const f:Samples={positions:[],colors:[]},{uniform,normal}=sequence(421787);
  for(let clump=0;clump<55;clump++){
    const t=uniform()*6.28,rad=uniform()*2.7,cx=Math.cos(t)*rad,cy=Math.sin(1.4*t)*.58,cz=Math.sin(t)*rad*.58;
    const spread=.12+uniform()*.43,warm=uniform();
    for(let i=0;i<90;i++){
      const small=uniform();
      point(f,cx+normal()*spread,cy+normal()*spread*.68,cz+normal()*spread,.10+.12*warm,.07+.065*warm,.12+.07*(1-warm),.55+small*.95);
    }
  }
  return cloud(app,f,'Gás em torno da protoestrela',55);
}
