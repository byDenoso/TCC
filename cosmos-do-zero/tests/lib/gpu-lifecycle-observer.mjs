/** Test-only instrumentation. Extra promise-reaction microtasks may affect timing.
 * It returns the original value or rethrows the original rejection; it never masks errors.
 */
export function installGpuLifecycleObserver() {
  window.__TEST_GPU_LIFECYCLE=[];
  const request=globalThis.GPUAdapter?.prototype.requestDevice;
  if(!request)return;
  let nextDevice=0;
  GPUAdapter.prototype.requestDevice=async function(...args){
    const deviceId=++nextDevice;
    const log=(event,extra={})=>window.__TEST_GPU_LIFECYCLE.push({event,deviceId,time:performance.now(),...extra});
    const info=this.info;
    const fallback=typeof info?.isFallbackAdapter==='boolean'?info.isFallbackAdapter:
      typeof this.isFallbackAdapter==='boolean'?this.isFallbackAdapter:null;
    log('request-device',{fallback,vendor:info?.vendor??'',architecture:info?.architecture??'',description:info?.description??''});
    try{
      const device=await request.apply(this,args);
      log('device-ready');
      let pending=0,nextScope=0;
      const pop=device.popErrorScope;
      device.popErrorScope=function(...scopeArgs){
        const scopeId=++nextScope;
        const promise=pop.apply(this,scopeArgs);
        pending++;log('scope-popped',{scopeId,pending});
        return promise.then(
          value=>{pending--;log('scope-resolved',{scopeId,pending});return value;},
          error=>{pending--;log('scope-rejected',{scopeId,pending});throw error;}
        );
      };
      const destroy=device.destroy;
      device.destroy=function(...destroyArgs){log('destroy-device',{pending});return destroy.apply(this,destroyArgs);};
      return device;
    }catch(error){log('device-rejected');throw error;}
  };
}
