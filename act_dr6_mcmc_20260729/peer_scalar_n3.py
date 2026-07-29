from __future__ import annotations

import numpy as np
from cobaya.theories.camb import camb as cobaya_camb
from cobaya.theories.camb.camb import CambTransfers

from camb import dark_energy


def _scalarize(value):
    if isinstance(value, np.ndarray) and value.size == 1:
        return value.reshape(-1)[0].item()
    if isinstance(value, np.generic):
        return value.item()
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
            clean = {k: _scalarize(v) for k, v in kwargs.items()}
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
