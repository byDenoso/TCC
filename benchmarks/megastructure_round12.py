from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping


GATE_147 = "T-MEGA26-LCDM-DATA-FREEZE-147"
GATE_148 = "T-MEGA26-LCDM-DETECTOR-CONTRACT-148"
OUTPUT_PATH = "megastructure_round12_result.json"

# Literature-backed inputs verified before execution on 2026-09-17.
# Campaign-specific choices are explicitly separated under `campaign_extension`.
FROZEN_ENSEMBLES: dict[str, dict[str, Any]] = {
    "EuclidLargeBox": {
        "version": "Euclid Preparation LXXVI public release; A&A 704 A306 (2025); arXiv:2507.12116",
        "role": "PRIMARY_EVT_ENSEMBLE",
        "literature_metadata": {
            "code": "PINOCCHIO",
            "n_realizations": 1000,
            "box_side_hinv_gpc": 3.38,
            "n_particles": "6144^3",
            "particle_mass_hinv_msun": 1.48e10,
            "minimum_halo_mass_hinv_msun": 1.48e11,
            "halo_lightcone": "half-sky, starting z=4",
            "galaxy_mock_footprint": "30 deg radius; 2763 deg^2; no box replication",
            "galaxy_mock_starting_redshift": 3.0,
        },
        "cosmology": {
            "Omega_m": 0.32,
            "Omega_Lambda": 0.68,
            "Omega_b": 0.049,
            "h": 0.67,
            "sigma8": 0.83,
            "n_s": 0.96,
        },
        "volume": {
            "geometry": "periodic cube plus past-light-cone products",
            "box_side_hinv_gpc": 3.38,
            "n_realizations": 1000,
        },
        "resolution": {
            "n_particles": "6144^3",
            "particle_mass_hinv_msun": 1.48e10,
        },
        "tracer_definition": {
            "literature": "Euclid spectroscopic H-alpha mock galaxies populated with HOD measured from Flagship",
            "fiducial_flux_cut_erg_s_cm2": 2.0e-16,
            "hod_redshift_bin": 0.01,
            "hod_log10_mass_bin_dex": 0.083,
            "primary_spectroscopic_redshift_interval": [0.9, 1.8],
            "number_density_target": "Flagship; approximately Pozzetti et al. 2016 model 3",
        },
        "halo_threshold": {
            "minimum_output_halo_mass_hinv_msun": 1.48e11,
            "minimum_particles_per_output_halo": 10,
        },
        "matter_products": {
            "independent_particle_density_field": False,
            "halo_catalogues": True,
            "past_lightcones": True,
            "merger_trees": True,
            "scope_note": "Primary EVT/tracer ensemble only; independent matter-support claims require FLAMINGO holdout.",
        },
        "data_access": {
            "halo_catalogues": "https://adlibitum.oats.inaf.it/pierluigi.monaco/euclid_mocks.html",
            "galaxy_catalogues": "https://cosmohub.pic.es",
        },
        "provenance": [
            "https://doi.org/10.1051/0004-6361/202556459",
            "https://arxiv.org/abs/2507.12116",
        ],
        "campaign_extension": {
            "use": "Estimate conditional L_max distribution and its dependence on volume, tracer density, bias, and finder.",
            "claim_boundary": "Do not use PINOCCHIO halo connectivity alone as independent matter support.",
        },
    },
    "FLAMINGO-10K": {
        "version": "FLAMINGO-10K public data-release identity; data release arXiv:2604.24324",
        "role": "HIGH_FIDELITY_MATTER_HOLDOUT",
        "literature_metadata": {
            "code": "SWIFT",
            "box_side_cgpc": 2.8,
            "n_cdm_particles": "10080^3",
            "n_neutrino_particles": "5600^3",
            "cdm_particle_mass_msun": 8.40e8,
            "softening_comoving_ckpc": 11.2,
            "softening_proper_pkpc": 2.85,
            "cosmology_label": "D3A",
        },
        "cosmology": {
            "Omega_m": 0.306,
            "Omega_Lambda": 0.694,
            "Omega_b": 0.0486,
            "h": 0.681,
            "sigma8": 0.807,
            "n_s": 0.967,
        },
        "volume": {
            "geometry": "periodic cube",
            "box_side_cgpc": 2.8,
            "n_realizations": 1,
        },
        "resolution": {
            "n_cdm_particles": "10080^3",
            "n_neutrino_particles": "5600^3",
            "cdm_particle_mass_msun": 8.40e8,
        },
        "tracer_definition": {
            "literature": "HBT-HERONS halo/subhalo catalogues are released; previous Giant-Arc comparisons used subhalo selections.",
            "campaign_rule": "Abundance-match halo/subhalo selections to the primary tracer density within each redshift bin; freeze thresholds before reading L_max.",
        },
        "halo_threshold": {
            "campaign_rule": "Threshold is not post-hoc: choose by preregistered abundance matching to Euclid-like tracer density; record exact threshold per redshift before topology measurement.",
        },
        "matter_products": {
            "full_particle_snapshots": True,
            "halo_catalogues": True,
            "structure_finder": "HBT-HERONS",
            "public_full_snapshot_redshifts": [5, 4, 3, 2, 1.5, 1, 0.75, 0.5, 0.4, 0.3, 0.2, 0.1, 0],
            "downsampled_particle_snapshots": "1% at all original outputs",
            "independent_particle_density_field": True,
        },
        "data_access": {
            "project": "https://flamingo.strw.leidenuniv.nl/data.html",
            "release_note": ">2.3 PB public release with selective-access web service",
        },
        "provenance": [
            "https://arxiv.org/abs/2604.24324",
            "https://academic.oup.com/mnrasl/article/541/1/L22/8071226",
            "https://flamingo.strw.leidenuniv.nl/simulations.html",
        ],
        "campaign_extension": {
            "use": "Unchanged detector replay plus independent matter-density/coherence holdout after volume, redshift, and tracer matching.",
            "claim_boundary": "One realization constrains holdout consistency, not the 1000-volume EVT tail by itself.",
        },
    },
}

PRIORITY_AND_STATE_OF_ART = {
    "existing_literature": [
        {
            "name": "Sawala et al. 2025",
            "result": "FLAMINGO-10K contains large connected patterns under a Giant-Arc-style selection; the paper argues apparent gigaparsec patterns are not by themselves anomalous in LambdaCDM.",
            "source": "https://academic.oup.com/mnrasl/article/541/1/L22/8071226",
        },
        {
            "name": "Lopez & Clowes 2025",
            "result": "Using SLHC/CHMS/MST on FLAMINGO-10K, they report no gigaparsec structures and only a few structures above 370 Mpc, highlighting detector-definition dependence.",
            "source": "https://arxiv.org/abs/2504.14940",
        },
        {
            "name": "Euclid Collaboration 2025",
            "result": "Publishes 1000 EuclidLargeBox/EuclidLargeMocks realizations suitable for survey-contained large-scale clustering covariance and extreme-volume sampling.",
            "source": "https://doi.org/10.1051/0004-6361/202556459",
        },
    ],
    "proposed_extension": "Measure the conditional extreme distribution L_max(V,z,n_tracer,bias,finder) while separating PATTERN_ONLY, TRACER_ROBUST, and MATTER_SUPPORTED classes and preserving finder stability as an explicit axis.",
    "potential_novelty": "A single preregistered cross-finder extreme-value envelope that joins 1000-volume EuclidLargeBox sampling to a particle-field FLAMINGO holdout, without equating connected tracer patterns with matter-supported structures.",
}

DETECTOR_CONTRACT: dict[str, Any] = {
    "version": "MEGASTRUCTURE_LCDM_ROUND12_DETECTOR_V1",
    "primary_observable": "L_span",
    "primary_observable_definition": "maximum 3D comoving Euclidean pairwise separation within one connected component",
    "secondary_observables": [
        "member_count",
        "tracer_overdensity",
        "matter_overdensity",
        "excess_mass",
        "anisotropy",
        "component_volume",
        "persistence",
        "finder_stability",
        "redshift",
    ],
    "families": {
        "FOF_SLHC": {
            "role": "observational connected-component family",
            "fof_grid_b_over_b0": [0.8, 0.9, 1.0, 1.1, 1.2],
            "headline_rule": "report the full preregistered grid; no single linking length defines the envelope",
        },
        "MST_GRAPH": {
            "role": "non-FoF graph/morphology family",
            "headline_rule": "apply frozen graph criteria and compare identity/rank overlap with FOF_SLHC",
        },
        "CONTINUOUS_MATTER": {
            "role": "independent particle-density/skeleton family",
            "headline_rule": "used only where particle-field products exist; required for MATTER_SUPPORTED classification",
        },
    },
    "classification": {
        "PATTERN_ONLY": "connected tracer component without cross-tracer/finder robustness and without independent matter support",
        "TRACER_ROBUST": "component persists across preregistered tracer/finder perturbations but lacks independent matter-field support",
        "MATTER_SUPPORTED": "component is tracer-robust and has preregistered independent matter-density/backbone support",
    },
    "anti_posthoc_rule": "No optimization of finder thresholds, tracer cuts, or redshift windows after inspecting candidate L_span is allowed in the primary envelope.",
    "tail_reporting": {
        "empirical_quantiles": [0.50, 0.95, 0.99],
        "q999_rule": "Report 0.999 only with sufficient empirical tail occupancy or a preregistered EVT fit with bootstrap stability.",
        "thresholds_gpc_comoving": [0.5, 0.8, 1.0, 1.5],
    },
}

_REQUIRED_147_FIELDS = (
    "version",
    "role",
    "cosmology",
    "volume",
    "resolution",
    "tracer_definition",
    "halo_threshold",
    "matter_products",
    "data_access",
    "provenance",
    "campaign_extension",
)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return True


def evaluate_admission_gate(ensembles: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    unresolved: list[str] = []
    required_names = ("EuclidLargeBox", "FLAMINGO-10K")
    for name in required_names:
        payload = ensembles.get(name)
        if not isinstance(payload, Mapping):
            unresolved.append(name)
            continue
        for field in _REQUIRED_147_FIELDS:
            if field not in payload or not _present(payload[field]):
                unresolved.append(f"{name}.{field}")

    euclid = ensembles.get("EuclidLargeBox", {})
    flamingo = ensembles.get("FLAMINGO-10K", {})
    if isinstance(euclid, Mapping):
        if euclid.get("volume", {}).get("n_realizations") != 1000:
            unresolved.append("EuclidLargeBox.volume.n_realizations")
        if euclid.get("halo_threshold", {}).get("minimum_output_halo_mass_hinv_msun") != 1.48e11:
            unresolved.append("EuclidLargeBox.halo_threshold.minimum_output_halo_mass_hinv_msun")
    if isinstance(flamingo, Mapping):
        if not flamingo.get("matter_products", {}).get("independent_particle_density_field"):
            unresolved.append("FLAMINGO-10K.matter_products.independent_particle_density_field")

    unresolved = sorted(set(unresolved))
    return {
        "gate_id": GATE_147,
        "status": "PASS" if not unresolved else "FAIL",
        "ensemble_names": [name for name in required_names if name in ensembles],
        "unresolved_required_fields": unresolved,
        "frozen_ensembles": copy.deepcopy(dict(ensembles)),
        "priority_and_state_of_art": copy.deepcopy(PRIORITY_AND_STATE_OF_ART),
        "claim_boundary": "EuclidLargeBox supplies the primary extreme-value/tracer ensemble; independent matter-support classification is delegated to the FLAMINGO-10K holdout.",
    }


def evaluate_detector_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    unresolved: list[str] = []
    families = contract.get("families") if isinstance(contract, Mapping) else None
    if not isinstance(families, Mapping):
        unresolved.append("families")
        families = {}
    required_families = ("FOF_SLHC", "MST_GRAPH", "CONTINUOUS_MATTER")
    for name in required_families:
        if name not in families:
            unresolved.append(f"families.{name}")
    fof_grid = families.get("FOF_SLHC", {}).get("fof_grid_b_over_b0", []) if isinstance(families.get("FOF_SLHC", {}), Mapping) else []
    expected_grid = [0.8, 0.9, 1.0, 1.1, 1.2]
    if fof_grid != expected_grid:
        unresolved.append("families.FOF_SLHC.fof_grid_b_over_b0")
    if contract.get("primary_observable") != "L_span":
        unresolved.append("primary_observable")
    if not _present(contract.get("anti_posthoc_rule")):
        unresolved.append("anti_posthoc_rule")

    unresolved = sorted(set(unresolved))
    return {
        "gate_id": GATE_148,
        "status": "PASS" if not unresolved else "FAIL",
        "primary_observable": contract.get("primary_observable"),
        "families": [name for name in required_families if name in families],
        "fof_grid_b_over_b0": list(fof_grid),
        "unresolved_required_fields": unresolved,
        "detector_contract": copy.deepcopy(dict(contract)),
    }


def run_gate(gate: str) -> dict[str, Any]:
    normalized = str(gate).strip().upper()
    if normalized in {"147", "T-MEGA26-LCDM-DATA-FREEZE-147", "LCDM-DATA-FREEZE"}:
        return evaluate_admission_gate(FROZEN_ENSEMBLES)
    if normalized in {"148", "T-MEGA26-LCDM-DETECTOR-CONTRACT-148", "LCDM-DETECTOR-CONTRACT"}:
        return evaluate_detector_contract(DETECTOR_CONTRACT)
    return {
        "gate_id": normalized,
        "status": "FAIL",
        "unresolved_required_fields": ["unsupported_gate"],
        "supported_gates": [147, 148],
    }


def main() -> None:
    gate = os.getenv("NEXO_PARAM_GATE", "147")
    output = Path(os.getenv("NEXO_PARAM_OUTPUT", OUTPUT_PATH))
    result = run_gate(gate)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result.get("status") == "PASS" else 2)


if __name__ == "__main__":
    main()
