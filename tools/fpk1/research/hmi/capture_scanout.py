"""Local QMP scanout capture, independent of the GLES bridge's client dumps.

Pause briefly for a consistent framebuffer/register snapshot. Keep the latest
PPM plus metadata and a compact timeline; do not accumulate unbounded images.
The current DC model supports one unscaled RGB plane. Report other layouts
explicitly rather than calling the model's first-plane image a full composite.
"""
import hashlib
import json
from pathlib import Path
import time


def assess(state):
    windows = [w for w in state['windows'] if w['registers']['700'] & (1 << 30)]
    active = state['display_active']
    width, height = active & 0x1fff, (active >> 16) & 0x1fff
    reasons = []
    if not state['display_command'] & 0x60:
        reasons.append('display stopped')
    if not width or not height:
        reasons.append('panel geometry not programmed')
    if state['display_options'] & (1 << 16):
        reasons.append('hardware cursor not modelled')
    if len(windows) > 1:
        reasons.append('multiple DC planes: blending not modelled')
    for window in windows:
        r = window['registers']
        if r['703'] not in (12, 13):
            reasons.append('scanout format outside validated RGBA/BGRA path')
        if r['704'] or r['705'] != active:
            reasons.append('plane does not cover panel at origin')
        if r['700'] & ((1 << 0) | (1 << 8) | (1 << 10) | (1 << 18)):
            reasons.append('reflection/filter/CSC outside capture model')
        expected_v = height - 1 if r['700'] & 4 else 0
        if r['701'] > 3 or r['70d'] or r['806'] or r['808'] not in (0, expected_v):
            reasons.append('tiled layout or source crop outside validated capture path')
        if r['706'] not in (0, (height << 16) | (width * 4)):
            reasons.append('source geometry differs from panel')
        if r['709'] not in (0, 0x10001000):
            reasons.append('scaled source not modelled')
        if r['710'] & 0x0c or (r['710'] >> 8) & 0xff != 0xff:
            reasons.append('single-plane alpha/fixed-weight blending not modelled')
        if not r['800'] or (r['70a'] & 0xffff) < width * 4:
            reasons.append('invalid framebuffer address or pitch')
    if not windows:
        reasons.append('no enabled plane')
    return dict(width=width, height=height,
                active_windows=[w['name'] for w in windows],
                complete=not reasons, limitations=reasons)


class ScanoutCapture:
    def __init__(self, directory, qmp, interval=0.1):
        if interval < 0.1:
            raise ValueError('scanout interval must be at least 0.1 seconds')
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.qmp = qmp
        self.interval = interval
        self.deadline = 0
        self.index = 0
        self.property_supported = None

    def capture(self, process, elapsed):
        now = time.monotonic()
        if now < self.deadline:
            return
        self.deadline = now + self.interval
        path = self.directory / 'dc-scanout.ppm'
        temporary = self.directory / 'dc-scanout.ppm.tmp'
        paused_at = time.monotonic()
        self.qmp(process, 'stop')
        try:
            state = None
            if self.property_supported is not False:
                try:
                    state = json.loads(self.qmp(process, 'qom-get', dict(
                        path='/machine/soc/dc-a', property='scanout-state')))
                    self.property_supported = True
                except RuntimeError:
                    if self.property_supported:
                        raise
                    self.property_supported = False
            self.qmp(process, 'screendump', dict(filename=str(temporary), format='ppm'))
        finally:
            self.qmp(process, 'cont')
        pause_ms = round((time.monotonic() - paused_at) * 1000, 3)
        raw = temporary.read_bytes()
        temporary.replace(path)
        report = assess(state) if state else dict(
            complete=False, limitations=['QEMU lacks scanout-state diagnostics'])
        report.update(sequence=self.index, t=round(elapsed, 3),
                      pause_ms=pause_ms,
                      source='QEMU dc-a scanout', file=path.name,
                      sha256=hashlib.sha256(raw).hexdigest(),
                      model='single plane; no shadow-bank latching or multi-plane blending')
        metadata = self.directory / 'dc-scanout.json'
        metadata_tmp = metadata.with_suffix('.json.tmp')
        metadata_tmp.write_text(json.dumps(dict(report, registers=state), indent=2) + '\n')
        metadata_tmp.replace(metadata)
        with (self.directory / 'dc-scanout.jsonl').open('a') as stream:
            stream.write(json.dumps(report) + '\n')
        self.index += 1
