import { observeScene } from '../visual/runtime';
import { cosmicWeb } from '../visual/web';
export interface Web3D { set(k:number):void; setPlaying(on:boolean):void; dispose():void }
/** Adaptador compatível; usa a mesma licença de WebGL e o relógio do motor. */
export async function mountWeb3D(stage:HTMLElement,_reduced:()=>boolean):Promise<Web3D|null>{
 const {prepareEmissionGalaxies,emissionSize}=await import('../visual/galaxy-emission');const size=emissionSize(stage.clientWidth);await prepareEmissionGalaxies(size);
 const view=observeScene(stage,()=>cosmicWeb(size));
 return {set(k){view.state({value:k});},setPlaying(on){view.play(on);},dispose(){view.dispose();}};
}
