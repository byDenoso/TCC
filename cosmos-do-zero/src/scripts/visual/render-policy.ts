import * as THREE from 'three';

/** An absent flag is unknown, not evidence of a software adapter. */
export function isSoftwareAdapter(info: {isFallbackAdapter?: boolean} | null | undefined): boolean {
  return info?.isFallbackAdapter === true;
}

/** WebGPURenderer cannot compile GLSL ShaderMaterial or onBeforeCompile patches. */
export function canUseWebGPU(root: THREE.Object3D): boolean {
  let compatible = true;
  root.traverse((object) => {
    // WebGPURenderer does not support LineLoop primitives.
    if ('isLineLoop' in object && object.isLineLoop === true) compatible = false;
    const material = (object as THREE.Mesh).material;
    if (!material) return;
    for (const item of Array.isArray(material) ? material : [material]) {
      if (item instanceof THREE.ShaderMaterial || ('isShaderMaterial' in item && item.isShaderMaterial === true) || item.onBeforeCompile !== THREE.Material.prototype.onBeforeCompile) compatible = false;
    }
  });
  return compatible;
}

/** Visible, continuous inter-frame intervals only. This is not a GPU benchmark. */
export class FrameBudget {
  private values: number[] = [];
  record(interval: number): void {
    if (Number.isFinite(interval) && interval > 0 && this.values.length < 120) this.values.push(interval);
  }
  decide(): 'low' | 'standard' | null {
    if (this.values.length < 90) return null;
    const sorted = [...this.values].sort((a, b) => a - b);
    return sorted[Math.ceil(sorted.length * .9) - 1] > 30 ? 'low' : 'standard';
  }
}
