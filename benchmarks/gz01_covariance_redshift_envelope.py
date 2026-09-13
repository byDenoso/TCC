#!/usr/bin/env python3
from __future__ import annotations
import json, math
from pathlib import Path

OUTPUT = Path("benchmark_result.json")
DK = {"label":"DESI DR1 x KiDS","s8":0.771,"sigma":0.017}
ER_FULL = {"label":"eROSITA eRASS1 full","s8":0.86,"sigma":0.01}
ER_BINS = [
    {"z_min":0.100,"z_max":0.175,"s8":0.83,"sigma":0.02},
    {"z_min":0.175,"z_max":0.244,"s8":0.82,"sigma":0.07},
    {"z_min":0.244,"z_max":0.330,"s8":0.86,"sigma":0.06},
    {"z_min":0.330,"z_max":0.452,"s8":0.84,"sigma":0.03},
    {"z_min":0.452,"z_max":0.800,"s8":0.94,"sigma":0.04},
]

def weighted_mean(rows):
    w=[1/r["sigma"]**2 for r in rows]
    return sum(a*r["s8"] for a,r in zip(w,rows))/sum(w), math.sqrt(1/sum(w))

def zcorr(a,sa,b,sb,rho):
    v=sa*sa+sb*sb-2*rho*sa*sb
    return abs(b-a)/math.sqrt(v)

def rho_for_z(a,sa,b,sb,target):
    d=abs(b-a)
    return (sa*sa+sb*sb-(d/target)**2)/(2*sa*sb)

def envelope(a,sa,b,sb):
    vals=[(rho,zcorr(a,sa,b,sb,rho)) for rho in (-1,-0.5,0,0.5,1)]
    return {"rho_grid":[{"rho":r,"z":z} for r,z in vals],"z_min_physical_rho":min(z for _,z in vals),"z_max_physical_rho":max(z for _,z in vals),"rho_required_for_3sigma":rho_for_z(a,sa,b,sb,3.0)}

def main():
    low, slow = weighted_mean(ER_BINS[:4])
    full = envelope(DK["s8"],DK["sigma"],ER_FULL["s8"],ER_FULL["sigma"])
    lowz = envelope(DK["s8"],DK["sigma"],low,slow)
    full_ind = zcorr(DK["s8"],DK["sigma"],ER_FULL["s8"],ER_FULL["sigma"],0)
    low_ind = zcorr(DK["s8"],DK["sigma"],low,slow,0)
    impossible = full["rho_required_for_3sigma"] < -1 or full["rho_required_for_3sigma"] > 1
    result={
      "schema":"nexo.gz01.covariance-redshift-envelope.v1",
      "campaign_id":"GZ-01",
      "batch_id":"GZ-01-B03-COVARIANCE-REDSHIFT",
      "status":"PASS",
      "inputs":{"desi_kids":DK,"erosita_full":ER_FULL,"erosita_bins":ER_BINS,"lowz_definition":"first four published eROSITA bins, z<0.452"},
      "tests":[
        {"test_id":"GZ01-T07-COVARIANCE-BOUND-FULL","independent_z":full_ind,**full},
        {"test_id":"GZ01-T08-REDSHIFT-MATCH-LOWZ","lowz_weighted_s8":low,"lowz_sigma":slow,"independent_z":low_ind,**lowz},
      ],
      "decision":{
        "classification":"REDSHIFT_MATCHING_DOMINATES_COVARIANCE_ONLY_EXPLANATION" if impossible and low_ind < 3 else "UNRESOLVED",
        "full_sample_below_3sigma_possible_by_gaussian_covariance_alone":not impossible,
        "next_discriminant":"Resolve redshift-matched posterior/likelihood constraints and calibration-systematic coupling; do not attribute the full-sample offset to covariance alone."
      },
      "claim_boundary":"Analytic sensitivity test over Gaussian summary constraints. It bounds what estimator covariance alone can do, but does not replace posterior-level redshift matching or calibration-systematics modeling."
    }
    OUTPUT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps({"status":result["status"],"classification":result["decision"]["classification"],"output":str(OUTPUT)},sort_keys=True))
if __name__ == "__main__": main()
