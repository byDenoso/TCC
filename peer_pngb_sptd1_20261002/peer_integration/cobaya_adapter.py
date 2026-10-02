"""CLASS→Cobaya adapter, locked outside explicit validation or passed gates.

Requires a locally built/pinned patched classy. No install or run entry point.
"""
from hashlib import sha256
import importlib
import math
import json
import time
from pathlib import Path
from cobaya.theories.classy import classy
from .calibration import Target, calibrate, scalar_peak, CalibrationError
from .class_backend import cosmology_args, make_class_probe, scalar_args


class PEERClassy(classy):
    execution_review_passed: bool = False
    validation_mode: bool = False
    validation_report: str = ''
    expected_classy_sha256: str = ''
    peer_eta: float = 0.1
    peer_log10_zc: float = 3.81
    peer_theta_i: float = 2.89155

    def initialize(self):
        if not (self.execution_review_passed or self.validation_mode):
            raise RuntimeError('REVIEW ONLY: execution disabled; approvals and physical gates pending')
        if not self.expected_classy_sha256:
            raise RuntimeError('A verified patched classy binary hash is required')
        super().initialize()
        extension = importlib.import_module(self.classy_module.Class.__module__)
        binary = Path(extension.__file__).resolve()
        if sha256(binary.read_bytes()).hexdigest() != self.expected_classy_sha256:
            raise RuntimeError(f'Unexpected classy binary: {binary}')
        self.backend_metadata = {'classy_version':str(self.classy_module.__version__),
            'classy_extension':str(binary),'classy_sha256':self.expected_classy_sha256,
            'eta':float(self.peer_eta),'theta_i':float(self.peer_theta_i),
            'log10_zc':float(self.peer_log10_zc),'validation_mode':self.validation_mode}
        if not self.validation_mode:
            if not self.validation_report:
                raise RuntimeError('Production requires an explicit validation report')
            report = json.loads(Path(self.validation_report).read_text())
            required = ('classy_null_field', 'classy_eta0_parity', 'classy_eta01_benchmark',
                        'calibration_grid', 'cobaya_spectrum_parity', 'spt_likelihood_pair',
                        'precision_likelihood_gate')
            if (report.get('classy_sha256') != self.expected_classy_sha256 or
                    any(report.get('gates',{}).get(key) is not True for key in required)):
                raise RuntimeError('Missing/failed production integration gates or binary mismatch')

    def get_can_support_params(self):
        return ['ombh2', 'omch2', 'logA', 'ns', 'tau', 'theta_s_100', 'peer_fede']

    def get_allow_agnostic(self):
        return False

    def must_provide(self, **requirements):
        # This is a custom result, never a CLASS derived-parameter name.
        requirements.pop('peer_diagnostics', None)
        return super().must_provide(**requirements)

    def set(self, params_values_dict):
        args = cosmology_args(params_values_dict)
        extra = dict(self.extra_args)
        if set(args).intersection(extra):
            raise ValueError('Cosmological input repeated in extra_args')
        args.update(extra)
        if params_values_dict['peer_fede'] == 0:
            # Exact no-field limit: never initialize a zero-energy KG field.
            args['theta_s_100'] = params_values_dict['theta_s_100']
            self.last_calibration = None
        else:
            target = Target(params_values_dict['peer_fede'], params_values_dict['theta_s_100'],
                            self.peer_log10_zc, self.peer_theta_i, self.peer_eta)
            result = calibrate(target, make_class_probe(self.classy_module.Class, args, target))
            args.update(scalar_args(result.amplitude, result.decay_constant, target))
            args['H0'] = result.H0
            self.last_calibration = result
        # CLASS.set updates its existing parameter dictionary. Explicitly clear
        # it so a pNGB→fEDE=0 transition cannot retain scalar-field arguments.
        self.classy.struct_cleanup()
        self.classy.empty()
        self.classy.set(**args)

    def calculate(self, state, want_derived=True, **params_values_dict):
        start = time.perf_counter()
        ok = super().calculate(state, want_derived=want_derived, **params_values_dict)
        if ok is False:
            return False
        if self.last_calibration is not None:
            f, z = scalar_peak(self.classy.get_background())
            theta = self.classy.get_current_derived_parameters(['theta_s_100'])['theta_s_100']
            residual = [math.log(f/params_values_dict['peer_fede'])/5e-4,
                        (math.log10(z)-self.peer_log10_zc)/5e-4,
                        (theta-params_values_dict['theta_s_100'])/1e-5]
            if max(map(abs,residual)) > 1:
                raise CalibrationError(f'Final CLASS recalibration mismatch: {residual}')
            state['peer_calibration_audit'] = {'fpeak':f,'zpeak':z,'theta_s_100':theta,
                'residuals':residual,'A':self.last_calibration.amplitude,
                'F':self.last_calibration.decay_constant,'H0':self.last_calibration.H0,
                'backend_calls':self.last_calibration.backend_calls}
        else:
            theta=float(self.classy.get_current_derived_parameters(['theta_s_100'])['theta_s_100'])
            theta_residual=theta-params_values_dict['theta_s_100']
            if abs(theta_residual)>1e-5:
                raise CalibrationError(f'LCDM acoustic mismatch: {theta_residual}')
            state['peer_calibration_audit'] = {'fpeak':0.,'no_field':True,
                'theta_s_100':theta,'theta_residual':theta_residual}
        h0_input=float(self.classy.h()*100.)
        h0_effective=float(self.classy.Hubble(0.)*299792.458)
        closure=(h0_effective/h0_input)**2-1.
        if abs(closure)>1e-6:
            raise CalibrationError(f'Present-day closure residual too large: {closure}')
        state['peer_calibration_audit'].update(H0_input=h0_input,H0_effective=h0_effective,
                                               closure_fraction=closure)
        state['peer_calibration_audit']['elapsed_seconds'] = time.perf_counter()-start
        state['peer_calibration_audit']['backend'] = dict(self.backend_metadata)
        return ok

    def get_peer_diagnostics(self):
        return self.current_state['peer_calibration_audit']
