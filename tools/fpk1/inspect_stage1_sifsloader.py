#!/usr/bin/env python3
"""Read-only SIFS loader evidence: strings and ELF section ranges.

Offsets refer to decoded LZF suffix, NOT an authenticated SIFS file format.
Only prints diagnostic strings and numeric metadata; never extracts binaries.
"""
import argparse,json,re,struct,zipfile
from pathlib import Path
from verify_sifs_partitions import verify_archive
from validate_stage1_unseeded_lzf import decode,scan_elf
from identify_stage1_elf_dependencies import inspect_elf

ELF_AT=0xfb4a0
FIND=re.compile(rb"[\x20-\x7e]{5,240}")
NEEDLES=("sifs","image","mount","partition","block","checksum","compress",
         "decompress","version","nand","nordma","usage","header","error")

def inspect(data):
    candidates=sorted(e["at"] for e in scan_elf(data) if e["strict_elf_valid"])
    if ELF_AT not in candidates:raise ValueError("sifsloader ELF not strict-valid")
    next_at=candidates[candidates.index(ELF_AT)+1]
    header=inspect_elf(data,ELF_AT)
    phoff=struct.unpack_from("<I",data,ELF_AT+28)[0]
    phnum=struct.unpack_from("<H",data,ELF_AT+44)[0]
    segments=[]
    for i in range(phnum):
        typ,off,va,pa,fs,ms,flags,align=struct.unpack_from(
            "<IIIIIIII",data,ELF_AT+phoff+32*i)
        segments.append({"type":hex(typ),"offset":hex(off),"vaddr":hex(va),
                         "filesz":fs,"memsz":ms,"align":hex(align)})
    strings=[]
    for m in FIND.finditer(data,ELF_AT,next_at):
        val=m.group().decode("ascii")
        if any(n in val.lower() for n in NEEDLES):
            strings.append({"decoded_at":hex(m.start()),"relative_to_elf":hex(m.start()-ELF_AT),
                            "text":val[:200]})
    return {"elf_at":hex(ELF_AT),"next_elf":hex(next_at),
            "elf":header,"segments":segments,
            "strings":strings[:150],"string_matches":len(strings),
            "limitations":["String references do not prove the on-disk SIFS structure.",
                           "Cannot infer checksums/compression algorithms without tracing implementation.",
                           "Next ELF boundary does not prove this ELF's true file size."]}

def code_evidence(data):
    """Small ARM windows in the observed loader; no inferred string xrefs."""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    phoff=struct.unpack_from("<I",data,ELF_AT+28)[0]
    phnum=struct.unpack_from("<H",data,ELF_AT+44)[0]
    loads=[]
    for i in range(phnum):
        typ,off,va,_,fs,_,flags,_=struct.unpack_from(
            "<8I",data,ELF_AT+phoff+32*i)
        if typ==1 and flags&1:
            loads.append((off,va,fs))
    windows=(("table_version",0x102b18,0x102b24),
             ("part_count",0x102c38,0x102c44),
             ("block_header_and_checksum_call",0x103068,0x1030dc),
             ("decompression_call_and_length_check",0x103100,0x10313c),
             ("checksum_constants",0x104c98,0x104cd4),
             ("checksum_reduction",0x104df4,0x104e1c))
    md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    rows=[]
    for label,start,end in windows:
        match=next(((off,va) for off,va,fs in loads
                    if va<=start and end<=va+fs),None)
        if match is None:
            raise ValueError("Code window outside executable PT_LOAD")
        off,va=match
        raw=data[ELF_AT+off+start-va:ELF_AT+off+end-va]
        instructions=list(md.disasm(raw,start))
        if sum(i.size for i in instructions)!=len(raw):
            raise ValueError("Incomplete ARM instruction window")
        rows.append({"interpretation":label,"start_va":hex(start),
                     "instructions":[{"va":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
                                     for i in instructions]})
    return {"mode":"ARM little-endian; selected static windows, not an execution trace",
            "windows":rows,
            "caution":"Labels interpret observed code; no direct diagnostic-string xrefs are asserted."}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path);parser.add_argument("--json",type=Path)
    parser.add_argument("--code-evidence", action="store_true",
                        help="report selected ARM instruction windows (requires capstone)")
    parser.add_argument("--verify-stage2", action="store_true",
                        help="verify observed Stage2 NOR/NAND SIFS table and block checksums")
    parser.add_argument("--decompress", action="store_true",
                        help="also verify LZO output and reconstructed imagefs sizes (requires lzokay)")
    args=parser.parse_args()
    if args.decompress and not args.verify_stage2:
        parser.error("--decompress requires --verify-stage2")
    with zipfile.ZipFile(args.archive) as z:
        names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
        if len(names)!=1:raise ValueError("Ambiguous Stage1")
        raw=z.read(names[0])
    if raw[:3]!=b"HSP":raise ValueError("Not HSP Stage1")
    buf,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
    if error or stop!=0x1f6ffb:raise ValueError("Unexpected decode boundary")
    report={"source_encoded_stop":hex(stop),**inspect(buf)}
    if args.code_evidence:
        report["code_evidence"] = code_evidence(buf)
    if args.verify_stage2:
        report["stage2_verification"] = verify_archive(args.archive, args.decompress)
    output=json.dumps(report,indent=2)+"\n";print(output,end="")
    if args.json:args.json.write_text(output)

if __name__=="__main__":main()
