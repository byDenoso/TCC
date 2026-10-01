from pathlib import Path
import json
import tempfile
import yaml

from peer_n31p_spt3g_20260729.campaign import (
    prepare_resume_config,
    quick_evaluate_ref,
    write_configs,
)


SPT_TEMPLATE = """
likelihood:
  candl_like:
    data_set_file: spt_candl_data.SPT3G_D1_TnE
    external: candl.interface.CandlCobayaLikelihood
    clear_internal_priors: true
params:
  Tcal_ext150:
    prior: {min: 0.8, max: 1.2}
    ref: 1.0
  ombh2:
    prior: {min: 0.0, max: 0.1}
    ref: 0.0222
prior:
  gaussian_Tcal_ext150: "lambda Tcal_ext150: stats.norm.logpdf(Tcal_ext150, loc=1.0, scale=0.01)"
"""


def test_model(model: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        root = td_path / model
        template = td_path / "cobaya_ttteee.yaml"
        template.write_text(SPT_TEMPLATE, encoding="utf-8")

        write_configs(
            model,
            "/tmp/packages",
            root,
            spt_template=template,
            spt_data_ref="test-spt-d1-ref",
        )
        config_path = root / "configs" / "mcmc.yaml"
        info = yaml.safe_load(config_path.read_text())

        assert "candl_like" in info["likelihood"]
        assert info["likelihood"]["candl_like"]["class"] == "candl.interface.CandlCobayaLikelihood"
        assert info["likelihood"]["candl_like"]["data_set_file"] == "spt_candl_data.SPT3G_D1_TnE"
        assert "spt3g_2022.TTTEEE" not in info["likelihood"]
        assert "act_dr6_cmbonly" not in info["likelihood"]
        assert "act_dr6_cmbonly.PlanckActCut" not in info["likelihood"]
        assert not any(name.startswith("planck_2018_highl") for name in info["likelihood"])

        assert "Tcal_ext150" in info["params"]
        assert "gaussian_Tcal_ext150" in info["prior"]
        # PEER/base cosmology owns cosmological priors; the SPT template must not overwrite them.
        assert info["params"]["ombh2"]["prior"] == {"min": 0.017, "max": 0.027}
        assert info["params"]["peer_zc"]["value"] == 3.81
        assert info["params"]["peer_thetai"]["value"] == 2.89155
        if model == "LCDM":
            assert info["params"]["peer_fede"]["value"] == 0.0
            assert info["params"]["Alens"]["value"] == 1.0
        elif model == "N31P":
            assert "prior" in info["params"]["peer_fede"]
            assert info["params"]["Alens"]["value"] == 1.0
        else:
            assert "prior" in info["params"]["peer_fede"]
            assert "prior" in info["params"]["Alens"]
        assert "A_act" not in info["params"]
        assert "P_act" not in info["params"]
        assert "A_planck" not in info["params"]

        # A 300-sample warmup consumed the entire first 150-minute segment on
        # the real SPT D1 stack without writing a single chain sample. Keep the
        # initial warmup short; the independent promotion gate still discards
        # 30% of stored samples and requires rank-Rhat < 0.01.
        assert info["sampler"]["mcmc"]["burn_in"] == 50
        assert info["force"] is True
        assert info["resume"] is False

        prepare_resume_config(config_path)
        resumed = yaml.safe_load(config_path.read_text())
        assert resumed["force"] is False
        assert resumed["resume"] is True
        assert resumed["sampler"]["mcmc"]["burn_in"] == 50

        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["spt_dataset"] == "SPT3G_D1_TnE"
        assert manifest["spt_data_ref"] == "test-spt-d1-ref"
        assert "D1" in manifest["stack"]
        assert "2018" not in manifest["stack"]

        quick_root = td_path / f"quick_{model}"
        write_configs(
            model,
            "/tmp/packages",
            quick_root,
            spt_template=template,
            spt_data_ref="test-spt-d1-ref",
            quick_evaluate_only=True,
        )
        assert not (quick_root / "configs" / "mcmc.yaml").exists()
        quick_info = yaml.safe_load((quick_root / "configs" / "evaluate.yaml").read_text())
        quick_manifest = json.loads((quick_root / "manifest.json").read_text())
        expected_refs = quick_evaluate_ref(model)
        for name, value in expected_refs.items():
            spec = quick_info["params"].get(name)
            if isinstance(spec, dict) and "prior" in spec:
                assert spec["ref"] == value
        if model != "LCDM":
            assert quick_info["params"]["peer_fede"]["ref"] == expected_refs["peer_fede"]
        if model == "N31P_ALENS":
            assert quick_info["params"]["Alens"]["ref"] == expected_refs["Alens"]
        assert quick_manifest["coverage"] == "evaluate_N1_only_no_MCMC_no_global_evidence"
        assert quick_info["sampler"]["evaluate"]["override"] == quick_manifest["evaluation_reference"]["values"]
        assert quick_info["sampler"]["evaluate"]["override"]["Tcal_ext150"] == 1.0


def main() -> None:
    test_model("LCDM")
    test_model("N31P")
    test_model("N31P_ALENS")
    print("SPT D1 campaign structural tests: PASS")


if __name__ == "__main__":
    main()
