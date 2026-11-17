import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';

// Separate process is required to observe the runtime's unhandled rejection policy.
const program=`import assert from 'node:assert/strict';
  import {mountWithGpu} from './src/scripts/visual/gpu-lease.ts';
  await assert.rejects(mountWithGpu(()=>true,async()=>{throw new Error('mount-failure');}),/mount-failure/);
  assert.equal(await mountWithGpu(()=>true,()=>42),42,'a failed mount leaves the queue usable');
  void Promise.reject(new Error('unhandled-sentinel'));
  await new Promise(resolve=>setTimeout(resolve,30));`;
const child=spawnSync(process.execPath,['--unhandled-rejections=strict','--input-type=module','-e',program],{encoding:'utf8',cwd:process.cwd()});
assert.notEqual(child.status,0);
assert.match(child.stderr,/unhandled-sentinel/);
console.log('GPU mount failure reaches its caller, the queue recovers, and unrelated unhandled failures remain observable.');
