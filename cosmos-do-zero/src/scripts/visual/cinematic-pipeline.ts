import { RenderPipeline, type WebGPURenderer } from 'three/webgpu';
import { pass } from 'three/tsl';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { smaa } from 'three/addons/tsl/display/SMAANode.js';
import type { Camera, Scene } from 'three';

/** On-demand post-processing for compatible WebGPU scenes only. */
export function createCinematicPipeline(renderer:WebGPURenderer,scene:Scene,camera:Camera) {
  const scenePass=pass(scene,camera);
  const color=scenePass.getTextureNode('output');
  const glow=bloom(color,.22,.35,1);
  const antialias=smaa(color.add(glow));
  const pipeline=new RenderPipeline(renderer);
  pipeline.outputNode=antialias;
  return {
    render(){pipeline.render();},
    dispose(){pipeline.dispose();antialias.dispose();glow.dispose();scenePass.dispose();}
  };
}
