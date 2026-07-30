from identity_gate import build_identity_infos


def test_identity_infos_fix_nfree_to_three_and_remove_n_from_reference():
    free, fixed = build_identity_infos("/packages")
    assert free["params"]["peer_n"] == {"value": 3.0}
    assert "peer_n" not in fixed["params"]
    assert set(free["theory"]) == {"peer_scalar_nfree.PEERScalarNFree"}
    assert set(fixed["theory"]) == {"peer_scalar_n3_reference.PEERScalarN3Reference"}
    assert set(free["likelihood"]) == set(fixed["likelihood"])
