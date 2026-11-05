import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';

// Separate process is required to observe the runtime's unhandled rejection policy.
const program=`import {installGpuLifecycleObserver} from './tests/lib/gpu-lifecycle-observer.mjs';
  globalThis.window=globalThis;
  globalThis.GPUAdapter=class {async requestDevice(){return {popErrorScope(){return Promise.reject(new Error('scope-sentinel'));},destroy(){}}}};
  installGpuLifecycleObserver();
  const device=await new GPUAdapter().requestDevice();device.popErrorScope();
  await new Promise(resolve=>setTimeout(resolve,30));`;
const child=spawnSync(process.execPath,['--unhandled-rejections=strict','--input-type=module','-e',program],{encoding:'utf8',cwd:process.cwd()});
assert.notEqual(child.status,0);
assert.match(child.stderr,/scope-sentinel/);
console.log('WebGPU diagnostic leaves an unhandled scope rejection observable.');
