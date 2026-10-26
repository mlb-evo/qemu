import os
from pathlib import Path
import tempfile
import unittest

try:
    import view_frames
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

    def test_send_keys_needs_a_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / 'keys'
            os.mkfifo(fifo)
            self.assertFalse(view_frames.send_keys(fifo, b'5'))
            reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
            try:
                self.assertTrue(view_frames.send_keys(fifo, b'46'))
                self.assertEqual(os.read(reader, 16), b'46')
            finally:
                os.close(reader)
            self.assertFalse(view_frames.send_keys(Path(directory) / 'missing', b'0'))

    def test_wheel_buttons_use_grengme_console_keys(self):
        sent = {label: data for label, _, _, data in view_frames.WHEEL_BUTTONS}
        self.assertEqual((sent['OK'], sent['\u21a9'], sent['\u25b2'], sent['\u25bc']),
                         (b'5', b'0', b'4', b'6'))


if __name__ == '__main__':
    unittest.main()
