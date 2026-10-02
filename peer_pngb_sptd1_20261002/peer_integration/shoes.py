"""Historical SH0ES H0 likelihood, unchanged normalization and numbers."""
import math
from cobaya.likelihood import Likelihood


class SH0ESGaussian(Likelihood):
    mean: float = 73.04
    sigma: float = 1.04

    def get_requirements(self):
        return {'H0':None}

    def logp(self, **params_values):
        h0=float(self.provider.get_param('H0'))
        return -.5*((h0-self.mean)/self.sigma)**2-math.log(self.sigma*math.sqrt(2*math.pi))
