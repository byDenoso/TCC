import * as THREE from 'three';

/** Keep clip-space products inside a conservative float32 range without changing NDC. */
export function worldFrameClipScale(near:number,far:number):number {
  if(!Number.isFinite(near)||!Number.isFinite(far)||near<=0||far<=near)throw new RangeError('planos da câmera inválidos');
  const scale=Math.fround(2**(-.5*(Math.log2(near)+Math.log2(far))));
  if(!Number.isFinite(Math.fround(far))||Math.fround(near)<2**-126||!Number.isFinite(scale)||scale<2**-126||near*scale<1e-18||far*scale>1e18)throw new RangeError('intervalo da câmera excede o contrato WebGL de origem flutuante');
  return scale;
}

/** Materials belong to the exhibit and are restored before its normal disposal. */
export function worldFrameWebGLMaterials(root:THREE.Object3D,near:number,far:number){
  const scale=worldFrameClipScale(near,far),literal=scale.toExponential(9);
  const patched=new Map<THREE.Material,{compileDescriptor:PropertyDescriptor|undefined;keyDescriptor:PropertyDescriptor|undefined;wrapped:THREE.Material['onBeforeCompile'];wrappedKey:THREE.Material['customProgramCacheKey']}>();
  const restoreOne=(material:THREE.Material,entry:NonNullable<ReturnType<typeof patched.get>>)=>{
    if(material.onBeforeCompile===entry.wrapped){if(entry.compileDescriptor)Object.defineProperty(material,'onBeforeCompile',entry.compileDescriptor);else Reflect.deleteProperty(material,'onBeforeCompile');}
    if(material.customProgramCacheKey===entry.wrappedKey){if(entry.keyDescriptor)Object.defineProperty(material,'customProgramCacheKey',entry.keyDescriptor);else Reflect.deleteProperty(material,'customProgramCacheKey');}
    material.needsUpdate=true;
  };
  const sync=()=>{
    const materials=new Set<THREE.Material>();
    root.traverse(object=>{const material=(object as THREE.Mesh).material;if(material)for(const item of Array.isArray(material)?material:[material])materials.add(item);});
    for(const material of materials){
      const existing=patched.get(material);
      if(existing){if(material.onBeforeCompile!==existing.wrapped||material.customProgramCacheKey!==existing.wrappedKey)throw new Error('callback de material alterado durante o frame físico');continue;}
      if(material instanceof THREE.ShaderMaterial||('isShaderMaterial' in material&&material.isShaderMaterial===true)||('isNodeMaterial' in material&&material.isNodeMaterial===true)||material.onBeforeCompile!==THREE.Material.prototype.onBeforeCompile)throw new Error('material customizado sem contrato de profundidade logarítmica');
    }
    for(const[material,entry]of patched)if(!materials.has(material)){restoreOne(material,entry);patched.delete(material);}
    for(const material of materials){
      if(patched.has(material))continue;
      const compile=material.onBeforeCompile,key=material.customProgramCacheKey,originalKey=key.call(material);
      const compileDescriptor=Object.getOwnPropertyDescriptor(material,'onBeforeCompile'),keyDescriptor=Object.getOwnPropertyDescriptor(material,'customProgramCacheKey');
      const wrapped:THREE.Material['onBeforeCompile']=function(this:THREE.Material,shader,renderer){
        compile.call(this,shader,renderer);
        const vertex='#include <logdepthbuf_vertex>',fragment='#include <logdepthbuf_fragment>';
        if(shader.vertexShader.split(vertex).length!==2||shader.fragmentShader.split(fragment).length!==2)throw new Error('shader sem chunks únicos de profundidade logarítmica');
        shader.vertexShader=shader.vertexShader.replace(vertex,`${vertex}\n gl_Position *= ${literal};`);
      };
      const wrappedKey:THREE.Material['customProgramCacheKey']=function(this:THREE.Material){return `${key===THREE.Material.prototype.customProgramCacheKey?originalKey:key.call(this)}|cosmos-world-clip-v1:${literal}`;};
      patched.set(material,{compileDescriptor,keyDescriptor,wrapped,wrappedKey});material.onBeforeCompile=wrapped;material.customProgramCacheKey=wrappedKey;material.needsUpdate=true;
    }
  };
  const restore=()=>{for(const[material,entry]of patched)restoreOne(material,entry);patched.clear();};
  return {sync,restore};
}
