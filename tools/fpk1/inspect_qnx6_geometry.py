#!/usr/bin/env python3
"""Read-only QNX6 superblock geometry/root-node probe of app.img and stage3.img."""
import argparse, json, struct, zipfile, zlib, xml.etree.ElementTree as ET
from pathlib import Path
MAGIC=0x68191122
def crc32_be(data):
    c=0
    for x in data:
        c^=x<<24
        for _ in range(8): c=((c<<1)^(0x04c11db7 if c&0x80000000 else 0))&0xffffffff
    return c
def load(z,name):
    for p in z.namelist():
        if not p.endswith("_SignInfo.xml"):continue
        e=ET.fromstring(z.read(p))
        if e.attrib.get("name")!=name:continue
        raw=z.read(p.rsplit("/",1)[0]+"/"+name)
        st=int(e.findtext("START-BYTE-FLASHDATA"))
        n=int(e.findtext("COMPRESSED-SIZE"))
        expect=int(e.findtext("UNCOMPRESSED-SIZE"))
        if expect>256*1024*1024:raise ValueError("too large")
        dec=zlib.decompressobj()
        out=dec.decompress(raw[st:st+n],expect+1)+dec.flush()
        if not dec.eof or dec.unused_data or len(out)!=expect:raise ValueError("invalid stream")
        return out
    raise ValueError("missing "+name)
def root(b,off):
    size=struct.unpack_from("<Q",b,off)[0]
    ptr=list(struct.unpack_from("<16I",b,off+8))
    return {"size_bytes":size,"levels":b[off+72],"mode":b[off+73],
            "pointers":[p for p in ptr if p!=0xffffffff],
            "raw_pointers":[hex(x) for x in ptr]}
def check(buf,offset):
    b=buf[offset:offset+512]
    if len(b)!=512 or struct.unpack_from("<I",b)[0]!=MAGIC:return {"error":"bad magic"}
    blocksize,ninodes,freeinodes,nblocks,freeblocks,allocgroup=struct.unpack_from("<6I",b,0x2c)
    base=0x3000
    second=base+blocksize*nblocks
    roots={name:root(b,0x44+80*i) for i,name in enumerate(("inode","bitmap","longfile","unknown"))}
    return {"offset":hex(offset),"crc_valid":struct.unpack_from("<I",b,4)[0]==crc32_be(b[8:]),
            "serial":struct.unpack_from("<Q",b,8)[0],"blocksize":blocksize,
            "num_inodes":ninodes,"free_inodes":freeinodes,
            "num_blocks":nblocks,"free_blocks":freeblocks,"allocgroup":allocgroup,
            "data_block_zero":hex(base),"predicted_secondary_superblock":hex(second),
            "predicted_secondary_in_bounds":second+512<=len(buf),
            "roots":roots}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    with zipfile.ZipFile(a.archive) as z:
        out={}
        for name in ("app.img","stage3.img"):
            buf=load(z,name)
            primary=check(buf,0x2000)
            backup=check(buf,int(primary["predicted_secondary_superblock"],16)) if primary["predicted_secondary_in_bounds"] else {"error":"out of bounds"}
            out[name]={"primary":primary,"secondary":backup}
    value=json.dumps(out,indent=2)+"\n"
    print(value,end="")
    if a.json:a.json.write_text(value)
if __name__=="__main__":main()
