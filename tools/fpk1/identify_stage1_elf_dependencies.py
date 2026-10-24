#!/usr/bin/env python3
"""Read-only metadata inventory for LZF-decoded Stage1 ELF files."""
import argparse
import json
import struct
import zipfile
from pathlib import Path
from validate_stage1_unseeded_lzf import decode, scan_elf

END = 0x1f6ffb

def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]

def cstring(data, offset, maximum=256):
    if offset is None or not 0 <= offset < len(data):
        return None
    end = data.find(b"\0", offset, min(len(data), offset + maximum))
    if end < 0:
        return None
    value = data[offset:end]
    if not value or any(byte < 32 or byte > 126 for byte in value):
        return None
    return value.decode("ascii")

def inspect_elf(data, start):
    entry = u32(data, start + 24)
    phoff = u32(data, start + 28)
    count = struct.unpack_from("<H", data, start + 44)[0]
    kind = struct.unpack_from("<H", data, start + 16)[0]
    segments = [struct.unpack_from("<IIIIIIII", data, start + phoff + 32*i)
                for i in range(count)]
    loads = [seg for seg in segments if seg[0] == 1]

    def address_to_offset(address, size=1):
        for seg in loads:
            _, fileoff, vaddr, _, filesz, _, _, _ = seg
            if vaddr <= address and address - vaddr + size <= filesz:
                absolute = start + fileoff + address - vaddr
                if absolute + size <= len(data):
                    return absolute
        return None

    interpreter = []
    dynamic = []
    for seg in segments:
        segment_type, fileoff, _, _, filesz, _, _, _ = seg
        absolute = start + fileoff
        if absolute + filesz > len(data):
            continue
        if segment_type == 3:
            interpreter.append(cstring(data, absolute))
        if segment_type == 2:
            for i in range(min(filesz // 8, 4096)):
                tag, value = struct.unpack_from("<II", data, absolute + 8*i)
                if tag == 0:
                    break
                dynamic.append((tag, value))

    strtab = next((value for tag, value in dynamic if tag == 5), None)
    strsz = next((value for tag, value in dynamic if tag == 10), None)
    def name(index):
        if strtab is None or strsz is None or index >= strsz:
            return None
        return cstring(data, address_to_offset(strtab + index), min(256, strsz - index))

    tag_names = {1: "needed", 14: "soname", 15: "rpath", 29: "runpath"}
    names = {name: [] for name in tag_names.values()}
    for tag, value in dynamic:
        if tag in tag_names:
            names[tag_names[tag]].append(name(value))
    return {
        "offset": hex(start),
        "elf_type": {2:"ET_EXEC", 3:"ET_DYN"}.get(kind, str(kind)),
        "entry": hex(entry),
        "interpreter": interpreter,
        "dynamic_entries": len(dynamic),
        "dynamic_strings": names,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--start", type=lambda x:int(x, 0), default=0x1318fc)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        matches = [name for name in archive.namelist() if name.endswith("/stage1_ifs.img")]
        if len(matches) != 1:
            raise ValueError("Ambiguous Stage1 image")
        raw = archive.read(matches[0])
    decoded, stop, error = decode(raw[0xc2:0xc2+END], args.start)
    candidates = [entry for entry in scan_elf(decoded) if entry["strict_elf_valid"]]
    report = {
        "decoded_start": hex(args.start),
        "stop": hex(stop),
        "decode_error": error,
        "strict_elf_count": len(candidates),
        "files": [inspect_elf(decoded, entry["at"]) for entry in candidates],
        "note": "Names from ELF metadata are not verified imagefs paths.",
    }
    result = json.dumps(report, indent=2) + "\n"
    print(result, end="")
    if args.json:
        args.json.write_text(result)

if __name__ == "__main__":
    main()
