"""Save changing diagnostic frames under build_fpk1/research-artifacts/."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from PySide6.QtGui import QImage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--seconds', type=int, default=240)
    args = parser.parse_args()
    repo = next(p for p in Path(__file__).resolve().parents
                if (p / 'hw/arm/fpk1.c').is_file())
    out = repo / 'build_fpk1/research-artifacts/blank-screen' / args.run.name
    out.mkdir(parents=True, exist_ok=True)
    seen = {}
    start = time.monotonic()
    with (out / 'frames.jsonl').open('w', buffering=1) as log:
        while time.monotonic() - start < args.seconds:
            for path in (args.run / 'frames').glob('*.ppm'):
                try:
                    raw = path.read_bytes()
                    digest = hashlib.sha256(raw).hexdigest()
                    if seen.get(path.name) == digest:
                        continue
                    im = QImage.fromData(raw, 'PPM')
                    if im.isNull():
                        continue
                    seen[path.name] = digest
                    elapsed = round(time.monotonic() - start, 2)
                    target = out / f'{elapsed:07.2f}-{path.stem}.png'
                    im.save(str(target))
                    pixels = raw[raw.index(b'\n255\n') + 5:]
                    log.write(json.dumps(dict(t=elapsed, file=path.name,
                                             snapshot=target.name, sha256=digest,
                                             nonzero=sum(v != 0 for v in pixels),
                                             mean=sum(pixels) / len(pixels))) + '\n')
                except (ValueError, OSError):
                    continue
            time.sleep(2)


if __name__ == '__main__':
    main()
