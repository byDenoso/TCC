from pathlib import Path
import tempfile
import yaml

from peer_n31p_spt3g_20260729.campaign import write_configs


def test_model(model: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / model
        write_configs(model, "/tmp/packages", root)
        info = yaml.safe_load((root / "configs" / "mcmc.yaml").read_text())
        assert "spt3g_2022.TTTEEE" in info["likelihood"]
        assert "act_dr6_cmbonly" not in info["likelihood"]
        assert "act_dr6_cmbonly.PlanckActCut" not in info["likelihood"]
        assert not any(name.startswith("planck_2018_highl") for name in info["likelihood"])
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


def main() -> None:
    test_model("N31P")
    test_model("N31P_ALENS")
    print("SPT campaign structural tests: PASS")


if __name__ == "__main__":
    main()
