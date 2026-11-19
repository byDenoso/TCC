import {describe,expect,it} from 'vitest';
import {moveWorldPosition,relativePositionMeters,worldPositionMeters} from '../../src/scripts/visual/world-frame';

describe('camera-relative world coordinates',()=>{
  it('retains metre and sub-metre offsets past cell boundaries at a synthetic 10^27 m anchor',()=>{
    const reference=worldPositionMeters(10n**27n,-(10n**27n),0n);
    const shifted=moveWorldPosition(reference,[1048576.25,-1048577.5,1]);
    expect(relativePositionMeters(shifted,reference)).toEqual([1048576.25,-1048577.5,1]);
    expect(relativePositionMeters(moveWorldPosition(shifted,[-1048576.25,1048577.5,-1]),reference)).toEqual([0,0,0]);
  });
  it('rejects an unrepresentable relative distance or invalid local offset',()=>{
    const origin=worldPositionMeters(0n,0n,0n);
    expect(()=>moveWorldPosition(origin,[NaN,0,0])).toThrow(RangeError);
    expect(()=>relativePositionMeters(worldPositionMeters(10n**400n,0n,0n),origin)).toThrow(RangeError);
  });
});
