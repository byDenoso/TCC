from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class DarkEnergyResponseError(RuntimeError):
    pass


def _float_env(name: str, default: float) -> float:
    raw = str(os.getenv(name, "")).strip()
    return default if not raw else float(raw)


def _csv_floats_env(name: str, default: str) -> list[float]:
    raw = str(os.getenv(name, default)).strip()
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise DarkEnergyResponseError(f"{name} must contain at least one numeric value")
    if not all(math.isfinite(value) for value in values):
        raise DarkEnergyResponseError(f"{name} contains non-finite values")
    return values


def _binding_request() -> dict[str, Any]:
    path = str(os.getenv("NEXO_BINDING_INPUT_PATH") or "").strip()
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DarkEnergyResponseError("bound input must be a JSON object")
    if payload.get("schema") not in {None, "nexo.dark-energy-linear-response.request.v1"}:
        raise DarkEnergyResponseError("unsupported bound dark-energy response schema")
    return payload


def _request_from_env() -> dict[str, Any]:
    bound = _binding_request()
    model = str(bound.get("dark_energy_model") or os.getenv("NEXO_PARAM_DARK_ENERGY_MODEL", "fluid")).strip().lower()
    if model not in {"fluid", "ppf"}:
        raise DarkEnergyResponseError("dark_energy_model must be 'fluid' or 'ppf'")

    w0 = float(bound.get("w0", _float_env("NEXO_PARAM_W0", -0.9)))
    wa = float(bound.get("wa", _float_env("NEXO_PARAM_WA", 0.0)))
    default_cs2 = 1e-4 if model == "fluid" else 1.0
    cs2 = float(bound.get("cs2", _float_env("NEXO_PARAM_CS2", default_cs2)))
    if not math.isfinite(w0) or not math.isfinite(wa) or not math.isfinite(cs2):
        raise DarkEnergyResponseError("w0, wa and cs2 must be finite")
    if cs2 < 0:
        raise DarkEnergyResponseError("cs2 must be non-negative")
    if model == "ppf" and not math.isclose(cs2, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise DarkEnergyResponseError(
            "CAMB 1.6.6 DarkEnergyPPF does not support varying sound speed; use cs2=1 or dark_energy_model=fluid"
        )
    if model == "fluid" and wa != 0.0:
        w_early = w0 + wa
        if (w0 + 1.0) * (w_early + 1.0) <= 0.0:
            raise DarkEnergyResponseError("DarkEnergyFluid cannot cross w=-1; use ppf for crossing w(a)")

    raw_redshifts = bound.get("redshifts")
    if raw_redshifts is None:
        redshifts = _csv_floats_env("NEXO_PARAM_REDSHIFTS", "0,0.05,0.1,0.2")
    else:
        redshifts = [float(value) for value in raw_redshifts]
    raw_k = bound.get("k_mpc")
    if raw_k is None:
        k_mpc = _csv_floats_env("NEXO_PARAM_K_MPC", "0.001,0.01,0.05")
    else:
        k_mpc = [float(value) for value in raw_k]

    redshifts = sorted(set(redshifts), reverse=True)
    k_mpc = sorted(set(k_mpc))
    if not redshifts or not k_mpc:
        raise DarkEnergyResponseError("redshifts and k_mpc must be non-empty")
    if any((not math.isfinite(z)) or z < 0 for z in redshifts):
        raise DarkEnergyResponseError("redshifts must be finite and >=0")
    if any((not math.isfinite(k)) or k <= 0 for k in k_mpc):
        raise DarkEnergyResponseError("k values must be finite and >0")

    bound_cosmology = bound.get("cosmology") if isinstance(bound.get("cosmology"), dict) else {}
    defaults = {
        "H0": ("NEXO_PARAM_H0", 67.4),
        "ombh2": ("NEXO_PARAM_OMBH2", 0.0224),
        "omch2": ("NEXO_PARAM_OMCH2", 0.12),
        "mnu": ("NEXO_PARAM_MNU", 0.06),
        "tau": ("NEXO_PARAM_TAU", 0.054),
        "As": ("NEXO_PARAM_AS", 2.1e-9),
        "ns": ("NEXO_PARAM_NS", 0.965),
        "omk": ("NEXO_PARAM_OMK", 0.0),
    }
    cosmology = {
        key: float(bound_cosmology.get(key, _float_env(env_name, default)))
        for key, (env_name, default) in defaults.items()
    }
    if not all(math.isfinite(value) for value in cosmology.values()):
        raise DarkEnergyResponseError("cosmology parameters must be finite")

    return {
        "schema": "nexo.dark-energy-linear-response.request.v1",
        "dark_energy_model": model,
        "w0": w0,
        "wa": wa,
        "cs2": cs2,
        "redshifts": redshifts,
        "k_mpc": k_mpc,
        "cosmology": cosmology,
    }


def _worker(request_path: Path, result_path: Path) -> int:
    import camb
    import numpy as np
    from camb import symbolic

    request = json.loads(request_path.read_text(encoding="utf-8"))
    c = request["cosmology"]
    pars = camb.CAMBparams()
    pars.set_cosmology(
        H0=c["H0"],
        ombh2=c["ombh2"],
        omch2=c["omch2"],
        mnu=c["mnu"],
        omk=c["omk"],
        tau=c["tau"],
    )
    pars.InitPower.set_params(As=c["As"], ns=c["ns"])
    pars.set_dark_energy(
        w=request["w0"],
        wa=request["wa"],
        cs2=request["cs2"],
        dark_energy_model=request["dark_energy_model"],
    )
    max_k = max(request["k_mpc"])
    pars.set_matter_power(redshifts=request["redshifts"], kmax=max(0.1, max_k * 1.2))
    pars.WantTransfer = True
    results = camb.get_transfer_functions(pars, only_time_sources=True)

    z = np.asarray(request["redshifts"], dtype=float)
    q = np.asarray(request["k_mpc"], dtype=float)
    base = results.get_redshift_evolution(q, z, vars=["delta_tot", "delta_tot_de", "growth", "H"])
    delta_de = results.get_redshift_evolution(q, z, vars=[symbolic.Delta_de])[:, :, 0]
    hubble = np.asarray(results.hubble_parameter(z), dtype=float)
    luminosity_distance = np.asarray(results.luminosity_distance(z), dtype=float)

    modes = []
    for ik, kval in enumerate(q.tolist()):
        evolution = []
        for iz, zval in enumerate(z.tolist()):
            delta_tot, delta_tot_de, growth, conformal_h = [float(x) for x in base[ik, iz, :]]
            evolution.append(
                {
                    "z": zval,
                    "delta_tot": delta_tot,
                    "delta_tot_de": delta_tot_de,
                    "delta_de": float(delta_de[ik, iz]),
                    "de_contribution_to_delta_tot": delta_tot_de - delta_tot,
                    "growth": growth,
                    "conformal_H_Mpc^-1": conformal_h,
                }
            )
        modes.append({"k_Mpc^-1": kval, "evolution": evolution})

    result = {
        "schema": "nexo.dark-energy-linear-response.v1",
        "status": "PASS",
        "solver": {"name": "CAMB", "version": camb.__version__},
        "request": request,
        "background": [
            {
                "z": float(zval),
                "H_km_s_Mpc": float(hubble[index]),
                "luminosity_distance_Mpc": float(luminosity_distance[index]),
            }
            for index, zval in enumerate(z.tolist())
        ],
        "modes": modes,
        "nexo_verification": {
            "status": "PASS",
            "decision": "INCONCLUSIVE",
            "reason_code": "LINEAR_DE_RESPONSE_COMPUTED",
            "scope": "SCIENTIFIC",
        },
        "claim_boundary": (
            "Linear FLRW perturbation response only; this output does not by itself model a localized "
            "anisotropic void or establish an observational dark-energy anisotropy."
        ),
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker":
        if len(sys.argv) != 4:
            raise SystemExit("worker requires request and result paths")
        return _worker(Path(sys.argv[2]), Path(sys.argv[3]))

    request = _request_from_env()
    output = Path(str(os.getenv("NEXO_PARAM_RESULT_PATH") or "dark_energy_response_result.json"))
    launcher = str(os.getenv("NEXO_CAPABILITY_PEER_CAMB_EXACT_V2_LAUNCHER") or "").strip()
    if not launcher:
        raise DarkEnergyResponseError("peer.camb.exact_v2 launcher is not prepared")

    request_path = output.with_suffix(output.suffix + ".request.json")
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        completed = subprocess.run(
            [launcher, str(Path(__file__).resolve()), "--worker", str(request_path), str(output)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(float(os.getenv("NEXO_PARAM_WORKER_TIMEOUT_SECONDS", "120"))),
        )
        if completed.returncode != 0:
            raise DarkEnergyResponseError(
                f"portable CAMB worker failed rc={completed.returncode}: {completed.stderr.strip()[-1200:]}"
            )
        if not output.is_file():
            raise DarkEnergyResponseError("portable CAMB worker returned success without result output")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if payload.get("status") != "PASS":
            raise DarkEnergyResponseError("portable CAMB response did not report PASS")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    finally:
        request_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
