# MLB Evo emulator: MHI2 head unit and FPK1 instrument cluster

Boot supported **Audi, Volkswagen and Porsche MHI2 firmware** and the
experimental **Audi FPK1 instrument cluster** on a Mac or Linux host, with the
original QNX user interface and emulated vehicle/companion services.
This is an experimental QEMU fork. It does not require a head unit,
Raspberry Pi Pico, QNX SDK or a separate Pico repository.

Repository: <https://github.com/mlb-evo/qemu>. This work is based on
[iscle/qemu-mhi2](https://github.com/iscle/qemu-mhi2), which provides the MHI2
machine, the host/guest bridges and the bootstrap release used below; the
FPK1 cluster workflow is added on top of it.

## Supported firmware

Supply your own supported firmware update archive; the repository does not
include firmware updates or navigation maps.

For the experimental Audi FPK1 instrument cluster, follow the
[FPK1 build steps below](#audi-fpk1-instrument-cluster-q7-0378-local-research).

The supported profiles are specific firmware trains, not every update for a
brand:

| Profile | Firmware train | MU | Controls |
| --- | --- | --- | --- |
| `audi-a3` | `MHI2_ER_AU37x_P5089` | 1326 | MMI rotary controller, context keys; no touchscreen |
| `vw` | `MHI2_ER_VWG11_K3342` | 1427 | Touchscreen and VW side keys/knobs |
| `porsche` | `MHI2_ER_POG11_K5126` | 1394 | Touchscreen and Porsche PCM fascia |

Use variant-70 update assets for these profiles. The builder checks the
archive's `[common]` release against the selected profile and rejects a
mismatch. Porsche P5250, POG24 K4196 and other trains are **not** substitutes
for the K5126 command below.

Apple Silicon macOS has been tested locally. Intel Macs have a toolchain
selection path but have not been validated here. Allow at least 25 GB of free
space per build, plus room for your archives; large firmware packages need
more. Keep the checkout and build directories after building: the generated
launcher uses both.

## 1. Set up

### 1.1 macOS
Install Apple's command-line tools if needed, and complete the installer:

```sh
xcode-select --install
```

Install [Homebrew](https://brew.sh/) if it is not already available, then run:

```sh
brew install git pkgconf ninja python glib pixman mesa lzo libusb libslirp sevenzip zstd \
  ffmpeg sox gnu-tar arm-none-eabi-gcc pyside

export MHI2_REPRO="$HOME/mhi2-repro"
mkdir -p "$MHI2_REPRO"
curl -fL https://github.com/mlb-evo/qemu/archive/refs/heads/main.zip \
  -o "$MHI2_REPRO/qemu.zip"
unzip -q "$MHI2_REPRO/qemu.zip" -d "$MHI2_REPRO"
mv "$MHI2_REPRO/qemu-main" "$MHI2_REPRO/qemu"
cd "$MHI2_REPRO/qemu"
"$(brew --prefix python)/bin/python3" -m venv .venv
. .venv/bin/activate
python -m pip install -r tools/mhi2/requirements-audi.txt
```

Despite its historical name, `requirements-audi.txt` supplies the Python
requirements for all three profiles. Use Python 3.11 or newer. **Code → Download
ZIP**, the ZIP command above, and Git clones (including shallow clones) are all
supported. If you prefer Git, replace the download/unzip/move commands with:

```sh
git clone --depth 1 --branch main https://github.com/mlb-evo/qemu.git "$MHI2_REPRO/qemu"
```

The ZIP contains source, so it still needs to be compiled. Git is used only to
fetch pinned third-party build dependencies; your QEMU directory needs no
`.git` metadata or history. First-time setup needs internet access to GitHub,
GitLab and Python packages.

### 1.2 Ubuntu

```bash
sudo apt install libavcodec-dev libavutil-dev libswscale-dev gcc-arm-none-eabi libpng-dev ninja-build python3-venv python3-capstone libpixman-1-dev python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
```

## 2. Download the emulator bootstrap

The update archive is not a complete flash image. All three workflows also
need the captured boot handoff and formatted disk template from the
[bootstrap release](https://github.com/iscle/qemu-mhi2/releases/tag/mhi2-bootstrap-v1)
published by the upstream iscle/qemu-mhi2 project:

```sh
mkdir -p "$MHI2_REPRO/bootstrap"
cd "$MHI2_REPRO/bootstrap"
release="https://github.com/iscle/qemu-mhi2/releases/download/mhi2-bootstrap-v1"
curl -fLO "$release/mhi2-bootstrap-v1.tar.zst"
curl -fLO "$release/SHA256SUMS"
shasum -a 256 -c SHA256SUMS
gtar --zstd -xf mhi2-bootstrap-v1.tar.zst
cd "$MHI2_REPRO/qemu"
```

GNU tar preserves the sparse disk. The extracted directory
`$MHI2_REPRO/bootstrap/bootstrap-v1` must contain `bootstrap.json`, `nor.bin`,
`iram.bin` and `emmc-template.raw`. The builder checks their hashes. The app
partition in the template is empty; the selected firmware supplies the app,
Quickboot, kernel and system files. This bootstrap is for emulation only.

## 3. Build and boot your firmware

Run the following from `$MHI2_REPRO/qemu` with `.venv` activated and the ARM
compiler on `PATH`. Replace the archive path with your actual file. Each build
creates its own QEMU executable, host/guest bridges, prepared NOR/eMMC images
and `run.sh`. **The output directory must not already exist.**

### Audi A3

```sh
python tools/mhi2/build_firmware.py --firmware audi-a3 \
  --archive "/path/to/MHI2_ER_AU37x_P5089_MU1326 (A3).7z" \
  --bootstrap "$MHI2_REPRO/bootstrap/bootstrap-v1" \
  --output "$MHI2_REPRO/audi-build" --jobs 6
bash "$MHI2_REPRO/audi-build/run.sh"
```

Use the displayed MMI buttons and controller. Arrow keys turn the selection
knob, Enter selects, Esc goes back and M opens Menu. Click or scroll over the
knobs. Screen clicks do not send touches for Audi. Its launcher selects the
required 12 MHz oscillator automatically.

### Volkswagen

```sh
python tools/mhi2/build_firmware.py --firmware vw \
  --archive "/path/to/your-MHI2_ER_VWG11_K3342-update.7z" \
  --bootstrap "$MHI2_REPRO/bootstrap/bootstrap-v1" \
  --output "$MHI2_REPRO/vw-build" --jobs 6
bash "$MHI2_REPRO/vw-build/run.sh"
```

Click the touchscreen or use the VW side buttons. Scroll over the volume and
selection knobs to turn them. The profile retains VW's touchscreen wiring and
clock configuration.

### Porsche PCM

```sh
python tools/mhi2/build_firmware.py --firmware porsche \
  --archive "/path/to/MHI2_ER_POG11_K5126_MU1394_9P1906961H.7z" \
  --bootstrap "$MHI2_REPRO/bootstrap/bootstrap-v1" \
  --output "$MHI2_REPRO/porsche-build" --jobs 6
bash "$MHI2_REPRO/porsche-build/run.sh"
```

Use the touchscreen and Porsche TUNER, MEDIA, NAV, CAR and HOME controls. The
cluster window uses the smaller Porsche viewport. A cluster window being
available does not guarantee map/video output: it requires the corresponding
native service and data. This boot guide does not install an Android Auto mod
or enable a physical car's cluster.

### Audi FPK1 instrument cluster (Q7 0378, local research)

Use the original `AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip`
update archive. This workflow builds its synthetic media directly from that
archive; skip the MHI2 bootstrap download in section 2. Keep the archive,
checkout and output directory at their original paths after building.

**1. Prepare the dependencies.** On macOS, complete section 1.1 above.
Use the Homebrew Python directly so the generated environment can see the
Homebrew PySide6 installation:

```sh
export MHI2_REPRO="$HOME/mhi2-repro"
cd "$MHI2_REPRO/qemu"
FPK1_PYTHON="$(brew --prefix python)/bin/python3"
"$FPK1_PYTHON" -c 'from PySide6 import QtCore, QtGui, QtWidgets; print(QtCore.__version__)'
pkg-config --exists egl glesv2 libavcodec libavutil libswscale
arm-none-eabi-gcc --version
```

On Ubuntu, install the build and viewer dependencies, then select the system
Python (3.11 or newer):

```sh
sudo apt update
sudo apt install build-essential git pkg-config ninja-build python3 python3-venv \
  libglib2.0-dev libpixman-1-dev zlib1g-dev libegl1-mesa-dev libgles2-mesa-dev \
  libavcodec-dev libavutil-dev libswscale-dev liblzo2-dev gcc-arm-none-eabi \
  python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
export MHI2_REPRO="$HOME/mhi2-repro"
cd "$MHI2_REPRO/qemu"  # use the checkout prepared in section 1
FPK1_PYTHON=/usr/bin/python3
"$FPK1_PYTHON" -c 'from PySide6 import QtCore, QtGui, QtWidgets; print(QtCore.__version__)'
```

**2. Build QEMU, the GLES bridge and media.** Replace the archive path with
your file. The output directory must not already exist:

```sh
"$FPK1_PYTHON" tools/fpk1/build_fpk1.py \
  --archive "/path/to/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip" \
  --output "$MHI2_REPRO/fpk1-build" --jobs 6
```

The builder creates `qemu/qemu-system-arm`, the host/guest GLES `bridge/`,
synthetic `media/emmc.img`, a Python `venv/` with `lzokay`, a translated shader
cache under `research-artifacts/`, `build-manifest.json` and `run.sh`.
It installs `lzokay` automatically. To reuse a QEMU executable already built
from this checkout, add `--qemu /path/to/qemu-system-arm` to the build command.

**3. Prepare the FPK1 shaders.** The build command above already extracts
the firmware's KZB shader binaries and translates their Tegra programs into
GLSL for the host GLES bridge. It runs
`tools/fpk1/research/shader-translate/build_cache.py` automatically.

The build directory contains:

- `research-artifacts/shader-audit/manifest.json` and `shader-audit/binaries/`:
  the inventory and extracted shader programs.
- `research-artifacts/shader-translate/cache/`: translated `.glsl` files and
  `.blend` metadata consumed by `glhost`.
- `research-artifacts/shader-translate/report.json`: translation results and
  unsupported-program diagnostics.

To regenerate the cache after updating the translator, run from the checkout:

```sh
"$MHI2_REPRO/fpk1-build/venv/bin/python" \
  tools/fpk1/research/shader-translate/build_cache.py \
  --archive "/path/to/AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip" \
  --build-dir "$MHI2_REPRO/fpk1-build"
```

Check the final `translated N/N` message; unsupported programs make this
command fail and are listed in the report. The generated `run.sh` sets
`MHI2_SHADER_CACHE` to this build's cache automatically. Shader binaries,
generated GLSL and reports stay under the build directory; the research
scripts stay in the checkout.

**4. Launch the cluster:**

```sh
bash "$MHI2_REPRO/fpk1-build/run.sh"
```

Use the same command for subsequent launches. The launcher prints the
firmware, coding, time limit and log directory it uses, opens the frame viewer
and KSS peer, prints the guest console in the Terminal, and saves logs and
frames under `fpk1-build/runs/<time>/`. Close the viewer to stop the KSS link;
press Ctrl-C in the Terminal to stop the emulator.

Common options (`run.sh --help` lists them):

| Option | Default | Meaning |
| --- | --- | --- |
| `--coding HEX` | `008500E07C98000801A369602000600000000000` (Q7 0378 panel) | Long coding sent to ConfigM; `--coding ''` sends none |
| `--seconds N` | `1800` | Stop the emulator after N seconds, e.g. `--seconds 60` for a bounded run |

Any other option is passed to `tools/fpk1/run_stage1_console.py`.

`--coding` accepts 20 bytes as 40 hexadecimal digits. The peer extracts the bit
fields into seven ConfigM RTE signals, sends them to `gss_ipc` before
application run, and repeats them with alive traffic. No coding UI is needed;
the transmitted IDs and values are recorded in `kss.log`.

FPK1 remains a local research workflow. Internal coding, vehicle type and
drivetrain require separate KSS data, and a fully configured cluster HMI
startup has not been confirmed. The 50-second coding smoke run reached
application run, then reported `diagnosis`/`swdlclient` startup watchdog errors
and a `gtf2` fallback. See the [FPK1 guide](docs/fpk1-diagnostic-machine.md)
and [firmware research](docs/fpk1-firmware-research.md) for details.

### Subsequent launches and shutdown (MHI2)

Close the viewer or press Ctrl-C in its Terminal to stop the session and its
helpers. Run **one emulator session at a time**; the helpers share local FIFO,
port and log names. The launcher uses temporary disk snapshots by default, so
guest changes are discarded on exit and the prepared images remain reusable.
Do not move the checkout or build directory without rebuilding the launcher.

In a new Terminal, you can boot an existing build without rebuilding:

```sh
export MHI2_REPRO="$HOME/mhi2-repro"
bash "$MHI2_REPRO/porsche-build/run.sh"  # or audi-build / vw-build
```

For console-only testing, add `--headless`. The generated launcher selects
its build's QEMU, graphics host, Python environment, firmware metadata and
media paths; no paths from the original developer's computer are needed.

## Wi-Fi, Bluetooth and cellular

The Marvell SDIO radio exposes one open network, **QEMU Wi-Fi**, backed by
QEMU user networking (NAT/DHCP) by default. Select it in the firmware's Wi-Fi
client settings. The access point is virtual; it does not scan your host's
wireless networks. You can change its name and use normal QEMU network options:

```sh
bash "$MHI2_REPRO/porsche-build/run.sh" --wifi-ssid "My emulator" \
  --wifi 'user,hostfwd=tcp:127.0.0.1:2222-:22'
```

`--wifi none` disconnects the network backend. Bluetooth defaults to an empty
controller. To discover and connect to peers, attach an external H4 controller
with `--bluetooth`; this can be a software controller or a dedicated USB
Bluetooth adapter through an H4 bridge. See [wireless setup and validation](tools/mhi2/WIRELESS.md)
for commands, backend choices and current limits.

An optional Cinterion USB modem presents a simulated SIM and 3G/4G network to
the original head-unit modem driver. Its USB Ethernet data path uses QEMU NAT:

```sh
bash "$MHI2_REPRO/porsche-build/run.sh" --cellular 4g
# Use --cellular 3g for UMTS, or --cellular off to omit the modem.
```

After Porsche K5126 finishes booting, use its data-connection settings to select
automatic connection with APN `qemu`, or request that configuration from another
terminal in the source directory:

```sh
python3 tools/mhi2/network.py cellular
# To connect through the native WLAN service instead:
python3 tools/mhi2/network.py wifi
```

For Wi-Fi client mode, boot with `--cellular off`: this Porsche firmware
rejects WLAN tethering while a SIM is inserted.

This uses the computer's Internet connection. It does not require a physical
SIM or mobile subscription. The Porsche K5126 companion profile enables the
native WLAN and online-data equipment settings. Actual Porsche/Audi/VW cloud
services still depend on compatible servers, accounts and vehicle entitlement;
an emulated modem does not provide those. See the [cellular notes](tools/mhi2/WIRELESS.md#cellular).

## What to expect

Cold boot can take several minutes. Porsche's Home page can remain at
**Loading Home** while services initialize, even after the radio screen works.
An empty cluster or unavailable navigation is expected without matching map
data; this guide does not download maps or speech/online-service packages.
The bootstrap's formatted data partitions are a starting point, not a complete
vehicle filesystem dump.

The shared host supports H.264 hardware encoding/decoding through VideoToolbox
on macOS. To require it and fail rather than fall back to software:

```sh
MHI2_ENCODER=hardware MHI2_DECODER=hardware \
  bash "$MHI2_REPRO/porsche-build/run.sh"
```

Mesa provides EGL/GLES rendering. The tested Mac uses **llvmpipe software GLES**;
hardware video decoding does not imply hardware-accelerated 3D rendering.
CoreAudio playback uses SoX; microphone use may require macOS permission.
See [host backend validation](tools/mhi2/HOST_PARITY.md) for the exact tests.

Audi and VW have earlier Linux boot evidence. Porsche K5126 and the shared
host backends have local Apple Silicon macOS execution evidence. The Porsche
workflow was also tested from an extracted source ZIP with no `.git` directory
after rebasing onto official QEMU: a clean build using the published bootstrap
and original K5126 archive reached the native radio screen. That run used
GNU Arm 14.3.Rel1. See [validation details](tools/mhi2/CONSOLIDATION.md). Audi and VW
were not freshly boot-tested on macOS for this guide. This is not a
claim that every firmware, host architecture, vehicle service or Android Auto
connection works. Original HMI executables are used with emulator compatibility
libraries and a diagnostic shell in disposable media. Do not flash those
images onto a real head unit.

## Troubleshooting

- **Wrong firmware train:** use the exact train in the table; renaming an
  archive or editing its manifest does not make it compatible.
- **Output already exists:** choose a new `--output` path. A failed build is
  retained for inspection rather than overwritten.
- **Missing EGL/FFmpeg/LZO/USB libraries:** check
  `pkg-config --exists egl glesv2 libavcodec libavutil libswscale libusb-1.0 slirp`.
  Use a native Homebrew installation matching your Mac's architecture. A custom
  FFmpeg installation needs its `lib/pkgconfig` directory in `PKG_CONFIG_PATH`.
- **No window / helper exited:** read `/tmp/mhi2-session.log`,
  `/tmp/mhi2-viewer.log`, `/tmp/mhi2-debug-host.log`, `/tmp/mhi2-debug-console.log`
  and `/tmp/mhi2-glhost.log`. Full logs are copied to the build's `media/runs/`
  when the session closes.
- **A session is already running:** close its viewer or stop its Terminal
  before starting another firmware profile.

To copy files from Linux or macOS into QNX, see
[file transfers and guest filesystem access](tools/mhi2/FILE_TRANSFER.md).
It includes a host upload command, an HMI JAR example, writable mounts and
persistent copies.

For advanced details see the [Audi reproduction guide](tools/mhi2/AUDI_A3.md),
[emulator internals](tools/mhi2/README.md), [fork notes](README.MHI2.md)
and the original [upstream QEMU README](README.rst).

## Source and licensing

The fork is based on [iscle/qemu-mhi2](https://github.com/iscle/qemu-mhi2),
which is in turn based on [official QEMU](https://github.com/qemu/qemu). MHI2-specific
and FPK1 changes are experimental and include AI-assisted work; they are not intended
as upstream QEMU submissions. QEMU and third-party source retain their existing
copyright and license notices; see [COPYING](COPYING) and [COPYING.LIB](COPYING.LIB).
Firmware and captured bootstrap data are separate from the emulator source;
the source license does not grant rights to redistribute those assets.
