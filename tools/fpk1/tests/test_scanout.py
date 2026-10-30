"""Local checks for scanout provenance, snapshot consistency and viewer pinning."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from hmi.capture_scanout import ScanoutCapture, assess
from PySide6.QtWidgets import QApplication
from ui import viewer as view_frames


def single_plane():
    windows = []
    for name in 'ABC':
        r = {f'{i:03x}': 0 for i in range(0x700, 0x840)}
        windows.append(dict(name=name, registers=r))
    windows[0]['registers'].update({
        '700': 0x40010004, '703': 13, '705': (540 << 16) | 1440,
        '709': 0x10001000, '70a': 5760, '800': 0x9f718000,
        '701': 2, '808': 539, '710': 0xffff00})
    return dict(display_active=(540 << 16) | 1440, display_command=0x20,
                display_options=0, windows=windows)


class Checks(unittest.TestCase):
    def test_full_panel_and_unsupported_layouts(self):
        state = single_plane()
        self.assertTrue(assess(state)['complete'])
        state['windows'][1]['registers']['700'] = 1 << 30
        self.assertFalse(assess(state)['complete'])
        state = single_plane()
        state['windows'][0]['registers']['806'] = 32
        self.assertFalse(assess(state)['complete'])
        state = single_plane()
        state['windows'][0]['registers']['709'] = 0x20002000
        self.assertFalse(assess(state)['complete'])

    def test_snapshot_stops_before_read_and_resumes_before_file_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def qmp(proc, command, arguments=None):
                calls.append(command)
                if command == 'qom-get':
                    return json.dumps(single_plane())
                if command == 'screendump':
                    Path(arguments['filename']).write_bytes(b'P6\n1 1\n255\n\xff\x00\x00')
                if command == 'cont':
                    self.assertFalse((Path(directory) / 'dc-scanout.ppm').exists())

            capture = ScanoutCapture(directory, qmp)
            capture.capture(None, 1.5)
            self.assertEqual(calls, ['stop', 'qom-get', 'screendump', 'cont'])
            self.assertTrue(json.loads((Path(directory) / 'dc-scanout.json').read_text())['complete'])
            capture.capture(None, 1.6)
            self.assertEqual(len(calls), 4, 'capture rate is bounded')

    def test_capture_error_resumes_vm(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def qmp(proc, command, arguments=None):
                calls.append(command)
                if command == 'qom-get':
                    return json.dumps(single_plane())
                if command == 'screendump':
                    raise RuntimeError('test failure')

            with self.assertRaises(RuntimeError):
                ScanoutCapture(directory, qmp).capture(None, 0)
            self.assertEqual(calls[-1], 'cont')

    def test_newer_client_does_not_replace_selected_scanout(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scanout = root / 'dc-scanout.ppm'
            scanout.write_bytes(b'P6\n1 1\n255\n\xff\x00\x00')
            client = root / 'mhi2-client-123.ppm'
            client.write_bytes(b'P6\n1 1\n255\n\x00\xff\x00')
            os.utime(scanout, ns=(1, 1))
            os.utime(client, ns=(2, 2))
            viewer = view_frames.Viewer(root / 'primary.ppm', root, source='DC scanout')
            viewer.refresh()
            self.assertEqual(viewer.choice.currentText(), 'DC scanout')
            self.assertEqual(viewer.view.frame.pixelColor(0, 0).red(), 255)
            self.assertEqual(viewer.view.frame.pixelColor(0, 0).green(), 0)
            viewer.timer.stop()
            viewer.close()
        del app


if __name__ == '__main__':
    unittest.main()
