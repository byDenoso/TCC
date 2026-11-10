import * as THREE from 'three';
import { journeyLayers } from '../../lib/scale-journey';
import type { Exhibit } from './runtime';

/** Adjacent models meet at the smaller scene's address in the wider one. */
export function scaleFlight(exhibit: Exhibit, steps: THREE.Group[], anchors: THREE.Vector3[]): Exhibit {
  const stages = steps.map(group => {
    const initialScale = group.scale.x;
    const materials = new Map<THREE.Material, { opacity: number; depthWrite: boolean; fade?: { value: number } }>();
    group.traverse(object => {
      const material = (object as THREE.Mesh).material;
      for (const item of Array.isArray(material) ? material : material ? [material] : []) {
        if (materials.has(item)) continue;
        const entry = { opacity: item.opacity, depthWrite: item.depthWrite };
        item.transparent = true;
        if (item instanceof THREE.ShaderMaterial) {
          const fade = { value: 1 };
          item.uniforms.uScaleOpacity = fade;
          item.fragmentShader = 'uniform float uScaleOpacity;\n' + item.fragmentShader.replace(/}\s*$/, 'gl_FragColor.a *= uScaleOpacity;}');
          materials.set(item, { ...entry, fade });
        } else materials.set(item, entry);
      }
    });
    return { group, initialScale, materials };
  });

  const address = new THREE.Vector3();
  return {
    ...exhibit,
    labels: undefined,
    cameraForValue(value, aspect) {
      const { from, to, blend } = journeyLayers(value);
      const a = exhibit.cameraForValue!(from, aspect), b = exhibit.cameraForValue!(to, aspect);
      const fit = Math.max(1, .8 / aspect);
      return [(a[0] + (b[0] - a[0]) * blend) * fit,
        (a[1] + (b[1] - a[1]) * blend) * fit,
        (a[2] + (b[2] - a[2]) * blend) * fit];
    },
    update({ value }) {
      const { from, to, blend } = journeyLayers(value);
      const anchor = anchors[to];
      address.copy(anchor).multiplyScalar(blend);
      stages.forEach(({ group, initialScale, materials }, i) => {
        const opacity = i === from ? 1 - blend : i === to ? blend : 0;
        group.visible = opacity > 0;
        if (!group.visible) return;
        const scale = i === from ? .08 ** blend : 3.2 ** (1 - blend);
        group.position.copy(address);
        if (i === to) group.position.addScaledVector(anchor, -scale);
        group.scale.setScalar(initialScale * scale);
        materials.forEach((entry, material) => {
          material.opacity = entry.opacity * opacity;
          material.depthWrite = entry.depthWrite && opacity >= .995;
          if (entry.fade) entry.fade.value = opacity;
        });
      });
    }
  };
}
