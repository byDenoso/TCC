import {describe,expect,it} from 'vitest';
import {photographicExposure} from '../../src/scripts/visual/camera-exposure';

describe('photographic exposure',()=>{
  it('computes EV100 and doubles exposure for one stop of shutter or ISO',()=>{
    const base={fNumber:8,shutterSeconds:1/125,iso:100};
    const first=photographicExposure(base);
    expect(first.ev100).toBeCloseTo(Math.log2(8000),12);
    expect(first.normalization).toBeCloseTo(1/9600,12);
    expect(photographicExposure({...base,shutterSeconds:2/125}).normalization/first.normalization).toBeCloseTo(2,12);
    expect(photographicExposure({...base,iso:200}).normalization/first.normalization).toBeCloseTo(2,12);
    expect(photographicExposure({...base,fNumber:16}).normalization/first.normalization).toBeCloseTo(.25,12);
  });
  it('rejects invalid camera settings',()=>{
    for(const value of [0,-1,Number.NaN,Infinity])expect(()=>photographicExposure({fNumber:value,shutterSeconds:1,iso:100})).toThrow(RangeError);
  });
});
