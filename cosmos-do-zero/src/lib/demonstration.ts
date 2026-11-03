/** Relógio didático: mostra, deixa ler, avança e repete. Não conhece DOM nem progresso. */
export interface DemonstrationState { value: number; phase: number; hold: number }
export interface DemonstrationSpec {
  kind: 'sweep' | 'stages' | 'choice' | 'time';
  min: number;
  max: number;
  duration: number;
  hold: number;
}

export function advanceDemonstration(state: DemonstrationState, dt: number, spec: DemonstrationSpec): DemonstrationState {
  if (dt <= 0) return state;
  const sweep = spec.kind === 'sweep';
  const phase = sweep ? (state.value - spec.min) / (spec.max - spec.min || 1) : state.phase;
  const period = spec.duration + spec.hold;
  const clock = phase * spec.duration + state.hold + dt;
  const hops = Math.floor((clock + 1e-8) / period);
  const local = Math.max(0, clock - hops * period);
  const nextPhase = Math.min(1, local / spec.duration);
  const value = sweep ? spec.min + (spec.max - spec.min) * nextPhase
    : spec.kind === 'time' ? state.value
    : spec.min + (state.value - spec.min + hops) % (spec.max - spec.min + 1);
  return { value, phase: nextPhase, hold: Math.max(0, local - spec.duration) };
}
