"""Local NavigationSD activation controls for the Qt viewer."""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, QSpinBox,
                               QPushButton, QHBoxLayout, QFormLayout)
from hmi.navigation import DEFAULT, PRESETS, preset


class NavigationPanel(QWidget):
    def __init__(self, peer, report, parent=None):
        super().__init__(parent)
        self.peer, self.report = peer, report
        self.accepted = None
        root = QVBoxLayout(self)
        note = QLabel('Navigation / BAP NavSD (FSG 0x32). Активация включает бит 14 '
                      'ConfigM Driverassist_Media (BAP_NAVIGATION_ACTIVE, бит кодировки 87) '
                      'и отвечает gtf2 от имени блока навигации, включая настройки карты (Menu R на первой вкладке). '
                      'Карта по LVDS не эмулируется.')
        note.setWordWrap(True)
        root.addWidget(note)
        self.presets = QComboBox()
        self.presets.addItem('Выберите пресет…', None)
        for key, (title, _) in PRESETS.items():
            self.presets.addItem(title, key)
        root.addWidget(self.presets)
        form = QFormLayout()
        self.operation = QSpinBox()
        self.operation.setRange(0, 255)
        self.operation.valueChanged.connect(self.edit)
        form.addRow('FSG_OperationState — код (0 = рабочий режим)', self.operation)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.apply = QPushButton('Активировать навигацию')
        self.stop = QPushButton('Выключить навигацию')
        buttons.addWidget(self.apply)
        buttons.addWidget(self.stop)
        root.addLayout(buttons)
        root.addStretch(1)
        self.status = QLabel('Навигация выключена.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.presets.currentIndexChanged.connect(self.select_preset)
        self.apply.clicked.connect(lambda: self.submit(self.values()))
        self.stop.clicked.connect(self.select_off)
        for control in (self.presets, self.operation, self.apply, self.stop):
            control.setEnabled(peer is not None)

    def edit(self, *_):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(0)
        self.status.setText('Значения изменены. Нажмите «Активировать навигацию».')

    def load(self, profile):
        with QSignalBlocker(self.operation):
            self.operation.setValue(profile['operation'])

    def values(self):
        return dict(DEFAULT, operation=self.operation.value())

    def select_preset(self, index):
        key = self.presets.itemData(index)
        if key is not None:
            self.submit(preset(key))

    def select_off(self):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(self.presets.findData('off'))
        self.submit(None)

    def submit(self, profile):
        if not self.peer or not self.peer.set_assist('@navigation', None, profile):
            with QSignalBlocker(self.presets):
                self.presets.setCurrentIndex(0)
            if self.accepted is not None:
                self.load(self.accepted)
            self.status.setText('Не удалось поставить навигацию в очередь: KSS остановлен или очередь заполнена.')
            return
        self.accepted = deepcopy(profile)
        if profile is not None:
            self.load(profile)
        text = ('Навигация: выключение поставлено в очередь KSS.' if profile is None else
                f'Навигация активируется: OperationState {profile["operation"]}.')
        self.status.setText(text)
        self.report(text)
