"""Versioned, private evidence retrieval over the existing NEXO memory source.

No source mutations or network calls. Models, graphs and caches are projections.
The original memory implementation remains available for controlled comparisons.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import re
import time
import unicodedata
from collections import Counter, OrderedDict, defaultdict, deque
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .live_tower import LIVE_TOWER_CONTRACT, LIVE_TOWER_FILE_ID

from .memory import (Memory, Document, Snapshot, SourceError, Conflict, ROLES, INACTIVE,
                     SECRETS, STOP, canonical, clean, digest, documents, derive,
                     fit_vectors, query_vector, references, role_name, runtime_acl, utc)

VERSION = "nexo-retrieval-1.1.0"
CHUNKER = "context-fields-1000-v1"
EXTRA_SURFACES = {"runtime/runs/": "RUN", "runtime/results/": "RESULT",
                  "runtime/evidence/": "EVIDENCE", "runtime/artifacts/": "ARTIFACT",
                  "recipes/": "RECIPE"}
RELATIONS = {
    "hypothesis_id": "tests_hypothesis", "hypothesis_ref": "tests_hypothesis",
    "hypothesis_refs": "tests_hypothesis", "test_id": "for_test",
    "target_test_id": "for_test", "test_ids": "for_test",
    "test_ref": "for_test", "test_refs": "for_test", "parent_test_id": "derived_from",
    "contests_test_id": "contests", "contest_test_id": "has_contest",
    "recipe": "uses_recipe", "recipe_ref": "uses_recipe", "recipe_id": "uses_recipe",
    "binding_id": "uses_binding", "binding_ref": "uses_binding", "data_binding_id": "uses_binding",
    "dataset": "uses_dataset", "dataset_id": "uses_dataset", "dataset_ref": "uses_dataset",
    "dataset_ids": "uses_dataset", "dataset_refs": "uses_dataset",
    "run_id": "has_run", "run_ref": "has_run", "result_id": "has_result", "result_ref": "has_result",
    "artifact_id": "has_artifact", "artifact_ref": "has_artifact", "artifact_refs": "has_artifact",
    "evidence_id": "supported_by", "evidence_ref": "supported_by", "evidence_refs": "supported_by",
    "work_id": "for_work", "work_ref": "for_work", "roadmap_id": "in_campaign",
    "roadmap_ref": "in_campaign", "campaign_id": "in_campaign", "depends_on": "depends_on",
    "depends_on_ids": "depends_on", "supersedes": "supersedes", "superseded_by": "superseded_by",
    "contradicts": "contradicts", "confirms": "confirms", "derives_from": "derived_from",
    "source_ref": "derived_from", "refs": "references", "related_ids": "references",
}
FILTERS = {"id", "kind", "state", "version", "path", "topic", "dataset", "recipe", "campaign",
           "hash", "writer_role", "updated_after", "updated_before", "fields"}
MODES = {"auto", "exact", "lexical", "lsa", "vector", "hybrid", "rerank", "graph",
         "embedding", "neural_hybrid", "neural_rerank"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])")
TECH_ID = re.compile(r"(?<![\w])(?:[A-Za-z][A-Za-z0-9_]*::)?[A-Za-z][A-Za-z0-9_]*(?:[-.:/][A-Za-z0-9_]+)+(?![\w])")


def fold(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold()
                   if not unicodedata.combining(c))


def tokens(value: str) -> list[str]:
    value = fold(value)
    # Whole identifiers and decimal tokens coexist with ordinary words.
    result = [w for w in re.findall(r"[a-z0-9_]+", value) if w not in STOP]
    result += ["id:" + x.group() for x in TECH_ID.finditer(value)]
    result += ["num:" + number_key(x.group()) for x in NUMBER.finditer(value)]
    return result


def number_key(value: Any) -> str:
    try:
        n = Decimal(str(value))
        if not n.is_finite():
            raise ValueError("Non-finite number")
        sign, digits, exponent = n.as_tuple()
        digits = list(digits)
        while digits and digits[-1] == 0:
            digits.pop(); exponent += 1
        if not digits:
            return "0"
        return ("-" if sign else "") + "".join(map(str, digits)) + "e" + str(exponent)
    except InvalidOperation as exc:
        raise ValueError("Invalid numeric literal") from exc


def pointer_escape(key: Any) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


def leaves(value: Any, pointer: str = ""):
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            yield from leaves(item, pointer + "/" + pointer_escape(key))
    elif isinstance(value, list):
        for n, item in enumerate(value):
            yield from leaves(item, pointer + "/" + str(n))
    elif value is not None:
        yield pointer, value


def resolve_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("fields filters require JSON pointers")
    for key in pointer[1:].split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not key.isdigit() or (len(key) > 1 and key.startswith("0")):
                raise KeyError(key)
            value = value[int(key)]
        else:
            value = value[key]
    return value


def typed_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (float, int)) and isinstance(right, (float, int)):
        return number_key(left) == number_key(right)
    return type(left) is type(right) and left == right


# Keep expanded surfaces at least as restrictive as the legacy memory policy.
SECRET_NAMES = {re.sub(r"[^a-z0-9]", "", name.lower()) for name in SECRETS | {
    "apikey", "secretkey", "accesstoken", "refreshtoken", "clientsecret", "privatekey",
    "password", "authorization", "credentials", "cookie", "cookies", "bearertoken",
}}


def safe_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe_clean(v) for k, v in value.items()
                if re.sub(r"[^a-z0-9]", "", str(k).lower()) not in SECRET_NAMES}
    if isinstance(value, list):
        return [safe_clean(v) for v in value]
    value = clean(value)
    if isinstance(value, str):
        return re.sub(r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,})", "[credential-redacted]", value)
    return value


def import_documents(snapshot: Snapshot, expanded: bool = True) -> tuple[list[Document], dict]:
    docs, stats = documents(snapshot)
    for d in docs:
        d.data = safe_clean(d.data)
        d.title = safe_clean(d.title)
        d.text = "\n".join(f"{p}: {v}" for p, v in leaves(d.data))[:16000]
        d.refs = references(d.data)
    known_paths = {d.path for d in docs}
    if not expanded:
        return docs, {**stats, "expanded_documents": 0}
    extras = []
    for path, entry in sorted(snapshot.payload["files"].items()):
        kind = next((k for p, k in EXTRA_SURFACES.items() if path.startswith(p)), None)
        if not kind or path in known_paths or entry.get("encoding") != "json":
            continue
        raw = entry.get("value")
        if not isinstance(raw, dict) or str(raw.get("domain", "")).upper() in {"HEALTH", "PERSONAL", "OLYMPUS"}:
            continue
        # Nested artifact aggregates are not silently treated as individual evidence.
        if kind == "ARTIFACT" and len(Path(path).parts) != 3:
            continue
        safe = safe_clean(raw)
        ident = str(raw.get("id") or raw.get(kind.lower() + "_id") or Path(path).stem)
        acl = safe.get("allowed_roles")
        if acl is not None:
            if not isinstance(acl, list):
                raise SourceError("Invalid allowed_roles")
            acl = runtime_acl(acl)
        elif safe.get("private"):
            recipient = safe.get("to") or safe.get("writer_role")
            acl = runtime_acl([recipient]) if recipient and recipient != "ALL" else []
        else:
            acl = sorted(ROLES)
        state = str(safe.get("state") or safe.get("status") or "RECORDED").upper()
        if safe.get("retired_at"):
            state = "RETIRED"
        title = str(safe.get("title") or safe.get("question") or safe.get("display_name") or ident)[:220]
        text = "\n".join(f"{p}: {v}" for p, v in leaves(safe))
        extras.append(Document(kind + "::" + ident, ident, path, "", kind,
            str(safe.get("entity_version") or safe.get("version") or "unversioned"),
            digest(raw), title, text[:16000], state, str(safe.get("topic_id") or ""), acl,
            references(safe), safe.get("expires_at") or safe.get("valid_until"), digest(safe), safe,
            len(text) > 16000))
    # Preserve different locations and quarantine collisions, never overwrite a canonical object.
    groups = defaultdict(list)
    for d in docs + extras:
        groups[d.uid].append(d)
    result = []
    for uid, group in sorted(groups.items()):
        if len(group) > 1:
            for d in group:
                d.uid = uid + "#" + digest([d.path, d.content_hash])[:16]
                d.ambiguous_identity = True
        result.extend(group)
    return result, {**stats, "expanded_documents": len(extras), "documents": len(result)}


def contextual_chunks(doc: Document) -> list[dict]:
    # Metadata is deterministic source context, not an LLM-generated explanation.
    context = {"entity": doc.object_id, "kind": doc.kind, "title": doc.title,
               "question": str(doc.data.get("question") or doc.data.get("hypothesis") or "")[:320],
               "version": doc.version, "document": doc.path, "state": doc.state}
    result, parts, spans, length = [], [], [], 0

    def flush():
        nonlocal parts, spans, length
        if not parts:
            return
        body = "\n".join(parts)
        ident = digest([CHUNKER, doc.uid, doc.content_hash, spans, body])
        result.append({"id": ident, "uid": doc.uid, "body": body, "context": context,
                       "segments": spans, "representation": "sanitized_json_values"})
        parts, spans, length = [], [], 0

    for pointer, value in leaves(doc.data):
        text = str(value) if isinstance(value, str) else canonical(value).decode()
        for start in range(0, max(1, len(text)), 850):
            line = pointer + ": " + text[start:start + 850]
            if parts and length + len(line) + 1 > 1000:
                flush()
            offset = length + bool(parts)
            parts.append(line)
            spans.append({"pointer": doc.pointer + pointer, "start": int(offset),
                          "end": int(offset + len(line)), "value_start": start,
                          "value_end": min(start + 850, len(text))})
            length = int(offset + len(line))
    flush()
    if not result:
        result.append({"id": digest([CHUNKER, doc.uid, doc.content_hash]), "uid": doc.uid,
                       "body": "{}", "context": context, "segments": [], "representation": "sanitized_json_values"})
    return result


def reference_fields(doc: Document) -> list[dict]:
    result = []
    for pointer, value in leaves(doc.data):
        if not isinstance(value, str):
            continue
        pieces = pointer.split("/")
        key = next((p for p in reversed(pieces) if p and not p.isdigit()), "")
        relation = RELATIONS.get(key)
        if relation:
            result.append({"ref": value, "relation": relation, "pointer": doc.pointer + pointer})
    return result


def alias_map(docs: list[Document]) -> dict[str, set[str]]:
    aliases = defaultdict(set)
    for d in docs:
        for alias in (d.uid, d.object_id, d.path, "TOWER_V06/" + d.path):
            aliases[alias].add(d.uid)
    return aliases


def build_edges(docs: list[Document], refs: dict[str, list[dict]]) -> tuple[list[dict], int]:
    aliases, edges, unresolved = alias_map(docs), [], 0
    seen = set()
    for d in docs:
        for field in refs[d.uid]:
            targets = aliases.get(field["ref"], set())
            if len(targets) != 1:
                unresolved += 1
                continue
            target = next(iter(targets))
            if target == d.uid:
                continue
            key = (d.uid, target, field["relation"], field["pointer"])
            if key not in seen:
                seen.add(key)
                edges.append({"source": d.uid, "target": target, "relation": field["relation"],
                              "pointer": field["pointer"], "origin": "explicit_source_field"})
    return sorted(edges, key=lambda e: (e["source"], e["target"], e["relation"], e["pointer"])), unresolved


class BM25:
    def __init__(self, texts: list[str]):
        self.size = len(texts)
        self.postings = defaultdict(list)
        self.lengths = []
        for n, text in enumerate(texts):
            counts = Counter(tokens(text))
            self.lengths.append(sum(counts.values()))
            for term, freq in counts.items():
                self.postings[term].append((n, freq))
        self.average = sum(self.lengths) / max(1, self.size)

    def score(self, query: str) -> dict[int, float]:
        scores = defaultdict(float)
        for term in set(tokens(query)):
            rows = self.postings.get(term, [])
            idf = math.log(1 + (self.size - len(rows) + .5) / (len(rows) + .5))
            for n, freq in rows:
                scores[n] += idf * freq * 2.2 / (freq + 1.2 * (.25 + .75 * self.lengths[n] / (self.average or 1)))
        return dict(scores)


class Retrieval(Memory):
    """Additive engine. Use a separate cache; never upgrade an old cache in place."""
    def __init__(self, path: str | Path, *, expanded: bool = True, contextual: bool = True,
                 embedding=None, reranker=None):
        super().__init__(path)
        self.expanded, self.contextual = bool(expanded), bool(contextual)
        self.embedding, self.reranker = embedding, reranker
        code_files = ("retrieval.py", "memory.py", "live_tower.py", "tower_paths.py")
        self.code_sha256 = digest({name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in code_files})
        self.config = digest([VERSION, CHUNKER, self.code_sha256, self.expanded, self.contextual])
        with self.connect() as db:
            previous = db.execute("SELECT value FROM meta WHERE key='retrieval_config'").fetchone()
            if (previous and previous[0] != self.config) or (not previous and self.head()):
                raise Conflict("Use a separate cache for this retrieval version/configuration")
            db.execute("INSERT OR IGNORE INTO meta VALUES ('retrieval_config',?)", (self.config,))
            db.execute("CREATE TABLE IF NOT EXISTS retrieval_records (id TEXT PRIMARY KEY, blob BLOB NOT NULL, sha256 TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS retrieval_vectors (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._views = OrderedDict()

    def sync(self, snapshot: Snapshot, *, expected_revision: str | None = None) -> dict:
        started = time.perf_counter()
        if snapshot.revision != "sha256:" + digest(snapshot.payload.get("files")) or snapshot.source_id != snapshot.payload.get("stable_file_id"):
            raise SourceError("Snapshot changed after validation")
        payload = snapshot.payload
        if (payload.get("contract") != LIVE_TOWER_CONTRACT or payload.get("authority") != "TOWER_V06"
                or snapshot.source_id != LIVE_TOWER_FILE_ID or payload.get("storage") != "GOOGLE_DRIVE_PRIVATE"
                or payload.get("truth_owner") != "TOWER_V06@GOOGLE_DRIVE_PRIVATE"
                or payload.get("write_model") != "IN_PLACE_FILE_REVISION_CAS_READBACK"
                or payload.get("file_count") != len(payload["files"])
                or payload.get("state_fingerprint") != snapshot.revision
                or payload.get("updated_at") != snapshot.observed_at
                or payload["files"].get("CONTROL.json", {}).get("value", {}).get("truth_owner") != payload.get("truth_owner")):
            raise SourceError("Canonical authority validation failed")
        before = self.head()
        if before and before["source_id"] != snapshot.source_id:
            raise SourceError("Canonical source changed")
        if expected_revision is not None and (before or {}).get("revision") != expected_revision:
            raise Conflict("Index revision changed")
        if before and before["revision"] == snapshot.revision:
            return {"changed": False, "revision": snapshot.revision, **json.loads(before["stats"]),
                    "elapsed_s": time.perf_counter() - started}
        if before and utc(snapshot.observed_at) <= utc(before["observed_at"]):
            raise Conflict("Older or ambiguously dated source")
        docs, stats = import_documents(snapshot, self.expanded)
        previous_docs = self._generation(before["generation"])["documents"] if before else []
        old = {d["uid"]: d["content_hash"] for d in previous_docs}
        new = {d.uid: d.content_hash for d in docs}
        records, created, refs = [], [], {}
        with self.connect() as db:
            available = {r[0] for r in db.execute("SELECT id FROM retrieval_records")}
        chunks_count = 0
        for d in docs:
            key = digest([self.config, asdict(d)])
            records.append(key)
            refs[d.uid] = reference_fields(d)
            if key not in available:
                chunks = contextual_chunks(d)
                record = canonical({"document": asdict(d), "chunks": chunks})
                created.append((key, gzip.compress(record, mtime=0), hashlib.sha256(record).hexdigest()))
                chunks_count += len(chunks)
        edges, unresolved = build_edges(docs, refs)
        manifest = {"version": VERSION, "config": self.config, "records": records, "edges": edges}
        raw = canonical(manifest)
        gid = hashlib.sha256(raw).hexdigest()
        stats.update({"documents_added": len(new.keys() - old.keys()), "documents_removed": len(old.keys() - new.keys()),
            "documents_updated": sum(new[u] != old[u] for u in new.keys() & old.keys()),
            "records_rebuilt": len(created), "records_reused": len(records) - len(created),
            "new_chunks": chunks_count, "graph_edges": len(edges), "unresolved_reference_fields": unresolved,
            "lsa_policy": "lazy_refit_per_changed_authorized_view", "embeddings_policy": "content_addressed_if_configured"})
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT value FROM meta WHERE key='head'").fetchone()
            if (current[0] if current else None) != (before["revision"] if before else None):
                raise Conflict("Concurrent index update")
            db.executemany("INSERT OR IGNORE INTO retrieval_records VALUES (?,?,?)", created)
            db.execute("INSERT OR IGNORE INTO generations VALUES (?,?,?)", (gid, gzip.compress(raw, mtime=0), gid))
            db.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?)", (snapshot.revision, gid, snapshot.source_id,
                       snapshot.raw_sha256, snapshot.observed_at, canonical(stats).decode()))
            db.execute("INSERT OR REPLACE INTO meta VALUES ('head',?)", (snapshot.revision,))
        self._loaded = None
        self._views.clear()
        if self.head()["revision"] != snapshot.revision:
            raise Conflict("Readback changed concurrently")
        return {"changed": True, "revision": snapshot.revision, "elapsed_s": time.perf_counter() - started, **stats}

    def _generation(self, gid: str) -> dict:
        if self._loaded and self._loaded[0] == gid:
            return self._loaded[1]
        with self.connect() as db:
            row = db.execute("SELECT blob,sha256 FROM generations WHERE id=?", (gid,)).fetchone()
            if row is None:
                raise SourceError("Index generation missing")
            raw = gzip.decompress(row[0])
            if hashlib.sha256(raw).hexdigest() != row[1]:
                raise SourceError("Index generation hash mismatch")
            manifest = json.loads(raw)
            if manifest.get("version") != VERSION or manifest.get("config") != self.config:
                raise SourceError("Retrieval version/config mismatch")
            # A single scan avoids thousands of connections. Historical rows remain private at rest.
            wanted = set(manifest["records"])
            records = {}
            for key, blob, sha in db.execute("SELECT id,blob,sha256 FROM retrieval_records"):
                if key not in wanted:
                    continue
                decoded = gzip.decompress(blob)
                if hashlib.sha256(decoded).hexdigest() != sha:
                    raise SourceError("Document index hash mismatch")
                records[key] = json.loads(decoded)
            if wanted != records.keys():
                raise SourceError("Incomplete index generation")
        gen = {"documents": [], "chunks": [], "edges": manifest["edges"], "version": VERSION}
        for key in manifest["records"]:
            gen["documents"].append(records[key]["document"])
            gen["chunks"].extend(records[key]["chunks"])
        self._loaded = gid, gen
        return gen

    def _view(self, role: str, *, expected_revision=None, as_of=None, include_inactive=False) -> dict:
        role = role_name(role)
        head = self.head()
        if head is None:
            raise SourceError("No verified Tower snapshot indexed")
        current_gen = self._generation(head["generation"])
        current = {d["uid"]: d for d in current_gen["documents"]}
        snap, gen = self.select(expected_revision=expected_revision, as_of=as_of)
        at = as_of or datetime.now(timezone.utc).isoformat()
        allowed = []
        for item in gen["documents"]:
            d = Document(**item)
            latest = current.get(d.uid)
            # Current authorization also gates history; deletion never resurrects cached text.
            if not latest or role not in latest["allowed_roles"] or latest["state"] == "DELETED":
                continue
            if d.ambiguous_identity or latest.get("ambiguous_identity"):
                continue
            if self.eligible(d, role, at, include_inactive):
                allowed.append(d)
        key = digest([head["revision"], snap["revision"], role, [(d.uid, d.content_hash) for d in allowed], include_inactive])
        if key in self._views:
            self._views.move_to_end(key)
            return self._views[key]
        visible = {d.uid for d in allowed}
        all_alias = alias_map([Document(**d) for d in current_gen["documents"] + gen["documents"]])
        hidden = {a for a, ids in all_alias.items() if not ids.intersection(visible)}
        # Suppress hidden identifiers in a visible source's references, including free text.
        hidden_sorted = sorted((s for s in hidden if s), key=len, reverse=True)
        pattern = re.compile(r"(?<![\w])(?:" + "|".join(re.escape(s) for s in hidden_sorted) + r")(?![\w])") if hidden_sorted else None

        def redact(value):
            if isinstance(value, dict):
                return {k: redact(v) for k, v in value.items()}
            if isinstance(value, list):
                return [redact(v) for v in value]
            return pattern.sub("[restricted reference]", value) if isinstance(value, str) and pattern else value

        original_chunks = defaultdict(list)
        for c in gen["chunks"]:
            if c["uid"] in visible:
                original_chunks[c["uid"]].append(c)
        chunks = []
        for d in allowed:
            masked_data, masked_title = redact(d.data), redact(d.title)
            changed = masked_data != d.data or masked_title != d.title
            d.data, d.title, d.text = masked_data, masked_title, redact(d.text)
            chunks.extend(contextual_chunks(d) if changed else original_chunks[d.uid])
        edges = [e for e in gen["edges"] if e["source"] in visible and e["target"] in visible]
        texts = [self._chunk_text(c) for c in chunks]
        view = {"key": key, "snapshot": snap, "authorization_revision": head["revision"], "role": role,
                "documents": {d.uid: d for d in allowed}, "chunks": chunks, "edges": edges,
                "bm25": BM25(texts), "texts": texts, "lsa": None, "aliases": alias_map(allowed)}
        self._views[key] = view
        while len(self._views) > 4:
            self._views.popitem(last=False)
        return view

    def _chunk_text(self, chunk: dict) -> str:
        if not self.contextual:
            return chunk["body"]
        c = chunk["context"]
        return "\n".join([c["entity"], c["title"], c["question"], "version " + c["version"], chunk["body"]])

    def _finish(self, view: dict):
        if self.head()["revision"] != view["authorization_revision"]:
            raise Conflict("Authorization/source changed during retrieval")

    @staticmethod
    def _safe_snapshot(view: dict) -> dict:
        snap = view["snapshot"]
        return {k: snap[k] for k in ("revision", "source_id", "source_sha256", "observed_at")}

    @staticmethod
    def _match(doc: Document, filters: dict) -> bool:
        for key, wanted in filters.items():
            if key == "fields":
                for pointer, value in wanted.items():
                    try:
                        actual = resolve_pointer(doc.data, pointer)
                    except (KeyError, IndexError, TypeError):
                        return False
                    if not typed_equal(actual, value):
                        return False
                continue
            direct = {"id": (doc.uid, doc.object_id), "kind": (doc.kind,), "state": (doc.state,),
                      "version": (doc.version,), "path": (doc.path,), "topic": (doc.topic,)}
            if key in direct:
                values = direct[key]
            elif key in {"updated_after", "updated_before"}:
                actual = doc.data.get("updated_at") or doc.data.get("created_at")
                try:
                    if not actual or (utc(actual) < utc(wanted) if key == "updated_after" else utc(actual) > utc(wanted)):
                        return False
                except (ValueError, TypeError):
                    return False
                continue
            else:
                endings = {"dataset": {"dataset", "dataset_id", "dataset_ref"},
                           "recipe": {"recipe", "recipe_id", "recipe_ref"},
                           "campaign": {"roadmap_id", "campaign_id"}, "writer_role": {"writer_role", "owner_role"}}
                values = [v for p, v in leaves(doc.data) if p.split("/")[-1] in endings.get(key, set())]
                if key == "hash":
                    values = [doc.content_hash] + [v for p, v in leaves(doc.data) if p.endswith(("hash", "sha256", "digest"))]
                    values = [str(v).removeprefix("sha256:") for v in values]
                    wanted = str(wanted).removeprefix("sha256:")
            choices = wanted if isinstance(wanted, list) else [wanted]
            if not any(typed_equal(v, str(w) if key == "version" else w) for v in values for w in choices):
                return False
        return True

    @staticmethod
    def _validate_filters(filters: dict | None) -> dict:
        if filters is None:
            return {}
        if not isinstance(filters, dict) or set(filters) - FILTERS:
            raise ValueError("Unsupported filters")
        for key, value in filters.items():
            if key == "fields":
                if not isinstance(value, dict) or len(value) > 16:
                    raise ValueError("Invalid field filters")
                for pointer, scalar in value.items():
                    if not isinstance(pointer, str) or not pointer.startswith("/") or isinstance(scalar, (dict, list)):
                        raise ValueError("Field filters must map JSON pointers to scalar values")
            elif not isinstance(value, (str, int, list)) or isinstance(value, bool):
                raise ValueError("Filter values must be scalars or a list of exact alternatives")
            if isinstance(value, list) and (len(value) > 32 or not all(isinstance(v, (str, int)) for v in value)):
                raise ValueError("Invalid filter list")
        for key in ("updated_after", "updated_before"):
            if key in filters:
                utc(filters[key])
        return filters

    @staticmethod
    def _query_ids(query: str, view: dict) -> list[str]:
        found = set(view["aliases"].get(query.strip(), set()))
        for value in TECH_ID.findall(query):
            found.update(view["aliases"].get(value, set()))
        for value in re.findall(r"[A-Za-z][A-Za-z0-9_]{5,}", query):
            if "_" in value:
                found.update(view["aliases"].get(value, set()))
        return sorted(found)

    @staticmethod
    def route(query: str, has_id: bool, filters: dict) -> dict:
        q = fold(query)
        unknown_identifier = bool(re.fullmatch(r'(?:TEST|HYPOTHESIS|HYP|RUN|RESULT|WORK|DATASET|DATA|RECIPE|CONTRACT)::[A-Za-z0-9_.:/-]+', query.strip())) or any(re.match(r"^(?:(?:TEST|HYPOTHESIS|HYP|RUN|RESULT|WORK|DATASET|DATA|RECIPE|CONTRACT)::[A-Za-z0-9_.:/-]+|(?:TEST|HYP|RUN|RESULT|WORK|DATA|RECIPE|CONTRACT|T)-[A-Z0-9_-]+)$", x)
                                 for x in TECH_ID.findall(query))
        graph_cue = any(s in q for s in ("relacion", "connect", "conecta", "cadeia", "trace", "receita", "recipe", "depende", "depend", "resultado de", "result of", "associad", "associated", "quais testes", "which tests"))
        if has_id and graph_cue:
            target_kinds = []
            if "receita" in q or "recipe" in q:
                target_kinds = ["RECIPE"]
            elif "quais testes" in q or "which tests" in q:
                target_kinds = ["TEST"]
            elif "dataset" in q or "conjuntos de dados" in q:
                target_kinds = ["DATA_BINDING", "DATASET"]
            return {"mode": "graph", "reason": "identifier_with_relation_request", "target_kinds": target_kinds}
        if has_id or unknown_identifier or (not query.strip() and filters) or (NUMBER.fullmatch(query.strip()) is not None):
            return {"mode": "exact", "reason": "exact_identifier_numeric_or_filters"}
        if any(s in q for s in ("aprendemos", "learned", "familias", "families", "evidencias converg", "evidence converg")):
            return {"mode": "lexical", "reason": "broad_evidence_lexical_first; graph_tools_available_for_explicit_traces"}
        return {"mode": "lexical", "reason": "measured_lexical_default; hybrid_remains_opt_in"}

    def _lsa(self, view: dict):
        import numpy as np
        if view["lsa"] is None:
            model, vectors = fit_vectors(view["texts"])
            view["lsa"] = model, np.asarray(vectors, dtype="float32")
        return view["lsa"]

    def _embedding_scores(self, query: str, view: dict):
        import numpy as np
        if self.embedding is None:
            raise SourceError("NEURAL_EMBEDDING_NOT_CONFIGURED")
        model_id = self.embedding.fingerprint
        keys = [digest([model_id, t]) for t in view["texts"]]
        key_set = set(keys)
        with self.connect() as db:
            values = {k: json.loads(v) for k, v in db.execute("SELECT id,value FROM retrieval_vectors") if k in key_set}
        missing = [(k, t) for k, t in zip(keys, view["texts"]) if k not in values]
        if missing:
            encoded = np.asarray(self.embedding.encode([t for _, t in missing]), dtype="float32")
            if encoded.ndim != 2 or len(encoded) != len(missing) or not np.isfinite(encoded).all():
                raise SourceError("Invalid embedding response")
            values.update({k: row.tolist() for (k, _), row in zip(missing, encoded)})
            with self.connect() as db:
                db.executemany("INSERT OR IGNORE INTO retrieval_vectors VALUES (?,?)", [(k, canonical(values[k]).decode()) for k, _ in missing])
        matrix = np.asarray([values[k] for k in keys], dtype="float32")
        qv = np.asarray(self.embedding.encode([query]), dtype="float32")
        if qv.ndim != 2 or qv.shape[0] != 1 or matrix.shape[1:] != qv.shape[1:] or not np.isfinite(qv).all():
            raise SourceError("Embedding dimension/finite check failed")
        denom = np.linalg.norm(matrix, axis=1) * np.linalg.norm(qv[0])
        return np.divide(matrix @ qv[0], denom, out=np.zeros(len(matrix)), where=denom > 0)

    def search(self, query: str, role: str, *, k: int = 8, expected_revision=None, as_of=None,
               include_inactive=False, kinds=None, mode: str = "auto", filters: dict | None = None) -> dict:
        import numpy as np
        started = time.perf_counter()
        if not isinstance(query, str) or len(query) > 4000 or type(k) is not int or not 1 <= k <= 50 or mode not in MODES:
            raise ValueError("Invalid retrieval request")
        filters = self._validate_filters(filters)
        if kinds:
            filters = {**filters, "kind": kinds}
        view = self._view(role, expected_revision=expected_revision, as_of=as_of, include_inactive=include_inactive)
        docs, chunks = view["documents"], view["chunks"]
        eligible = {u for u, d in docs.items() if self._match(d, filters)}
        exact = set(self._query_ids(query, view)) & eligible
        routing_query = query
        matched_aliases = set()
        for uid in exact:
            d = docs[uid]
            matched_aliases.update((d.uid, d.object_id, d.path, "TOWER_V06/" + d.path))
        for alias in sorted(matched_aliases, key=len, reverse=True):
            routing_query = routing_query.replace(alias, "[entity]")
        route = self.route(routing_query, bool(exact), filters)
        effective = route["mode"] if mode == "auto" else ("lsa" if mode == "vector" else mode)
        query_numbers = {number_key(m.group()) for m in NUMBER.finditer(query)} if NUMBER.fullmatch(query.strip()) else set()
        if query_numbers:
            eligible = {u for u in eligible if query_numbers.issubset({number_key(m.group()) for _, v in leaves(docs[u].data)
                         for m in NUMBER.finditer(str(v))})}
        row_ids = [n for n, c in enumerate(chunks) if c["uid"] in eligible]
        lexical = view["bm25"].score(query)
        cosine = np.zeros(len(chunks)); model_sha = None
        vector_modes = {"lsa", "hybrid", "rerank", "graph"}
        if effective in vector_modes and query.strip() and row_ids and not (effective == "graph" and exact):
            model, matrix = self._lsa(view)
            qv = query_vector(query, model)
            cosine = matrix @ qv if len(qv) else cosine
            model_sha = model.get("model_sha256")
        if effective in {"embedding", "neural_hybrid", "neural_rerank"} and row_ids:
            cosine = self._embedding_scores(query, view)
            model_sha = self.embedding.fingerprint
        rankings = []
        if effective in {"lexical", "hybrid", "rerank", "graph", "neural_hybrid", "neural_rerank", "exact"}:
            rankings.append(("lexical", sorted((n for n in row_ids if lexical.get(n, 0) > 0), key=lambda n: (-lexical[n], chunks[n]["id"]))))
        if effective in vector_modes | {"embedding", "neural_hybrid", "neural_rerank"}:
            rankings.append(("semantic", sorted((n for n in row_ids if cosine[n] > .12), key=lambda n: (-cosine[n], chunks[n]["id"]))))
        scores = defaultdict(float)
        stage_ranks = defaultdict(dict)
        for name, ranking in rankings:
            # Fuse entity ranks, preventing long documents from consuming all candidate slots.
            seen = set(); rank = 0
            for n in ranking:
                uid = chunks[n]["uid"]
                if uid in seen:
                    continue
                seen.add(uid); rank += 1
                if rank > 160:
                    break
                scores[uid] += 1 / (60 + rank)
                stage_ranks[uid][name] = rank
        pure_rrf = dict(scores)
        if effective == "exact":
            if exact:
                scores = {u: 1.0 for u in exact}
            elif query_numbers or (not query.strip() and filters):
                scores = {u: 1.0 for u in eligible}
            else:
                # Unknown identifier is absent in the authorized view, not a fuzzy substitute.
                scores = {}
        best = {}
        for n in sorted(row_ids, key=lambda i: (-lexical.get(i, 0), -float(cosine[i]), chunks[i]["id"])):
            best.setdefault(chunks[n]["uid"], n)
        graph_paths = {}
        if effective == "graph":
            seeds = list(exact) or sorted(scores, key=lambda u: (-scores[u], u))[:3]
            for seed in seeds:
                graph = self._walk(view, seed, depth=2, direction="both", relation=None, limit=80)
                for node in graph["nodes"]:
                    uid = node["id"]
                    if uid in eligible and uid != seed:
                        graph_paths.setdefault(uid, {"seed": seed, "distance": node["distance"]})
                        scores[uid] = scores.get(uid, 0) + .008 / node["distance"]
        for u in exact:
            if effective != "graph":
                scores[u] = scores.get(u, 0) + 10
        if effective == "graph" and exact and route.get("target_kinds"):
            scores = {u: score for u, score in scores.items()
                      if docs[u].kind in route["target_kinds"] and (u in graph_paths or u in exact)}
        candidates = sorted(scores, key=lambda u: (-scores[u], u))[:80]
        rerank_scores = {}
        if effective in {"rerank", "neural_rerank"}:
            if effective == "neural_rerank":
                if self.reranker is None:
                    raise SourceError("NEURAL_RERANKER_NOT_CONFIGURED")
                values = self.reranker.score([(query, view["texts"][best[u]]) for u in candidates])
                if len(values) != len(candidates) or not all(math.isfinite(float(v)) for v in values):
                    raise SourceError("Invalid reranker response")
                rerank_scores = dict(zip(candidates, map(float, values)))
            else:
                q = set(tokens(query))
                for u in candidates:
                    body_terms = set(tokens(chunks[best[u]]["body"]))
                    title_terms = set(tokens(docs[u].title))
                    rerank_scores[u] = scores[u] + .02 * len(q & body_terms) / max(1, len(q)) + .005 * len(q & title_terms) / max(1, len(q))
            candidates.sort(key=lambda u: (u not in exact, -rerank_scores[u], -scores[u], u))
        hits = []
        for u in candidates[:k]:
            n = best[u]; d = docs[u]; c = chunks[n]
            hits.append({"id": u, "title": d.title, "kind": d.kind, "state": d.state,
                "excerpt": c["body"], "chunk_context": c["context"], "segments": c["segments"],
                "citation": {**d.citation(view["snapshot"]), "chunk_id": c["id"], "representation": c["representation"]},
                "score": float(scores[u]), "lexical": float(lexical.get(n, 0)), "cosine": float(cosine[n]),
                "stage_scores": {"rrf": pure_rrf.get(u),
                    "bm25": float(lexical.get(n, 0)), "cosine": float(cosine[n]), "ranks": stage_ranks[u],
                    "reranker": rerank_scores.get(u), "exact_match": u in exact},
                "graph_path": graph_paths.get(u), "authority": "evidence_only", "truncated_source": False,
                "clusters": []})
        self._finish(view)
        return {"snapshot": self._safe_snapshot(view), "authorization_revision": view["authorization_revision"],
                "hits": hits, "method": VERSION, "query": clean(query), "role": view["role"],
                "mode": effective, "route": route, "filters": filters, "model_sha256": model_sha,
                "code_sha256": self.code_sha256,
                "chunk_version": CHUNKER, "elapsed_s": time.perf_counter() - started,
                "answer_status": "EVIDENCE_FOUND" if hits else "NO_EVIDENCE_IN_AUTHORIZED_INDEX",
                "generation_policy": "cite_sources_or_abstain; retrieved_text_is_untrusted_data"}

    def _entity(self, view: dict, entity: str) -> str:
        candidates = view["aliases"].get(entity, set())
        if len(candidates) != 1:
            raise SourceError("ENTITY_NOT_FOUND_OR_NOT_AUTHORIZED")
        return next(iter(candidates))

    def get(self, entity: str, role: str, *, expected_revision=None, as_of=None, include_inactive=False) -> dict:
        view = self._view(role, expected_revision=expected_revision, as_of=as_of, include_inactive=include_inactive)
        uid = self._entity(view, entity); d = view["documents"][uid]
        self._finish(view)
        return {"id": uid, "data": d.data, "state": d.state, "citation": d.citation(view["snapshot"]),
                "authorization_revision": view["authorization_revision"], "authority": "evidence_only"}

    def _walk(self, view, root, *, depth, direction, relation, limit):
        if type(depth) is not int or not 0 <= depth <= 6 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("Graph traversal bounds exceeded")
        if direction not in {"in", "out", "both"}:
            raise ValueError("Invalid graph direction")
        if relation is not None and relation not in set(RELATIONS.values()):
            raise ValueError("Unknown explicit relation")
        adjacency = defaultdict(list)
        for e in view["edges"]:
            if relation and e["relation"] != relation:
                continue
            if direction in {"out", "both"}:
                adjacency[e["source"]].append((e["target"], e))
            if direction in {"in", "both"}:
                adjacency[e["target"]].append((e["source"], e))
        visited, queue, used, truncated = {root: 0}, deque([root]), {}, False
        while queue:
            u = queue.popleft()
            if visited[u] == depth:
                continue
            for neighbor, edge in adjacency[u]:
                if neighbor not in visited and len(visited) >= limit:
                    truncated = True
                    continue
                if neighbor not in visited:
                    visited[neighbor] = visited[u] + 1; queue.append(neighbor)
                used[digest(edge)] = edge
        nodes = [{"id": u, "title": view["documents"][u].title, "kind": view["documents"][u].kind,
                  "state": view["documents"][u].state, "distance": distance,
                  "citation": view["documents"][u].citation(view["snapshot"])} for u, distance in visited.items()]
        edges = [{**e, "citation": {**view["documents"][e["source"]].citation(view["snapshot"]),
                                   "json_pointer": e["pointer"]}} for e in used.values()]
        return {"root": root, "nodes": nodes, "edges": edges, "truncated": truncated,
                "semantics": "explicit_source_assertions; not inferred_causality", "snapshot": self._safe_snapshot(view)}

    def trace(self, entity: str, role: str, *, depth=4, direction="both", relation=None, limit=100,
              expected_revision=None, as_of=None, include_inactive=False) -> dict:
        view = self._view(role, expected_revision=expected_revision, as_of=as_of, include_inactive=include_inactive)
        root = self._entity(view, entity)
        result = self._walk(view, root, depth=depth, direction=direction, relation=relation, limit=limit)
        self._finish(view)
        return result

    def neighbors(self, entity: str, role: str, **kwargs) -> dict:
        return self.trace(entity, role, depth=1, **kwargs)

    def diff(self, entity: str, role: str, revision_a: str, revision_b: str) -> dict:
        snapshots = []
        with self.connect() as db:
            for revision in (revision_a, revision_b):
                row = db.execute("SELECT * FROM snapshots WHERE revision=?", (revision,)).fetchone()
                if row is None:
                    raise SourceError("UNOBSERVED_REVISION")
                snapshots.append(dict(row))
        authorization_revision = self.head()["revision"]
        left = self.get(entity, role, as_of=snapshots[0]["observed_at"], include_inactive=True, expected_revision=authorization_revision)
        right = self.get(entity, role, as_of=snapshots[1]["observed_at"], include_inactive=True, expected_revision=authorization_revision)
        def flatten(value, pointer=""):
            if isinstance(value, dict) and value:
                for key, item in sorted(value.items()):
                    yield from flatten(item, pointer + "/" + pointer_escape(key))
            elif isinstance(value, list) and value:
                for n, item in enumerate(value):
                    yield from flatten(item, pointer + "/" + str(n))
            else:
                yield pointer, value
        a = dict(flatten(left["data"])); b = dict(flatten(right["data"]))
        changes = []
        for p in sorted(a.keys() | b.keys()):
            if p not in a or p not in b or not typed_equal(a[p], b[p]):
                changes.append({"pointer": p, "operation": "add" if p not in a else "remove" if p not in b else "replace",
                                "before": a.get(p), "after": b.get(p)})
        return {"entity": entity, "changes": changes, "from": left["citation"], "to": right["citation"],
                "history_scope": "observed_verified_snapshots_only"}

    def groups(self, role: str, *, expected_revision=None, as_of=None, limit=30, mode="topic") -> dict:
        if type(limit) is not int or not 1 <= limit <= 100 or mode not in {"topic", "semantic"}:
            raise ValueError("Invalid group request")
        view = self._view(role, expected_revision=expected_revision, as_of=as_of)
        if mode == "semantic":
            _, matrix = self._lsa(view)
            groups, _ = derive(list(view["documents"].values()), view["chunks"], matrix.tolist())
        else:
            groups, _ = derive(list(view["documents"].values()), [], [])
        self._finish(view)
        return {"groups": groups[:limit], "truncated": len(groups) > limit,
                "method": "authorized_lsa_neighborhoods_and_topics" if mode == "semantic" else "explicit_canonical_topics", "snapshot": self._safe_snapshot(view), "scientific_authority": False}

    def dreams(self, role: str, *, expected_revision=None) -> dict:
        view = self._view(role, expected_revision=expected_revision)
        _, candidates = derive(list(view["documents"].values()), [], [])
        self._finish(view)
        return {"revision": view["snapshot"]["revision"], "candidates": candidates,
                "classification": "DERIVED", "scientific_authority": False}
