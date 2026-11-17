import { Application, Asset, Color, Entity, PROJECTION_ORTHOGRAPHIC, SEMANTIC_POSITION, SEMANTIC_NORMAL, SEMANTIC_TEXCOORD0, ShaderMaterial, StandardMaterial, Vec3, type RenderComponent } from 'playcanvas';
import { measurement, type StudyKey } from '../lib/atlas-studies';

/** Blender exports metres in a Y-up frame. Each instrument has its own optical axis. */
const setups = {
  redshift: {eye:[0,8,6], aim:[0,0,0], height:1.85, width:3.7},
  lens: {eye:[0,9,.001], aim:[0,0,0], height:2.1, width:2.25},
  star: {eye:[0,.3,9], aim:[.2,0,0], height:1.98, width:3.22},
  orbit: {eye:[0,6.5,6.4], aim:[0,0,0], height:1.95, width:2.95},
  air: {eye:[1.5,2.3,8], aim:[0,1.12,0], height:1.5, width:2.2}
} as const;

/** Emitting photospheres keep the same surface brightness as their radius changes. */
function photospheres(root:Entity) {
  const material=new ShaderMaterial({
    uniqueName:'atlas-solar-limb',
    attributes:{ vertex_position:SEMANTIC_POSITION, vertex_normal:SEMANTIC_NORMAL, vertex_texCoord0:SEMANTIC_TEXCOORD0 },
    vertexGLSL:`
      attribute vec3 vertex_position;
      attribute vec3 vertex_normal;
      attribute vec2 vertex_texCoord0;
      uniform mat4 matrix_model;
      uniform mat4 matrix_view;
      uniform mat4 matrix_viewProjection;
      varying vec3 normalEye;
      varying vec2 surfaceUV;
      void main() {
        surfaceUV=vertex_texCoord0;
        normalEye=mat3(matrix_view*matrix_model)*vertex_normal;
        gl_Position=matrix_viewProjection*matrix_model*vec4(vertex_position,1.);
      }`,
    fragmentGLSL:`
      precision highp float;
      varying vec3 normalEye;
      varying vec2 surfaceUV;
      uniform sampler2D surfaceMap;
      void main() {
        float limb=.46+.54*pow(max(normalize(normalEye).z,0.),.72);
        vec3 surface=texture2D(surfaceMap,surfaceUV).rgb;
        gl_FragColor=vec4(surface*limb,1.);
      }`
  });
  for(const component of root.findComponents('render') as RenderComponent[]){
    for(const mesh of component.meshInstances){
      const original=mesh.material;
      if(original instanceof StandardMaterial && original.name==='Granulação da fotosfera' && original.diffuseMap){
        material.setParameter('surfaceMap',original.diffuseMap);
        mesh.material=material;
      }
    }
  }
  return material;
}

export async function openStudy(canvas: HTMLCanvasElement, key: StudyKey, url: string) {
  const app = new Application(canvas, {graphicsDeviceOptions:{antialias:true,alpha:true,powerPreference:'low-power'}});
  try {
    app.graphicsDevice.maxPixelRatio=Math.min(devicePixelRatio,1.75);
    app.scene.ambientLight=new Color(.24,.27,.33);
    const setup=setups[key], target=new Vec3(...setup.aim);
    const camera=new Entity('Projeção do instrumento');
    camera.addComponent('camera',{projection:PROJECTION_ORTHOGRAPHIC,clearColor:new Color(0,0,0,0),nearClip:.05,farClip:50});
    camera.setPosition(new Vec3(...setup.eye));
    camera.lookAt(target);
    app.root.addChild(camera);
    for(const [position,tint,power] of [
      [[-4,6,5],[1,.88,.71],1.32],[[4,3,-4],[.49,.68,1],.78]
    ] as const) {
      const lamp=new Entity();
      lamp.addComponent('light',{type:'directional',color:new Color(...tint),intensity:power});
      lamp.setPosition(new Vec3(...position));
      lamp.lookAt(target);
      lamp.rotateLocal(90,0,0);
      app.root.addChild(lamp);
    }
    const model=new Asset(key,'container',{url});
    app.assets.add(model);
    await new Promise<void>((resolve,reject)=>{
      model.once('load',resolve); model.once('error',reject); app.assets.load(model);
    });
    if(!model.resource) throw new Error('Modelo sem geometria');
    const root:Entity=model.resource.instantiateRenderEntity();
    app.root.addChild(root);
    const measure=root.findByName('Measure'), planet=root.findByName('Planet');
    if(!measure) throw new Error('Medição ausente no modelo');
    const solar=key==='star'||key==='orbit'?photospheres(root):null;
    const halo=root.findByName('HaloMeasure');
    app.autoRender=false;
    const resize=()=>{
      const {width,height}=canvas.getBoundingClientRect();
      if(!width||!height)return;
      app.graphicsDevice.resizeCanvas(Math.round(width),Math.round(height));
      camera.camera!.orthoHeight=Math.max(setup.height,setup.width*height/width);
      app.renderNextFrame=true;
    };
    resize(); const observer=new ResizeObserver(resize); observer.observe(canvas); app.start();
    return {
      update(v:number) {
        if(key==='redshift') measure.setLocalScale(1+v,1,1);
        if(key==='lens'||key==='orbit'){
          const scale=key==='lens'?measurement(key,v):v;
          measure.setLocalScale(scale,1,scale);
          planet?.setLocalPosition(1.24*v,0,0);
        }
        if(key==='star'){measure.setLocalScale(v,v,v);halo?.setLocalScale(v,v,v);}
        if(key==='air'){
          const ratio=measurement(key,v)/100;
          measure.setLocalScale(1,ratio,1);
          measure.setLocalPosition(1.15,.15+ratio,0);
        }
        app.renderNextFrame=true;
      },
      close(){observer.disconnect(); solar?.destroy(); app.destroy();}
    };
  } catch(e){app.destroy();throw e;}
}
