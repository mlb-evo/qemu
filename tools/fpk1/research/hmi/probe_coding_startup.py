"""Local boot with RTE/HMI connection traces; firmware executables unchanged.

Run with the build directory's venv Python. Logs and generated configuration
go under build_fpk1/research-artifacts/, never beside this script.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import datetime
import json
import os
import subprocess
from pathlib import Path
import zipfile

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from hmi.configm import (DEFAULT_CODING, DEFAULT_INTERNAL_CODING, parse_coding,
                     parse_internal, all_signals)
from inspect_stage2_catalogs import parse_catalog
from verify_sifs_partitions import member, parse_table, verify_part
import run_stage1_console as console


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=REPO / 'build-fpk1')
    parser.add_argument('--bridge', type=Path, help='local experiment: alternate guest bridge libraries')
    parser.add_argument('--seconds', type=int, default=65)
    parser.add_argument('--coding', default=DEFAULT_CODING)
    parser.add_argument('--internal-coding', default=os.environ.get('FPK1_INTERNAL_CODING', DEFAULT_INTERNAL_CODING),
                        help='16-byte NvM block 0x39 in hex; default: original ROM fallback')
    parser.add_argument('--startup-only', action='store_true', help='trace stage-3 startup without per-signal RTE traffic')
    parser.add_argument('--active-design', type=int, choices=(0, 1),
                        help='explicit local BAP_DesignChange experiment; ConfigM unchanged')
    parser.add_argument('--viewer', action='store_true', help='open the unified QEMU display and KSS peer UI')
    parser.add_argument('--capture-scanout', action=argparse.BooleanOptionalAction, default=False,
                        help='diagnostic only: save QEMU scanout to PPM (default: disabled)')
    parser.add_argument('--native-display', choices=('none', 'sdl', 'embedded'),
                        help='QEMU display; defaults to embedded with --viewer, otherwise none')
    parser.add_argument('--dump-gl-frames', action='store_true',
                        help='diagnostic only: enable primary/per-client GLES PPM files')
    parser.add_argument('--scanout-interval', type=float, default=0.1,
                        help='seconds between scanout snapshots (default: 0.1)')
    parser.add_argument('--state-debug', action='store_true', help='trace HMI view/state/background transitions')
    parser.add_argument('--watch', action='store_true', help='record host child status and frame history')
    parser.add_argument('--sample-threads', action='store_true', help='read guest gtf2 thread states periodically through the serial shell')
    parser.add_argument('--asset-debug', action='store_true', help='include KZB load/merge and batch completion events')
    parser.add_argument('--stage3-delay', type=int, help='local experiment: replace fallback sleep (normally 30 seconds)')
    args = parser.parse_args()
    build = args.build.resolve()
    coding = parse_coding(args.coding).hex()
    internal = parse_internal(args.internal_coding)
    archive = REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip'
    out = REPO / 'build_fpk1/research-artifacts/coding-startup' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    (out / 'configm.json').write_text(json.dumps(dict(
        coding=coding, internal_coding=internal.hex(),
        internal_source='ROM fallback' if internal.hex() == DEFAULT_INTERNAL_CODING else 'explicit override',
        signals=[dict(name=name, data_id=hex(key), wire=value.hex(), status=0)
                 for name, key, value in all_signals(bytes.fromhex(coding), internal)]), indent=2) + '\n')
    with zipfile.ZipFile(archive) as z:
        nor = member(z, 'stage2_ifs.img', b'CIFS')
        table = parse_table(nor)
        part = next(p for p in table['partitions'] if p['name'] == 'STAGE2.1')['parts'][0]
        _, image = verify_part(nor, table['data_base'] + part['offset'], part, True)
        entries = {r['path']: r for r in parse_catalog(image)['entries']}
        row = entries['config/tracing.json']
        config = image[row['offset']:row['offset'] + row['size']].decode()
    channels = ('GSS_IPC_RteInbound', 'GSS_IPC_HmiKssCommService',
                'GSS_MAN_GssManager', 'GSS_MAN_AliveManager')
    config = json.loads('\n'.join(line for line in config.splitlines()
                                  if not line.lstrip().startswith('#')))
    client = config['client']['gss_ipc']
    client['levels']['channel'].update(dict.fromkeys(channels, 'debug'))
    client['backends']['ConsoleBackend']['levels']['channel'].update(dict.fromkeys(channels, 'debug'))
    if args.startup_only:
        for channel in channels:
            client['levels']['channel'][channel] = 'info'
            client['backends']['ConsoleBackend']['levels']['channel'][channel] = 'info' if channel.startswith('GSS_MAN') else 'warning'
    gtf = config['client']['gtf2']
    gtf_channels = dict.fromkeys(('GSS_GTF_CHMIGuiMain', 'GSS_GTF_main', 'GSS_APP_Configuration'), 'debug')
    if args.startup_only:
        gtf_channels = dict.fromkeys(('GSS_GTF_CHMIGuiMain', 'GSS_GTF_main', 'GSS_ThreadManager',
                                     'GSS_GTF_StageManager', 'GSS_GTF_DisplayManager',
                                     'GSS_HMI_GTF2_FsTools', 'GSS_HMI_CHMIGTFAssetManager',
                                     'GSS_HMI_CHMIGTFResources'), 'info')
    gtf['levels']['channel'].update(gtf_channels)
    gtf['backends']['ConsoleBackend']['levels']['channel'].update(gtf_channels)
    if args.state_debug:
        states = dict.fromkeys(('GSS_GTF_ViewManager', 'GSS_HMI_GTF2_STATEMACHINE',
                                'GSS_GTF_StageManager', 'GSS_GTF_DisplayManager',
                                'GSS_System_StateInputSignals'), 'debug')
        gtf['levels']['channel'].update(states)
        gtf['backends']['ConsoleBackend']['levels']['channel'].update(states)
    if args.asset_debug:
        gtf['levels']['channel']['GSS_HMI_CHMIGTFAssetManager'] = 'debug'
        gtf['backends']['ConsoleBackend']['levels']['channel']['GSS_HMI_CHMIGTFAssetManager'] = 'debug'
    # NOR replacements must fit in the original file's allocated extent.
    # The firmware parser cannot read the entire configuration as one long line.
    config = (json.dumps(config, indent=2) + '\n').encode()
    (out / 'tracing.json').write_bytes(config)
    os.environ.update(FPK1_CODING=coding, FPK1_INTERNAL_CODING=internal.hex(), MHI2_GL_WIDTH='1440', MHI2_GL_HEIGHT='540',
                      TEGRA_GR3D_DISCARD='1', PYTHONDONTWRITEBYTECODE='1',
                      MHI2_SHADER_CACHE=str(build / 'research-artifacts/shader-translate/cache'))
    bridge = args.bridge.resolve() if args.bridge else build / 'bridge'
    replacements = {name: (bridge / Path(name).name).read_bytes()
                    for name in ('lib/libEGL.so', 'lib/libGLESv2.so')}
    replacements['config/tracing.json'] = config
    if args.stage3_delay is not None:
        if not 0 <= args.stage3_delay <= 300:
            parser.error('--stage3-delay must be 0..300')
        row = entries['bin/gtf2_error_fallback.sh']
        fallback = image[row['offset']:row['offset'] + row['size']]
        assert fallback.count(b'/bin/sleep 30') == 1
        replacements['bin/gtf2_error_fallback.sh'] = fallback.replace(b'/bin/sleep 30', f'/bin/sleep {args.stage3_delay}'.encode())
    (out / 'probe.json').write_text(json.dumps(vars(args), default=str, indent=2) + '\n')
    print(out, flush=True)
    original_popen = subprocess.Popen
    watch = None
    if args.watch:
        from boot_watch import BootWatch
        watch = BootWatch(out)
        watch.start()
    if args.active_design is not None or watch:
        def design_peer(command, *pos, **kwargs):
            if args.active_design is not None and isinstance(command, list) and len(command) > 1 and str(command[1]).endswith('/kss_peer.py'):
                command = [command[0], str(Path(__file__).with_name('peer.py')), *command[2:],
                           '--timeout', '2', '--active-design', str(args.active_design)]
            elif args.active_design is not None and isinstance(command, list) and len(command) > 1 and str(command[1]).endswith('/view_frames.py'):
                command = [command[0], str(Path(__file__).with_name('design_viewer.py')), *command[2:],
                           '--active-design', str(args.active_design)]
            process = original_popen(command, *pos, **kwargs)
            if watch:
                watch.add(command, process)
            return process
        subprocess.Popen = design_peer
    samples = ['/stage3/bin/pidin -p gtf2 threads'] * 20 if args.sample_threads else []
    try:
        result = console.run(archive, build / 'qemu/qemu-system-arm', args.seconds,
                         tcg_thread='multi', emmc=build / 'media/emmc.img',
                         keep_dir=out, cmdline=console.BOARD_CMDLINE,
                         replacements=replacements, glhost=build / 'bridge/glhost',
                         gl_frames=out / 'frames', viewer=args.viewer, kss=True,
                         capture_scanout=args.capture_scanout,
                         scanout_interval=args.scanout_interval,
                         native_display=args.native_display or ('embedded' if args.viewer else 'none'),
                         dump_gl_frames=args.dump_gl_frames,
                         diag_shell=args.sample_threads,
                         screendump=out / 'display-controller' if args.watch and args.capture_scanout else None,
                         shell=samples, shell_interval=4,
                         progress=lambda row: print(f"[{row['t']}] {row['text']}", flush=True))
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    finally:
        subprocess.Popen = original_popen
        if watch:
            watch.stop()


if __name__ == '__main__':
    main()
