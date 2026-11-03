#!/usr/bin/env python3
"""FPK1 unified QEMU display, KSS peer, and optional saved-frame viewer.

With --embed-qemu-name the native SDL/X11 QEMU console is embedded beside the
KSS log. QEMU presents live pixels directly; no PPM reads or screenshot timer.

glhost writes the primary display frame (MHI2_GL_FRAME) and, with
MHI2_GL_DUMP_CLIENTS=1, one PPM per guest client process
(MHI2_GL_CLIENT_DIR/mhi2-client-<pid>.ppm) on every swap, atomically via
rename. This viewer lists those sources, follows the most recently updated one
unless a source is chosen, and polls for new frames. `--snapshot FILE.png`
saves the current frame without opening a window (usable headless).
With --capture-scanout the launcher also writes dc-scanout.ppm from QEMU's
display controller and selects that source. Its JSON describes capture limits.

With --kss SOCKET the steering-wheel panel sends MFL_Tasten_Kon_01 events
through the KSS SPI peer to gss_ipc and gtf2. Each click is a short button
pulse or one roller tick.

With --kss SOCKET the viewer is also the KSS peer: it runs kss_peer.py's SPI
master in a thread on QEMU's kss chardev and shows its log under the frame
(and appends it to --kss-log). Closing the window stops the peer.
"""
import argparse
import json
from pathlib import Path
import sys
import threading
from queue import Queue, Full

from PySide6.QtCore import QObject, Qt, QTimer, Signal, QSignalBlocker
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QPlainTextEdit, QSplitter, QToolButton,
                               QVBoxLayout, QWidget, QTabWidget)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'mhi2'))
from viewer_widgets import FrameView, fit_to_screen  # noqa: E402

FOLLOW = 'Most recent'

# Right steering-wheel cluster: (label, row, column, MFL action).
# The roller's up/down are its turn direction. Keys are sent only by clicking
# these buttons (no mouse-wheel or keyboard shortcuts).
WHEEL_BUTTONS = (
    ('\u25c1', 0, 0, 'left'),
    ('\u25b7', 0, 1, 'right'),
    ('\u25b2', 1, 0, 'up'),
    ('VIEW', 1, 1, 'view'),
    ('OK', 2, 0, 'ok'),
    ('\u21a9', 2, 1, 'back'),
    ('\u25bc', 3, 0, 'down'),
    ('MENU', 4, 0, 'menu'),
    ('Menu L', 5, 0, 'side_left'),
    ('Menu R', 5, 1, 'side_right'),
)


class WheelPanel(QWidget):
    def __init__(self, peer, report):
        super().__init__()
        self.peer, self.report = peer, report
        grid = QGridLayout(self)
        grid.addWidget(QLabel('Steering wheel'), 6, 0, 1, 2, Qt.AlignHCenter)
        for label, row, column, data in WHEEL_BUTTONS:
            button = QToolButton()
            button.setText(label)
            button.setMinimumSize(56, 40)
            if peer is None:
                button.setEnabled(False)
                button.setToolTip('Steering wheel needs the KSS peer (--kss)')
            else:
                button.setToolTip(f'MFL {data} via KSS')
                button.clicked.connect(lambda _=False, d=data: self.press(d))
            grid.addWidget(button, row, column)

    def press(self, data):
        if self.peer and self.peer.send_wheel(data):
            self.report(f'queued MFL {data}')
        else:
            self.report(f'cannot queue MFL {data}: KSS stopped or input queue full')


class KssPeer(QObject):
    """kss_peer.run in a daemon thread; each log line arrives as `line`."""
    line = Signal(str)

    def __init__(self, socket_path, log_path=None):
        super().__init__()
        self.socket_path = str(socket_path)
        self.log_file = log_path.open('a', buffering=1) if log_path else None
        self.wheel_commands = Queue(maxsize=32)
        self.closure_commands = Queue(maxsize=32)
        self.assist_commands = Queue(maxsize=128)
        self.stopped = False

    def set_assist(self, name, field, value):
        from hmi.driver_assist import valid_command
        if self.stopped or not valid_command(name, field, value):
            return False
        try:
            self.assist_commands.put_nowait((name, field, value))
            return True
        except Full:
            return False

    def set_assist_scenario(self, key):
        return self.set_assist('@scenario', None, key)

    def set_closure(self, name, opened):
        from hmi.closures import BITS
        if self.stopped or name not in BITS:
            return False
        try:
            self.closure_commands.put_nowait((name, bool(opened)))
            return True
        except Full:
            return False

    def send_wheel(self, action):
        if self.stopped:
            return False
        try:
            self.wheel_commands.put_nowait(action)
            return True
        except Full:
            return False

    def start(self):
        threading.Thread(target=self.serve, name='kss', daemon=True).start()

    def emit(self, text):
        if self.log_file:
            self.log_file.write(text + '\n')
        self.line.emit(text)

    def serve(self):
        import kss_peer
        try:
            kss_peer.run(self.socket_path, 0.01, self.emit, wheel_commands=self.wheel_commands,
                         closure_commands=self.closure_commands, assist_commands=self.assist_commands)
        except (OSError, SystemExit) as error:
            self.emit(f'[kss] stopped: {error}')
        finally:
            self.stopped = True


class ClosurePanel(QWidget):
    """Six independent, persistent KSS closure switches (checked = open)."""
    def __init__(self, peer, report):
        super().__init__()
        from hmi.closures import CLOSURES
        self.peer, self.report = peer, report
        self.buttons = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Doors / lids'))
        for name, label, _ in CLOSURES:
            button = QToolButton()
            button.setCheckable(True)
            button.setText(f'{label}: Closed')
            button.setMinimumSize(156, 28)
            button.setEnabled(peer is not None)
            button.setToolTip('Checked = open; click to open or close via KSS')
            button.toggled.connect(lambda opened, n=name, l=label: self.change(n, l, opened))
            self.buttons[name] = button
            layout.addWidget(button)

    def change(self, name, label, opened):
        button = self.buttons[name]
        if self.peer and self.peer.set_closure(name, opened):
            button.setText(f'{label}: {"Open" if opened else "Closed"}')
            self.report(f'KSS {label}: {"open" if opened else "closed"} queued')
        else:
            with QSignalBlocker(button):
                button.setChecked(not opened)
            self.report(f'Cannot change {label}: KSS stopped or input queue full')


class InputPanel(QWidget):
    def __init__(self, peer, report):
        super().__init__()
        layout = QVBoxLayout(self)
        self.wheel = WheelPanel(peer, report)
        self.closures = ClosurePanel(peer, report)
        layout.addWidget(self.wheel)
        layout.addWidget(self.closures)


def read_ppm(path):
    """Return a QImage for a complete binary PPM, or None."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    parts = data.split(b'\n', 3)
    if len(parts) != 4 or parts[0] != b'P6' or parts[2] != b'255':
        return None
    try:
        width, height = map(int, parts[1].split())
    except ValueError:
        return None
    if len(parts[3]) != width * height * 3:
        return None
    image = QImage.fromData(data, 'PPM')
    return None if image.isNull() else image


def sources(frame, client_dir):
    found = {}
    if frame and frame.exists():
        found['Primary display'] = frame
    scanout = client_dir / 'dc-scanout.ppm'
    if scanout.exists():
        found['DC scanout'] = scanout
    for path in sorted(client_dir.glob('mhi2-client-*.ppm')):
        found['Client pid ' + path.stem.rsplit('-', 1)[1]] = path
    return found


def newest(found):
    stamped = []
    for name, path in found.items():
        try:
            stamped.append((path.stat().st_mtime_ns, name))
        except OSError:
            pass
    return max(stamped)[1] if stamped else None


class Viewer(QWidget):
    def __init__(self, frame, client_dir, kss=None, source=None, embedded_name=None):
        super().__init__()
        self.frame_path, self.client_dir = frame, client_dir
        self.setWindowTitle('FPK1 display')
        waiting = 'Waiting for QEMU scanout...' if source == 'DC scanout' else 'Waiting for glhost frames...'
        if embedded_name:
            from ui.embedded_qemu import EmbeddedQemu
            self.view = EmbeddedQemu(embedded_name)
        else:
            self.view = FrameView(1440, 540, waiting)
        self.choice = QComboBox()
        self.choice.addItem(FOLLOW)
        if source:
            self.choice.addItem(source)
            self.choice.setCurrentText(source)
        self.status = QLabel()
        if embedded_name:
            self.view.status.connect(self.status.setText)
        top = QHBoxLayout()
        top.addWidget(QLabel('Source:'))
        top.addWidget(self.choice, 1)
        self.keys_status = QLabel()
        middle = QHBoxLayout()
        middle.addWidget(self.view, 1)
        self.panel = InputPanel(kss, self.keys_status.setText)
        middle.addWidget(self.panel, 0, Qt.AlignVCenter)
        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main = QWidget()
        layout = QVBoxLayout(main)
        if not embedded_name:
            layout.addLayout(top)
        if kss:
            frame_area = QWidget()
            frame_area.setLayout(middle)
            middle.setContentsMargins(0, 0, 0, 0)
            self.kss_log = QPlainTextEdit()
            self.kss_log.setReadOnly(True)
            self.kss_log.setMaximumBlockCount(5000)
            self.kss_log.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
            self.kss_log.setPlaceholderText('Waiting for the KSS link...')
            self.kss_log.setMinimumHeight(self.kss_log.fontMetrics().lineSpacing() * 8 + 12)
            kss.line.connect(self.kss_log.appendPlainText)
            split = QSplitter(Qt.Vertical)
            split.addWidget(frame_area)
            split.addWidget(self.kss_log)
            split.setStretchFactor(0, 3)
            split.setStretchFactor(1, 1)
            layout.addWidget(split, 1)
        else:
            layout.addLayout(middle, 1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.keys_status)
        layout.addLayout(bottom)
        from ui.assist import AssistPanel
        self.assist = AssistPanel(kss, self.keys_status.setText)
        self.tabs.addTab(main, 'Log & wheel')
        self.tabs.addTab(self.assist, 'Driver assist')
        from ui.tpms import TpmsPanel
        self.tpms = TpmsPanel(kss, self.keys_status.setText)
        self.tabs.addTab(self.tpms, 'TPMS')
        from ui.navigation import NavigationPanel
        self.navigation = NavigationPanel(kss, self.keys_status.setText)
        self.tabs.addTab(self.navigation, 'Navigation')
        outer.addWidget(self.tabs)
        self.stamp = None
        self.timer = None
        if not embedded_name:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(100)

    def refresh(self):
        found = sources(self.frame_path, self.client_dir)
        known = {self.choice.itemText(i) for i in range(self.choice.count())}
        for name in found:
            if name not in known:
                self.choice.addItem(name)
        selected = self.choice.currentText()
        name = newest(found) if selected == FOLLOW else selected
        path = found.get(name)
        if path is None:
            return
        try:
            stamp = (name, path.stat().st_mtime_ns)
        except OSError:
            return
        if stamp == self.stamp:
            return
        image = read_ppm(path)
        if image is not None:
            self.view.frame, self.stamp = image, stamp
            self.status.setText(f'{name}: {image.width()}x{image.height()} ({path})')
            if name == 'DC scanout':
                try:
                    metadata = json.loads(path.with_suffix('.json').read_text())
                    detail = ('window ' + ','.join(metadata['active_windows'])
                              if metadata['complete'] else '; '.join(metadata['limitations']))
                    self.status.setText(f'{name}: {image.width()}x{image.height()} | {detail}')
                except (OSError, ValueError, KeyError):
                    self.status.setText(f'{name}: {image.width()}x{image.height()} | metadata pending')
            self.view.update()


class PeerWindow(QWidget):
    """KSS log/controls only; QEMU owns the live display window."""
    def __init__(self, kss=None):
        super().__init__()
        self.setWindowTitle('FPK1 KSS')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Display is shown in the QEMU window.'))
        self.tabs = QTabWidget()
        main = QWidget()
        middle = QHBoxLayout(main)
        self.kss_log = QPlainTextEdit()
        self.kss_log.setReadOnly(True)
        self.kss_log.setMaximumBlockCount(5000)
        self.kss_log.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.kss_log.setPlaceholderText('Waiting for the KSS link...' if kss else 'KSS peer disabled')
        if kss:
            kss.line.connect(self.kss_log.appendPlainText)
        middle.addWidget(self.kss_log, 1)
        self.keys_status = QLabel()
        self.panel = InputPanel(kss, self.keys_status.setText)
        middle.addWidget(self.panel)
        from ui.assist import AssistPanel
        self.assist = AssistPanel(kss, self.keys_status.setText)
        self.tabs.addTab(main, 'Log & wheel')
        self.tabs.addTab(self.assist, 'Driver assist')
        from ui.tpms import TpmsPanel
        self.tpms = TpmsPanel(kss, self.keys_status.setText)
        self.tabs.addTab(self.tpms, 'TPMS')
        from ui.navigation import NavigationPanel
        self.navigation = NavigationPanel(kss, self.keys_status.setText)
        self.tabs.addTab(self.navigation, 'Navigation')
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.keys_status)
        self.resize(900, 580)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', type=Path, default=Path('/tmp/glhost_frame.ppm'),
                        help='primary frame written by glhost (MHI2_GL_FRAME)')
    parser.add_argument('--client-dir', type=Path, default=Path('/tmp'),
                        help='directory of mhi2-client-<pid>.ppm dumps (MHI2_GL_CLIENT_DIR)')
    parser.add_argument('--snapshot', type=Path, help='save the newest frame as PNG and exit')
    parser.add_argument('--source', help='pin this source instead of following the newest client')
    parser.add_argument('--log-only', action='store_true',
                        help='only KSS log/controls; QEMU displays the image directly')
    parser.add_argument('--embed-qemu-name', help='embed the uniquely named native QEMU console')
    parser.add_argument('--kss', type=Path,
                        help="QEMU kss chardev socket; run kss_peer.py here and show its log")
    parser.add_argument('--kss-log', type=Path, help='also append the KSS log to this file')
    args = parser.parse_args()
    if args.snapshot:
        found = sources(args.frame, args.client_dir)
        name = args.source if args.source else newest(found)
        image = read_ppm(found[name]) if name in found else None
        if image is None or not image.save(str(args.snapshot)):
            raise SystemExit('no complete frame found')
        print(f'{name} -> {args.snapshot}')
        return
    app = QApplication(sys.argv)
    kss = KssPeer(args.kss, args.kss_log) if args.kss else None
    viewer = (PeerWindow(kss) if args.log_only else
              Viewer(args.frame, args.client_dir, kss, args.source, args.embed_qemu_name))
    fit_to_screen(viewer)
    viewer.show()
    if kss:
        kss.start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
