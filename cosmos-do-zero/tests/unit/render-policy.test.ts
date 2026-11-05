import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { canUseWebGPU, isSoftwareAdapter, FrameBudget } from '../../src/scripts/visual/render-policy';

describe('renderer safety and quality', () => {
  it('only selects WebGL for an explicitly reported fallback adapter', () => {
    expect(isSoftwareAdapter({isFallbackAdapter:true})).toBe(true);
    expect(isSoftwareAdapter({isFallbackAdapter:false})).toBe(false);
    expect(isSoftwareAdapter({})).toBe(false);
    expect(isSoftwareAdapter(undefined)).toBe(false);
    expect(isSoftwareAdapter(null)).toBe(false);
  });
  it('allows built-in materials and rejects every legacy custom shader, including hidden objects', () => {
    const root = new THREE.Group();
    root.add(new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial()));
    expect(canUseWebGPU(root)).toBe(true);
    const custom = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.ShaderMaterial());
    custom.visible = false;
    root.add(custom);
    expect(canUseWebGPU(root)).toBe(false);
  });
  it('rejects onBeforeCompile patches as well as arrays containing a custom material', () => {
    const root = new THREE.Group();
    const material = new THREE.MeshBasicMaterial();
    material.onBeforeCompile = () => {};
    root.add(new THREE.Mesh(new THREE.BoxGeometry(), [new THREE.MeshBasicMaterial(), material]));
    expect(canUseWebGPU(root)).toBe(false);
  });
  it('uses WebGL for LineLoop primitives unsupported by WebGPURenderer', () => {
    const root = new THREE.Group();
    expect(canUseWebGPU(root)).toBe(true);
    root.add(new THREE.LineLoop(new THREE.BufferGeometry(),new THREE.LineBasicMaterial()));
    expect(canUseWebGPU(root)).toBe(false);
  });
  it('does not infer performance from too few frames or invalid values', () => {
    const budget = new FrameBudget();
    for (const value of [0, -1, Number.NaN, ...Array(20).fill(16)]) budget.record(value);
    expect(budget.decide()).toBeNull();
  });
  it('uses measured visible frame intervals to choose a conservative profile', () => {
    const fast = new FrameBudget();
    const slow = new FrameBudget();
    for (let i = 0; i < 90; i++) { fast.record(16.7); slow.record(40); }
    expect(fast.decide()).toBe('standard');
    expect(slow.decide()).toBe('low');
  });
  it('counts long frames as stalls', () => {
    const budget = new FrameBudget();
    for (let i = 0; i < 80; i++) budget.record(16.7);
    for (let i = 0; i < 10; i++) budget.record(500);
    expect(budget.decide()).toBe('low');
  });
});
