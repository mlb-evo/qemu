"""Local NavigationSD activation controls for the Qt viewer."""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, QSpinBox,
                               QPushButton, QHBoxLayout, QFormLayout, QCheckBox)
from hmi.navigation import DEFAULT, PRESETS, preset


class NavigationPanel(QWidget):
    def __init__(self, peer, report, parent=None):
        super().__init__(parent)
        self.peer, self.report = peer, report
        self.accepted = None
        root = QVBoxLayout(self)
        note = QLabel('Navigation / BAP NavSD (FSG 0x32). Activation sets bit 14 of '
                      'ConfigM Driverassist_Media (BAP_NAVIGATION_ACTIVE, coding bit 87) '
                      'and answers gtf2 on behalf of the navigation unit, including map settings (Menu R on the first tab). '
                      'The LVDS map is not emulated.')
        note.setWordWrap(True)
        root.addWidget(note)
        self.presets = QComboBox()
        self.presets.addItem('Choose a preset…', None)
        for key, (title, _) in PRESETS.items():
            self.presets.addItem(title, key)
        root.addWidget(self.presets)
        form = QFormLayout()
        self.operation = QSpinBox()
        self.operation.setRange(0, 255)
        self.operation.valueChanged.connect(self.edit)
        form.addRow('FSG_OperationState — code (0 = normal operation)', self.operation)
        self.carplay = QCheckBox('CarPlay item in "Map display" (SupportedMapViews bit 3, au736_evo patch)')
        self.carplay.setChecked(True)
        self.carplay.toggled.connect(self.edit)
        form.addRow(self.carplay)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.apply = QPushButton('Activate navigation')
        self.stop = QPushButton('Turn navigation off')
        buttons.addWidget(self.apply)
        buttons.addWidget(self.stop)
        root.addLayout(buttons)
        root.addStretch(1)
        self.status = QLabel('Navigation is off.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.presets.currentIndexChanged.connect(self.select_preset)
        self.apply.clicked.connect(lambda: self.submit(self.values()))
        self.stop.clicked.connect(self.select_off)
        for control in (self.presets, self.operation, self.carplay, self.apply, self.stop):
            control.setEnabled(peer is not None)

    def edit(self, *_):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(0)
        self.status.setText('Values changed. Press "Activate navigation".')

    def load(self, profile):
        with QSignalBlocker(self.operation), QSignalBlocker(self.carplay):
            self.operation.setValue(profile['operation'])
            self.carplay.setChecked(bool(profile['map_views'] & 8))

    def values(self):
        return dict(DEFAULT, operation=self.operation.value(),
                    map_views=DEFAULT['map_views'] if self.carplay.isChecked() else DEFAULT['map_views'] & ~8)

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
            self.status.setText('Could not queue navigation: KSS is stopped or the queue is full.')
            return
        self.accepted = deepcopy(profile)
        if profile is not None:
            self.load(profile)
        text = ('Navigation: turn-off queued to KSS.' if profile is None else
                f'Navigation activating: OperationState {profile["operation"]}.')
        self.status.setText(text)
        self.report(text)
