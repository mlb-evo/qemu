#!/usr/bin/env python3
"""FPK1 diagnostic machine smoke checks against a built qemu-system-arm.

Requires no proprietary firmware and makes no QNX boot claim.
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

def run(qemu, *args, timeout=12):
    return subprocess.run([str(qemu), *args], capture_output=True, text=True,
                          timeout=timeout, check=False)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--qemu", required=True, type=Path)
    args=parser.parse_args()
    help_result=run(args.qemu, "-machine", "help")
    assert help_result.returncode == 0, help_result.stderr
    assert "fpk1" in help_result.stdout, "FPK1 machine not registered"

    missing=run(args.qemu, "-machine", "fpk1", "-display", "none")
    assert missing.returncode != 0, "FPK1 accepted absent boot addresses"
    assert "fpk1:" in missing.stderr, missing.stderr

    with tempfile.TemporaryDirectory(prefix="fpk1-smoke-") as directory:
        image=Path(directory)/"loop.bin"
        # ARM A32 branch-to-self: EAFFFFFE (little-endian).
        image.write_bytes(bytes.fromhex("fe ff ff ea"))
        invalid=run(args.qemu, "-machine",
                    "fpk1,load=0x80010000,entry=0x80010008",
                    "-bios", str(image), "-display", "none")
        assert invalid.returncode != 0, "Out-of-image entry was accepted"
        assert "fpk1:" in invalid.stderr, invalid.stderr

        # QEMU must start; self-branch then runs until our short timeout.
        try:
            started=run(args.qemu, "-machine",
                        "fpk1,load=0x80010000,entry=0x80010000",
                        "-m", "512M", "-bios", str(image),
                        "-display", "none", "-monitor", "none",
                        "-serial", "none", timeout=2)
        except subprocess.TimeoutExpired:
            print("FPK1 diagnostic machine started and executed test loop")
        else:
            raise AssertionError("Diagnostic machine exited unexpectedly: "
                                 +started.stdout+"\n"+started.stderr)

if __name__=="__main__":
    main()
