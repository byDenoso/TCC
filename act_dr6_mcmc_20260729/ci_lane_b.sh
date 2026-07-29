#!/usr/bin/env bash
set -euo pipefail

: "${MODEL:?MODEL is required}"
: "${LANEA_RUN_ID:?LANEA_RUN_ID is required}"
: "${COBAYA_PACKAGES_PATH:?COBAYA_PACKAGES_PATH is required}"
: "${ACT_COMMIT:?ACT_COMMIT is required}"

ROOT="$GITHUB_WORKSPACE/lane_b_${MODEL}"

install_common() {
  sudo apt-get update
  sudo apt-get install -y libgsl-dev openmpi-bin libopenmpi-dev
  python -m pip install --upgrade pip wheel setuptools
  python -m pip install 'numpy<2.4' 'scipy<1.18' pandas pyyaml getdist mpi4py arviz \
    'cobaya==3.6.2' 'sacc>=0.12.0'
}

download_source() {
  rm -rf common lane_a_download
  gh run download "$LANEA_RUN_ID" --repo "$GITHUB_REPOSITORY" \
    --name act-dr6-common-runtime-20260729 --dir common
  gh run download "$LANEA_RUN_ID" --repo "$GITHUB_REPOSITORY" \
    --name "act-dr6-lanea-final-${MODEL}-20260729" --dir lane_a_download
}

activate_runtime() {
  (cd common/payload && sha256sum -c official-likelihood-packages-v3.tar.gz.sha256)
  tar -xzf common/payload/official-likelihood-packages-v3.tar.gz -C "$GITHUB_WORKSPACE"
  rm -rf "$COBAYA_PACKAGES_PATH/code/CAMB"
  local wheel db dev camblib
  wheel=$(find common/validated -type f -name 'camb-*.whl' | head -1)
  db=$(find common/validated -type d -name Rec_database | head -1)
  dev=$(find common/validated -type d -name Development | head -1)
  test -n "$wheel"; test -n "$db"; test -n "$dev"
  python -m pip install --force-reinstall --no-deps "$wheel"
  rm -rf "$GITHUB_WORKSPACE/Rec_database" "$GITHUB_WORKSPACE/Development"
  ln -s "$(realpath "$db")" "$GITHUB_WORKSPACE/Rec_database"
  ln -s "$(realpath "$dev")" "$GITHUB_WORKSPACE/Development"
  mkdir -p "$GITHUB_WORKSPACE/temp"
  camblib=$(python - <<'PY'
from pathlib import Path
import camb
print(sorted(Path(camb.__file__).resolve().parent.glob('camblib*.so'))[0])
PY
)
  ldd "$camblib" | tee camb_ldd.txt
  ! grep -q 'not found' camb_ldd.txt
}

install_likelihoods() {
  rm -rf act-lite
  git clone https://github.com/ACTCollaboration/DR6-ACT-lite.git act-lite
  (cd act-lite && git checkout "$ACT_COMMIT" && python -m pip install -e .)
  cobaya-install planck_2018_highl_plik.TTTEEE_lite_native \
    --packages-path "$COBAYA_PACKAGES_PATH" --no-progress-bars
  rm -rf "$COBAYA_PACKAGES_PATH/code/CAMB"
}

prepare_minimize() {
  local lanea best cov
  lanea=$(find lane_a_download -type d -name "campaign_${MODEL}" | head -1)
  test -n "$lanea"
  best="$lanea/best_minimum.json"
  test -f "$best"
  cov=$(find "$lanea/mcmc" -type f -name '*.covmat' | head -1 || true)
  rm -rf "$ROOT"
  local args=()
  if [[ -n "$cov" ]]; then args+=(--lane-a-covmat "$cov"); fi
  python act_dr6_mcmc_20260729/lane_b_campaign.py write-configs \
    --model "$MODEL" --packages "$COBAYA_PACKAGES_PATH" --root "$ROOT" \
    --lane-a-best "$best" "${args[@]}"
  python - "$ROOT/configs/mcmc.yaml" <<'PY'
import sys, yaml
path = sys.argv[1]
info = yaml.safe_load(open(path, encoding='utf-8'))
info['resume'] = False
yaml.safe_dump(info, open(path, 'w', encoding='utf-8'), sort_keys=False)
PY
  find "$COBAYA_PACKAGES_PATH/data/planck_2018" -type f -print0 | sort -z | xargs -0 sha256sum \
    > "$ROOT/lane_b_planck_highl_sha256.txt"
}

run_minima() {
  run_one() {
    local i="$1" work code
    mkdir -p "$ROOT/logs"
    work="$ROOT/work/start_${i}"
    mkdir -p "$work/temp"
    ln -sfn "$GITHUB_WORKSPACE/Rec_database" "$work/Rec_database"
    ln -sfn "$GITHUB_WORKSPACE/Development" "$work/Development"
    set +e
    (cd "$work" && cobaya-run "$ROOT/configs/minimize_${i}.yaml") \
      >"$ROOT/logs/minimize_${i}.stdout.log" 2>"$ROOT/logs/minimize_${i}.stderr.log"
    code=$?
    set -e
    printf '%s\n' "$code" > "$ROOT/logs/minimize_${i}.exit_code"
  }
  export -f run_one
  export ROOT GITHUB_WORKSPACE
  seq 1 8 | xargs -n1 -P2 bash -c 'run_one "$@"' _
  local nmin
  nmin=$(find "$ROOT/minimize" -name 'chain.minimum.txt' | wc -l)
  printf 'valid_minima=%s\n' "$nmin" | tee "$ROOT/valid_minima.txt"
  test "$nmin" -ge 4
}

restore_minima() {
  local src
  src=$(find lane_b_download -type d -name "lane_b_${MODEL}" | head -1)
  test -n "$src"
  rm -rf "$ROOT"
  cp -r "$src" "$ROOT"
  python act_dr6_mcmc_20260729/lane_b_campaign.py promote-best --model "$MODEL" --root "$ROOT"
}

diagnose() {
  python act_dr6_mcmc_20260729/convergence_gate.py --root "$ROOT" --burn 0.30 || true
}

is_done() {
  python - "$ROOT/convergence_gate.json" <<'PY'
import json, sys
try:
    ok = bool(json.load(open(sys.argv[1], encoding='utf-8'))['converged'])
except Exception:
    ok = False
raise SystemExit(0 if ok else 1)
PY
}

run_mcmc() {
  export ROOT GITHUB_WORKSPACE
  mkdir -p "$ROOT/logs"
  diagnose
  for segment in 1 2; do
    if is_done; then break; fi
    export SEGMENT="$segment"
    export RESUME=""
    [[ -f "$ROOT/mcmc/chain.checkpoint" ]] && export RESUME="-r"
    mkdir -p "$ROOT/mpi_work_${segment}"
    set +e
    timeout --signal=TERM 140m mpirun --oversubscribe -np 4 bash -lc '
      rank=${OMPI_COMM_WORLD_RANK:-0}
      work="$ROOT/mpi_work_${SEGMENT}/rank_${rank}"
      mkdir -p "$work/temp"
      ln -sfn "$GITHUB_WORKSPACE/Rec_database" "$work/Rec_database"
      ln -sfn "$GITHUB_WORKSPACE/Development" "$work/Development"
      cd "$work"
      cobaya-run $RESUME "$ROOT/configs/mcmc.yaml"
    ' >"$ROOT/logs/mcmc_${segment}.stdout.log" 2>"$ROOT/logs/mcmc_${segment}.stderr.log"
    code=$?
    set -e
    printf '%s\n' "$code" > "$ROOT/logs/mcmc_${segment}.exit_code"
    diagnose
  done
  python act_dr6_mcmc_20260729/analyze_chains.py --model "$MODEL" --root "$ROOT" --burn 0.30 || true
}

case "${1:-}" in
  install) install_common ;;
  prepare-minimize) download_source; activate_runtime; install_likelihoods; prepare_minimize ;;
  run-minima) run_minima ;;
  prepare-mcmc) download_source; activate_runtime; install_likelihoods; restore_minima ;;
  run-mcmc) run_mcmc ;;
  *) echo "usage: $0 {install|prepare-minimize|run-minima|prepare-mcmc|run-mcmc}" >&2; exit 2 ;;
esac
