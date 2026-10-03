"""Real Drive and GitHub adapters. No credentials are created or persisted.

Only instantiate writable adapters in the existing serialized Writer job.
`publication_authorized` is deployment configuration, never an MCP argument.
"""
from __future__ import annotations

import base64
import io
import json
import re
import stat
import zipfile
from urllib.parse import quote, urlparse

from .operational_control import OperationalError, REPOSITORY, WORKFLOW, canonical, digest, require, verify_run

DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3"
META = "id,name,mimeType,parents,trashed,headRevisionId,size"
MAX_BYTES = 2 * 1024 * 1024


class BoundedDrive:
    def __init__(self, session, *, allowed_folders: set[str], forbidden_roots: set[str] = frozenset({"root"})):
        self.session = session
        self.allowed_folders = set(allowed_folders)
        self.forbidden_roots = set(forbidden_roots) | {"root", ""}
        require(not self.allowed_folders.intersection(self.forbidden_roots), "ROOT_WRITE_FORBIDDEN")

    def _request(self, method, url, **kwargs):
        try:
            response = self.session.request(method, url, timeout=45, **kwargs)
        except Exception as exc:
            raise OperationalError("DRIVE_TRANSPORT_UNKNOWN", retryable=True) from exc
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise OperationalError("DRIVE_TEMPORARY_FAILURE", retryable=True)
        require(response.status_code < 400, f"DRIVE_HTTP_{response.status_code}")
        return response

    def metadata(self, file_id):
        require(isinstance(file_id, str) and re.fullmatch(r"[\w-]+", file_id), "DRIVE_ID_INVALID")
        return self._request("GET", f"{DRIVE}/files/{quote(file_id)}", params={"fields": META, "supportsAllDrives": "true"}).json()

    def read_frozen(self, reference):
        file_id = reference.get("file_id")
        require(file_id and reference.get("version") and reference.get("sha256"), "FROZEN_REFERENCE_INCOMPLETE")
        before = self.metadata(file_id)
        require(not before.get("trashed") and before.get("id") == file_id, "DRIVE_SOURCE_ID_MISMATCH")
        require(before.get("headRevisionId") == reference["version"], "DRIVE_REVISION_CHANGED")
        require(int(before.get("size", MAX_BYTES + 1)) <= MAX_BYTES, "DRIVE_SOURCE_TOO_LARGE")
        raw = self._request("GET", f"{DRIVE}/files/{quote(file_id)}", params={"alt": "media", "supportsAllDrives": "true"}).content
        require(len(raw) <= MAX_BYTES and digest(raw) == reference["sha256"], "DRIVE_BODY_HASH_MISMATCH")
        after = self.metadata(file_id)
        require(after.get("headRevisionId") == before["headRevisionId"], "DRIVE_READ_RACE")
        if reference.get("parent_id"):
            require(after.get("parents") == [reference["parent_id"]], "DRIVE_SOURCE_DESTINATION_CHANGED")
        return raw

    def _find(self, parent, name):
        require(re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", name), "DRIVE_NAME_INVALID")
        items, page = [], None
        while True:
            params = {"q": f"'{parent}' in parents and name = '{name}' and trashed = false",
                      "fields": "nextPageToken,files(" + META + ")", "pageSize": 100,
                      "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
            if page:
                params["pageToken"] = page
            result = self._request("GET", f"{DRIVE}/files", params=params).json()
            items.extend(result.get("files", []))
            page = result.get("nextPageToken")
            if not page:
                return items
            require(len(items) <= 1000, "DRIVE_LIST_BOUND_EXCEEDED")

    def put_immutable(self, parent, name, raw):
        require(parent in self.allowed_folders and parent not in self.forbidden_roots, "DESTINATION_NOT_ALLOWLISTED")
        require(isinstance(raw, bytes) and len(raw) <= MAX_BYTES, "DRIVE_BODY_INVALID")
        folder = self.metadata(parent)
        require(folder.get("id") == parent and not folder.get("trashed") and folder.get("mimeType") == "application/vnd.google-apps.folder", "DESTINATION_NOT_EXISTING_FOLDER")
        files = self._find(parent, name)
        require(len(files) <= 1, "DRIVE_DUPLICATE_NAME")
        if files:
            metadata = self.metadata(files[0]["id"])
            require(metadata.get("parents") == [parent] and metadata.get("name") == name, "DRIVE_DESTINATION_MISMATCH")
            ref = {"file_id": metadata["id"], "version": metadata.get("headRevisionId"), "sha256": digest(raw), "parent_id": parent}
            require(self.read_frozen(ref) == raw, "IMMUTABLE_CONTENT_CONFLICT")
            return ref
        # A single multipart request writes metadata and body; no empty bridges.
        boundary = "nexo-" + digest(raw)
        metadata = canonical({"name": name, "mimeType": "application/json", "parents": [parent]})
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + metadata
                + f"\r\n--{boundary}\r\nContent-Type: application/json\r\n\r\n".encode() + raw
                + f"\r\n--{boundary}--\r\n".encode())
        created = self._request("POST", f"{UPLOAD}/files", params={"uploadType": "multipart", "fields": META, "supportsAllDrives": "true"},
                                headers={"Content-Type": f"multipart/related; boundary={boundary}"}, data=body).json()
        actual = self.metadata(created["id"])
        require(actual.get("parents") == [parent] and actual.get("name") == name, "DRIVE_DESTINATION_MISMATCH")
        reference = {"file_id": actual["id"], "version": actual.get("headRevisionId"), "sha256": digest(raw), "parent_id": parent}
        require(self.read_frozen(reference) == raw, "DRIVE_WRITE_READBACK_FAILED")
        return reference


def verified_result_archive(raw, metadata, run, work):
    verify_run(run, work)
    require(metadata.get("workflow_run", {}).get("id") == run["id"], "ARTIFACT_RUN_MISMATCH")
    require(metadata.get("workflow_run", {}).get("head_sha") == run["head_sha"], "ARTIFACT_COMMIT_MISMATCH")
    require(metadata.get("name") == f"operational-result-{run['id']}-{run['run_attempt']}", "ARTIFACT_ATTEMPT_MISMATCH")
    require(not metadata.get("expired"), "ARTIFACT_EXPIRED")
    require(len(raw) <= MAX_BYTES and metadata.get("digest") == "sha256:" + digest(raw), "ARTIFACT_DIGEST_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        require(len(members) == 1 and members[0].filename == "result.json", "ARTIFACT_MEMBERS_INVALID")
        info = members[0]
        require(info.file_size <= MAX_BYTES and not stat.S_ISLNK(info.external_attr >> 16), "ARTIFACT_UNSAFE_ENTRY")
        result = archive.read(info)
        require(len(result) <= MAX_BYTES, "ARTIFACT_RESULT_TOO_LARGE")
        return json.loads(result)


class GitHubActions:
    def __init__(self, session, token, *, publication_authorized=False):
        require(bool(token), "EXISTING_GITHUB_TOKEN_REQUIRED")
        self.session, self.token, self.authorized = session, token, publication_authorized
        self.api = f"https://api.github.com/repos/{REPOSITORY}"

    def _request(self, method, path, **kwargs):
        require(path.startswith("/") and ".." not in path, "GITHUB_PATH_INVALID")
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        try:
            response = self.session.request(method, self.api + path, headers=headers, timeout=45, **kwargs)
        except Exception as exc:
            raise OperationalError("GITHUB_TRANSPORT_UNKNOWN", retryable=True) from exc
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise OperationalError("GITHUB_TEMPORARY_FAILURE", retryable=True)
        require(response.status_code < 400, f"GITHUB_HTTP_{response.status_code}")
        return response

    def preflight(self, work):
        require(self.authorized, "PUBLICATION_SUSPENDED")
        current = self._request("GET", "/commits/main").json()
        require(re.fullmatch(r"[a-f0-9]{40}", str(current.get("sha", ""))), "MAIN_COMMIT_INVALID")
        self.verify_code_at(current["sha"], work)
        workflow = self._request("GET", "/actions/workflows/" + WORKFLOW.split("/")[-1]).json()
        require(workflow.get("path") == WORKFLOW and workflow.get("state") == "active", "WORKFLOW_UNAVAILABLE")
        return current["sha"]

    def verify_code_at(self, commit, work):
        files = work["definition"]["code"].get("files", {})
        require(set(files) == {WORKFLOW, "scripts/nexo_operational_package.py"}, "CODE_FILE_BINDINGS_REQUIRED")
        for path, expected_hash in files.items():
            content = self._request("GET", "/contents/" + path, params={"ref": commit}).json()
            require(content.get("type") == "file" and content.get("encoding") == "base64"
                    and int(content.get("size", 262145)) <= 262144, "REVIEWED_CODE_RESPONSE_INVALID")
            raw = base64.b64decode(content.get("content", ""))
            require(digest(raw) == expected_hash, "REVIEWED_CODE_CHANGED")

    def dispatch(self, work):
        try:
            current = self.preflight(work)
            require(current == work["outbox"]["execution_sha"], "MAIN_MOVED_BEFORE_DISPATCH")
        except Exception as exc:
            error = OperationalError(getattr(exc, "code", "DISPATCH_PREFLIGHT_FAILED"), retryable=True)
            error.dispatch_not_sent = True
            raise error from exc
        response = self._request("POST", "/actions/workflows/" + WORKFLOW.split("/")[-1] + "/dispatches",
                                 json={"ref": "main", "inputs": {
                                     "package_file_id": work["package"]["file_id"],
                                     "package_version": work["package"]["version"],
                                     "package_sha256": work["package"]["sha256"],
                                     "correlation": work["outbox"]["key"],
                                     "expected_commit": work["outbox"]["execution_sha"],
                                 }})
        require(response.status_code == 204, "DISPATCH_ACK_UNEXPECTED")

    def get_run(self, run_id):
        require(type(run_id) is int and run_id > 0, "RUN_ID_INVALID")
        return self._request("GET", f"/actions/runs/{run_id}").json()

    def find_runs(self, work):
        found = []
        for page in range(1, 11):
            data = self._request("GET", "/actions/workflows/" + WORKFLOW.split("/")[-1] + "/runs",
                                 params={"event": "workflow_dispatch", "branch": "main", "per_page": 100, "page": page}).json()
            rows = data.get("workflow_runs", [])
            found.extend(row for row in rows if row.get("display_title") == "nexo-op-" + work["outbox"]["key"])
            if len(rows) < 100:
                return found
        raise OperationalError("RUN_LOOKUP_INCOMPLETE", retryable=True)

    def result(self, run, work):
        verify_run(run, work)
        self.verify_code_at(run["head_sha"], work)
        name = f"operational-result-{run['id']}-{run['run_attempt']}"
        listing = self._request("GET", f"/actions/runs/{run['id']}/artifacts", params={"name": name, "per_page": 100}).json()
        items = listing.get("artifacts", [])
        require(listing.get("total_count") == 1 and len(items) == 1, "RESULT_ARTIFACT_NOT_UNIQUE")
        artifact = items[0]
        require(int(artifact.get("size_in_bytes", MAX_BYTES + 1)) <= MAX_BYTES, "ARTIFACT_TOO_LARGE")
        # Download redirects must not carry the API bearer to a storage host.
        response = self._request("GET", f"/actions/artifacts/{artifact['id']}/zip", allow_redirects=False)
        require(response.status_code == 302, "ARTIFACT_REDIRECT_REQUIRED")
        url = response.headers.get("Location", "")
        parsed = urlparse(url)
        require(parsed.scheme == "https" and parsed.hostname and
                (parsed.hostname.endswith(".githubusercontent.com") or parsed.hostname.endswith(".blob.core.windows.net")), "ARTIFACT_REDIRECT_HOST_INVALID")
        response = self.session.get(url, timeout=45, stream=True, allow_redirects=False)
        require(response.status_code == 200, "ARTIFACT_DOWNLOAD_FAILED")
        chunks, size = [], 0
        for part in response.iter_content(65536):
            size += len(part)
            require(size <= MAX_BYTES, "ARTIFACT_TOO_LARGE")
            chunks.append(part)
        return verified_result_archive(b"".join(chunks), artifact, run, work)
