import sys
sys.dont_write_bytecode = True
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
CGDRV_LIBRARY=REPO/'build_fpk1/research-artifacts/cgdrv-experiment/libcgdrv.so'
