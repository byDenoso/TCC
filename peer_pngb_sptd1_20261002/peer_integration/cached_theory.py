"""Read-only, single-point theory replay for isolated likelihood diagnostics.

This component is deliberately not a cosmological sampler/backend: it accepts
no cosmological inputs and fails for redshifts/spectra outside the saved point.
"""
import json
import numpy as np
from cobaya.theory import Theory


class CachedPoint(Theory):
    cache_file: str = ''
    # Cobaya requires every theory component to depend on at least one input.
    # This fixed identity coordinate is neither sampled nor cosmological.
    params={'cache_point_id':{'value':0}}

    def initialize(self):
        with np.load(self.cache_file,allow_pickle=False) as data:
            self.cache={k:np.array(data[k],copy=True) for k in data.files}
        self.meta=json.loads(str(self.cache['metadata_json']))
        if self.meta['schema']!='peer-single-point-v1':
            raise ValueError('Unknown cache schema')

    def get_can_support_params(self): return ['cache_point_id']
    def get_allow_agnostic(self): return False
    def get_can_provide_params(self): return ['H0','rdrag','rs_drag','Omega_m']

    def must_provide(self,**requirements):
        for key,value in requirements.items():
            if key=='Cl':
                for spec,lmax in value.items():
                    if 'raw_'+spec not in self.cache or lmax>self.cache['ell'][-1]:
                        raise ValueError(f'Cache does not provide {spec} to {lmax}')
            elif key in ('Hubble','angular_diameter_distance'):
                self._at_redshift('H_km_s_Mpc' if key=='Hubble' else 'DA_Mpc',value['z'])
            elif key not in self.get_can_provide_params():
                raise ValueError(f'Unsupported cache requirement: {key}')

    def calculate(self,state,want_derived=True,**params_values_dict):
        if params_values_dict not in ({},{'cache_point_id':0}):
            raise ValueError('CachedPoint cannot vary cosmology or its fixed cache identity')
        state['derived']={k:self.meta['derived'][k] for k in self.get_can_provide_params()}

    def _at_redshift(self,key,z):
        zz=np.atleast_1d(z).astype(float)
        delta=np.abs(zz[:,None]-self.cache['bao_z'][None,:])
        indices=np.argmin(delta,axis=1)
        if np.any(delta[np.arange(len(zz)),indices]>1e-10):
            raise ValueError('Requested redshift was not saved; no interpolation allowed')
        result=self.cache[key][indices]
        # Match BoltzmannBase: even one scalar z returns a length-one array.
        # Cobaya BAO assembles these arrays and transposes before taking row 0.
        # Returning a scalar would silently keep only the first BAO prediction.
        return result

    def get_Hubble(self,z,units='km/s/Mpc'):
        value=self._at_redshift('H_km_s_Mpc',z)
        if units=='km/s/Mpc': return value
        if units=='1/Mpc': return value/299792.458
        raise ValueError(f'Unknown Hubble units {units}')

    def get_angular_diameter_distance(self,z): return self._at_redshift('DA_Mpc',z)

    def get_Cl(self,ell_factor=False,units='FIRASmuK2'):
        factor={'muK2':1.,'FIRASmuK2':2.7255/self.meta['T_cmb'],
                'K2':1e-6,'1':1/(self.meta['T_cmb']*1e6)}.get(units)
        if factor is None: raise ValueError(f'Unsupported Cl units {units}')
        out={'ell':self.cache['ell'].copy()}
        ell=out['ell']; ef=ell*(ell+1)/(2*np.pi)
        for key,value in self.cache.items():
            if not key.startswith('raw_'): continue
            spec=key[4:]; v=value.copy()
            v*=factor**sum(spec.count(x) for x in 'teb')
            if ell_factor:
                if spec=='pp': v[2:]*=ef[2:]**2*(2*np.pi)
                elif 'p' in spec: v[2:]*=ef[2:]**1.5*np.sqrt(2*np.pi)
                else: v[2:]*=ef[2:]
            out[spec]=v
        return out
