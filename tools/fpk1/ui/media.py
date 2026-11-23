"""Local AudioSD (radio / media now playing) controls for the Qt viewer."""
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)
from hmi.media import DEFAULT, PRESETS, preset

TEXTS = (('source_name', 'ActiveSourceName'), ('primary', 'Primary (станция / трек)'),
         ('secondary', 'Secondary (радиотекст / артист)'), ('tertiary', 'Tertiary (альбом)'))
NUMBERS = (('source_type', 'SourceType (2 FM, 3 DAB, 0x0f USB, 0x0b SD, 0x0d AUX)', 255),
           ('primary_type', 'PI_Type', 255), ('secondary_type', 'SI_Type (0x49 артист)', 255),
           ('tertiary_type', 'TI_Type (0x4a альбом)', 255),
           ('position', 'PlayPosition, с', 0xffff), ('total', 'Длительность, с', 0xffff),
           ('state', 'SourceState StateInfo', 255), ('mute', 'MuteState', 255),
           ('list_available', 'ListAvailable (бит 0: список станций)', 15))


class MediaPanel(QWidget):
    def __init__(self, peer, report, parent=None):
        super().__init__(parent)
        self.peer, self.report = peer, report
        self.accepted = None
        root = QVBoxLayout(self)
        note = QLabel('Аудио / BAP AudioSD (FSG 0x31). Активация включает бит 5 ConfigM '
                      'Driverassist_Media (BAP_AUDIO_ACTIVE) и отвечает gtf2 от имени MMI: '
                      'источник, название станции или трека, артист, альбом и позиция. '
                      'Позиция играющего трека растёт раз в секунду.')
        note.setWordWrap(True)
        root.addWidget(note)
        self.presets = QComboBox()
        self.presets.addItem('Выберите пресет…', None)
        for key, (title, _) in PRESETS.items():
            self.presets.addItem(title, key)
        root.addWidget(self.presets)
        form = QFormLayout()
        self.fields = {}
        for key, title in TEXTS:
            edit = QLineEdit()
            edit.setMaxLength(60)
            edit.textEdited.connect(self.edit)
            form.addRow(title, edit)
            self.fields[key] = edit
        for key, title, hi in NUMBERS:
            spin = QSpinBox()
            spin.setRange(0, hi)
            if hi in (15, 255):
                spin.setDisplayIntegerBase(16)
                spin.setPrefix('0x')
            spin.valueChanged.connect(self.edit)
            form.addRow(title, spin)
            self.fields[key] = spin
        self.playing = QCheckBox('Трек играет (позиция растёт)')
        self.playing.toggled.connect(self.edit)
        form.addRow(self.playing)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.apply = QPushButton('Отправить')
        self.stop = QPushButton('Выключить аудио')
        buttons.addWidget(self.apply)
        buttons.addWidget(self.stop)
        root.addLayout(buttons)
        root.addStretch(1)
        self.status = QLabel('Аудио выключено.')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.presets.currentIndexChanged.connect(self.select_preset)
        self.apply.clicked.connect(lambda: self.submit(self.values()))
        self.stop.clicked.connect(self.select_off)
        for control in (self.presets, self.playing, self.apply, self.stop, *self.fields.values()):
            control.setEnabled(peer is not None)

    def edit(self, *_):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(0)
        self.status.setText('Значения изменены. Нажмите «Отправить».')

    def load(self, profile):
        for key, widget in self.fields.items():
            with QSignalBlocker(widget):
                if isinstance(widget, QLineEdit):
                    widget.setText(profile[key])
                else:
                    widget.setValue(profile[key])
        with QSignalBlocker(self.playing):
            self.playing.setChecked(profile['playing'])

    def values(self):
        base = deepcopy(self.accepted) if self.accepted else dict(DEFAULT)
        for key, widget in self.fields.items():
            base[key] = widget.text() if isinstance(widget, QLineEdit) else widget.value()
        base['playing'] = self.playing.isChecked()
        return base

    def select_preset(self, index):
        key = self.presets.itemData(index)
        if key is not None:
            self.submit(preset(key))

    def select_off(self):
        with QSignalBlocker(self.presets):
            self.presets.setCurrentIndex(self.presets.findData('off'))
        self.submit(None)

    def submit(self, profile):
        if not self.peer or not self.peer.set_assist('@media', None, profile):
            with QSignalBlocker(self.presets):
                self.presets.setCurrentIndex(0)
            if self.accepted is not None:
                self.load(self.accepted)
            self.status.setText('Не удалось поставить аудио в очередь: KSS остановлен, очередь '
                                'заполнена или значения неверны (строки до 127 байт).')
            return
        self.accepted = deepcopy(profile)
        if profile is not None:
            self.load(profile)
        text = ('Аудио: выключение поставлено в очередь KSS.' if profile is None else
                f'Аудио: источник {profile["source_type"]:#04x} «{profile["primary"]}».')
        self.status.setText(text)
        self.report(text)
