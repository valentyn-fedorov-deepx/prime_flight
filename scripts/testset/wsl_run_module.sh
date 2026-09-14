#!/usr/bin/env bash
# Run scripts/run_module.py inside WSL (Ubuntu-24.04) with a Linux venv, for production modules that cannot run in
# the Windows Python.
#
# Why: external/hair-policy/main.py is obfuscated by Pyarmor 8.3.7 (trial) with a Linux x86-64 runtime
# (pyarmor_runtime_000000/pyarmor_runtime.so). Its bytecode header is CPython 3.8 (magic 3413) and the runtime loads
# only on CPython 3.8 (3.9 and 3.10 fail with "undefined symbol: _Py_hashtable_get_entry"). The branches python_3_10
# and python3_10 carry the same obfuscated main.py and runtime (they change only the Dockerfile, the mediapipe pin and
# the submodule pins). The newest official PyTorch for cp38 is 2.4.1, which has no sm_120 (RTX 50xx) kernels, so the
# 3.8 venv has the CPU build of torch: pass --device cpu.
#
# Usage from Windows (all arguments go to run_module.py; relative paths resolve against the repo root, as on Windows):
#   wsl -d Ubuntu-24.04 -- bash /mnt/g/prime_flight/scripts/testset/wsl_run_module.sh \
#       --module hair-policy --video zHxIAF2vUGxJ.mp4 --videos-dir out/testset/videos \
#       --inferences-dir out/testset/prod/zHxIAF2vUGxJ.mp4 --device cpu --cone-camera true \
#       --out out/testset/modules/envtest/zHxIAF2vUGxJ.mp4/hair-policy.json
#   Add --module-dir external/_branches/<export> to run another checkout of the module.
#
# Venv: ~/pf_envs/hair-policy-py<XY>, where XY is the CPython version of the module's Pyarmor build, read from the
# header of <module dir>/main.py (b'PY000000\x00\x03\x08...' = 3.8, b'PY000000\x00\x03\n...' = 3.10); 38 when that
# file has no Pyarmor header. The exact package list of a venv is in its pf-freeze.txt.
#
# Windows absolute paths (G:\prime_flight\out\... or G:/prime_flight/out/..., also as --name=value) are converted to
# /mnt/g/prime_flight/out/... . How arguments reach this script depends on the caller:
#   * `wsl ... -- bash ...` hands the command line to the Linux login shell: unquoted backslashes are dropped
#     (G:\prime_flight\out -> G:prime_flightout) and $VARS are expanded. Such mangled paths are rejected below.
#     Programmatic callers (subprocess with an argument list) should use `wsl -d Ubuntu-24.04 --exec bash ...`,
#     which passes every argument verbatim.
#   * Git Bash rewrites /mnt/g/... into C:/Program Files/Git/mnt/g/... : prefix the call with MSYS_NO_PATHCONV=1.
#
# Linux-side environment (from Windows: `wsl -d Ubuntu-24.04 -- env PF_THREADS=4 bash .../wsl_run_module.sh ...`):
#   PF_THREADS=<n>     CPU threads for torch/OpenMP, MKL, OpenBLAS, OpenCV and its FFmpeg decoder (default 2)
#   PF_WSL_VENV=<dir>  venv to use instead of the one matching the Pyarmor build
#   PF_WSL_DRY_RUN=1   print the resolved command instead of running it
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # /mnt/g/prime_flight
THREADS="${PF_THREADS:-2}"
if [[ ! $THREADS =~ ^[1-9][0-9]*$ ]]; then
  echo "wsl_run_module.sh: PF_THREADS must be a positive integer, got '$THREADS'" >&2
  exit 2
fi

win_re='^([A-Za-z]):[\/](.*)$'   # G:\x or G:/x
mangled_re='^[A-Za-z]:[^\/]'     # G:x - a Windows path whose backslashes a shell has already removed
kv_re='^(--[A-Za-z0-9_-]+=)(.*)$'

to_linux() {
  local p="$1"
  if [[ $p =~ $win_re ]]; then
    local drive="${BASH_REMATCH[1],,}" rest
    rest="$(printf '%s' "${BASH_REMATCH[2]}" | tr '\\' '/')"
    printf '/mnt/%s/%s' "$drive" "$rest"
  elif [[ $p =~ $mangled_re ]]; then
    echo "wsl_run_module.sh: '$p' looks like a Windows path whose backslashes were stripped by the shell;" \
      "pass forward slashes or call 'wsl -d Ubuntu-24.04 --exec bash ...'" >&2
    return 2
  else
    printf '%s' "$p"
  fi
}

# CPython version ("3.8", "3.10", ...) of a Pyarmor 8 script, from the version bytes of its header; empty otherwise.
pyarmor_python() {
  local hdr
  hdr="$(head -c 512 "$1" 2>/dev/null | grep -a -o -m1 'PY[0-9]\{6\}\\x00\\x03\\\(x0[0-9a-f]\|[tnr]\)' || true)"
  case "$hdr" in
    *'\x03\x08') echo 3.8 ;;
    *'\x03\t') echo 3.9 ;;
    *'\x03\n') echo 3.10 ;;
    *'\x03\x0b') echo 3.11 ;;
    *'\x03\x0c') echo 3.12 ;;
    *'\x03\r') echo 3.13 ;;
  esac
}

args=()
for a in "$@"; do
  if [[ $a =~ $kv_re ]]; then
    key="${BASH_REMATCH[1]}"
    v="$(to_linux "${BASH_REMATCH[2]}")" || exit 2
    args+=("$key$v")
  else
    v="$(to_linux "$a")" || exit 2
    args+=("$v")
  fi
done

# Module folder as run_module.py resolves it (--module-dir, else external/<module>) and the venv for its Pyarmor build.
module="" moddir="" prev=""
for a in "${args[@]}"; do
  case "$prev" in
    --module) module="$a" ;;
    --module-dir) moddir="$a" ;;
  esac
  case "$a" in
    --module=*) module="${a#--module=}" ;;
    --module-dir=*) moddir="${a#--module-dir=}" ;;
  esac
  prev="$a"
done
[[ -n $moddir ]] || moddir="external/$module"
[[ $moddir == /* ]] || moddir="$ROOT/$moddir"
PYARMOR_PY=""
if [[ -f $moddir/main.py ]]; then
  PYARMOR_PY="$(pyarmor_python "$moddir/main.py")"
fi
pyver="${PYARMOR_PY:-3.8}"
VENV="${PF_WSL_VENV:-$HOME/pf_envs/hair-policy-py${pyver/./}}"
PY="$VENV/bin/python"

cd "$ROOT"
export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1   # as scripts/testset/profiles.py ENV (no-op on torch < 2.6)
export PYTHONDONTWRITEBYTECODE=1            # do not drop cpython-38 __pycache__ folders into the Windows tree
export PYTHONUNBUFFERED=1                   # progress reaches the caller's log as it happens
export MPLBACKEND=Agg                       # WSLg sets DISPLAY; the production containers are headless

# The machine is shared with the rest of the test-set run (GM, trackers, other modules): small CPU footprint by default.
export OMP_NUM_THREADS="$THREADS"           # torch intra-op pool and other OpenMP code
export MKL_NUM_THREADS="$THREADS"
export OPENBLAS_NUM_THREADS="$THREADS"      # numpy / scipy wheels
export OPENCV_FOR_THREADS_NUM="$THREADS"    # cv2 parallel_for_ (cv2.getNumThreads())
export OPENCV_FFMPEG_THREADS="$THREADS"     # decoder threads of cv2.VideoCapture (FFmpeg back-end)

if [[ "${PF_WSL_DRY_RUN:-0}" == 1 ]]; then
  printf 'cwd: %s\nmodule dir: %s (Pyarmor build: %s)\nvenv: %s (%s)\nthreads: %s\ncmd:' "$PWD" "$moddir" \
    "${PYARMOR_PY:-none}" "$VENV" "$([[ -x $PY ]] && echo ok || echo missing)" "$THREADS"
  printf ' %q' "$PY" scripts/run_module.py "${args[@]}"
  echo
  exit 0
fi
if [[ ! -x $PY ]]; then
  echo "wsl_run_module.sh: venv python not found: $PY (Pyarmor build of $moddir: ${PYARMOR_PY:-none});" \
    "build that venv or set PF_WSL_VENV" >&2
  exit 2
fi
exec "$PY" scripts/run_module.py "${args[@]}"
