"""Check the HD package offline. Pass --refresh to rehash the same asset set."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--refresh", action="store_true")
opts = parser.parse_args()
root = Path(__file__).resolve().parents[3] / 'public/models/worlds-hd'
manifest = root / "manifest.json"
original = manifest.read_bytes()
data = json.loads(original)
records = data["frames"] + data["otherAssets"]
paths = {item["file"] for item in records}
actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p != manifest}
if actual != paths or len(paths) != len(records):
    raise SystemExit(f"Inventory differs: {sorted(actual ^ paths)}")
for item in records:
    path = root / item["file"]
    item["bytes"] = path.stat().st_size
    item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix == ".webp":
        with Image.open(path) as image:
            image.load()
            item["size"] = list(image.size)
encoded = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
if encoded != original:
    if not opts.refresh:
        raise SystemExit("Manifest differs from local assets")
    with tempfile.NamedTemporaryFile(dir=root.parent, delete=False) as out:
        out.write(encoded)
        out.flush()
        os.fsync(out.fileno())
    os.replace(out.name, manifest)
print(f"{len(records)} assets verified. SHA-256 {hashlib.sha256(encoded).hexdigest()}")
