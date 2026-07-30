#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path


def sh(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--act-contract",type=Path,required=True); ap.add_argument("--spt-contract",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); args=ap.parse_args()
    report={
      "status":"INDEPENDENT_DATA_LIKELIHOOD_REPLICATION_CONTRACT",
      "act":{"contract":str(args.act_contract),"sha256":sh(args.act_contract),"likelihood":"ACT DR6 lite","commit":"627aeafb88ae5ad1aa66b406bea2d65cfa66a27d"},
      "spt":{"contract":str(args.spt_contract),"sha256":sh(args.spt_contract),"likelihood":"SPT-3G TTTEEE","commit":"633c5a3da99bb6e78c60a7514f311fc3577965bc"},
      "independent_axes":["high-l data product","likelihood implementation","nuisance/calibration model","random seeds","MCMC shard initial centres"],
      "shared_axes":["PEER CAMB scalar-field implementation","Planck low-l","Planck lensing","DESI DR2 BAO","SH0ES"],
      "claim_limit":"Independent high-l data/likelihood replication, not an external-team or independent-theory-code replication."
    }
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(report,indent=2),encoding="utf-8"); print(json.dumps(report,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
