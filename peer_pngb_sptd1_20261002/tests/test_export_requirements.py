"""Regression: standalone cache export has no H0-dependent likelihood."""
import importlib.util
import unittest
import copy
import numpy as np
from smoke_integration import spectrum_requirements,CACHE_DERIVED,validated_cache_payload


class ExportContractTests(unittest.TestCase):
    def payload_args(self):
        spectra={'ell':np.arange(5),**{p:np.ones(5) for p in ('tt','te','ee','pp')}}
        metadata={'derived':{'H0':70.,'Omega_m':.3,'rs_drag':145.,'rdrag':145.}}
        return [spectra,copy.deepcopy(spectra),[.295,.51],[80.,90.],[900.,1300.],metadata]

    def test_valid_cache_numeric_contract(self):
        payload=validated_cache_payload(*self.payload_args())
        self.assertIn('raw_pp',payload)
        self.assertIn('metadata_json',payload)

    def test_nonfinite_cache_products_rejected(self):
        for index,key in ((0,'pp'),(1,'tt'),(1,'pp')):
            args=self.payload_args();args[index][key][3]=np.nan
            with self.assertRaises(ValueError):validated_cache_payload(*args)
        for index in (3,4):
            args=self.payload_args();args[index][0]=np.inf
            with self.assertRaises(ValueError):validated_cache_payload(*args)
        args=self.payload_args();args[5]['extra_metadata']=float('nan')
        with self.assertRaises(ValueError):validated_cache_payload(*args)

    def test_broken_grid_or_shape_rejected(self):
        args=self.payload_args();args[0]['ell']=np.array([0,1,2,4,5])
        with self.assertRaises(ValueError):validated_cache_payload(*args)
        args=self.payload_args();args[1]['te']=np.ones(4)
        with self.assertRaises(ValueError):validated_cache_payload(*args)
        args=self.payload_args();args[3]=[80.]
        with self.assertRaises(ValueError):validated_cache_payload(*args)

    def test_registers_metadata_consumers(self):
        req=spectrum_requirements(100,export_cache=True)
        self.assertEqual(CACHE_DERIVED,('H0','Omega_m','rs_drag'))
        for name in CACHE_DERIVED:
            self.assertIn(name,req)
            self.assertIsNone(req[name])
        self.assertIn('Hubble',req)
        self.assertIn('angular_diameter_distance',req)

    @unittest.skipUnless(importlib.util.find_spec('cobaya'),'requires provisioned Cobaya')
    def test_provider_with_only_dummy_likelihood(self):
        from cobaya.theory import Theory
        from cobaya.model import get_model
        class MetadataTheory(Theory):
            params={'metadata_anchor':{'value':1.}}
            def get_can_support_params(self): return ['metadata_anchor']
            def get_can_provide_params(self): return list(CACHE_DERIVED)
            def calculate(self,state,want_derived=True,**params_values):
                state['derived']={'H0':70.,'Omega_m':.3,'rs_drag':145.}
        info={'theory':{'metadata':{'external':MetadataTheory}},'likelihood':{'one':None},
              'params':{p:{'derived':True} for p in CACHE_DERIVED}}
        with get_model(info) as model:
            # Exact exported metadata requirements, independent of any likelihood.
            model.add_requirements({p:v for p,v in spectrum_requirements(100,True).items()
                                    if p in CACHE_DERIVED})
            model.logposterior({})
            self.assertEqual(model.provider.get_param('H0'),70.)
            self.assertEqual(model.provider.get_param('Omega_m'),.3)
            self.assertEqual(model.provider.get_param('rs_drag'),145.)
