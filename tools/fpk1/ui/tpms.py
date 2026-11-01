"""Local TPMS value presets and atomic manual updates for the Qt viewer."""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox,
                               QGridLayout, QSpinBox, QPushButton, QHBoxLayout,
                               QCheckBox, QScrollArea)
from hmi.tpms import DEFAULT, PRESETS, WHEELS, preset


class TpmsPanel(QWidget):
    def __init__(self, peer, report, parent=None):
        super().__init__(parent)
        self.peer, self.report = peer, report
        self.accepted = None
        self.controls = {}
        root = QVBoxLayout(self)
        note = QLabel('TPMS / RDK — давление, температура и состояния четырёх колёс.\n'
                      'Поля содержат коды BAP: при единицах 0 давление = код / 10 bar, температура = код − 60 °C. '
                      'Открыть экран кнопками руля на первой вкладке: вкладка автомобиля (заправка) → Меню L → Sport displays → OK. '
                      'Затем меняйте пресеты. Коды состояний пока не расшифрованы.')
        note.setWordWrap(True)
        root.addWidget(note)
        self.presets = QComboBox()
        self.presets.addItem('Выберите пресет…', None)
        for key, (title, _) in PRESETS.items():
            self.presets.addItem(title, key)
        root.addWidget(self.presets)
        page = QWidget()
        grid = QGridLayout(page)
        grid.setAlignment(Qt.AlignTop)
        titles = ('Колесо', 'Давление\n0…255', 'Температура\n0…255', 'Заданное давление\n0…255',
                  'Состояние давления\n0…15', 'Состояние температуры\n0…15')
        for col, title in enumerate(titles):
            grid.addWidget(QLabel(title), 0, col)
        fields = ('pressure', 'temperature', 'required', 'state', 'temperature_state')
        for row, (wheel, title) in enumerate(zip(WHEELS, ('Переднее левое', 'Переднее правое',
                                                       'Заднее левое', 'Заднее правое')), 1):
            grid.addWidget(QLabel(f'{title} ({wheel})'), row, 0)
            for col, field in enumerate(fields, 1):
                control = self.spin(field, row - 1, 15 if field.endswith('state') else 255)
                grid.addWidget(control, row, col)
        for row, (key, title) in enumerate((('pressure_unit', 'Единица давления — код'),
                                           ('temperature_unit', 'Единица температуры — код'),
                                           ('collected', 'Общее состояние — код'),
                                           ('operation', 'Рабочее состояние — код (0 = рабочий режим)')), 5):
            grid.addWidget(QLabel(title), row, 0, 1, 2)
            grid.addWidget(self.spin(key, None, 255), row, 2)
        self.lamp = QCheckBox('Лампа RDK (tt_rdk_b = 1)')
        self.lamp.toggled.connect(self.edit)
        grid.addWidget(self.lamp, 9, 0, 1, 6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        root.addWidget(scroll, 1)
        buttons = QHBoxLayout()
        self.apply = QPushButton('Отправить значения')
        self.stop = QPushButton('Остановить TPMS')
        buttons.addWidget(self.apply)
        buttons.addWidget(self.stop)
        root.addLayout(buttons)
        self.status = QLabel('Передача TPMS выключена.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.load(DEFAULT)
        self.presets.currentIndexChanged.connect(self.select_preset)
        self.apply.clicked.connect(lambda: self.submit(self.values()))
        self.stop.clicked.connect(lambda: self.select_off())
        for control in (self.presets, self.apply, self.stop, self.lamp, *self.controls.values()):
            control.setEnabled(peer is not None)

    def spin(self, key, index, maximum):
        control = QSpinBox()
        control.setRange(0, maximum)
        control.valueChanged.connect(self.edit)
        self.controls[key, index] = control
        return control

    def edit(self, *_):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(0)
        self.status.setText('Значения изменены. Нажмите «Отправить значения».')

    def load(self, profile):
        for (key, index), control in self.controls.items():
            with QSignalBlocker(control):
                control.setValue(profile[key] if index is None else profile[key][index])
        with QSignalBlocker(self.lamp):
            self.lamp.setChecked(bool(profile['lamp']))

    def values(self):
        result = deepcopy(DEFAULT)
        for (key, index), control in self.controls.items():
            if index is None:
                result[key] = control.value()
            else:
                result[key][index] = control.value()
        result['lamp'] = int(self.lamp.isChecked())
        return result

    def select_preset(self, index):
        key = self.presets.itemData(index)
        if key is not None:
            self.submit(preset(key))

    def select_off(self):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(self.presets.findData('off'))
        self.submit(None)

    def submit(self, profile):
        if not self.peer or not self.peer.set_assist('@tpms', None, profile):
            with QSignalBlocker(self.presets):
                self.presets.setCurrentIndex(0)
            if self.accepted is not None:
                self.load(self.accepted)
            self.status.setText('Не удалось поставить TPMS в очередь: KSS остановлен или очередь заполнена.')
            return
        self.accepted = deepcopy(profile)
        if profile is not None:
            self.load(profile)
        text = ('TPMS: остановка поставлена в очередь KSS.' if profile is None else
                f'TPMS в очереди KSS: давление {profile["pressure"]}; '
                f'температура {profile["temperature"]}; лампа {profile["lamp"]}.')
        self.status.setText(text)
        self.report(text)
