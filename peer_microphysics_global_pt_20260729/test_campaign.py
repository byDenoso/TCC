from pathlib import Path

import campaign


def test_campaign_preserves_global_microphysics_target(tmp_path):
    info = campaign.build_info("/packages", str(tmp_path / "output"))
    assert info["params"]["peer_fede"]["prior"] == {"min": 0.0, "max": 0.18}
    assert info["params"]["peer_n"]["prior"] == {"min": 1.05, "max": 8.0}
    assert info["params"]["peer_zc"]["value"] == 3.81
    assert info["params"]["peer_thetai"]["value"] == 2.89155
    assert info["params"]["Alens"]["value"] == 1.0


def test_campaign_uses_exact_anchor_free_planck_desi_stack(tmp_path):
    info = campaign.build_info("/packages", str(tmp_path / "output"))
    likes = set(info["likelihood"])
    assert likes == {
        "planck_2018_highl_plik.TTTEEE_lite_native",
        "planck_2018_lowl.TT",
        "planck_2018_lowl.EE_sroll2",
        "planck_2018_lensing.native",
        "bao.desi_2024_bao_all",
    }
    assert not any("shoes" in name.lower() or "trgb" in name.lower() for name in likes)
    assert not any(name.startswith("act_") or name.startswith("spt") for name in likes)


def test_nfree_wrapper_assigns_sampled_index():
    source = Path(__file__).with_name("peer_scalar_nfree.py").read_text(encoding="utf-8")
    assert '"peer_n"' in source
    assert "ede.n = peer_n" in source
    assert 'peer_n = float(values.pop("peer_n", 3.0))' in source


def test_fixed_reference_wrapper_is_locked_to_n3():
    source = Path(__file__).with_name("peer_scalar_n3_reference.py").read_text(encoding="utf-8")
    assert "ede.n = 3" in source
    assert '"peer_n"' not in source
