"""Local Qt Driver Assist controls, generated wire metadata only at runtime."""
import sys
sys.dont_write_bytecode = True
import re
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QTabWidget, QScrollArea,
                               QWidget, QFormLayout, QCheckBox, QComboBox, QSpinBox,
                               QGroupBox, QLineEdit)
from research.hmi.assist_catalog import SIGNALS, WARNINGS
from research.hmi.driver_assist import limits

GROUPS = {
    'ACC': ('ACC_KBI', 'ACC_HMI_Display', 'ACC_HMI_Ring', 'ACC_02', 'ACC_12', 'ACC_14', 'ACC_13_HMIStatus'),
    'Lane / lamps': ('LDW_02', 'TelltaleAALA_Display', 'TelltaleHMI_Display'),
    'Cruise / limiter': ('TSK_07',),
    'Signs': ('VZE_01', 'VZE_Timeout'),
    'Night Vision': ('HMI_C_NightVision_Display', 'HMI_C_NightVision_Parameters'),
    'Warnings': ('ZPM_HMI_Info',),
}


def label(key):
    key = re.sub(r'_(?:u?int\d+|sint\d+|b)$', '', key)
    key = re.sub(r'([a-z])([A-Z])', r'\1 \2', key)
    return key.replace('_', ' ')


class AssistPanel(QWidget):
    def __init__(self, peer, report, parent=None):
        super().__init__(parent)
        self.peer, self.report = peer, report
        self.controls, self.enables, self.accepted = {}, {}, {}
        root = QVBoxLayout(self)
        note = QLabel('Выберите сценарий: связанные состояния и команды показа отправятся вместе.\n'
                      'Сценарий заменяет текущие входы ассистентов; кодировка не меняется.')
        note.setWordWrap(True)
        root.addWidget(note)
        from research.hmi.assist_scenarios import LABELS
        self.scenario = QComboBox()
        self.scenario.addItem('Выберите сценарий…', None)
        for key, title in LABELS.items():
            self.scenario.addItem(title, key)
        self.scenario.setEnabled(peer is not None)
        self.scenario.currentIndexChanged.connect(self.apply_scenario)
        self.last_scenario = 0
        root.addWidget(self.scenario)
        self.advanced = QCheckBox('Расширенный режим — отдельные поля')
        root.addWidget(self.advanced)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter fields in the current tab…')
        root.addWidget(self.search)
        self.tabs = QTabWidget()
        self.rows = []
        for title, names in GROUPS.items():
            page = QWidget()
            layout = QVBoxLayout(page)
            for name in names:
                group = QGroupBox(name)
                form = QFormLayout(group)
                if name == 'ZPM_HMI_Info':
                    help_text = QLabel('Warning IDs cover all systems in this firmware. Text numbers are\n'
                                       'lookup IDs, not translated messages. Side Assist warnings use\n'
                                       'this route; its separate BAP operating-status session is not emulated.')
                    help_text.setWordWrap(True)
                    form.addRow(help_text)
                toggle = QCheckBox('Transmit')
                toggle.setEnabled(peer is not None)
                toggle.toggled.connect(lambda value, n=name: self.change(n, None, value))
                self.enables[name] = toggle
                self.accepted[name, None] = False
                form.addRow(toggle)
                for key, bits, signed in SIGNALS[name][2]:
                    lo, hi = limits(bits, signed)
                    if name == 'ZPM_HMI_Info' and key in ('ZPM_warnID_unit16', 'ZPM_popupID_unit16'):
                        control = QComboBox()
                        control.addItem('None', 0)
                        for warn, tid, kind in sorted(WARNINGS):
                            control.addItem(f'0x{warn:04X} · text {tid} · layout {kind}', warn)
                        control.setEditable(True)
                        control.setInsertPolicy(QComboBox.NoInsert)
                        control.completer().setFilterMode(Qt.MatchContains)
                        control.currentIndexChanged.connect(lambda i, n=name, k=key, c=control:
                            self.change(n, k, c.itemData(i)) if i >= 0 else None)
                    elif len(bits) == 1:
                        control = QCheckBox('On')
                        control.toggled.connect(lambda value, n=name, k=key: self.change(n, k, int(value)))
                    elif hi <= 15 and lo == 0:
                        control = QComboBox()
                        for value in range(hi + 1):
                            control.addItem(f'Value {value}', value)
                        control.currentIndexChanged.connect(lambda value, n=name, k=key: self.change(n, k, value))
                    else:
                        control = QSpinBox()
                        control.setRange(lo, hi)
                        control.valueChanged.connect(lambda value, n=name, k=key: self.change(n, k, value))
                    control.setEnabled(peer is not None)
                    control.setToolTip(key)
                    self.controls[name, key] = control
                    self.accepted[name, key] = 0
                    caption = QLabel(label(key))
                    caption.setWordWrap(True)
                    form.addRow(caption, control)
                    self.rows.append((page, caption, control, (name + ' ' + key).lower()))
                layout.addWidget(group)
            layout.addStretch(1)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, title)
        root.addWidget(self.tabs, 1)
        self.status = QLabel('Выберите сценарий. Отдельно включать Transmit не нужно.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.bottom_gap = QWidget()
        root.addWidget(self.bottom_gap, 1)
        self.search.textChanged.connect(self.filter)
        self.tabs.currentChanged.connect(lambda _: self.filter(self.search.text()))
        self.advanced.toggled.connect(self.show_advanced)
        self.show_advanced(False)

    def show_advanced(self, shown):
        self.search.setVisible(shown)
        self.tabs.setVisible(shown)
        self.bottom_gap.setVisible(not shown)

    def apply_scenario(self, index):
        key = self.scenario.itemData(index)
        if key is None:
            return
        if not self.peer or not self.peer.set_assist_scenario(key):
            with QSignalBlocker(self.scenario):
                self.scenario.setCurrentIndex(self.last_scenario)
            self.status.setText('Не удалось поставить сценарий в очередь KSS.')
            return
        from research.hmi.assist_scenarios import scenario
        profile = scenario(key)
        for name, button in self.enables.items():
            enabled = name in profile
            with QSignalBlocker(button):
                button.setChecked(enabled)
            self.accepted[name, None] = enabled
        for (name, field), control in self.controls.items():
            value = profile.get(name, {}).get(field, 0)
            with QSignalBlocker(control):
                if isinstance(control, QCheckBox):
                    control.setChecked(bool(value))
                elif isinstance(control, QSpinBox):
                    control.setValue(value)
                else:
                    control.setCurrentIndex(control.findData(value))
            self.accepted[name, field] = value
        self.last_scenario = index
        title = self.scenario.itemText(index)
        self.status.setText('Сценарий поставлен в очередь KSS: ' + title)
        self.report('Assist scenario: ' + key)

    def filter(self, text):
        text = text.lower().strip()
        for _, caption, control, key in self.rows:
            visible = not text or text in key
            caption.setVisible(visible)
            control.setVisible(visible)

    def change(self, name, field, value):
        if self.peer and self.peer.set_assist(name, field, value):
            with QSignalBlocker(self.scenario):
                self.scenario.setCurrentIndex(0)
            self.last_scenario = 0
            self.accepted[name, field] = value
            detail = f'{name}.{field}={value}' if field else f'{name}: transmit={value}'
            self.status.setText('Queued: ' + detail)
            self.report('Assist: ' + detail)
            return
        control = self.enables[name] if field is None else self.controls[name, field]
        old = self.accepted[name, field]
        with QSignalBlocker(control):
            if isinstance(control, QCheckBox):
                control.setChecked(bool(old))
            elif isinstance(control, QSpinBox):
                control.setValue(old)
            else:
                control.setCurrentIndex(control.findData(old))
        self.status.setText('Cannot queue input: KSS stopped or input queue full.')
