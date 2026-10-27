"""Local regressions: no PPM output from glhost; KSS-only UI has no image reader."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import view_frames


class Checks(unittest.TestCase):
    def test_glhost_no_ppm_flag_suppresses_primary_and_client_files(self):
        def record(op, payload=b''):
            return struct.pack('<II', op, len(payload)) + payload
        commands = (record(1, struct.pack('<II', 4, 4)) +
                    record(3, struct.pack('<ffff', 1, 0, 0, 1)) +
                    record(4, struct.pack('<I', 0x4000)) + record(5))
        for disabled in (False, True):
            with self.subTest(disabled=disabled), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                env = dict(os.environ, MHI2_GL_FRAME=str(root / 'primary.ppm'),
                           MHI2_GL_CLIENT_DIR=str(root), MHI2_GL_DUMP_CLIENTS='1',
                           MHI2_GL_WIDTH='4', MHI2_GL_HEIGHT='4')
                env.pop('MHI2_GL_NO_PPM', None)
                if disabled:
                    env['MHI2_GL_NO_PPM'] = '1'
                result = subprocess.run([REPO / 'build-fpk1/bridge/glhost'], input=commands,
                                        env=env, cwd=root, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                files = sorted(p.name for p in root.glob('*.ppm'))
                self.assertEqual(files, [] if disabled else ['mhi2-client-0.ppm', 'primary.ppm'])

    def test_log_only_ui_does_not_create_frame_view_or_polling_timer(self):
        app = QApplication.instance() or QApplication([])
        peer = view_frames.KssPeer(Path('/unused'), None)
        window = view_frames.PeerWindow(kss=peer)
        peer.line.emit('KSS test message')
        self.assertIn('KSS test message', window.kss_log.toPlainText())
        self.assertEqual(window.findChildren(view_frames.FrameView), [])
        self.assertEqual(window.findChildren(QTimer), [])
        window.close()
        del app


if __name__ == '__main__':
    unittest.main()
