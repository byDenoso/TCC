from __future__ import annotations

import numpy as np
from cobaya.theories.camb import camb as cobaya_camb
from cobaya.theories.camb.camb import CambTransfers

from camb import bbn, constants, dark_energy


_SCALAR_COSMOLOGY_KEYS = {
    "H0", "ombh2", "omch2", "omk", "cosmomc_theta", "thetastar",
    "num_massive_neutrinos", "mnu", "nnu", "YHe", "meffsterile",
    "standard_neutrino_neff", "TCMB", "tau", "zrei", "Alens",
}


def _scalarize(value):
    if isinstance(value, (list, tuple)):
        if not value:
            return value
        return _scalarize(value[0])
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return value
        return _scalarize(value.reshape(-1)[0])
    if isinstance(value, np.generic):
        return value.item()
    try:
        arr = np.asarray(value)
        if arr.ndim > 0 and arr.size:
            return _scalarize(arr.reshape(-1)[0])
    except Exception:
        pass
    return value


class PEERCambTransfers(CambTransfers):
    def get_can_support_params(self):
        return set(super().get_can_support_params()) | {"peer_fede", "peer_zc", "peer_thetai"}


class PEERScalarN3(cobaya_camb.CAMB):
    """CAMB EarlyQuintessence wrapper for the fixed-shape PEER1P model."""

    params = {"peer_fede": None, "peer_zc": None, "peer_thetai": 2.89155}

    def initialize(self):
        super().initialize()
        self._original_camb_set_params = self.camb.set_params

    def get_can_support_params(self):
        return super().get_can_support_params() + ["peer_fede", "peer_zc", "peer_thetai"]

    def get_helper_theories(self):
        self._camb_transfers = PEERCambTransfers(
            self, "camb.transfers", {"stop_at_error": self.stop_at_error}, timing=self.timer
        )
        self._camb_transfers.requires = self._transfer_requires
        return {"camb.transfers": self._camb_transfers}

    def set(self, params_values_dict, state):
        values = {k: _scalarize(v) for k, v in params_values_dict.items()}
        fede = float(values.pop("peer_fede", 0.0))
        logzc = float(values.pop("peer_zc", 3.81))
        thetai = float(values.pop("peer_thetai", 2.89155))
        original = self._original_camb_set_params

        def patched_set_params(*args, **kwargs):
            clean = dict(kwargs)
            for key in _SCALAR_COSMOLOGY_KEYS:
                if key in clean and clean[key] is not None:
                    clean[key] = _scalarize(clean[key])
            if clean.get("YHe") is None:
                ombh2 = float(_scalarize(clean.get("ombh2", 0.022)))
                nnu = float(_scalarize(clean.get("nnu", constants.default_nnu)))
                standard = float(_scalarize(clean.get("standard_neutrino_neff", constants.default_nnu)))
                tcmb = float(_scalarize(clean.get("TCMB", constants.COBE_CMBTemp)))
                predictor = clean.get("bbn_predictor")
                if isinstance(predictor, str):
                    predictor = bbn.get_predictor(predictor)
                predictor = predictor or bbn.get_predictor()
                yhe = predictor.Y_He(
                    ombh2 * (constants.COBE_CMBTemp / tcmb) ** 3,
                    nnu - standard,
                )
                clean["YHe"] = float(_scalarize(yhe))
                clean.pop("bbn_predictor", None)
            pars = original(*args, **clean)
            if fede <= 1e-10:
                return pars
            ede = dark_energy.EarlyQuintessence()
            ede.n = 3
            ede.fde_zc = fede
            ede.zc = 10.0 ** logzc
            ede.theta_i = thetai
            pars.DarkEnergy = ede
            return pars

        self.camb.set_params = patched_set_params
        return super().set(values, state)
