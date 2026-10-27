#!/usr/bin/env bash
# Local experiment: normal viewer/peer with the validated longer-polling shim.
# Pass normal run.sh arguments, including --coding HEX when needed.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../../../.." && pwd)
bridge="$repo/build_fpk1/research-artifacts/stage3-spin/65536-4096"
if [[ ! -f "$bridge/libEGL.so" || ! -f "$bridge/libGLESv2.so" ]]; then
    python3 "$repo/tools/fpk1/research/hmi/build_spin_probe.py"
fi
exec bash "$repo/build-fpk1/run.sh" \
    --stage2-replace "lib/libEGL.so=$bridge/libEGL.so" \
    --stage2-replace "lib/libGLESv2.so=$bridge/libGLESv2.so" "$@"
