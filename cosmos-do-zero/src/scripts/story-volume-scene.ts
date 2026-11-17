import { Application, BLEND_NORMAL, Color, CULLFACE_NONE, Entity, Mesh, MeshInstance, PRIMITIVE_LINESTRIP, SEMANTIC_NORMAL, SEMANTIC_POSITION, SEMANTIC_TEXCOORD0, ShaderMaterial, StandardMaterial, Texture, Vec3 } from 'playcanvas';
import { background, cosmicWeb, stellarNursery } from './story-volume-fields';

const TAU=2*Math.PI;
// Textures and spherical geometry come from the same Blender collection as Saturn.
export async function openStoryVolume(canvas:HTMLCanvasElement, chapter:string, base:string) {
  const app=new Application(canvas,{graphicsDeviceOptions:{antialias:true,alpha:false,powerPreference:'low-power'}});
  app.autoRender=false;
  const resources=new Set<{destroy:()=>void}>();
  const own=<T extends {destroy:()=>void}>(r:T)=>{resources.add(r);return r;};
  const cameras=new Entity('Observador');
  const world=new Entity('Cena da aula');
  app.root.addChild(world);
  cameras.addComponent('camera',{clearColor:new Color(.009,.014,.023),fov:37,nearClip:.08,farClip:70});
  app.root.addChild(cameras);
  app.scene.ambientLight=new Color(.28,.33,.40);
  const light=new Entity('Luz solar');
  light.addComponent('light',{type:'directional',color:new Color(1,.954,.89),intensity:1.65});
  light.setPosition(-4.5,4,7);light.lookAt(Vec3.ZERO);light.rotateLocal(90,0,0);app.root.addChild(light);
  const rim=new Entity('Luz de contorno');
  rim.addComponent('light',{type:'directional',color:new Color(.48,.67,1),intensity:.78});
  rim.setPosition(3,1.5,-4);rim.lookAt(Vec3.ZERO);rim.rotateLocal(90,0,0);app.root.addChild(rim);

  const textures=new Map<string,Promise<Texture>>();
  function asset(url:string,type:string) {
    return new Promise<import('playcanvas').Asset>((resolve,reject)=>app.assets.loadFromUrl(base+url,type,(err,a)=>err||!a?reject(new Error('Ativo indisponível: '+url)):resolve(a)));
  }
  function texture(url:string) {
    if(!textures.has(url))textures.set(url,asset(url,'texture').then(a=>a.resource as Texture));
    return textures.get(url)!;
  }
  let worlds:Promise<Entity>|undefined;
  async function planet(name:string){
    worlds??=asset('models/mundos.glb','container').then(a=>(a.resource as {instantiateRenderEntity:()=>Entity}).instantiateRenderEntity());
    const root=await worlds;
    const model=root.findByName(name);
    if(!(model instanceof Entity))throw new Error('Corpo ausente: '+name);
    const body=model.clone();
    if(name==='terra')body.forEach(n=>{
      if(!(n instanceof Entity)||!n.render)return;
      for(const mesh of n.render.meshInstances){
        const mapped=mesh.material;
        if(!(mapped instanceof StandardMaterial))continue;
        if(mapped.name.includes('cloud')){
          const cloud=own(mapped.clone());
          cloud.opacity=.14;cloud.depthWrite=false;cloud.update();mesh.material=cloud;
        }else if(mapped.diffuseMap){
          const surface=own(new ShaderMaterial({uniqueName:'story-mapped-earth',
            attributes:{aPosition:SEMANTIC_POSITION,aNormal:SEMANTIC_NORMAL,aUv:SEMANTIC_TEXCOORD0},
            vertexGLSL:`attribute vec3 aPosition;attribute vec3 aNormal;attribute vec2 aUv;
            uniform mat4 matrix_viewProjection;uniform mat4 matrix_model;
            varying vec3 nW;varying vec3 wPos;varying vec2 coord;
            void main(){vec4 w=matrix_model*vec4(aPosition,1.);nW=normalize(mat3(matrix_model)*aNormal);
            wPos=w.xyz;coord=aUv;gl_Position=matrix_viewProjection*w;}`,
            fragmentGLSL:`precision highp float;varying vec3 nW;varying vec3 wPos;varying vec2 coord;
            uniform sampler2D surfaceMap;uniform vec3 view_position;
            void main(){vec3 n=normalize(nW);float sun=dot(n,normalize(vec3(-.65,.55,.83)));
            float edge=pow(1.-max(0.,dot(n,normalize(view_position-wPos))),3.);
            vec3 land=pow(texture2D(surfaceMap,coord).rgb,vec3(.48));
            gl_FragColor=vec4(land*(.25+1.08*max(0.,sun))+vec3(.06,.23,.40)*edge*smoothstep(-.32,.5,sun),1.);}`}));
          surface.setParameter('surfaceMap',mapped.diffuseMap);mesh.material=surface;
        }
      }
    });
    return body;
  }
  function solid(name:string,color:Color,emission=.06) {
    const m=own(new StandardMaterial());
    m.diffuse=color;m.emissive=color.clone().mulScalar(emission);m.gloss=.24;m.update();
    const e=new Entity(name);e.addComponent('render',{type:'sphere',material:m});return e;
  }
  async function photosphere(color:Color) {
    const m=own(new ShaderMaterial({uniqueName:'story-granular-star',attributes:{aPosition:SEMANTIC_POSITION,aNormal:SEMANTIC_NORMAL,aUv:SEMANTIC_TEXCOORD0},
      vertexGLSL:`attribute vec3 aPosition;attribute vec3 aNormal;attribute vec2 aUv;uniform mat4 matrix_model;uniform mat4 matrix_viewProjection;
      varying vec3 positionW;varying vec3 normalW;varying vec2 uv;void main(){vec4 world=matrix_model*vec4(aPosition,1.);
      positionW=world.xyz;normalW=normalize(mat3(matrix_model)*aNormal);uv=aUv;gl_Position=matrix_viewProjection*world;}`,
      fragmentGLSL:`precision highp float;uniform sampler2D granulation;uniform vec3 tint;uniform vec3 view_position;
      varying vec3 positionW;varying vec3 normalW;varying vec2 uv;void main(){
      float mu=max(dot(normalize(normalW),normalize(view_position-positionW)),0.);
      float gran=texture2D(granulation,uv*vec2(3.,1.5)).r;
      float regions=texture2D(granulation,uv*vec2(1.,.8)+.18).r;
      float brightness=(.34+.66*pow(mu,.54))*(.8+1.25*(gran-.5));
      vec3 surface=mix(tint,tint*vec3(.65,.41,.23),(1.-smoothstep(.05,.34,regions))*.42);
      gl_FragColor=vec4(surface*brightness,1.);}`}));
    m.setParameter('granulation',await texture('models/stellar/granulation.png'));m.setParameter('tint',[color.r,color.g,color.b]);
    const e=new Entity('Fotosfera');e.addComponent('render',{type:'sphere',material:m});return e;
  }
  function line(name:string,coords:number[],color:Color){
    const m=own(new StandardMaterial());m.useLighting=false;m.emissive=color;m.update();
    const mesh=own(new Mesh(app.graphicsDevice));mesh.setPositions(coords);mesh.update(PRIMITIVE_LINESTRIP);
    const e=new Entity(name);e.addComponent('render',{meshInstances:[new MeshInstance(mesh,m)]});return e;
  }
  function orbit(radius:number,color:Color){
    const points=[];
    for(let i=0;i<=180;i++){const t=TAU*i/180;points.push(radius*Math.cos(t),0,radius*Math.sin(t));}
    return line('Órbita ilustrativa',points,color);
  }
  async function disk(){
    const tex=await texture('models/galaxies-v4/768/barred-spiral.webp');
    const material=own(new StandardMaterial());
    material.useLighting=false;material.diffuse=new Color(0,0,0);material.emissive=new Color(1.48,1.28,1.14);material.emissiveMap=tex;
    material.opacityMap=tex;material.opacityMapChannel='a';material.blendType=BLEND_NORMAL;material.depthWrite=false;material.cull=CULLFACE_NONE;material.update();
    const galaxy=new Entity('Disco da galáxia');galaxy.addComponent('render',{type:'plane',material});
    galaxy.setLocalScale(7.8,1,7.8);return galaxy;
  }
  function place(parent:Entity, object:Entity, x:number,y:number,z:number, scale?:number){
    parent.addChild(object);object.setLocalPosition(x,y,z);if(scale!==undefined)object.setLocalScale(scale,scale,scale);
    return object;
  }
  let tilt=.1, distance=7.6;
  type Frame=(p:number,i:number)=>string;
  async function build():Promise<Frame> {
    if(chapter==='galaxias-e-nebulosas'){
      const [earth,galaxy]=await Promise.all([planet('terra'),disk()]);
      place(world,earth,0,0,0,1.58);world.addChild(galaxy);
      const web=cosmicWeb(app);world.addChild(web);
      const sun=solid('Posição esquemática do Sol',new Color(1,.74,.26),1.3);
      place(world,sun,1.5,.085,.65,.095);
      return(p,i)=>{
        earth.enabled=i===0;galaxy.enabled=sun.enabled=i===1;web.enabled=i===2;
        earth.setLocalEulerAngles(10,-18+23*p,-14);
        tilt=i===1?.64:.14;distance=i===2?10.5:7.4;
        return ['Terra · superfície e nuvens','Via Láctea · posição ilustrativa do Sol','Teia cósmica · filamentos e vazios ilustrativos'][i];
      };
    }
    if(chapter==='sistema-solar'){
      const [sun,...planets]=await Promise.all([photosphere(new Color(1,.86,.61)),planet('mercurio'),planet('terra'),planet('marte')]);
      place(world,sun,0,0,0,.9);
      const axes=[.387,1,1.524], sizes=[.12,.25,.18];
      planets.forEach((e,i)=>{world.addChild(orbit(axes[i]*2.2,new Color(.32,.35,.38)));place(world,e,0,0,0,sizes[i]);});
      tilt=.62;
      return p=>{
        planets.forEach((e,i)=>{const angle=i*2+TAU*p/axes[i]**1.5;e.setLocalPosition(axes[i]*2.2*Math.cos(angle),0,axes[i]*2.2*Math.sin(angle));});
        return 'Mercúrio, Terra e Marte · raios dos planetas ampliados';
      };
    }
    if(chapter==='terra-e-atmosfera'){
      const earth=await planet('terra');
      place(world,earth,0,-2,0,3.65);
      earth.setLocalEulerAngles(0,-18,-15);
      const profile=line('Perfil de altitude',[0,0,0,0,1.8,0],new Color(.79,.83,.88));
      place(world,profile,0,1.66,0);
      const marker=solid('Altitude',new Color(.97,.64,.25),.9);place(world,marker,0,1.67,0,.14);
      distance=9.6;tilt=.09;
      return(p)=>{marker.setLocalPosition(0,1.68+1.72*p,0);return `${Math.round(p*120)} km · altura do marcador ampliada`;};
    }
    if(chapter==='origem-do-universo'){
      const wave=(color:Color)=>{
        const points=[];
        for(let k=0;k<=640;k++){const x=6*k/640;points.push(x,.35*Math.sin(TAU*x/.85),0);}
        return line('Cristas da onda',points,color);
      };
      const source=await disk();source.setLocalScale(2.2,1,2.2);source.setLocalEulerAngles(44,0,-14);place(world,source,-3,.12,0);
      const ref=wave(new Color(.45,.72,1)), arriving=wave(new Color(1,.68,.32));
      place(world,ref,-2.1,.63,0);place(world,arriving,-2.1,-.62,0);
      const receiver=solid('Extremo do trecho',new Color(.71,.66,.53),.2);
      place(world,receiver,3.3,-.62,0,.19);distance=8.6;
      return p=>{
        // Wavelength doubles within a fixed spatial window. Clip the path by resampling its vertices.
        const mesh=arriving.render!.meshInstances[0].mesh!;
        const pts=[];for(let k=0;k<=320;k++){const x=5.4*k/320;pts.push(x,.35*Math.sin(TAU*x/(.85*(1+p))),0);}
        mesh.setPositions(pts);mesh.update(PRIMITIVE_LINESTRIP);
        return `Emissão 400 nm · recepção ${Math.round(400*(1+p))} nm · cores convencionais`;
      };
    }
    if(chapter==='misterios-do-cosmos'){
      const galaxy=await disk();world.addChild(galaxy);
      const guide=orbit(2.5,new Color(.39,.45,.52));world.addChild(guide);
      const predicted=solid('Matéria visível',new Color(.44,.73,.96),.7),total=solid('Componente de halo',new Color(.99,.68,.33),.9);
      place(world,predicted,0,0,0,.18);place(world,total,0,0,0,.18);
      tilt=.69;
      return (p,i)=>{
        for(const [body,t] of [[predicted,TAU*.66*p],[total,TAU*1.02*p]] as const)body.setLocalPosition(2.5*Math.cos(t),.07,2.5*Math.sin(t));
        total.enabled=i>0;return i?'Mesma órbita · azul: matéria visível · âmbar: giro maior':'Disco visível · marcador azul na órbita de referência';
      };
    }
    const [young,companion]=await Promise.all([photosphere(new Color(1,.79,.51)),photosphere(new Color(.72,.85,1.0))]);
    const cloud=stellarNursery(app);world.addChild(cloud);
    place(world,young,-.7,0,0,1.7);place(world,companion,1.23,0,.12,2.6);
    const remnant=solid('Anã branca',new Color(.89,.94,1),.98), neutron=solid('Estrela de nêutrons',new Color(.72,.87,1),.9);
    place(world,remnant,-1,0,0,.50);place(world,neutron,1.22,0,.08,.18);
    return(p,i)=>{
      cloud.enabled=i===0;young.enabled=i<2;companion.enabled=i===1;
      remnant.enabled=neutron.enabled=i===2;
      young.setLocalPosition(i===0?0:-1.15,0,0);young.setLocalScale(i===0?.62:1.7,i===0?.62:1.7,i===0?.62:1.7);young.setLocalEulerAngles(0,p*36,0);
      return ['Nuvem de gás · protoestrela central','Duas massas iniciais · superfícies ilustrativas','Dois remanescentes possíveis · tamanhos ampliados'][i];
    };
  }
  let observer:ResizeObserver|undefined;
  const dispose=()=>{
    observer?.disconnect();
    world.forEach(node=>{
      if(!(node instanceof Entity)||!node.render)return;
      for(const instance of node.render.meshInstances)if(instance.material instanceof ShaderMaterial)resources.add(instance.material);
    });
    for(const resource of resources)resource.destroy();
    void worlds?.then(e=>e.destroy()).catch(()=>{});
    app.destroy();
  };
  try{
    world.addChild(background(app));
    const animate=await build();
    const resize=()=>{
      const {width,height}=canvas.getBoundingClientRect();
      if(!width||!height)return;
      const ratio=Math.min(devicePixelRatio||1,1.65);
      app.graphicsDevice.resizeCanvas(Math.round(width*ratio),Math.round(height*ratio));
      app.renderNextFrame=true;
    };
    observer=new ResizeObserver(resize);observer.observe(canvas);app.start();
    return {dispose,resize,frame(p:number,phase:number,yaw:number,pitch:number){
      const label=animate(p,phase);
      const angle=Math.max(-.58,Math.min(1.15,tilt+pitch));
      cameras.setPosition(distance*Math.cos(angle)*Math.sin(yaw),distance*Math.sin(angle),distance*Math.cos(angle)*Math.cos(yaw));
      cameras.lookAt(Vec3.ZERO);
      app.renderNextFrame=true;
      return label;
    }};
  }catch(error){dispose();throw error;}
}
