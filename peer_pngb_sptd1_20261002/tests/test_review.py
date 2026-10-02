import math
import unittest
import numpy as np
from build_review import make_review, template_contract, STACKS
from peer_integration.calibration import Target, Summary, calibrate, scalar_peak, CalibrationError
from peer_integration.class_backend import cosmology_args, scalar_args


class ReviewTests(unittest.TestCase):
    def test_symmetric_contracts(self):
        nuis, priors = template_contract()
        self.assertEqual(len(nuis), 43)
        self.assertEqual(len(priors), 26)
        for stack in STACKS:
            a = make_review('LCDM',stack)['cobaya_preview']
            b = make_review('PNGB_ETA01',stack)['cobaya_preview']
            self.assertEqual(a['likelihood'],b['likelihood'])
            self.assertEqual(a['prior'],b['prior'])
            for k in a['params']:
                if k != 'peer_fede': self.assertEqual(a['params'][k],b['params'][k])
            self.assertFalse(a['theory']['peer_integration.cobaya_adapter.PEERClassy']['execution_review_passed'])
            if stack=='spt_only':
                self.assertEqual(a['params']['tau']['prior'], {'dist':'norm','loc':.051,'scale':.006})
            else:
                self.assertEqual(a['params']['tau']['prior'], {'min':0.,'max':.1})
            self.assertNotIn('SPT3G_D1_KK',str(a['likelihood']))
            for name in nuis: self.assertEqual(a['params'][name],nuis[name])

    def test_calibration_recomputes_for_cosmology(self):
        target = Target(.08,1.041)
        results = []
        for omega in (.12,.14):
            def mock(A,F,H0):
                return Summary(.08*(F/.12)**2*(.12/omega),
                               10**3.81*(A/862.)**.25*(F/.12)**-.5,
                               1.041*(H0/68.)**.2*(omega/.12)**.02)
            r = calibrate(target,mock)
            self.assertLess(max(abs(x) for x in r.residuals_in_tolerance_units),1)
            results.append(r)
        self.assertNotAlmostEqual(results[0].amplitude,results[1].amplitude,places=4)
        self.assertNotAlmostEqual(results[0].decay_constant,results[1].decay_constant,places=4)

    def test_no_silent_theta_conversion(self):
        with self.assertRaises(ValueError): cosmology_args({'cosmomc_theta':.0104})

    def test_zero_fede_requires_lcdm_branch(self):
        with self.assertRaises(ValueError): Target(0,1.04)

    def test_potential_contract(self):
        p=scalar_args(862.,.12,Target(.08,1.041))
        self.assertEqual(p['kpeer_pngb_eta'],.1)
        self.assertEqual(p['kpeer_decay_fraction'],0.)
        self.assertNotIn('vacuum',str(p).lower())

    def test_peak_interpolation(self):
        x=np.linspace(-12,0,1201); f=.1*np.exp(-((x+8.4)/.5)**2)
        peak,z=scalar_peak({'z':np.expm1(-x),'(.)rho_scf':f,'(.)rho_tot':np.ones_like(x)})
        self.assertAlmostEqual(peak,.1,places=8)
        self.assertAlmostEqual(math.log1p(z),8.4,places=6)

    def test_boundary_peak_rejected(self):
        with self.assertRaises(CalibrationError):
            scalar_peak({'z':np.arange(10),'(.)rho_scf':np.arange(10),'(.)rho_tot':np.ones(10)})


if __name__=='__main__': unittest.main()
