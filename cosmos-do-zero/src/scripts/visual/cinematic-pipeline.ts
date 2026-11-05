import { RenderPipeline, type Node, type WebGPURenderer } from 'three/webgpu';
import { convertToTexture, getScreenPositionFromClip, getViewPosition, logarithmicDepthToViewZ, nodeObject, orthographicDepthToViewZ, pass, perspectiveDepthToViewZ, uniform, uv, vec4, viewZToPerspectiveDepth } from 'three/tsl';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { dof } from 'three/addons/tsl/display/DepthOfFieldNode.js';
import { smaa } from 'three/addons/tsl/display/SMAANode.js';
import { Matrix4, type Camera, type OrthographicCamera, type PerspectiveCamera, type Scene, type Vector3 } from 'three';

export interface CinematicOptions { depthOfField?:boolean; bloom?:boolean; cameraBlur?:boolean; antialias?:boolean }

/** On-demand post-processing for compatible WebGPU scenes only. */
export function createCinematicPipeline(renderer:WebGPURenderer,scene:Scene,camera:Camera,focusTarget:Vector3,options:CinematicOptions={}) {
  const lens=camera as PerspectiveCamera|OrthographicCamera;
  camera.updateMatrixWorld();
  const previousMatrix=new Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);
  const currentMatrix=new Matrix4(), previous=uniform(previousMatrix);
  const projectionInverse=uniform(camera.projectionMatrixInverse),worldMatrix=uniform(camera.matrixWorld);
  const near=uniform(lens.near),far=uniform(lens.far);
  const focus=uniform(Math.max(camera.position.distanceTo(focusTarget),.1)),focusRange=uniform(Math.max(focus.value*.75,.1));
  let historyInvalid=false;
  const scenePass=pass(scene,camera);
  const color=scenePass.getTextureNode('output');
  const depth=scenePass.getTextureNode('depth').r;
  const orthographic='isOrthographicCamera' in camera&&camera.isOrthographicCamera===true;
  const viewZ=orthographic?orthographicDepthToViewZ(depth,near,far):renderer.logarithmicDepthBuffer?logarithmicDepthToViewZ(depth,near,far):perspectiveDepthToViewZ(depth,near,far);
  const projectionDepth=orthographic?depth:viewZToPerspectiveDepth(viewZ,near,far);
  const viewPosition=getViewPosition(uv(),projectionDepth,projectionInverse);
  const worldPosition=worldMatrix.mul(vec4(viewPosition,1));
  const lastPosition=getScreenPositionFromClip(previous.mul(worldPosition));
  // Reproject the current depth through the previous camera only. Moving scene
  // objects with a stationary camera therefore do not acquire motion blur.
  const velocity=uv().sub(lastPosition).mul(.2).clamp(-.015,.015);
  const depthOfField=options.depthOfField===false?null:dof(color,viewZ,focus,focusRange,.25);
  // The addon declaration omits the TSL node extensions available at runtime.
  const focused=depthOfField?convertToTexture(nodeObject(depthOfField as unknown as Node<'vec4'>)):color;
  const glow=options.bloom===false?null:bloom(focused,.22,.35,1);
  const combined=glow?convertToTexture(focused.add(glow)):focused;
  const center=uv(),blur=combined.sample(center).mul(.4)
    .add(combined.sample(center.add(velocity.mul(.5))).mul(.15))
    .add(combined.sample(center.sub(velocity.mul(.5))).mul(.15))
    .add(combined.sample(center.add(velocity)).mul(.15))
    .add(combined.sample(center.sub(velocity)).mul(.15));
  const blurred=options.cameraBlur===false?combined:convertToTexture(blur);
  const antialias=options.antialias===false?null:smaa(blurred);
  const pipeline=new RenderPipeline(renderer);
  pipeline.outputNode=antialias??blurred;
  return {
    render(){
      camera.updateMatrixWorld();
      near.value=lens.near;far.value=lens.far;
      focus.value=Math.max(camera.position.distanceTo(focusTarget),.1);focusRange.value=Math.max(focus.value*.75,.1);
      currentMatrix.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);
      if(historyInvalid){previousMatrix.copy(currentMatrix);historyInvalid=false;}
      pipeline.render();previousMatrix.copy(currentMatrix);
    },
    resetHistory(){historyInvalid=true;},
    dispose(){pipeline.dispose();antialias?.dispose();if(blurred!==combined)blurred.dispose();if(combined!==focused)combined.dispose();glow?.dispose();if(focused!==color)focused.dispose();depthOfField?.dispose();scenePass.dispose();}
  };
}
