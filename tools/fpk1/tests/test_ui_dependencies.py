"""Keep the local viewer usable without research scripts or analysis engines."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class DependencyTests(unittest.TestCase):
    def test_ui_and_inputs_run_with_research_imports_blocked(self):
        tools = Path(__file__).resolve().parents[1]
        script = '''
import importlib.abc
import sys
class BlockResearch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('research', 'capstone', 'unicorn', 'tests'):
            raise AssertionError('UI imported an analysis dependency: ' + fullname)
sys.meta_path.insert(0, BlockResearch())
from pathlib import Path
from queue import Queue
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
import kss_peer
from hmi.configm import DEFAULT_CODING
from hmi.assist_scenarios import LABELS, scenario
from hmi.driver_assist import pack
from hmi.tpms import preset
from hmi.navigation import preset as navigation_preset
from ui.viewer import KssPeer, PeerWindow, Viewer
import view_frames
assert view_frames.Viewer is Viewer
peer = kss_peer.Kss(lambda _: None, coding=DEFAULT_CODING, assist_commands=Queue())
peer.application_running = True
for key in LABELS:
    for name, values in scenario(key).items():
        pack(name, values)
peer.assist.traffic.select('traffic_red')
peer.assist.tpms.select(preset('values_30'))
peer.assist.navigation.select(navigation_preset('normal'))
peer.assist.send()
assert peer.outbox
app = QApplication([])
proxy = KssPeer(Path('/unused'))
for window in (PeerWindow(proxy), Viewer(Path('/unused.ppm'), Path('/unused'), proxy)):
    window.tpms.submit(preset('values_30'))
    window.panel.wheel.press('side_left')
    window.navigation.submit(navigation_preset('normal'))
    window.close()
    window.deleteLater()
proxy.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
'''
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=tools,
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
