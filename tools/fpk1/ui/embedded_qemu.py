"""Embed this run's native SDL/X11 QEMU console in the existing Qt UI.

No framebuffer files or screenshot polling. QEMU owns pixel presentation;
Qt embeds its native child window and supplies the surrounding KSS controls.
"""
import ctypes as C
import ctypes.util

from PySide6.QtCore import QSize, QTimer, Signal
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class XClassHint(C.Structure):
    _fields_ = [('res_name', C.c_void_p), ('res_class', C.c_void_p)]


class X11Windows:
    def __init__(self):
        self.x = C.CDLL(ctypes.util.find_library('X11'))
        self.x.XOpenDisplay.argtypes = [C.c_char_p]
        self.x.XOpenDisplay.restype = C.c_void_p
        self.x.XDefaultRootWindow.argtypes = [C.c_void_p]
        self.x.XDefaultRootWindow.restype = C.c_ulong
        self.x.XQueryTree.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
                                      C.POINTER(C.c_ulong), C.POINTER(C.POINTER(C.c_ulong)),
                                      C.POINTER(C.c_uint)]
        self.x.XFetchName.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_void_p)]
        self.x.XGetClassHint.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(XClassHint)]
        self.x.XFree.argtypes = [C.c_void_p]
        self.x.XCloseDisplay.argtypes = [C.c_void_p]
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Cannot open X11 display for embedded QEMU')
        # A window may disappear between tree enumeration and title lookup.
        # Ignore errors on this discovery connection, preserving other handlers.
        self.x.XSetErrorHandler.argtypes = [C.c_void_p]
        self.x.XSetErrorHandler.restype = C.c_void_p
        handler_type = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)
        self.previous_handler = None

        def error(display, event):
            if display != self.display and self.previous_handler:
                return handler_type(self.previous_handler)(display, event)
            return 0

        self.error_handler = handler_type(error)
        self.previous_handler = self.x.XSetErrorHandler(C.cast(self.error_handler, C.c_void_p))

    def find(self, prefix):
        pending = [(self.x.XDefaultRootWindow(self.display), 0)]
        visited = 0
        while pending and visited < 4096:
            window, depth = pending.pop()
            visited += 1
            title = C.c_void_p()
            if self.x.XFetchName(self.display, window, C.byref(title)) and title.value:
                try:
                    if (C.string_at(title).decode(errors='replace').startswith(prefix)
                            and self.is_qemu_client(window)):
                        return window
                finally:
                    self.x.XFree(title)
            if depth >= 4:
                continue
            root, parent, count = C.c_ulong(), C.c_ulong(), C.c_uint()
            children = C.POINTER(C.c_ulong)()
            if self.x.XQueryTree(self.display, window, C.byref(root), C.byref(parent),
                                 C.byref(children), C.byref(count)):
                pending.extend((children[i], depth + 1) for i in range(count.value))
                if children:
                    self.x.XFree(children)
        return None

    def is_qemu_client(self, window):
        # Some window managers copy the client title onto their decoration
        # window. Embed SDL's real client, never the window-manager frame.
        hint = XClassHint()
        if not self.x.XGetClassHint(self.display, window, C.byref(hint)):
            return False
        try:
            return any('qemu' in C.string_at(value).decode(errors='replace').lower()
                       for value in (hint.res_name, hint.res_class) if value)
        finally:
            for value in (hint.res_name, hint.res_class):
                if value:
                    self.x.XFree(value)

    def close(self):
        if self.display:
            self.x.XCloseDisplay(self.display)
            self.display = None
            self.x.XSetErrorHandler(self.previous_handler)


class EmbeddedQemu(QWidget):
    status = Signal(str)

    def __init__(self, name):
        super().__init__()
        self.prefix = f'QEMU ({name}-0)'
        self.foreign = self.container = None
        self.x11 = X11Windows()
        self.destroyed.connect(self.x11.close)
        self.waiting = QLabel('Waiting for QEMU display...', self)
        self.setMinimumSize(160, 96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.attach)
        self.timer.start(100)

    def sizeHint(self):
        return QSize(1440, 540)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_display()

    def fit_display(self):
        if self.container is not None:
            self.container.setGeometry(self.rect())
            self.foreign.setGeometry(0, 0, self.width(), self.height())
        else:
            self.waiting.setGeometry(self.rect())

    def attach(self):
        window = self.x11.find(self.prefix)
        if window is None:
            return
        self.foreign = QWindow.fromWinId(window)
        if self.foreign is None:
            self.status.emit('Cannot embed the QEMU native window')
            self.timer.stop()
            return
        self.container = QWidget.createWindowContainer(self.foreign, self)
        self.waiting.hide()
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.fit_display()
        self.container.show()
        QTimer.singleShot(0, self.fit_display)
        self.timer.stop()
        self.x11.close()
        self.status.emit('QEMU display connected')
        print(f'FPK1: embedded QEMU window {window:#x}', flush=True)
