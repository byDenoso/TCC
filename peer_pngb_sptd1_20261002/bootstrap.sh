#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
WORK=${PEER_RUNTIME_ROOT:-"$ROOT/runtime"}
CLASS_REF=e85808324f51fc694d12e3ed7439552a3c3f9540
SPT_REF=f22611a9671d50af6135f048a2ea3f43ef4c2f62
PATCH_SHA=6d3233cefda14f7cb74526952ece9efe6d035c42ae0adc6650c0b1f177168194
mkdir -p "$WORK" "$ROOT/validation"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export XDG_CONFIG_HOME="$WORK/config" XDG_CACHE_HOME="$WORK/cache" MPLCONFIGDIR="$WORK/matplotlib"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export CC=gcc CXX=g++
export COBAYA_PACKAGES_PATH="${COBAYA_PACKAGES_PATH:-$WORK/packages}"

python -m venv "$WORK/venv"
PY="$WORK/venv/bin/python"
"$PY" -m pip install 'setuptools==84.0.0' wheel 'Cython==3.1.4' \
  'numpy==2.3.5' 'scipy==1.17.0' 'pandas==2.2.3' 'pyyaml==6.0.3' \
  'cobaya==3.6.2' 'candl-like==2.0.3' 'arviz==0.23.4'

git clone --filter=blob:none --no-checkout https://github.com/lesgourg/class_public.git "$WORK/class"
git -C "$WORK/class" fetch --depth 1 origin "$CLASS_REF"
git -C "$WORK/class" checkout --detach "$CLASS_REF"
test "$(git -C "$WORK/class" rev-parse HEAD)" = "$CLASS_REF"
echo "$PATCH_SHA  $ROOT/pure_pngb_from_upstream.patch" | sha256sum -c -
patch --batch --forward -p1 -d "$WORK/class" < "$ROOT/pure_pngb_from_upstream.patch"
make -C "$WORK/class" -j1 class libclass.a
"$PY" -m pip install --use-pep517 --no-build-isolation --no-deps -e "$WORK/class"

git clone --filter=blob:none --no-checkout https://github.com/SouthPoleTelescope/spt_candl_data.git "$WORK/spt"
git -C "$WORK/spt" fetch --depth 1 origin "$SPT_REF"
git -C "$WORK/spt" checkout --detach "$SPT_REF"
test "$(git -C "$WORK/spt" rev-parse HEAD)" = "$SPT_REF"
# KK is officially disabled. Its emulator dependencies are not installed or used.
"$PY" -m pip install --no-deps "$WORK/spt"
"$WORK/venv/bin/cobaya-install" planck_2018_lowl.TT planck_2018_lowl.EE_sroll2 \
  planck_2018_lensing.native bao.desi_dr2.desi_bao_all \
  --packages-path "$COBAYA_PACKAGES_PATH" --no-progress-bars

export PEER_ROOT="$ROOT" PEER_CLASS_REF="$CLASS_REF" PEER_SPT_REF="$SPT_REF"
"$PY" - <<'PY'
from pathlib import Path
import hashlib, importlib, importlib.metadata, json, os, platform, subprocess
import classy, spt_candl_data
root=Path(os.environ['PEER_ROOT'])
binary=Path(importlib.import_module(classy.Class.__module__).__file__).resolve()
record={'class_ref':os.environ['PEER_CLASS_REF'],'spt_ref':os.environ['PEER_SPT_REF'],
 'classy_extension':str(binary),'classy_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
 'classy_version':classy.__version__,'spt_version':spt_candl_data.__version__,
 'python':platform.python_version(),'platform':platform.platform(),
 'packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','pandas','cobaya','candl-like','Cython','arviz']}}
assert record['classy_version']=='v3.3.4'
assert record['spt_version']=='3.0.1'
(root/'validation/runtime_identity.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
PY
"$PY" -m pip freeze > "$ROOT/validation/pip_freeze.txt"
find "$COBAYA_PACKAGES_PATH" -type f -print0 | sort -z | xargs -0 sha256sum > "$ROOT/validation/likelihood_payload_sha256.txt"
find "$WORK/spt/spt_candl_data/SPT3G_D1_TnE_v0" -type f -print0 | sort -z | xargs -0 sha256sum > "$ROOT/validation/spt_tne_payload_sha256.txt"
printf 'PEER_RUNTIME_ROOT=%s\nCOBAYA_PACKAGES_PATH=%s\n' "$WORK" "$COBAYA_PACKAGES_PATH"
