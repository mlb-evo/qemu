"""Local live X11/Qt integration check for the single-window QEMU display."""
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import time

sys.dont_write_bytecode = True
os.environ['QT_QPA_PLATFORM'] = 'xcb'
REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
from probe_stage1_startup import qmp, receive
from research.hmi.embedded_qemu import X11Windows
from PySide6.QtWidgets import QApplication, QSplitter, QWidget
import view_frames


def main():
    out = REPO / 'build_fpk1/research-artifacts/embedded-display-check'
    out.mkdir(parents=True, exist_ok=True)
    bios = out / 'loop.bin'
    bios.write_bytes(bytes.fromhex('feffffea'))
    name = f'fpk1-embed-check-{os.getpid()}'
    socket_path = out / 'qtest.sock'
    socket_path.unlink(missing_ok=True)
    app = QApplication([])
    peer = view_frames.KssPeer(out / 'unused-kss.sock', None)
    window = view_frames.Viewer(out / 'unused.ppm', out, keys=out / 'unused-keys',
                               kss=peer, embedded_name=name)
    window.showMaximized()
    decoy = QWidget()
    decoy.setWindowTitle(f'QEMU ({name}-0)')
    decoy.show()
    command = [str(REPO / 'build-fpk1/qemu/qemu-system-arm'),
               '-machine', 'fpk1,load=0x80000000,entry=0x80000000',
               '-m', '512M', '-bios', str(bios), '-display', 'sdl', '-name', name,
               '-S', '-qmp', 'stdio', '-nic', 'none',
               '-qtest', f'unix:{socket_path},server=on,wait=off', '-qtest-log', '/dev/null']
    with (out / 'stderr.log').open('wb') as error:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=error, bufsize=0,
                                env=dict(os.environ, SDL_VIDEODRIVER='x11', QEMU_SDL_EMBEDDED='1'))
        try:
            assert 'QMP' in receive(proc)
            qmp(proc, 'qmp_capabilities')
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(5)
            client.connect(str(socket_path))
            stream = client.makefile('rwb', buffering=0)

            def qt(command):
                stream.write(command.encode() + b'\n')
                while True:
                    reply = stream.readline()
                    if reply.startswith(b'OK'):
                        return
                    if not reply.startswith(b'IRQ '):
                        raise RuntimeError(repr(reply))

            def reg(index, value):
                qt(f'writel {0x54200000 + index * 4:#x} {value:#x}')
            deadline = time.monotonic() + 8
            while window.view.container is None and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.02)
            assert window.view.container is not None, 'native QEMU window was not embedded'
            assert int(window.view.foreign.winId()) != int(decoy.winId()), 'must select the real SDL client'
            decoy.hide()
            assert window.view.waiting.isHidden(), 'waiting label must disappear after attachment'
            assert window.view.container.geometry() == window.view.rect()
            window.showNormal()
            window.resize(1000, 650)
            deadline = time.monotonic() + .5
            while time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            assert window.view.foreign.width() == window.view.container.width()
            assert window.view.container.geometry() == window.view.rect()
            assert window.timer is None, 'embedded UI must not poll frame files'
            assert qmp(proc, 'qom-get', dict(path='/machine/soc/dc-b', property='show-console')) is False
            x11 = X11Windows()
            x11.x.XGetGeometry.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
                                           C.POINTER(C.c_int), C.POINTER(C.c_int),
                                           C.POINTER(C.c_uint), C.POINTER(C.c_uint),
                                           C.POINTER(C.c_uint), C.POINTER(C.c_uint)]

            def check_native_size():
                root, x, y = C.c_ulong(), C.c_int(), C.c_int()
                width, height, border, depth = (C.c_uint() for _ in range(4))
                assert x11.x.XGetGeometry(x11.display, int(window.view.foreign.winId()),
                                          C.byref(root), C.byref(x), C.byref(y),
                                          C.byref(width), C.byref(height), C.byref(border), C.byref(depth))
                assert (width.value, height.value) == (window.view.width(), window.view.height()), (
                    'actual X11 geometry must fill the display area', width.value, height.value,
                    window.view.width(), window.view.height())

            check_native_size()
            splitter = window.findChild(QSplitter)
            assert splitter is not None
            splitter.setSizes([300, 220])
            deadline = time.monotonic() + .2
            while time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            check_native_size()
            window.showMaximized()
            deadline = time.monotonic() + .3
            while time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            check_native_size()
            current = int(window.view.foreign.winId())
            ancestors = []
            for _ in range(8):
                root, parent, count = C.c_ulong(), C.c_ulong(), C.c_uint()
                children = C.POINTER(C.c_ulong)()
                x11.x.XQueryTree(x11.display, current, C.byref(root), C.byref(parent),
                                C.byref(children), C.byref(count))
                if children:
                    x11.x.XFree(children)
                current = parent.value
                ancestors.append(current)
                if current == root.value:
                    break
            assert int(window.winId()) in ancestors, 'QEMU must be a child of the unified UI'
            reg(0x42, 0x10)
            reg(0x409, (4 << 16) | 4)
            reg(0x705, (4 << 16) | 4)
            reg(0x703, 13)
            reg(0x70a, 16)
            reg(0x800, 0x81000000)
            reg(0x700, 0x40000000)
            x11.x.XGetImage.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int,
                                        C.c_uint, C.c_uint, C.c_ulong, C.c_int]
            x11.x.XGetImage.restype = C.c_void_p
            x11.x.XGetPixel.argtypes = [C.c_void_p, C.c_int, C.c_int]
            x11.x.XGetPixel.restype = C.c_ulong
            x11.x.XDestroyImage.argtypes = [C.c_void_p]
            observed = []
            for rgba, expected in ((b'\xff\x00\x00\xff', 0xff0000),
                                   (b'\x00\xff\x00\xff', 0x00ff00)):
                qt(f'write 0x81000000 0x40 0x{(rgba * 16).hex()}')
                deadline = time.monotonic() + 3
                pixel = None
                while time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(.03)
                    image = x11.x.XGetImage(x11.display, int(window.view.foreign.winId()),
                                           window.view.foreign.width() // 2,
                                           window.view.foreign.height() // 2, 1, 1,
                                           C.c_ulong(-1).value, 2)
                    if image:
                        pixel = x11.x.XGetPixel(image, 0, 0)
                        x11.x.XDestroyImage(image)
                    if pixel == expected:
                        break
                assert pixel == expected, ('live embedded pixel', pixel, expected)
                check_native_size()
                observed.append(hex(pixel))
            x11.close()
            client.close()
            summary = dict(embedded=True, native_window=int(window.view.foreign.winId()),
                           parent_ui=int(window.winId()), size=[window.view.foreign.width(),
                                                               window.view.foreign.height()],
                           frame_file_timer=False, secondary_console=False,
                           real_geometry_checked=True, waiting_label_hidden=True,
                           splitter_resize_checked=True, same_title_decoy_rejected=True,
                           live_pixels=observed)
            (out / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
            print('PASS: QEMU is embedded inside the Qt UI, resizes with it, and uses no frame files')
            qmp(proc, 'quit')
            proc.wait(timeout=5)
        finally:
            window.close()
            decoy.close()
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            socket_path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
