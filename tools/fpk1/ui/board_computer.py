"""Local board computer controls for the Qt viewer: trips, consumption, range."""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget)
from hmi.board_computer import DEFAULT, PRESETS, preset

TRIP_TITLES = (('short', 'С момента старта'), ('tank', 'С заправки'), ('long', 'Длительно'))
TRIP_FIELDS = (('distance', 'км', 1), ('minutes', 'мин', 0), ('cons', 'л/100', 1),
               ('speed', 'км/ч', 0))
VALUES = (('range', 'Запас хода, км', 0, 9999), ('current_cons', 'Текущий расход, л/100 км', 1, 99.9),
          ('current_cons_h', 'Текущий расход, л/ч', 1, 99.9),
          ('odometer', 'Одометр, км', 0, 999999), ('trip', 'Суточный пробег, км', 1, 99999.9))


def spin(decimals, hi):
    box = QDoubleSpinBox() if decimals else QSpinBox()
    if decimals:
        box.setDecimals(decimals)
    box.setRange(0, hi)
    return box


class BoardComputerPanel(QWidget):
    def __init__(self, peer, report, parent=None):
        super().__init__(parent)
        self.peer, self.report = peer, report
        root = QVBoxLayout(self)
        note = QLabel('Бортовой компьютер: BC_HMI_ShortTerm / TankCycle / LongTerm, BC_HMI_Range, '
                      'BC_HMI_CurrentCons, ODO_HMI_Distance и часы (CLK_HMI_dateTime, время '
                      'хоста) раз в секунду. «Живые данные» копят пробег, время и расход по '
                      'пресету на вкладке «Движение». Единицы предположительные.')
        note.setWordWrap(True)
        root.addWidget(note)
        self.presets = QComboBox()
        self.presets.addItem('Выберите пресет…', None)
        for key, (title, _) in PRESETS.items():
            self.presets.addItem(title, key)
        root.addWidget(self.presets)
        grid = QGridLayout()
        self.trips = {}
        for column, (_, unit, _) in enumerate(TRIP_FIELDS, 1):
            grid.addWidget(QLabel(unit), 0, column)
        for row, (name, title) in enumerate(TRIP_TITLES, 1):
            grid.addWidget(QLabel(title), row, 0)
            for column, (key, _, decimals) in enumerate(TRIP_FIELDS, 1):
                box = spin(decimals, {'distance': 999999.9, 'minutes': 999999, 'cons': 99.9,
                                      'speed': 300}[key])
                box.valueChanged.connect(self.edit)
                grid.addWidget(box, row, column)
                self.trips[name, key] = box
        root.addLayout(grid)
        form = QFormLayout()
        self.values = {}
        for key, title, decimals, hi in VALUES:
            box = spin(decimals, hi)
            box.valueChanged.connect(self.edit)
            form.addRow(title, box)
            self.values[key] = box
        self.live = QCheckBox('Живые данные (по пресету движения)')
        self.live.setChecked(True)
        self.live.toggled.connect(self.edit)
        form.addRow(self.live)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.apply = QPushButton('Отправить')
        self.stop = QPushButton('Остановить')
        buttons.addWidget(self.apply)
        buttons.addWidget(self.stop)
        root.addLayout(buttons)
        root.addStretch(1)
        self.status = QLabel('Данные бортового компьютера не отправляются.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.presets.currentIndexChanged.connect(self.select_preset)
        self.apply.clicked.connect(lambda: self.submit(self.profile()))
        self.stop.clicked.connect(lambda: self.submit(None))
        for control in (self.presets, self.live, self.apply, self.stop, *self.trips.values(),
                        *self.values.values()):
            control.setEnabled(peer is not None)

    def edit(self, *_):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(0)
        self.status.setText('Значения изменены. Нажмите «Отправить».')

    def load(self, profile):
        for (name, key), box in self.trips.items():
            with QSignalBlocker(box):
                box.setValue(profile[name][key])
        for key, box in self.values.items():
            with QSignalBlocker(box):
                box.setValue(profile[key])
        with QSignalBlocker(self.live):
            self.live.setChecked(profile['live'])

    def profile(self):
        result = deepcopy(DEFAULT)
        for (name, key), box in self.trips.items():
            result[name][key] = box.value()
        for key, box in self.values.items():
            result[key] = box.value()
        result['live'] = self.live.isChecked()
        return result

    def select_preset(self, index):
        key = self.presets.itemData(index)
        if key is not None:
            self.submit(preset(key))

    def submit(self, profile):
        if not self.peer or not self.peer.set_assist('@board', None, profile):
            with QSignalBlocker(self.presets):
                self.presets.setCurrentIndex(0)
            self.status.setText('Не удалось поставить в очередь: KSS остановлен или очередь '
                                'заполнена.')
            return
        if profile is None:
            with QSignalBlocker(self.presets):
                self.presets.setCurrentIndex(0)
            text = 'Бортовой компьютер: отправка остановлена.'
        else:
            self.load(profile)
            text = (f'Бортовой компьютер: запас хода {profile["range"]} км, '
                    f'{"живые данные" if profile["live"] else "статичные данные"}.')
        self.status.setText(text)
        self.report(text)
