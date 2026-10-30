"""Local RDK guest trace probe. Generated files stay in private artifacts."""
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
import time
import shutil
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))


def peer(socket):
    import kss_peer
    from hmi.tpms import preset
    commands = Queue()
    wheel = Queue()
    def read_actions():
        path = Path(os.environ['FPK1_TPMS_ACTIONS'])
        offset = 0
        while True:
            lines = path.read_text().splitlines()
            for line in lines[offset:]:
                item = json.loads(line)
                if 'wheel' in item:
                    wheel.put(item['wheel'])
                if 'preset' in item:
                    commands.put(('@tpms', None, preset(item['preset'])))
            offset = len(lines)
            time.sleep(.2)
    threading.Thread(target=read_actions, daemon=True).start()
    for second, key in ((20, 'lamp_on'), (38, 'values_30'), (48, 'wheel_FL')):
        timer = threading.Timer(second, lambda key=key: commands.put(('@tpms', None, preset(key))))
        timer.daemon = True
        timer.start()
    timer = threading.Timer(28, lambda: wheel.put('side_right'))
    timer.daemon = True
    timer.start()
    kss_peer.run(socket, .01, assist_commands=commands, wheel_commands=wheel)


def boot(seconds):
    import run_stage1_console as console
    from hmi.configm import DEFAULT_CODING
    build = REPO / 'build_fpk1'
    out = build / 'research-artifacts/tpms' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    raw = (build / 'research-artifacts/wheel/tracing.json').read_text()
    actions = out / 'actions.jsonl'
    actions.touch()
    os.environ['FPK1_TPMS_ACTIONS'] = str(actions)
    config = json.loads('\n'.join(line for line in raw.splitlines() if not line.lstrip().startswith('#')))
    for name, channels in {
        'gss_ipc': ('GSS_IPC_RteInbound', 'GSS_IPC_HmiKssCommService', 'GSS_IPC_BapIpcService', 'GSS_IPC_BapBindings', 'GSS_IPC_BapLogger'),
        'gtf2': ('GSS_APP_AsgRdk', 'GSS_BAP_RDK', 'GSS_BAP_RDK_DATA', 'GSS_GTF_ViewManager', 'GSS_APP_Configuration_Manager'),
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
    parser.add_argument('--seconds', type=int, default=65)
    args = parser.parse_args()
    peer(args.peer) if args.peer else boot(args.seconds)
