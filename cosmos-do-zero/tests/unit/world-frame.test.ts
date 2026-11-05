import {describe,expect,it} from 'vitest';
import {Object3D,PerspectiveCamera,Vector3} from 'three';
import {moveWorldPosition,rebaseWorld,relativePositionMeters,worldPositionMeters} from '../../src/scripts/visual/world-frame';

describe('camera-relative world coordinates',()=>{
  it('retains metre and sub-metre offsets past cell boundaries at a synthetic 10^27 m anchor',()=>{
    const reference=worldPositionMeters(10n**27n,-(10n**27n),0n);
    const shifted=moveWorldPosition(reference,[1048576.25,-1048577.5,1]);
    expect(relativePositionMeters(shifted,reference)).toEqual([1048576.25,-1048577.5,1]);
    expect(relativePositionMeters(moveWorldPosition(shifted,[-1048576.25,1048577.5,-1]),reference)).toEqual([0,0,0]);
  });
  it('keeps real Three.js camera projection continuous through a rebase',()=>{
    const reference=worldPositionMeters(10n**27n,0n,0n);
    const cameraWorld=moveWorldPosition(reference,[.25,0,0]);
    const targetWorld=moveWorldPosition(reference,[1.25,0,-4]);
    const camera=new PerspectiveCamera(50,16/9,.01,100),target=new Object3D();
    const anchors=[{object:camera,position:cameraWorld},{object:target,position:targetWorld}];
    const project=()=>{camera.updateMatrixWorld(true);target.updateMatrixWorld(true);return new Vector3().setFromMatrixPosition(target.matrixWorld).project(camera);};
    rebaseWorld(reference,anchors);const before=project();
    rebaseWorld(cameraWorld,anchors);const after=project();
    expect(after.x).toBeCloseTo(before.x,12);expect(after.y).toBeCloseTo(before.y,12);expect(after.z).toBeCloseTo(before.z,12);
    expect(target.position.toArray()).toEqual([1,0,-4]);
    expect(Math.fround(target.position.x)).toBe(1);
    const moved=moveWorldPosition(cameraWorld,[.125,0,0]);
    rebaseWorld(moved,[{object:camera,position:moved},{object:target,position:targetWorld}]);
    const later=project();expect(later.x).toBeLessThan(after.x);expect(later.x).toBeGreaterThan(0);
  });
  it('rejects invalid offsets or scale without partially moving scene objects',()=>{
    const zero=worldPositionMeters(0n,0n,0n),node=new Object3D();node.position.set(3,4,5);
    expect(()=>moveWorldPosition(zero,[Number.NaN,0,0])).toThrow(RangeError);
    expect(()=>rebaseWorld(zero,[{object:node,position:zero}],0)).toThrow(RangeError);
    expect(node.position.toArray()).toEqual([3,4,5]);
  });
  it('rejects transformed parents instead of silently treating local positions as world coordinates',()=>{
    const zero=worldPositionMeters(0n,0n,0n),parent=new Object3D(),node=new Object3D();
    parent.position.x=1;parent.add(node);
    expect(()=>rebaseWorld(zero,[{object:node,position:zero}])).toThrow(RangeError);
    expect(node.position.toArray()).toEqual([0,0,0]);
  });
});
