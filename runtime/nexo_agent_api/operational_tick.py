"""Integration with the existing scheduled Writer; no new credentials or cron."""
from __future__ import annotations
import base64
import csv
import io
import json
from .operational_control import TowerWriterStore, OperationalWorker, initialize_work, digest, require
from .operational_transports import BoundedDrive, GitHubActions
from .operational_bootstrap import install_if_requested

SPOOL_ID = "1M2maKkuEjxumZRa145dzei7dEPFi2yKsKlUf7_scC-E"
WRITER_REF = "byDenoso/Pantheon/.github/workflows/nexo-writer-robot.yml@refs/heads/main"


def private_intents(session):
    response = session.get(f"https://www.googleapis.com/drive/v3/files/{SPOOL_ID}/export",
                           params={"mimeType": "text/csv"}, timeout=45)
    require(response.status_code == 200, "PRIVATE_SPOOL_UNAVAILABLE")
    require(len(response.content) <= 4 * 1024 * 1024, "PRIVATE_SPOOL_TOO_LARGE")
    rows = list(csv.reader(io.StringIO(response.text)))
    header_index = next((i for i, row in enumerate(rows) if "stable_id" in row and "envelope_b64url" in row), None)
    require(header_index is not None, "PRIVATE_SPOOL_HEADER_MISSING")
    header = rows[header_index]
    reader = (dict(zip(header, row)) for row in rows[header_index + 1:])
    intents, errors = {}, []
    for row in reader:
        stable = (row.get("stable_id") or "").strip()
        if not stable.startswith("op-"):
            continue
        try:
            encoded = (row.get("envelope_b64url") or "").strip()
            require(len(encoded) <= 48000, "INTENT_TOO_LARGE")
            value = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            require(value.get("id") == stable and value.get("contract") == "NEXO_OPERATIONAL_INTENT_V1", "SPOOL_BODY_ID_MISMATCH")
            require(stable == "op-" + digest({k:v for k,v in value.items() if k != "id"})[:48], "INTENT_HASH_MISMATCH")
            if stable in intents:
                require(intents[stable] == value, "SPOOL_IDENTITY_CONFLICT")
            intents[stable] = value
        except Exception as exc:
            errors.append({"id": stable, "error": getattr(exc, "code", type(exc).__name__)})
    return list(intents.values()), errors


def tick_existing_writer(tower, env):
    if env.get("NEXO_ROBOT_DRY"):
        return {"status": "NO_OP", "reason": "DRY_RUN"}
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_WORKFLOW_REF") == WRITER_REF,
            "EXISTING_SINGLETON_WRITER_REQUIRED")
    store = TowerWriterStore(tower)
    _, _, data = store._load()
    try:
        return _tick(tower, env, store, data)
    finally:
        if env.get("GITHUB_OUTPUT"):
            _, _, after = store._load()
            if after["revision"] != data["revision"]:
                # The existing workflow signals Atlas only after verified writes.
                # A later normal Writer write replaces this output with its head.
                with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write("tower_revision=" + after["revision"] + "\n")


def _tick(tower, env, store, data):
    config = install_if_requested(store, data, env)
    if not config or not config.get("enabled"):
        return {"status": "NO_OP", "reason": "NO_AUTHORIZED_OPERATIONAL_CONFIG"}
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_WORKFLOW_REF") == WRITER_REF,
            "EXISTING_SINGLETON_WRITER_REQUIRED")
    require(config.get("contract") == "NEXO_OPERATIONAL_RUNTIME_V1", "OPERATIONAL_CONFIG_INVALID")
    require(config.get("spool_id") == SPOOL_ID, "PRIVATE_SPOOL_DESTINATION_CHANGED")
    require(config.get("publication_authorized") is True and config.get("approval_ref"), "PUBLICATION_SUSPENDED")
    import requests
    drive = BoundedDrive(tower.session, allowed_folders=set(config.get("allowed_folder_ids") or []),
                         forbidden_roots={"root", "0ANZwoXbzaIA-Uk9PVA"})
    actions = GitHubActions(requests.Session(), env.get("GH_TOKEN") or env.get("GITHUB_TOKEN"), publication_authorized=True)
    errors = []
    existing = {item["id"] for item in store.all()}
    for definition in config.get("work", []):
        try:
            if definition["id"] not in existing:
                store.save(initialize_work(definition), 0)
        except Exception as exc:
            errors.append({"work_id": definition.get("id"), "error": getattr(exc, "code", type(exc).__name__)})
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    reader_json = env.get("NEXO_OPERATIONAL_READER_JSON", "")
    require(bool(reader_json), "EXISTING_DRIVE_READER_REQUIRED")
    reader_credentials = service_account.Credentials.from_service_account_info(
        json.loads(reader_json), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    reader = BoundedDrive(AuthorizedSession(reader_credentials), allowed_folders=set())
    worker = OperationalWorker(store, drive, actions,
                               recipe_loader=lambda recipe: drive.read_frozen(recipe["drive"]),
                               input_loader=reader.read_frozen)
    try:
        from .operational_probe import probe_role_session
        probe = probe_role_session(store, config, env)
    except Exception as exc:
        probe = {"state": "DEFERRED", "code": getattr(exc, "code", type(exc).__name__)}
    try:
        intents, spool_errors = private_intents(tower.session)
    except Exception as exc:
        intents, spool_errors = [], [{"error": getattr(exc, "code", type(exc).__name__)}]
    result = worker.tick(intents)
    result["role_probe"] = probe
    result["errors"].extend(errors + spool_errors)
    return {"status": "TICK_COMPLETED", **result}
