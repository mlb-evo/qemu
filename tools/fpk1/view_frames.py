#!/usr/bin/env python3
"""Show FPK1 frames rendered by glhost in a host window (no display-path changes).

glhost writes the primary display frame (MHI2_GL_FRAME) and, with
MHI2_GL_DUMP_CLIENTS=1, one PPM per guest client process
(MHI2_GL_CLIENT_DIR/mhi2-client-<pid>.ppm) on every swap, atomically via
rename. This viewer lists those sources, follows the most recently updated one
unless a source is chosen, and polls for new frames. `--snapshot FILE.png`
saves the current frame without opening a window (usable headless).
These are host-rendered GLES frames, not the guest display controller.
"""
import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
                               QVBoxLayout, QWidget)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'mhi2'))
from viewer_widgets import FrameView, fit_to_screen  # noqa: E402

FOLLOW = 'Most recent'


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
    def __init__(self, frame, client_dir):
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
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.status)
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
    viewer = Viewer(args.frame, args.client_dir)
    fit_to_screen(viewer)
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
