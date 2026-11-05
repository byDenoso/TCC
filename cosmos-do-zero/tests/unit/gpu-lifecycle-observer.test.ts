import {afterEach, describe, expect, it, vi} from 'vitest';
import {installGpuLifecycleObserver} from '../lib/gpu-lifecycle-observer.mjs';

const events=()=> (globalThis as unknown as {__TEST_GPU_LIFECYCLE:Array<{event:string;pending?:number;fallback?:boolean|null}>}).__TEST_GPU_LIFECYCLE;
afterEach(()=>vi.unstubAllGlobals());

function setup(promise:Promise<unknown>,fallback?:boolean) {
  const fakeDevice={popErrorScope:()=>promise,destroy:vi.fn()};
  class FakeAdapter { info=fallback===undefined?{}:{isFallbackAdapter:fallback}; async requestDevice(){return fakeDevice;} }
  vi.stubGlobal('window',globalThis);
  vi.stubGlobal('GPUAdapter',FakeAdapter);
  installGpuLifecycleObserver();
  return {adapter:new FakeAdapter(),fakeDevice};
}

describe('test-only WebGPU scope observation',()=>{
  it('records fallback adapter status without inferring an unknown value',async()=>{
    const {adapter}=setup(Promise.resolve(null),true);
    await adapter.requestDevice();
    expect(events().find(e=>e.event==='request-device')?.fallback).toBe(true);
  });
  it('records an undisclosed adapter as unknown',async()=>{
    const {adapter}=setup(Promise.resolve(null));
    await adapter.requestDevice();
    expect(events().find(e=>e.event==='request-device')?.fallback).toBeNull();
  });
  it('preserves a scope value and records pending scope at destruction',async()=>{
    let resolve!:(value:object)=>void;
    const scope=new Promise<object>(done=>{resolve=done;});
    const {adapter}=setup(scope),device=await adapter.requestDevice();
    const result=device.popErrorScope();
    device.destroy();
    expect(events().find(e=>e.event==='destroy-device')?.pending).toBe(1);
    const value={};resolve(value);
    await expect(result).resolves.toBe(value);
    expect(events().find(e=>e.event==='scope-resolved')?.pending).toBe(0);
  });
  it('rethows the original scope rejection',async()=>{
    let reject!:(error:Error)=>void;
    const scope=new Promise((_,fail)=>{reject=fail;});
    const {adapter}=setup(scope),device=await adapter.requestDevice();
    const result=device.popErrorScope(),original=new Error('scope failure');
    const assertion=expect(result).rejects.toBe(original);
    reject(original);await assertion;
    expect(events().find(e=>e.event==='scope-rejected')?.pending).toBe(0);
  });
});
