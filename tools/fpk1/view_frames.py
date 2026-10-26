#!/usr/bin/env python3
"""Show FPK1 frames rendered by glhost in a host window (no display-path changes).

glhost writes the primary display frame (MHI2_GL_FRAME) and, with
MHI2_GL_DUMP_CLIENTS=1, one PPM per guest client process
(MHI2_GL_CLIENT_DIR/mhi2-client-<pid>.ppm) on every swap, atomically via
rename. This viewer lists those sources, follows the most recently updated one
unless a source is chosen, and polls for new frames. `--snapshot FILE.png`
saves the current frame without opening a window (usable headless).
These are host-rendered GLES frames, not the guest display controller.

With --keys FIFO (run_stage1_console.py passes one), a steering-wheel button
panel types keys on the guest serial console using grengme's console key
bytes (libengmenufw): '4'/'6' turn the roller by -1/+1 tick, '5' selects,
'0' goes back. The firmware disables that backend (/config/gem.json
"consoleInput":false) and grengme's stdin is not the console, so these bytes
reach the login shell, not the menu. In the car the buttons reach the HMI
through KSS (MFL_Tasten_Kon_01 -> gss_ipc -> gtf2); moving the panel onto
tools/fpk1/kss_peer.py is the intended route.

With --kss SOCKET the viewer is also the KSS peer: it runs kss_peer.py's SPI
master in a thread on QEMU's kss chardev and shows its log under the frame
(and appends it to --kss-log). Closing the window stops the peer.
"""
import argparse
import os
from pathlib import Path
import sys
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase, QImage
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QHBoxLayout,
                               QLabel, QPlainTextEdit, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'mhi2'))
from viewer_widgets import FrameView, fit_to_screen  # noqa: E402

FOLLOW = 'Most recent'

# Right steering-wheel cluster: (label, row, column, console byte or None).
# The roller's up/down are its turn direction. Keys are sent only by clicking
# these buttons (no mouse-wheel or keyboard shortcuts).
WHEEL_BUTTONS = (
    ('\u25c1', 0, 0, None),
    ('\u25b7', 0, 1, None),
    ('\u25b2', 1, 0, b'4'),
    ('VIEW', 1, 1, None),
    ('OK', 2, 0, b'5'),
    ('\u21a9', 2, 1, b'0'),
    ('\u25bc', 3, 0, b'6'),
)


def send_keys(path, data):
    """Write bytes to the launcher's key FIFO; False when nobody reads it."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        return os.write(fd, data) == len(data)
    except OSError:
        return False
    finally:
        os.close(fd)


class WheelPanel(QWidget):
    def __init__(self, keys, report):
        super().__init__()
        self.keys, self.report = keys, report
        grid = QGridLayout(self)
        grid.addWidget(QLabel('Steering wheel'), 4, 0, 1, 2, Qt.AlignHCenter)
        for label, row, column, data in WHEEL_BUTTONS:
            button = QToolButton()
            button.setText(label)
            button.setMinimumSize(56, 40)
            if data is None:
                button.setEnabled(False)
                button.setToolTip('No console key in grengme (needs the KSS path)')
            else:
                button.setToolTip(f'Types {data.decode()!r} on the console')
                button.clicked.connect(lambda _=False, d=data: self.press(d))
            grid.addWidget(button, row, column)

    def press(self, data):
        if send_keys(self.keys, data):
            self.report(f'sent {data.decode()!r}')
        else:
            self.report(f'cannot send {data.decode()!r}: no reader on {self.keys}')


class KssPeer(QObject):
    """kss_peer.run in a daemon thread; each log line arrives as `line`."""
    line = Signal(str)

    def __init__(self, socket_path, log_path=None):
        super().__init__()
        self.socket_path = str(socket_path)
        self.log_file = log_path.open('a', buffering=1) if log_path else None

    def start(self):
        threading.Thread(target=self.serve, name='kss', daemon=True).start()

    def emit(self, text):
        if self.log_file:
            self.log_file.write(text + '\n')
        self.line.emit(text)

    def serve(self):
        import kss_peer
        try:
            kss_peer.run(self.socket_path, 0.01, self.emit)
        except (OSError, SystemExit) as error:
            self.emit(f'[kss] stopped: {error}')


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
    def __init__(self, frame, client_dir, keys=None, kss=None):
        super().__init__()
        self.frame_path, self.client_dir = frame, client_dir
        self.setWindowTitle('FPK1 glhost frames')
        self.view = FrameView(1440, 540, 'Waiting for glhost frames...')
        self.choice = QComboBox()
        self.choice.addItem(FOLLOW)
        self.status = QLabel()
        top = QHBoxLayout()
        top.addWidget(QLabel('Source:'))
        top.addWidget(self.choice, 1)
        self.keys_status = QLabel()
        middle = QHBoxLayout()
        middle.addWidget(self.view, 1)
        self.panel = None
        if keys:
            self.panel = WheelPanel(keys, self.keys_status.setText)
            middle.addWidget(self.panel, 0, Qt.AlignVCenter)
        layout = QVBoxLayout(self)
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
        self.stamp = None
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
            self.view.update()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', type=Path, default=Path('/tmp/glhost_frame.ppm'),
                        help='primary frame written by glhost (MHI2_GL_FRAME)')
    parser.add_argument('--client-dir', type=Path, default=Path('/tmp'),
                        help='directory of mhi2-client-<pid>.ppm dumps (MHI2_GL_CLIENT_DIR)')
    parser.add_argument('--snapshot', type=Path, help='save the newest frame as PNG and exit')
    parser.add_argument('--keys', type=Path,
                        help="launcher key FIFO (run_stage1_console.py --keys); shows the button panel")
    parser.add_argument('--kss', type=Path,
                        help="QEMU kss chardev socket; run kss_peer.py here and show its log")
    parser.add_argument('--kss-log', type=Path, help='also append the KSS log to this file')
    args = parser.parse_args()
    if args.snapshot:
        found = sources(args.frame, args.client_dir)
        name = newest(found)
        image = read_ppm(found[name]) if name else None
        if image is None or not image.save(str(args.snapshot)):
            raise SystemExit('no complete frame found')
        print(f'{name} -> {args.snapshot}')
        return
    app = QApplication(sys.argv)
    kss = KssPeer(args.kss, args.kss_log) if args.kss else None
    viewer = Viewer(args.frame, args.client_dir, args.keys, kss)
    fit_to_screen(viewer)
    viewer.show()
    if kss:
        kss.start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
