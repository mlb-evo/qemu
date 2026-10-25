#!/usr/bin/env python3
"""Read-only SIFS loader evidence: strings and ELF program segments.

By default reads the catalog-owned ELF from fully verified ZV/LZF Stage1.
The old suffix probe is available only with --legacy-suffix.
Only prints diagnostic strings and numeric metadata; never extracts binaries.
"""
import argparse,json,re,struct,zipfile
from pathlib import Path
from verify_sifs_partitions import verify_archive
from validate_stage1_unseeded_lzf import decode,scan_elf
from identify_stage1_elf_dependencies import inspect_elf
from inspect_stage1_framed import decode_archive, startup_layout
from inspect_stage2_catalogs import parse_catalog

ELF_AT=0xfb4a0
FIND=re.compile(rb"[\x20-\x7e]{5,240}")
NEEDLES=("sifs","image","mount","partition","block","checksum","compress",
         "decompress","version","nand","nordma","usage","header","error")

def inspect(data, elf_at=ELF_AT, next_at=None):
    candidates=sorted(e["at"] for e in scan_elf(data) if e["strict_elf_valid"])
    if elf_at not in candidates:raise ValueError("sifsloader ELF not strict-valid")
    if next_at is None:
        index=candidates.index(elf_at)+1
        next_at=candidates[index] if index<len(candidates) else len(data)
    header=inspect_elf(data,elf_at)
    phoff=struct.unpack_from("<I",data,elf_at+28)[0]
    phnum=struct.unpack_from("<H",data,elf_at+44)[0]
    segments=[]
    for i in range(phnum):
        typ,off,va,pa,fs,ms,flags,align=struct.unpack_from(
            "<IIIIIIII",data,elf_at+phoff+32*i)
        segments.append({"type":hex(typ),"offset":hex(off),"vaddr":hex(va),
                         "filesz":fs,"memsz":ms,"align":hex(align)})
    strings=[]
    for m in FIND.finditer(data,elf_at,next_at):
        val=m.group().decode("ascii")
        if any(n in val.lower() for n in NEEDLES):
            strings.append({"decoded_at":hex(m.start()),"relative_to_elf":hex(m.start()-elf_at),
                            "text":val[:200]})
    return {"elf_at":hex(elf_at),"inspection_end":hex(next_at),
            "elf":header,"segments":segments,
            "strings":strings[:150],"string_matches":len(strings),
            "limitations":["String references do not prove the on-disk SIFS structure.",
                           "Cannot infer checksums/compression algorithms without tracing implementation.",
                           "Legacy suffix bounds are heuristic; default bounds come from the verified catalog."]}

def code_evidence(data, elf_at=ELF_AT):
    """Small ARM windows in the observed loader; no inferred string xrefs."""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    phoff=struct.unpack_from("<I",data,elf_at+28)[0]
    phnum=struct.unpack_from("<H",data,elf_at+44)[0]
    loads=[]
    for i in range(phnum):
        typ,off,va,_,fs,_,flags,_=struct.unpack_from(
            "<8I",data,elf_at+phoff+32*i)
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
        raw=data[elf_at+off+start-va:elf_at+off+end-va]
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
    parser.add_argument("--legacy-suffix", action="store_true",
                        help="historical unframed suffix probe; not authoritative ELF contents")
    args=parser.parse_args()
    if args.decompress and not args.verify_stage2:
        parser.error("--decompress requires --verify-stage2")
    if args.legacy_suffix:
        with zipfile.ZipFile(args.archive) as z:
            names=[n for n in z.namelist() if n.endswith("/stage1_ifs.img")]
            if len(names)!=1:raise ValueError("Ambiguous Stage1")
            raw=z.read(names[0])
        buf,stop,error=decode(raw[0xc2:0xc2+0x1f6ffb],0x1318fc)
        if error or stop!=0x1f6ffb:raise ValueError("Unexpected decode boundary")
        at=ELF_AT
        report={"warning":"Legacy unframed suffix can corrupt file contents and metadata.",
                "source_encoded_stop":hex(stop),**inspect(buf)}
    else:
        decoded,framing=decode_archive(args.archive)
        layout=startup_layout(decoded)
        image=decoded[layout['decoded_imagefs_offset']:]
        catalog=parse_catalog(image)
        matches=[r for r in catalog['entries'] if r['path']=='bin/sifsloader' and r['kind']=='regular']
        if len(matches)!=1:raise ValueError("Missing catalog-owned sifsloader")
        row=matches[0]
        buf=image[row['offset']:row['offset']+row['size']]
        at=0
        report={"coordinates":"Offsets relative to verified bin/sifsloader file",
                "framing":framing,"catalog_path":row['path'],
                "imagefs_file_offset":row['offset'],**inspect(buf,0,len(buf))}
    if args.code_evidence:
        report["code_evidence"] = code_evidence(buf,at)
    if args.verify_stage2:
        report["stage2_verification"] = verify_archive(args.archive, args.decompress)
    output=json.dumps(report,indent=2)+"\n";print(output,end="")
    if args.json:args.json.write_text(output)

if __name__=="__main__":main()
