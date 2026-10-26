#!/usr/bin/env bash
# Build the scratch inputs for FPK1 GLES-bridge experiments into one directory:
#   venv/          Python with lzokay (Stage2 LZO decoding)
#   emmc.img       synthetic eMMC from the update archive
#   gl/            guest shim libEGL.so/libGLESv2.so (1440x540) and host glhost
#   grate/         grate checkout and tegra_shader_disasm (optional, needs network)
# Usage: tools/fpk1/prepare_gl_env.sh <firmware.zip> <output-dir> [--with-grate]
set -euo pipefail
archive=$(realpath "$1")
out=$(realpath -m "$2")
repo=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$out/gl"
chmod 700 "$out"

if [[ ! -x "$out/venv/bin/python" ]]; then
    python3 -m venv --system-site-packages "$out/venv"
    "$out/venv/bin/pip" -q install lzokay
fi

if [[ ! -f "$out/emmc.img" ]]; then
    "$out/venv/bin/python" "$repo/tools/fpk1/create_fpk1_emmc.py" "$archive" "$out/emmc.img" > "$out/emmc.json"
fi

arm-none-eabi-gcc -mfloat-abi=soft -mcpu=cortex-a9 -marm -fPIC -ffreestanding -fno-builtin -O2 \
    -DGLBRIDGE_DEFAULT_W=1440 -DGLBRIDGE_DEFAULT_H=540 \
    -c "$repo/tools/mhi2/glforward/guest/gl_shim.c" -o "$out/gl/gl-shim.o"
for name in libGLESv2.so libEGL.so; do
    arm-none-eabi-ld -shared --hash-style=sysv -soname "$name" -o "$out/gl/$name" "$out/gl/gl-shim.o"
done
bash "$repo/tools/mhi2/glforward/build_host.sh" "$out/gl/glhost"

if [[ "${3:-}" == --with-grate ]]; then
    if [[ ! -d "$out/grate" ]]; then
        git clone -q --depth 1 https://github.com/grate-driver/grate.git "$out/grate"
    fi
    cc -w -I"$out/grate/include" -I"$out/grate/src/libcgc" -o "$out/tegra_shader_disasm" \
        "$repo/tools/fpk1/tegra_shader_disasm.c" "$out/grate/src/libcgc/stream.c" \
        "$out/grate/src/libcgc/instruction.c" "$out/grate/src/libcgc/dummy.c"
fi
echo "prepared $out"
