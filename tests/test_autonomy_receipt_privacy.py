"""Synthetic envelopes only; no authority or data from a live Tower."""
import copy

import pytest

from runtime.nexo_agent_api import autonomy, operation_receipts as receipts
from runtime.nexo_agent_api.gpt_writer import (
    _gateway_results, _transport_gateway_report, apply_to_tower,
)
from runtime.nexo_agent_api.live_tower import build_live_tower_payload, read_live_tower_bytes
from tests.test_autonomy_prepared import approval, root


def gateway(item, identity="private-fixture"):
    return dict(item, _inbox_source="GATEWAY", _inbox_id="gateway:" + identity,
                _inbox_name="gw-" + identity)


def packed(root):
    import json
    return json.dumps(build_live_tower_payload(root)).encode()


@pytest.mark.parametrize("action", ["APPROVE_AUTONOMY_MANDATE", "REVOKE_AUTONOMY_MANDATE"])
def test_authority_envelopes_are_not_public_gateway_receipts(action):
    item = gateway(approval(action=action))
    assert not receipts.public_gateway_envelope(item, "gateway:private-fixture")
    # The deny rule applies only to the two authority-changing actions.
    item["payload"]["action"] = "OTHER_EXISTING_OPERATION"
    assert receipts.public_gateway_envelope(item, "gateway:private-fixture")


@pytest.mark.parametrize("action", ["APPROVE_AUTONOMY_MANDATE", "REVOKE_AUTONOMY_MANDATE"])
def test_terminal_rejection_and_replay_remain_private_and_idempotent(root, action):
    item = gateway(approval(action=action))
    first, report = apply_to_tower(packed(root), [item])
    assert report["rejected"]
    rows = [row for row in report["operation_receipts"]
            if row["effect_id"] == receipts.envelope_effect_id("gateway:private-fixture")]
    assert rows and all(row["visibility"] == "PRIVATE" for row in rows)
    assert not report["public_operation_receipts"]
    again, replay = apply_to_tower(first, [item])
    assert not replay["public_operation_receipts"]
    assert _gateway_results(replay, ["private-fixture"], {"private-fixture"})[0]["items"] == []
    before = read_live_tower_bytes(first)["files"]
    after = read_live_tower_bytes(again or first)["files"]
    private_ledger = lambda files: {k: v for k, v in files.items() if k.startswith("operations/receipts/")}
    assert private_ledger(after) == private_ledger(before)


def test_verified_activation_still_applies_privately_and_replays_once(root):
    item = gateway(approval())
    first, report = apply_to_tower(packed(root), [item],
                                 verified_human_intents=frozenset({autonomy.envelope_hash(item)}))
    control = read_live_tower_bytes(first)["files"]["CONTROL.json"]["value"]
    assert control["autonomy_mandate"]["status"] == "ACTIVE"
    assert not report["public_operation_receipts"]
    second, replay = apply_to_tower(first, [item],
                                   verified_human_intents=frozenset({autonomy.envelope_hash(item)}))
    after = read_live_tower_bytes(second or first)["files"]["CONTROL.json"]["value"]
    assert after["autonomy_mandate"] == control["autonomy_mandate"]
    assert not replay["public_operation_receipts"]


def test_verified_revocation_still_applies_privately_and_replays_once(root):
    activation = gateway(approval(), "activation-fixture")
    active, _ = apply_to_tower(packed(root), [activation],
                              verified_human_intents=frozenset({autonomy.envelope_hash(activation)}))
    revocation = gateway(approval(revision=1, action="REVOKE_AUTONOMY_MANDATE"))
    revoked, report = apply_to_tower(active, [revocation],
                                   verified_human_intents=frozenset({autonomy.envelope_hash(revocation)}))
    control = read_live_tower_bytes(revoked)["files"]["CONTROL.json"]["value"]
    assert control["autonomy_mandate"]["status"] == "REVOKED"
    assert not report["public_operation_receipts"]
    duplicate, replay = apply_to_tower(revoked, [revocation],
                                      verified_human_intents=frozenset({autonomy.envelope_hash(revocation)}))
    after = read_live_tower_bytes(duplicate or revoked)["files"]["CONTROL.json"]["value"]
    assert after["autonomy_mandate"] == control["autonomy_mandate"]
    assert not replay["public_operation_receipts"]


def test_legacy_public_receipt_is_not_reexported_or_rewritten(root):
    item = gateway(approval())
    intent = "gateway:private-fixture"
    old = receipts.build_receipt(intent=intent,
        payload_sha256=receipts.payload_hash(item, trusted_transport=True),
        effect=receipts.envelope_effect_id(intent), outcome="REJECTED_TERMINAL",
        source_revision="sha256:" + "1" * 64, result_revision="sha256:" + "2" * 64,
        visibility="PUBLIC", reason_code="SYNTHETIC_OLD_REJECTION")
    receipts.persist_receipt(root, old)
    output, report = apply_to_tower(packed(root), [item])
    assert not report["public_operation_receipts"]
    assert report["operation_receipts"][0]["receipt_id"] == old["receipt_id"]
    files = read_live_tower_bytes(output or packed(root))["files"]
    assert files["operations/receipts/" + old["receipt_id"] + ".json"]["value"] == old


@pytest.mark.parametrize("failure", [RuntimeError("synthetic outage"), PermissionError("synthetic refusal")])
def test_transport_and_shadow_outcomes_never_export_private_metadata(failure):
    entries = [{"id": "private-fixture", "envelope": approval()}]
    report = _transport_gateway_report(entries, failure)
    assert report["operation_receipts"][0]["visibility"] == "PRIVATE"
    assert _gateway_results(report, ["private-fixture"], {"private-fixture"}) == (
        {"contract": receipts.CONTRACT, "items": []}, [], [],
    )


def test_mixed_batch_preserves_public_sibling_and_hides_parent(root):
    public = {"kind": "UNKNOWN_FIXTURE_KIND", "source": "CHATGPT", "payload": {}}
    item = gateway({"kind": "BATCH", "payload": {"items": [approval(), public]}})
    _, report = apply_to_tower(packed(root), [item])
    assert [row["intent_id"] for row in report["public_operation_receipts"]] == [
        "gateway:private-fixture.batch-1",
    ]
    assert _gateway_results(report, ["private-fixture"], {"private-fixture"})[0]["items"] == []
    report = _transport_gateway_report([{"id": "private-fixture", "envelope": item}], RuntimeError())
    assert not report["public_operation_receipts"]


def test_nested_batch_is_private_without_affecting_plain_public_failure():
    private = {"kind": "BATCH", "payload": {"items": [
        {"kind": "BATCH", "payload": {"items": [approval()]}},
    ]}}
    assert receipts.private_operator_envelope(private)
    public = copy.deepcopy(private)
    public["payload"]["items"][0]["payload"]["items"][0]["payload"]["action"] = "OTHER_EXISTING_OPERATION"
    report = _transport_gateway_report([{"id": "ordinary", "envelope": public}], RuntimeError())
    result, reported, resolved = _gateway_results(report, ["ordinary"])
    assert result["items"][0]["outcome"] == "RETRYABLE_TRANSPORT"
    assert reported == ["ordinary"] and not resolved
