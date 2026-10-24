#!/usr/bin/env python3
"""Probe QNX6 root inode and immediate directory entries in FPK1 volumes.

Read-only; no extraction, bounded traversal and strict block checks.
Based on Linux include/linux/qnx6_fs.h and fs/qnx6/inode.c.
"""
import argparse, json, struct, zipfile, zlib
import xml.etree.ElementTree as ET
from pathlib import Path

TARGETS=("app.img","stage3.img")
MAGIC=0x68191122
BLOCK_BASE=0x3000
UNUSED=0xffffffff

def image_from_signinfo(z,target):
    for path in z.namelist():
        if not path.endswith("_SignInfo.xml"):continue
        root=ET.fromstring(z.read(path))
        if root.attrib.get("name")!=target:continue
        data=z.read(path.rsplit("/",1)[0]+"/"+target)
        start=int(root.findtext("START-BYTE-FLASHDATA"))
        length=int(root.findtext("COMPRESSED-SIZE"))
        size=int(root.findtext("UNCOMPRESSED-SIZE"))
        if size>256*1024*1024:raise ValueError("Unexpected output size")
        obj=zlib.decompressobj()
        decoded=obj.decompress(data[start:start+length],size+1)
        decoded+=obj.flush()
        if not obj.eof or obj.unused_data or len(decoded)!=size:raise ValueError("Invalid image")
        return decoded
    raise ValueError("No SignInfo for "+target)

class Volume:
    def __init__(self,image):
        self.image=image
        sb=image[0x2000:0x2200]
        if struct.unpack_from("<I",sb)[0]!=MAGIC:raise ValueError("No QNX6 superblock")
        self.blocksize=struct.unpack_from("<I",sb,0x30)[0]
        self.blocks=struct.unpack_from("<I",sb,0x3c)[0]
        self.inodes=struct.unpack_from("<I",sb,0x34)[0]
        if self.blocksize!=1024 or self.blocks!=204784:raise ValueError("Unexpected geometry")
        self.inode_root=self.root(sb,0x48)
    @staticmethod
    def root(buf,off):
        return {"size":struct.unpack_from("<Q",buf,off)[0],
                "pointers":list(struct.unpack_from("<16I",buf,off+8)),
                "levels":buf[off+72]}
    def block(self,index):
        if index==UNUSED or index>=self.blocks:raise ValueError("Invalid QNX6 block "+str(index))
        start=BLOCK_BASE+index*self.blocksize
        if start+self.blocksize>len(self.image):raise ValueError("Out of image")
        return self.image[start:start+self.blocksize]
    def map(self,node,index):
        per=self.blocksize//4
        depth=node["levels"]
        if depth>5:raise ValueError("Unexpected inode level")
        slot=index//(per**depth)
        if slot>=16:raise ValueError("Logical block out of root range")
        ptr=node["pointers"][slot]
        if ptr==UNUSED:return None
        for level in range(depth-1,-1,-1):
            pos=(index//(per**level))%per
            ptr=struct.unpack_from("<I",self.block(ptr),pos*4)[0]
            if ptr==UNUSED:return None
        return ptr
    def read(self,node,offset,count):
        if offset>=node["size"]:return b""
        count=min(count,node["size"]-offset)
        result=bytearray()
        while count:
            logical=offset//self.blocksize
            local=offset%self.blocksize
            take=min(count,self.blocksize-local)
            ptr=self.map(node,logical)
            result+=bytes(take) if ptr is None else self.block(ptr)[local:local+take]
            count-=take
            offset+=take
        return bytes(result)
    def inode(self,number):
        if not 1<=number<=self.inodes:raise ValueError("Invalid inode number")
        b=self.read(self.inode_root,(number-1)*128,128)
        if len(b)!=128:raise ValueError("Short inode")
        return {"ino":number,"size":struct.unpack_from("<Q",b)[0],
                "mode":struct.unpack_from("<H",b,32)[0],
                "status":b[101],"levels":b[100],
                "pointers":list(struct.unpack_from("<16I",b,36))}
    def directory(self,node):
        if node["size"]>1024*1024:raise ValueError("Directory too large for probe")
        buf=self.read(node,0,node["size"])
        out=[]
        for i in range(0,len(buf)-31,32):
            ino=struct.unpack_from("<I",buf,i)[0]
            size=buf[i+4]
            if not ino:continue
            if size<=27:
                name=buf[i+5:i+5+size].decode("utf-8","replace")
            else:
                name="<long-name-ref>"
            out.append({"inode":ino,"name":name,"size_field":size})
            if len(out)>=128:break
        return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("--json",type=Path)
    a=p.parse_args()
    out={}
    with zipfile.ZipFile(a.archive) as z:
        for target in TARGETS:
            v=Volume(image_from_signinfo(z,target))
            inode=v.inode(1)
            entries=v.directory(inode) if inode["mode"]&0xf000==0x4000 else []
            out[target]={"inode_root":v.inode_root,"root_inode":inode,
                         "root_directory_entries":entries,
                         "root_inode_is_directory":inode["mode"]&0xf000==0x4000}
    result=json.dumps(out,indent=2)+"\n"
    print(result,end="")
    if a.json:a.json.write_text(result)

if __name__=="__main__":main()
