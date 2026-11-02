"""Local NavigationSD guest trace probe. Generated files stay in private artifacts.

Boots the cluster, enables the navigation fixture, then presses the scheduled
wheel keys (default: three sections right to the map, then Menu R and down).
"""
import sys
sys.dont_write_bytecode = True
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import threading
import shutil
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))


def schedule(second, queue, item):
    timer = threading.Timer(second, lambda: queue.put(item))
    timer.daemon = True
    timer.start()


def peer(socket):
    import kss_peer
    from hmi.navigation import preset
    commands, wheel = Queue(), Queue()
    experiment = json.loads(os.environ['FPK1_NAV_EXPERIMENT'])
    if experiment['profile'] != 'none':
        schedule(experiment['enable_at'], commands, ('@navigation', None, preset(experiment['profile'])))
    for second, action in experiment['actions']:
        schedule(second, wheel, action)
    kss_peer.run(socket, .01, assist_commands=commands, wheel_commands=wheel)


def persist_emmc(build, directory, out):
    """Copy of the eMMC whose persist_fpk volume holds DIRECTORY as au736_evo/."""
    import create_fpk1_emmc
    layout = json.loads((build / 'media/emmc.json').read_text())
    row = next(p for p in layout['partitions'] if p['label'] == 'persist_fpk')
    work = out / 'persist'
    shutil.copytree(directory, work / 'blank/au736_evo')
    volume = create_fpk1_emmc.blank_volume(work, row['sectors'] * 512)
    image = out / 'emmc.img'
    if subprocess.run(['cp', '-c', str(build / 'media/emmc.img'), str(image)],
                      stderr=subprocess.DEVNULL).returncode != 0:
        shutil.copyfile(build / 'media/emmc.img', image)
    with image.open('r+b') as stream:
        stream.seek(row['start_sector'] * 512)
        stream.write(volume)
    shutil.rmtree(work)
    return image


def boot(seconds, experiment, gtf2=None, persist=None, coding=None):
    import run_stage1_console as console
    from hmi.configm import DEFAULT_CODING
    build = REPO / 'build_fpk1'
    out = build / 'research-artifacts/navigation' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    os.environ['FPK1_NAV_EXPERIMENT'] = json.dumps(experiment)
    raw = (build / 'research-artifacts/wheel/tracing.json').read_text()
    config = json.loads('\n'.join(line for line in raw.splitlines() if not line.lstrip().startswith('#')))
    for name, channels in {
        'gss_ipc': ('GSS_IPC_RteInbound', 'GSS_IPC_BapIpcService', 'GSS_IPC_BapBindings', 'GSS_IPC_BapLogger'),
        'gtf2': ('GSS_APP_AsgNavigation', 'GSS_BAP_NavigationSD', 'GSS_BAP_NavigationSD_DATA',
                 'GSS_GTF_ViewManager', 'GSS_APP_Configuration_Manager'),
    }.items():
        client = config['client'][name]
        for levels in (client['levels'], client['backends']['ConsoleBackend']['levels']):
            levels['channel'].update(dict.fromkeys(channels, 'debug'))
    tracing = (json.dumps(config, indent=2) + '\n').encode()
    (out / 'tracing.json').write_bytes(tracing)
    os.environ.update(FPK1_CODING=coding or DEFAULT_CODING, TEGRA_GR3D_DISCARD='1', PYTHONDONTWRITEBYTECODE='1',
                      MHI2_GL_WIDTH='1440', MHI2_GL_HEIGHT='540',
                      MHI2_SHADER_CACHE=str(build / 'research-artifacts/shader-translate/cache'))
    from hmi.capture_scanout import ScanoutCapture
    original_capture = ScanoutCapture.capture
    def capture(instance, process, elapsed):
        original_capture(instance, process, elapsed)
        source = instance.directory / 'dc-scanout.ppm'
        if source.exists():
            target = out / 'frames' / f'at-{int(elapsed):03d}.ppm'
            if not target.exists():
                shutil.copyfile(source, target)
    ScanoutCapture.capture = capture
    original = subprocess.Popen
    def popen(command, *args, **kwargs):
        if isinstance(command, list) and len(command) > 1 and str(command[1]).endswith('/kss_peer.py'):
            command = [command[0], str(Path(__file__).resolve()), '--peer', command[2]]
        return original(command, *args, **kwargs)
    subprocess.Popen = popen
    print(out, flush=True)
    overrides = {}
    if gtf2:
        overrides['bin/gtf2'] = gtf2.read_bytes()
        experiment = dict(experiment, gtf2_override=str(gtf2.resolve()),
                          gtf2_sha256=hashlib.sha256(overrides['bin/gtf2']).hexdigest())
        if (gtf2.parent / 'patch.json').exists():
            shutil.copyfile(gtf2.parent / 'patch.json', out / 'patch.json')
    emmc = build / 'media/emmc.img'
    if persist:
        emmc = persist_emmc(build, persist, out)
        experiment = dict(experiment, persist=str(persist.resolve()),
                          persist_files=sorted(str(p.relative_to(persist)) for p in persist.rglob('*')))
    (out / 'experiment.json').write_text(json.dumps(experiment, indent=2) + '\n')
    try:
        result = console.run(REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip',
            build / 'qemu/qemu-system-arm', seconds, tcg_thread='multi', emmc=emmc,
            keep_dir=out, cmdline=console.BOARD_CMDLINE,
            replacements={'config/tracing.json': tracing, **overrides, **{
                'lib/' + name: (build / 'bridge' / name).read_bytes() for name in ('libEGL.so', 'libGLESv2.so')}},
            glhost=build / 'bridge/glhost', gl_frames=out / 'frames', kss=True,
            native_display='none', capture_scanout=True, scanout_interval=2)
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    finally:
        subprocess.Popen = original
        ScanoutCapture.capture = original_capture


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--peer')
    parser.add_argument('--seconds', type=int, default=150)
    parser.add_argument('--profile', default='normal', help="hmi.navigation preset key, or 'none'")
    parser.add_argument('--enable-at', type=float, default=15)
    parser.add_argument('--actions', default='90:right,98:right,106:right,116:side_right,124:down,132:down',
                        help='comma-separated SECONDS:WHEEL_ACTION presses')
    parser.add_argument('--gtf2', type=Path, help='Private experiment executable override (bin/gtf2)')
    parser.add_argument('--persist', type=Path,
                        help='directory copied to /mnt/persist_fpk/au736_evo/ on a run-local eMMC copy')
    parser.add_argument('--coding', help='20-byte ConfigM long coding in hex (default: hmi.configm.DEFAULT_CODING)')
    args = parser.parse_args()
    if args.peer:
        peer(args.peer)
    else:
        actions = [(float(t), a) for t, a in (item.split(':') for item in args.actions.split(','))]
        experiment = dict(profile=args.profile, enable_at=args.enable_at, actions=actions, coding=args.coding)
        boot(args.seconds, experiment, args.gtf2, args.persist, args.coding)
