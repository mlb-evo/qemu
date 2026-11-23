"""Local driving presets for the Qt viewer: speed, engine speed and gear."""
import sys
sys.dont_write_bytecode = True
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget
from hmi.driving import PRESETS


class DrivingPanel(QWidget):
    def __init__(self, peer, report, parent=None):
        super().__init__(parent)
        self.peer, self.report = peer, report
        root = QVBoxLayout(self)
        note = QLabel('Пресет повторяется по кругу: скорость (SPD_HMI_01), обороты '
                      '(TCH_HMI_EngineRPM) и передача (Gear_Display) отправляются 10 раз в секунду. '
                      'Свет и ассистенты — на вкладке Driver assist.')
        note.setWordWrap(True)
        root.addWidget(note)
        self.presets = QComboBox()
        self.presets.addItem('Выберите пресет…', None)
        for key, (title, _) in PRESETS.items():
            self.presets.addItem(title, key)
        self.presets.currentIndexChanged.connect(self.select)
        root.addWidget(self.presets)
        self.stop = QPushButton('Остановить')
        self.stop.clicked.connect(lambda: self.presets.setCurrentIndex(0))
        root.addWidget(self.stop)
        self.status = QLabel('Пресет не выбран: скорость не отправляется.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch(1)
        self.last = 0
        for control in (self.presets, self.stop):
            control.setEnabled(peer is not None)

    def select(self, index):
        key = self.presets.itemData(index)
        if not self.peer or not self.peer.set_assist('@driving', None, key):
            with QSignalBlocker(self.presets):
                self.presets.setCurrentIndex(self.last)
            self.report('Пресет не отправлен: KSS остановлен или очередь заполнена')
            return
        self.last = index
        text = f'Пресет: {PRESETS[key][0]}' if key else 'Пресет остановлен.'
        self.status.setText(text)
        self.report(text)
