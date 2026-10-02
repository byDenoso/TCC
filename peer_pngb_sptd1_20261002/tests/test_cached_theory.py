import importlib.util
import unittest
import numpy as np

@unittest.skipUnless(importlib.util.find_spec('cobaya'),'requires provisioned Cobaya')
class CachedTheoryTests(unittest.TestCase):
    def make_cache(self):
        from peer_integration.cached_theory import CachedPoint
        obj=CachedPoint(initialize=False)
        ell=np.arange(10)
        obj.cache={'ell':ell,'raw_tt':np.ones(10),'raw_ee':np.ones(10)*2,
                   'raw_te':np.ones(10)*3,'raw_pp':np.ones(10)*.001,
                   'bao_z':np.array([.295,.51]),'H_km_s_Mpc':np.array([80.,90.]),
                   'DA_Mpc':np.array([900.,1300.])}
        obj.meta={'T_cmb':2.7255}
        return obj

    def test_units_and_ell_factors(self):
        obj=self.make_cache(); cl=obj.get_Cl(ell_factor=True,units='muK2')
        ef=np.arange(10)*np.arange(1,11)/(2*np.pi)
        np.testing.assert_allclose(cl['tt'][2:],ef[2:])
        np.testing.assert_allclose(cl['pp'][2:],.001*ef[2:]**2*2*np.pi)
        np.testing.assert_allclose(obj.get_Cl(units='K2')['tt'],np.ones(10)*1e-12)
        obj.cache['raw_tp']=np.ones(10)*.002
        np.testing.assert_allclose(obj.get_Cl(ell_factor=True)['tp'][2:],.002*ef[2:]**1.5*np.sqrt(2*np.pi))

    def test_distances_exact_no_interpolation(self):
        obj=self.make_cache()
        self.assertAlmostEqual(obj.get_Hubble(.295,units='1/Mpc'),80/299792.458)
        np.testing.assert_array_equal(obj.get_angular_diameter_distance([.51,.295]),[1300,900])
        with self.assertRaises(ValueError):obj.get_Hubble(.3)

    def test_requirements_fail_closed(self):
        obj=self.make_cache()
        obj.must_provide(Cl={'tt':9,'pp':9})
        with self.assertRaises(ValueError):obj.must_provide(Cl={'tt':10})
        with self.assertRaises(ValueError):obj.must_provide(unlensed_Cl={'tt':9})

    def test_no_cosmology_variation(self):
        obj=self.make_cache()
        with self.assertRaises(ValueError):obj.calculate({},H0=70)
