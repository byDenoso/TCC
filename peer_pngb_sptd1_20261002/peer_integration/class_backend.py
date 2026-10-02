"""Real CLASS probe prototype; not executed or integration-validated here."""
import math
from .calibration import Summary, Target, scalar_peak


def scalar_args(A: float, F: float, target: Target) -> dict:
    return {
        'Omega_scf_direct': 1e-30,
        'kpeer_exact_scf': 'yes',
        'kpeer_pngb_eta': target.eta,
        'kpeer_decay_fraction': 0.0,
        'scf_parameters': f'{A:.17g}, {F:.17g}, 0, 3, {target.theta_i*F:.17g}, 0',
        'attractor_ic_scf': 'no',
        'scf_tuning_index': 0,
        'gauge': 'synchronous',
    }


def make_class_probe(Class, base_args: dict, target: Target):
    """Create fresh CLASS objects to prevent history-dependent state or cache reuse."""
    def probe(A: float, F: float, H0: float) -> Summary:
        obj = Class()
        try:
            args = dict(base_args)
            # Only background + thermodynamics, with all physical inputs kept.
            for key in ('100*theta_s', 'theta_s_100', 'h'):
                args.pop(key, None)
            args.update(scalar_args(A, F, target))
            # Keep *all* final precision/physics/input controls. Limit work by
            # selecting the compute stage, not by changing the requested model.
            args.update(H0=H0)
            args.setdefault('output', 'tCl,pCl,lCl,mPk')
            obj.set(args)
            obj.compute(['thermodynamics'])
            background=obj.get_background()
            f, z = scalar_peak(background)
            theta = obj.get_current_derived_parameters(['theta_s_100'])['theta_s_100']
            today=min(range(len(background['z'])),key=lambda i:abs(background['z'][i]))
            H0_effective=float(obj.Hubble(0.)*299792.458)
            f_today=float(background['(.)rho_scf'][today]/background['(.)rho_tot'][today])
            return Summary(f,z,float(theta),H0_effective,f_today,(H0_effective/H0)**2-1.)
        finally:
            # Cleanup also if a numerical evaluation fails.
            obj.struct_cleanup()
            obj.empty()
    return probe


def cosmology_args(values: dict) -> dict:
    """Explicit mapping; cosmomc_theta is intentionally unsupported."""
    if 'cosmomc_theta' in values or 'theta_MC_100' in values:
        raise ValueError('CAMB theta_MC cannot be silently replaced with CLASS theta_s')
    required = ('ombh2', 'omch2', 'logA', 'ns', 'tau', 'theta_s_100', 'peer_fede')
    missing = set(required) - values.keys()
    if missing:
        raise ValueError(f'Missing cosmological inputs: {sorted(missing)}')
    return dict(omega_b=values['ombh2'], omega_cdm=values['omch2'],
                A_s=1e-10*math.exp(values['logA']), n_s=values['ns'],
                tau_reio=values['tau'])
