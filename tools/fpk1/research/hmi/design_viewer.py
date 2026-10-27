"""Regular FPK1 viewer with an explicit local BAP active-design fixture."""
import sys
sys.dont_write_bytecode = True
import argparse
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
sys.path.insert(0, str(REPO / 'tools/fpk1'))
import kss_peer
import view_frames


def enable_design(design):
    if design not in (0, 1):
        raise ValueError('Active design must be 0 or 1')
    base = kss_peer.Kss

    class DesignKss(base):
        def queue_config(self, log=False):
            super().queue_config(log=log)
            payload = bytes([design]) * 4
            if log:
                self.log(f'tx RTE BAP_DesignChange EXPERIMENT id=0x3cd value={payload.hex()} status=0')
            self.queue(*kss_peer.ipc.rte_signal(0x3cd, payload))

    kss_peer.Kss = DesignKss


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--active-design', type=int, choices=(0, 1), required=True)
    args, viewer_args = parser.parse_known_args()
    enable_design(args.active_design)
    sys.argv = [sys.argv[0], *viewer_args]
    view_frames.main()


if __name__ == '__main__':
    main()
