"""Local NavigationSD guest trace probe. Generated files stay in private artifacts.

Boots the cluster, enables the navigation fixture, then steps through the
cluster sections with the wheel's right key so scanout frames show each view.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import datetime
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
    for n in range(experiment['steps']):
        schedule(experiment['first_step'] + n * experiment['step_every'], wheel, experiment['key'])
    kss_peer.run(socket, .01, assist_commands=commands, wheel_commands=wheel)


def boot(seconds, experiment):
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
    os.environ.update(FPK1_CODING=DEFAULT_CODING, TEGRA_GR3D_DISCARD='1', PYTHONDONTWRITEBYTECODE='1',
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
    (out / 'experiment.json').write_text(json.dumps(experiment, indent=2) + '\n')
    try:
        result = console.run(REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip',
            build / 'qemu/qemu-system-arm', seconds, tcg_thread='multi', emmc=build / 'media/emmc.img',
            keep_dir=out, cmdline=console.BOARD_CMDLINE,
            replacements={'config/tracing.json': tracing, **{
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
    parser.add_argument('--key', default='right', help='wheel action used to step views')
    parser.add_argument('--first-step', type=float, default=90)
    parser.add_argument('--step-every', type=float, default=8)
    parser.add_argument('--steps', type=int, default=6)
    args = parser.parse_args()
    if args.peer:
        peer(args.peer)
    else:
        boot(args.seconds, dict(profile=args.profile, enable_at=args.enable_at, key=args.key,
                                first_step=args.first_step, step_every=args.step_every, steps=args.steps))
