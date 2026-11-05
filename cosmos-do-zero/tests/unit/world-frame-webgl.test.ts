import {describe,expect,it} from 'vitest';
import * as THREE from 'three';
import {worldFrameClipScale,worldFrameWebGLMaterials} from '../../src/scripts/visual/world-frame-webgl';

describe('world frame WebGL clip normalization',()=>{
  it('balances 1 m and 10 Gpc ranges using a normal positive float32',()=>{
    const scale=worldFrameClipScale(.02,2e27);
    expect(scale).toBe(Math.fround(scale));expect(scale).toBeGreaterThan(2**-126);
    expect(.02*scale).toBeGreaterThanOrEqual(1e-18);expect(2e27*scale).toBeLessThanOrEqual(1e18);
    expect(()=>worldFrameClipScale(1e-30,1e30)).toThrow(RangeError);
    expect(()=>worldFrameClipScale(1e-50,1e-20)).toThrow(RangeError);
    expect(worldFrameClipScale(1e-30,1e-20)).toBeGreaterThan(1e18);
  });
  it('preserves shared materials, references, cache keys and restores callbacks',()=>{
    const material=new THREE.MeshBasicMaterial({color:0xff2222}),other=new THREE.MeshBasicMaterial();
    const compile=material.onBeforeCompile,key=material.customProgramCacheKey;
    const otherKey=()=> 'existing-custom-key';other.customProgramCacheKey=otherKey;
    const group=new THREE.Group(),first=new THREE.Mesh(new THREE.BoxGeometry(),[material,other]),second=new THREE.Mesh(new THREE.BoxGeometry(),material);
    group.add(first,second);const normalizer=worldFrameWebGLMaterials(group,.02,2e27);normalizer.sync();
    expect(first.material[0]).toBe(material);expect(second.material).toBe(material);
    material.color.setHex(0x22ff22);expect((second.material as THREE.MeshBasicMaterial).color.getHex()).toBe(0x22ff22);
    expect(material.customProgramCacheKey()).toContain('cosmos-world-clip-v1:');
    expect(other.customProgramCacheKey()).toContain('existing-custom-key|cosmos-world-clip-v1:');
    const shader={vertexShader:'void main(){\n#include <logdepthbuf_vertex>\n}',fragmentShader:'#include <logdepthbuf_fragment>',uniforms:{}};
    material.onBeforeCompile(shader as never,{} as THREE.WebGLRenderer);
    expect(shader.vertexShader).toMatch(/#include <logdepthbuf_vertex>\n gl_Position \*= [0-9.e+-]+;/);
    expect(()=>material.onBeforeCompile({...shader,vertexShader:'void main(){}'} as never,{} as THREE.WebGLRenderer)).toThrow('chunks únicos');
    const newMaterial=new THREE.MeshBasicMaterial(),added=new THREE.Mesh(new THREE.BoxGeometry(),newMaterial);group.add(added);normalizer.sync();
    expect(newMaterial.onBeforeCompile).not.toBe(compile);
    group.remove(added);normalizer.sync();expect(newMaterial.onBeforeCompile).toBe(THREE.Material.prototype.onBeforeCompile);
    normalizer.restore();
    expect(material.onBeforeCompile).toBe(compile);expect(material.customProgramCacheKey).toBe(key);
    expect(Object.hasOwn(material,'onBeforeCompile')).toBe(false);expect(Object.hasOwn(material,'customProgramCacheKey')).toBe(false);
    expect(other.customProgramCacheKey).toBe(otherKey);expect(Object.hasOwn(other,'customProgramCacheKey')).toBe(true);
    expect(newMaterial.onBeforeCompile).toBe(THREE.Material.prototype.onBeforeCompile);
  });
  it('keeps incompatible material fallback atomic and keys distinct for different camera ranges',()=>{
    const standard=new THREE.MeshBasicMaterial(),custom=new THREE.ShaderMaterial(),root=new THREE.Group();
    root.add(new THREE.Mesh(new THREE.BoxGeometry(),standard),new THREE.Mesh(new THREE.BoxGeometry(),custom));
    const failed=worldFrameWebGLMaterials(root,.02,2e27);expect(()=>failed.sync()).toThrow('material customizado');
    expect(standard.onBeforeCompile).toBe(THREE.Material.prototype.onBeforeCompile);
    root.remove(root.children[1]);const first=worldFrameWebGLMaterials(root,.02,2e27);first.sync();const key=standard.customProgramCacheKey();first.restore();
    const second=worldFrameWebGLMaterials(root,.02,2e20);second.sync();expect(standard.customProgramCacheKey()).not.toBe(key);second.restore();
    standard.onBeforeCompile=()=>{};expect(()=>worldFrameWebGLMaterials(root,.02,2e27).sync()).toThrow('material customizado');
  });
});
