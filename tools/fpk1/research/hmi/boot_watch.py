"""Observe host child exits and frame evolution during a local boot experiment."""
import json
import signal
from pathlib import Path
import threading
import time


class BootWatch:
    def __init__(self, output):
        self.output = Path(output)
        self.children = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def add(self, command, process):
        if Path(str(command[0])).name == 'ldconfig':
            return
        self.children.append((list(map(str, command)), process, time.monotonic()))

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=3)

    def run(self):
        from PySide6.QtGui import QImage
        history = self.output / 'frame-history'
        history.mkdir(exist_ok=True)
        saved = {}
        origin = None
        signalled = set()
        with (self.output / 'host-watch.jsonl').open('w', buffering=1) as log:
            while not self.stop_event.wait(1):
                if not self.children:
                    continue
                if origin is None:
                    origin = min(start for _, _, start in self.children)
                elapsed = round(time.monotonic() - origin, 2)
                for command, process, _ in list(self.children):
                    if Path(command[0]).name == 'glhost' and process.poll() is None:
                        for deadline in (12, 25, 45):
                            key = (process.pid, deadline)
                            if elapsed >= deadline and key not in signalled:
                                process.send_signal(signal.SIGUSR1)
                                signalled.add(key)
                frames = []
                for path in sorted((self.output / 'frames').glob('*.ppm')):
                    try:
                        raw = path.read_bytes()
                        end = raw.index(b'\n255\n') + 5
                        pixels = raw[end:]
                        sample = pixels[::97]
                        row = dict(name=path.name, bytes=len(raw),
                                   mean_sample=round(sum(sample) / len(sample), 3) if sample else 0,
                                   nonzero_sample=sum(v != 0 for v in sample))
                        if elapsed - saved.get(path.name, -10) >= 2:
                            image = QImage.fromData(raw, 'PPM')
                            if not image.isNull():
                                target = history / f'{elapsed:07.2f}-{path.stem}.png'
                                image.save(str(target))
                                saved[path.name] = elapsed
                                row['snapshot'] = target.name
                        frames.append(row)
                    except (OSError, ValueError):
                        continue
                children = [dict(pid=proc.pid, command=cmd, exit_status=proc.poll())
                            for cmd, proc, _ in list(self.children)]
                log.write(json.dumps(dict(t=elapsed, children=children, frames=frames)) + '\n')
