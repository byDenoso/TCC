from pathlib import Path
import json
import tempfile
import yaml

from peer_n31p_spt3g_20260729.campaign import write_configs


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
        info = yaml.safe_load((root / "configs" / "mcmc.yaml").read_text())

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
        assert "prior" in info["params"]["peer_fede"]
        if model == "N31P":
            assert info["params"]["Alens"]["value"] == 1.0
        else:
            assert "prior" in info["params"]["Alens"]
        assert "A_act" not in info["params"]
        assert "P_act" not in info["params"]
        assert "A_planck" not in info["params"]

        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["spt_dataset"] == "SPT3G_D1_TnE"
        assert manifest["spt_data_ref"] == "test-spt-d1-ref"
        assert "D1" in manifest["stack"]
        assert "2018" not in manifest["stack"]


def main() -> None:
    test_model("N31P")
    test_model("N31P_ALENS")
    print("SPT D1 campaign structural tests: PASS")


if __name__ == "__main__":
    main()
