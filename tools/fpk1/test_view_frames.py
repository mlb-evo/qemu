import os
from pathlib import Path
import tempfile
import unittest

try:
    from ui import viewer as view_frames
except ImportError:  # PySide6 QtGui/QtWidgets not installed
    view_frames = None


def ppm(width, height, body=None):
    data = body if body is not None else bytes(width * height * 3)
    return b'P6\n%d %d\n255\n' % (width, height) + data


@unittest.skipIf(view_frames is None, 'PySide6 is not installed')
class ViewFramesTests(unittest.TestCase):
    def test_reads_complete_ppm_and_rejects_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'frame.ppm'
            path.write_bytes(ppm(4, 2))
            image = view_frames.read_ppm(path)
            self.assertEqual((image.width(), image.height()), (4, 2))
            path.write_bytes(ppm(4, 2, bytes(10)))
            self.assertIsNone(view_frames.read_ppm(path))
            path.write_bytes(b'P5\n1 1\n255\n\0')
            self.assertIsNone(view_frames.read_ppm(path))

    def test_lists_sources_and_follows_newest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / 'primary.ppm'
            client = root / 'mhi2-client-458785.ppm'
            primary.write_bytes(ppm(2, 2))
            client.write_bytes(ppm(2, 2))
            os.utime(primary, ns=(1, 1))
            os.utime(client, ns=(2, 2))
            found = view_frames.sources(primary, root)
            self.assertEqual(set(found), {'Primary display', 'Client pid 458785'})
            self.assertEqual(view_frames.newest(found), 'Client pid 458785')
            os.utime(primary, ns=(3, 3))
            self.assertEqual(view_frames.newest(found), 'Primary display')
            self.assertIsNone(view_frames.newest({}))

    def test_wheel_buttons_use_mfl_actions(self):
        sent = {label: data for label, _, _, data in view_frames.WHEEL_BUTTONS}
        self.assertEqual((sent['OK'], sent['\u21a9'], sent['\u25b2'], sent['\u25bc']),
                         ('ok', 'back', 'up', 'down'))


if __name__ == '__main__':
    unittest.main()
