"""Optional offline neural encoders. No auto-download and no remote model code."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
from .memory import SourceError, canonical


def verify_model(folder: str | Path, manifest: str | Path) -> tuple[Path, str]:
    root = Path(folder).resolve(strict=True)
    spec = json.loads(Path(manifest).read_text(encoding="utf-8"))
    if spec.get("format") != "NEXO_LOCAL_MODEL_V1" or not isinstance(spec.get("files"), dict) or not spec["files"]:
        raise SourceError("A complete pinned local model manifest is required")
    observed = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise SourceError("Symlinks are not allowed inside the pinned model")
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
    if observed != set(spec["files"]):
        raise SourceError("Model manifest must cover exactly every file")
    for name, expected in spec["files"].items():
        path = (root / name).resolve()
        if root not in path.parents or len(expected) != 64:
            raise SourceError("Invalid model manifest entry")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SourceError("Pinned model hash mismatch")
    if any(name.endswith((".bin", ".pt", ".pkl", ".pickle")) for name in observed):
        raise SourceError("Use safetensors weights, not executable pickle weights")
    return root, hashlib.sha256(canonical(spec)).hexdigest()


class LocalEmbedding:
    def __init__(self, folder, manifest):
        root, self.fingerprint = verify_model(folder, manifest)
        if importlib.util.find_spec("sentence_transformers") is None:
            raise SourceError("sentence_transformers is not installed; no download attempted")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(str(root), local_files_only=True, trust_remote_code=False, device="cpu")

    def encode(self, texts):
        return self.model.encode(texts, batch_size=16, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False)


class LocalReranker:
    def __init__(self, folder, manifest):
        root, self.fingerprint = verify_model(folder, manifest)
        if importlib.util.find_spec("sentence_transformers") is None:
            raise SourceError("sentence_transformers is not installed; no download attempted")
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(str(root), local_files_only=True, trust_remote_code=False, device="cpu")

    def score(self, pairs):
        return self.model.predict(pairs, batch_size=8, show_progress_bar=False).tolist()
