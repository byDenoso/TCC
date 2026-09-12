from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import camb


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True)
    p.add_argument('--H0', type=float, required=True)
    p.add_argument('--ombh2', type=float, required=True)
    p.add_argument('--omch2', type=float, required=True)
    p.add_argument('--ns', type=float, required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()

    pars = camb.CAMBparams()
    pars.set_cosmology(H0=args.H0, ombh2=args.ombh2, omch2=args.omch2, mnu=0.06, omk=0.0, tau=0.0544)
    pars.InitPower.set_params(As=2.1e-9, ns=args.ns)
    pars.set_for_lmax(1200, lens_potential_accuracy=0)

    results = camb.get_results(pars)
    derived = results.get_derived_params()
    cmb = results.get_cmb_power_spectra(pars, CMB_unit='muK', raw_cl=False)['total']

    sigma8 = float(results.get_sigma8_0())
    payload = {
        'schema': 'nexo.camb.gha.pilot.v1',
        'case': args.case,
        'inputs': {
            'H0': args.H0,
            'ombh2': args.ombh2,
            'omch2': args.omch2,
            'ns': args.ns,
            'As': 2.1e-9,
            'mnu': 0.06,
            'tau': 0.0544,
        },
        'runtime': {
            'python': sys.version.split()[0],
            'platform': platform.platform(),
            'camb_version': getattr(camb, '__version__', 'UNKNOWN'),
            'camb_module': str(Path(camb.__file__).resolve()),
        },
        'outputs': {
            'age_gyr': float(derived['age']),
            'rdrag_mpc': float(derived['rdrag']),
            'zstar': float(derived['zstar']),
            'sigma8': sigma8,
            'tt_ell_200_uK2': float(cmb[200, 0]),
            'tt_ell_1000_uK2': float(cmb[1000, 0]),
        },
        'status': 'PASS',
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    digest = sha256(out)
    out.with_suffix(out.suffix + '.sha256').write_text(f'{digest}  {out.name}\n', encoding='utf-8')
    print(json.dumps(payload, sort_keys=True))
    print(f'sha256={digest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
