from __future__ import annotations

import math
from cobaya.likelihood import Likelihood


class SH0ESGaussian(Likelihood):
    mean: float = 73.04
    sigma: float = 1.04

    def get_requirements(self):
        return {"H0": None}

    def logp(self, **params_values):
        h0 = float(self.provider.get_param("H0"))
        z = (h0 - self.mean) / self.sigma
        return -0.5 * z * z - math.log(self.sigma * math.sqrt(2.0 * math.pi))
