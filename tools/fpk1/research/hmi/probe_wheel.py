"""Boot local firmware and click the real Qt wheel panel with debug tracing.

Run using build_fpk1/venv/bin/python; all outputs stay in research-artifacts.
The --peer mode is an internal headless Qt/KSS subprocess used by this probe.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import datetime
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import zipfile

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').exists())
sys.path.insert(0, str(REPO / 'tools/fpk1'))


def scenario_keys():
    from hmi.assist_scenarios import LABELS
    selected = os.environ.get('FPK1_PROBE_SCENARIOS')
    keys = tuple(selected.split(',')) if selected else tuple(LABELS)
    if any(key not in LABELS for key in keys):
        raise ValueError('Unknown FPK1_PROBE_SCENARIOS key')
    return keys


def verify(out):
    text = (out / 'console.log').read_text()
    peer_log = (out / 'kss.log').read_text()
    expected = {473: 1, 447: 1, 439: 1, 444: 1, 495: 2}
    dispatched = [int(n) for n in re.findall(
        r'dispatchKeyEvent sent Button-Event to hmi with KeyEvent type: BUTTON \(1\), hmiEventID:(\d+)', text)]
    buttons = {str(key): dispatched.count(key) for key in expected}
    rotary = re.findall(r'dispatchKeyEvent send Rotary-Event to hmi with [^\n]*? ticks:(-?\d+)', text)
    summary = dict(button_hmi_events=buttons, rotary_ticks=list(map(int, rotary)),
                   queued_clicks=peer_log.count('UI queued MFL '),
                   transmitted_updates=peer_log.count('tx RTE MFL_Tasten_Kon_01 '))
    summary['passed'] = (all(buttons[str(k)] == v for k, v in expected.items())
                         and summary['rotary_ticks'] == [-1, -1, 1]
                         and summary['queued_clicks'] == 9
                         and summary['transmitted_updates'] == 24)
    (out / 'wheel-check.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    if not summary['passed']:
        raise SystemExit('Wheel events did not all reach HMI; inspect console.log/kss.log')


def verify_closures(out):
    text = (out / 'console.log').read_text()
    peer_log = (out / 'kss.log').read_text()
    fields = ('frontLeftDoor', 'frontRightDoor', 'rearLeftDoor', 'rearRightDoor', 'boot', 'bonnet')
    masks = []
    for line in text.splitlines():
        if 'CarOutline_HMI(incoming data=t_rte_CarOutline_01(' in line:
            values = [re.search(r'car_' + field + r'_b = ([01])', line) for field in fields]
            if all(values):
                masks.append(sum(int(value[1]) << bit for bit, value in enumerate(values)))
    names = ('front left', 'front right', 'rear left', 'rear right', 'hatch/boot', 'hood/bonnet')
    states = {name: list(map(int, re.findall(
        r'door ' + re.escape(name) + r' status changed: (\d+)', text))) for name in names}
    transitions = [mask for n, mask in enumerate(masks) if n == 0 or mask != masks[n - 1]]
    received_states = {field: [(mask >> bit) & 1 for mask in transitions]
                       for bit, field in enumerate(fields)}
    app_updates = len(re.findall(r'GSS_APP_CarOutline\s+info\s+\d+\s+triggerUpdate\(', text))
    summary = dict(hmi_view_states=states, received_masks=transitions,
                   received_states=received_states, gtf2_app_updates=app_updates,
                   queued_changes=peer_log.count(' queued'))
    summary['all_view_models_updated'] = all(values.count(1) >= 2 and values[-1:] == [0]
                                            for values in states.values())
    summary['warning_active_seen'] = 'condTemplateIsDoorWarningActive=1' in text
    summary['warning_design_eligible_seen'] = 'condTemplateIsSportDesign=1' in text
    summary['passed'] = (summary['queued_changes'] == 24 and 63 in masks
        and masks[-1:] == [0]
        and app_updates >= 24
        and all(1 in values and values[-1:] == [0] for values in received_states.values()))
    (out / 'closure-check.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    if not summary['passed']:
        raise SystemExit('Closure changes did not all reach HMI; inspect console.log/kss.log')


def verify_assist(out):
    from hmi.assist_catalog import SIGNALS
    text = (out / 'console.log').read_text()
    received = {}
    for name, (_, _, fields) in SIGNALS.items():
        candidates = [line for line in text.splitlines() if name + '(incoming data=' in line]
        if name == 'ACC_KBI':
            received[name] = any('ACC_KBI(incoming data=1)' in line for line in candidates)
            continue
        expected = {field: (0xa800 if field == 'ZPM_warnID_unit16' else 0)
                    if name == 'ZPM_HMI_Info' else 1 for field, _, _ in fields}
        received[name] = any(all(
            (match := re.search(re.escape(field) + r' = (-?\d+)', line))
            and int(match[1]) == value for field, value in expected.items()) for line in candidates)
    report = dict(received=received, checked_fields=sum(len(row[2]) for row in SIGNALS.values()),
                  passed=all(received.values()))
    (out / 'assist-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    if not report['passed']:
        raise SystemExit('Some configured assist fields were not observed in HMI input traces')


def verify_scenarios(out):
    """Check guest input traces; does not certify pixels or raw enum meanings."""
    from hmi.assist_catalog import SIGNALS
    from hmi.assist_scenarios import LABELS, scenario
    text = (out / 'console.log').read_text()
    peer_log = (out / 'kss.log').read_text()
    lines = text.splitlines()
    received = {}
    for key in scenario_keys():
        profile = scenario(key)
        channels = {}
        for name, values in profile.items():
            if name == 'ACC_KBI':
                channels[name] = f'ACC_KBI(incoming data={values.get("available", 0)})' in text
                continue
            channels[name] = any(all(
                (match := re.search(re.escape(field) + r' = (-?\d+)', line))
                and int(match[1]) == values.get(field, 0) for field, _, _ in SIGNALS[name][2])
                for line in lines if name + '(incoming data=' in line)
        from hmi.traffic_lights import PROFILES
        if key in PROFILES:
            signal, seconds, speed = PROFILES[key]
            channels.update(
                available='handleConnectionStateChange(): Traffic light available' in text,
                synchronized='on_GetAll_StatusAll(): Request FunctionList::Get next' in text,
                no_sync_error=not any('GSS_BAP_OnlineFunction' in line and 'on_GetAll_Error(' in line
                                      for line in lines),
                functions='Supported functions: AIO Info: true, AIO Speed true, AIO Time: true' in text,
                info=f'AioInfo( Signalstate: {signal},' in text,
                display=f'writeAioTrafficLight(): Writing traffic light to DP: signalState { {0: 0, 1: 1, 3: 2}[signal]},' in text,
                time=f'Sending AioTime to Application: time {seconds}, validity {int(bool(seconds))}' in text,
                speed=f'Sending AioSpeed to Application: speed {speed}, unit 0, validity {int(bool(speed))}' in text)
        received[key] = dict(queued=bool(re.search(r'\[kss[^\n]*\] Assist scenario: '
                             + re.escape(key) + r'(?=\n|$)', peer_log)),
                             channels=channels)
    report = dict(scenarios=received, scope='Input delivery only; rendering not certified',
                  passed=all(row['queued'] and all(row['channels'].values())
                             for row in received.values()))
    (out / 'scenario-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    if not report['passed']:
        raise SystemExit('Some scenario inputs were not observed in guest traces')


def peer(socket, closures=False, assist=False, scenarios=False):
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QToolButton
    from ui.viewer import KssPeer, WheelPanel, WHEEL_BUTTONS, ClosurePanel
    app = QApplication([])
    kss = KssPeer(Path(socket))
    kss.line.connect(lambda line: print(line, flush=True))
    report = lambda line: print('UI ' + line, flush=True)
    if assist or scenarios:
        from ui.assist import AssistPanel
        from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox
        panel = AssistPanel(kss, report)
        if scenarios:
            from hmi.assist_scenarios import LABELS
            for n, key in enumerate((*scenario_keys(), 'off')):
                QTimer.singleShot(int(os.environ.get('FPK1_PROBE_START', '60')) * 1000 + n * 6000,
                    lambda key=key: panel.scenario.setCurrentIndex(panel.scenario.findData(key)))
        for n, ((name, field), control) in enumerate(panel.controls.items() if not scenarios else ()):
            if name == 'ZPM_HMI_Info':
                if field != 'ZPM_warnID_unit16':
                    continue
                callback = lambda c=control: c.setCurrentIndex(c.findData(0xa800))
            elif isinstance(control, QCheckBox):
                callback = lambda c=control: c.setChecked(True)
            elif isinstance(control, QComboBox):
                callback = lambda c=control: c.setCurrentIndex(1)
            else:
                callback = lambda c=control: c.setValue(1)
            QTimer.singleShot(20000 + n * 30, callback)
        for n, button in enumerate(panel.enables.values() if not scenarios else ()):
            QTimer.singleShot(75000 + n * 1000, button.click)
    else:
        panel = ClosurePanel(kss, report) if closures else WheelPanel(kss, report)
    # HMI startup can take over a minute on the host. Repeated equal actions
    # verify that the neutral state prevents gtf2's duplicate suppression.
    if assist or scenarios:
        pass
    elif closures:
        for n, button in enumerate(panel.buttons.values()):
            QTimer.singleShot(75000 + n * 4000, button.click)
            QTimer.singleShot(77000 + n * 4000, button.click)
        for n, button in enumerate(panel.buttons.values()):
            QTimer.singleShot(102000 + n * 250, button.click)
            QTimer.singleShot(110000 + n * 250, button.click)
    else:
        buttons = dict(zip((row[3] for row in WHEEL_BUTTONS), panel.findChildren(QToolButton)))
        actions = ('up', 'up', 'down', 'ok', 'back', 'left', 'right', 'view', 'view')
        for n, action in enumerate(actions):
            QTimer.singleShot(75000 + n * 2000, buttons[action].click)
    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if kss.stopped else None)
    timer.start(100)
    kss.start()
    app.exec()


def boot(seconds, closures=False, capture=False, assist=False, scenarios=False):
    from inspect_stage2_catalogs import parse_catalog
    from verify_sifs_partitions import member, parse_table, verify_part
    from hmi.configm import DEFAULT_CODING
    import run_stage1_console as console
    build = REPO / 'build_fpk1'
    kind = 'assist-scenarios' if scenarios else ('driver-assist' if assist else ('closures' if closures else 'wheel'))
    out = build / 'research-artifacts' / kind / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    archive = REPO / 'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip'
    with zipfile.ZipFile(archive) as z:
        nor = member(z, 'stage2_ifs.img', b'CIFS')
        table = parse_table(nor)
        part = next(p for p in table['partitions'] if p['name'] == 'STAGE2.1')['parts'][0]
        _, image = verify_part(nor, table['data_base'] + part['offset'], part, True)
        row = next(r for r in parse_catalog(image)['entries'] if r['path'] == 'config/tracing.json')
        raw = image[row['offset']:row['offset'] + row['size']].decode()
    config = json.loads('\n'.join(l for l in raw.splitlines() if not l.lstrip().startswith('#')))
    for name, channels in {
        'gss_ipc': ('GSS_IPC_RteInbound', 'GSS_IPC_HmiKssCommService', 'GSS_IPC_BapIpcService', 'GSS_IPC_BapBindings', 'GSS_IPC_BapLogger'),
        'gtf2': ('GSS_APP_KeyHandler', 'GSS_APP_KeyEventConverter', 'GSS_APP_GemHandler',
                 'GSS_HMI_GTF2_GEMKeyInputServiceImpl', 'GSS_APP_CarOutline',
                 'GSS_HMI_Model_CHMIGTFCarOutlineModel', 'GSS_HMI_CHMIGTFCarOutline',
                 'GSS_HMI_CHMIGTFCarOutline_DoorWarning', 'GSS_APP_Warning',
                 'GSS_GTF_ViewManager', 'GSS_APP_ACC', 'GSS_APP_AsgSwa', 'GSS_APP_FAS',
                 'GSS_HMI_CHMIGTF_FAS', 'GSS_APP_AsgNightVision', 'GSS_ASG_NightVision',
                 'GSS_APP_AsgVza', 'GSS_APP_AsgOnlineFunctions', 'GSS_APP_AioVza',
                 'GSS_BAP_OnlineFunctionsSD', 'GSS_BAP_OnlineFunctionsSD_DATA',
                 'GSS_HMI_Model_CHMIGTFAIOVZAModel'),
    }.items():
        client = config['client'][name]
        for levels in (client['levels'], client['backends']['ConsoleBackend']['levels']):
            levels['channel'].update(dict.fromkeys(channels, 'debug'))
    tracing = (json.dumps(config, indent=2) + '\n').encode()
    (out / 'tracing.json').write_bytes(tracing)
    os.environ.update(FPK1_CODING=DEFAULT_CODING, TEGRA_GR3D_DISCARD='1',
                      PYTHONDONTWRITEBYTECODE='1', MHI2_GL_WIDTH='1440', MHI2_GL_HEIGHT='540',
                      MHI2_SHADER_CACHE=str(build / 'research-artifacts/shader-translate/cache'))
    original = subprocess.Popen
    if capture:
        from hmi.capture_scanout import ScanoutCapture
        original_capture = ScanoutCapture.capture

        def capture_frame(instance, process, elapsed):
            original_capture(instance, process, elapsed)
            from hmi.assist_scenarios import LABELS
            samples = (tuple(int(os.environ.get('FPK1_PROBE_START', '60')) + 4 + n * 6 for n in range(len(scenario_keys()) + 1)) if scenarios
                       else (70, 76, 80, 88, 96, 104, 108, 115, 122))
            for second in samples:
                target = out / 'frames' / f'at-{second:03d}.ppm'
                if elapsed >= second and not target.exists():
                    source = instance.directory / 'dc-scanout.ppm'
                    if source.exists():
                        shutil.copyfile(source, target)

        ScanoutCapture.capture = capture_frame

    def popen(command, *args, **kwargs):
        if isinstance(command, list) and len(command) > 1 and str(command[1]).endswith('/kss_peer.py'):
            command = [command[0], str(Path(__file__).resolve()), '--peer', command[2]]
            if closures:
                command += ['--closures']
            if assist:
                command += ['--assist']
            if scenarios:
                command += ['--scenarios']
        return original(command, *args, **kwargs)

    subprocess.Popen = popen
    print(out, flush=True)
    try:
        result = console.run(archive, build / 'qemu/qemu-system-arm', seconds,
            tcg_thread='multi', emmc=build / 'media/emmc.img', keep_dir=out,
            cmdline=console.BOARD_CMDLINE,
            replacements={'config/tracing.json': tracing, **{
                'lib/' + n: (build / 'bridge' / n).read_bytes() for n in ('libEGL.so', 'libGLESv2.so')}},
            glhost=build / 'bridge/glhost', gl_frames=out / 'frames',
            kss=True, native_display='none', capture_scanout=capture, scanout_interval=1)
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        if scenarios:
            verify_scenarios(out)
        elif assist:
            verify_assist(out)
        else:
            (verify_closures if closures else verify)(out)
    finally:
        subprocess.Popen = original
        if capture:
            ScanoutCapture.capture = original_capture


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--peer')
    parser.add_argument('--closures', action='store_true', help='exercise six closure switches instead of wheel')
    parser.add_argument('--capture', action='store_true', help='retain selected QEMU scanout samples')
    parser.add_argument('--assist', action='store_true', help='exercise all Driver Assist message controls')
    parser.add_argument('--scenarios', action='store_true', help='exercise coherent assist scenarios via Qt')
    parser.add_argument('--verify', type=Path, help='verify a saved probe run without booting')
    parser.add_argument('--seconds', type=int, help='run duration; defaults to all scenarios or 110 s')
    args = parser.parse_args()
    if args.verify:
        (verify_scenarios if args.scenarios else (verify_assist if args.assist else
            (verify_closures if args.closures else verify)))(args.verify)
    elif args.peer:
        peer(args.peer, args.closures, args.assist, args.scenarios)
    else:
        from hmi.assist_scenarios import LABELS
        seconds = args.seconds if args.seconds is not None else (70 + 6 * len(scenario_keys()) if args.scenarios else 110)
        boot(seconds, args.closures, args.capture, args.assist, args.scenarios)
