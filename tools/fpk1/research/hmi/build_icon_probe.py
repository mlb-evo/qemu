"""Build a local pixel-change probe for recorded icon draws; no upstream use."""
from pathlib import Path
import re
import subprocess

repo = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
out = repo / 'build_fpk1/research-artifacts/icon-render'
out.mkdir(parents=True, exist_ok=True)
original = repo / 'tools/mhi2/glforward/host/glhost.c'
source = re.sub(r'#include "([^"]+)"', lambda m: f'#include "{original.parent / m[1]}"', original.read_text())
source = source.replace('begin_binary_blend(mode,&saved);', '''begin_binary_blend(mode,&saved);
            unsigned char before[8]={0},after[8]={0};
            int probe=frames>=strtoul(getenv("ICON_FIRST")?getenv("ICON_FIRST"):"0",0,10);
            if(probe){glReadPixels(1120,70,1,1,GL_RGBA,GL_UNSIGNED_BYTE,before);glReadPixels(1180,70,1,1,GL_RGBA,GL_UNSIGNED_BYTE,before+4);}
''')
source = source.replace('end_binary_blend(mode,&saved);', '''end_binary_blend(mode,&saved);
            if(probe){
                glReadPixels(1120,70,1,1,GL_RGBA,GL_UNSIGNED_BYTE,after);glReadPixels(1180,70,1,1,GL_RGBA,GL_UNSIGNED_BYTE,after+4);
                if(memcmp(before,after,8)){
                    GLint fb=0,program=0,texture=0;
                    glGetIntegerv(GL_FRAMEBUFFER_BINDING,&fb);glGetIntegerv(GL_CURRENT_PROGRAM,&program);glGetIntegerv(GL_TEXTURE_BINDING_2D,&texture);
                    fprintf(stderr,"ICON frame=%lu pid=%u guestprog=%u hostprog=%d fb=%d texture=%d pixels=%u,%u,%u,%u/%u,%u,%u,%u\\n",frames,current_pid,blend->active_program,program,fb,texture,after[0],after[1],after[2],after[3],after[4],after[5],after[6],after[7]);
                }
            }
''')
target = out / 'glhost.c'
target.write_text(source)
subprocess.run(['bash', str(repo / 'tools/mhi2/glforward/build_host.sh'), str(out / 'glhost'), str(target)], check=True)
print(out / 'glhost')
