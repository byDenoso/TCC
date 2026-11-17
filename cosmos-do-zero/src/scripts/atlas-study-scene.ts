import { Application, Asset, Color, Entity, PROJECTION_ORTHOGRAPHIC } from 'playcanvas';
import { measurement, type StudyKey } from '../lib/atlas-studies';

export async function openStudy(canvas:HTMLCanvasElement, key:StudyKey, url:string) {
  const app = new Application(canvas, { graphicsDeviceOptions:{antialias:true,alpha:false} });
  try {
    app.graphicsDevice.maxPixelRatio = Math.min(devicePixelRatio, 1.75);
    app.scene.ambientLight = new Color(.48,.53,.55);
    const camera = new Entity('Caméra');
    camera.addComponent('camera',{ projection:PROJECTION_ORTHOGRAPHIC,orthoHeight:3.1, clearColor:new Color(.025,.049,.058),nearClip:.05,farClip:60 });
    camera.setPosition(2.2,7.5,6.1);
    camera.lookAt(0,.22,0);
    app.root.addChild(camera);
    for (const [pitch,yaw,intensity] of [[46,-35,1.9], [28,155,.8]]) {
      const lamp = new Entity();
      lamp.addComponent('light',{type:'directional',intensity,color:new Color(1,.94,.84)});
      lamp.setEulerAngles(-pitch,yaw,0);
      app.root.addChild(lamp);
    }
    const model = new Asset(key,'container',{url});
    app.assets.add(model);
    await new Promise<void>((resolve,reject)=>{
      model.once('load',resolve);
      model.once('error',reject);
      app.assets.load(model);
    });
    if (!model.resource) throw new Error('Modelo sem geometria');
    const root:Entity = model.resource.instantiateRenderEntity();
    app.root.addChild(root);
    const measure = root.findByName('Measure');
    if (!measure) throw new Error('Medição ausente no modelo');
    const planet = root.findByName('Planet');
    app.autoRender = false;
    const resize=()=>{
      const w=canvas.clientWidth, h=canvas.clientHeight;
      if (!w || !h) return;
      app.graphicsDevice.resizeCanvas(w,h);
      camera.camera!.orthoHeight=Math.max(2.75,4.15*h/w);
      app.renderNextFrame=true;
    };
    resize();
    const observer=new ResizeObserver(resize);
    observer.observe(canvas);
    app.start();
    return {
      update(v:number) {
        if(key==='redshift') measure.setLocalScale(1+v,1,1);
        if(key==='lens'||key==='orbit') {
          const scale=key==='lens'?measurement(key,v):v;
          measure.setLocalScale(scale,1,scale);
          planet?.setLocalPosition(.94*v,.14,0);
        }
        if(key==='star') {
          measure.setLocalScale(v,v,v);
          measure.setLocalPosition(1.25,.03+.62*v,0);
        }
        if(key==='air') {
          const ratio=measurement(key,v)/100;
          measure.setLocalScale(1,ratio,1);
          measure.setLocalPosition(1.1,.22+.95*ratio,0);
        }
        app.renderNextFrame=true;
      },
      close(){observer.disconnect();app.destroy();}
    };
  } catch(e) {app.destroy();throw e;}
}
