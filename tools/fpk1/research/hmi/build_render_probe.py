"""Build a local glhost probe for replaying MHI2_GL_CAPTURE recordings."""
import argparse
import re
import subprocess
from pathlib import Path

repo = next(p for p in Path(__file__).resolve().parents if (p / 'hw/arm/fpk1.c').is_file())
out = repo / 'build_fpk1/research-artifacts/blank-screen/render-probe'
out.mkdir(parents=True, exist_ok=True)
original = repo / 'tools/mhi2/glforward/host/glhost.c'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--revision', help='read glhost.c at this Git revision instead of the workspace')
args = parser.parse_args()
source = (subprocess.check_output(['git', 'show', f'{args.revision}:tools/mhi2/glforward/host/glhost.c'],
                                  cwd=repo, text=True) if args.revision else original.read_text())
source = re.sub(r'#include "([^"]+)"', lambda m: f'#include "{original.parent / m[1]}"', source)
source = source.replace('glReadPixels(0, 0, win_w, win_h, GL_RGBA, GL_UNSIGNED_BYTE, rgba);', '''GLint probe_read_fb=0;
    glGetIntegerv(GL_FRAMEBUFFER_BINDING,&probe_read_fb);
    if(getenv("PROBE_DEFAULT_READ"))glBindFramebuffer(GL_FRAMEBUFFER,0);
    glReadPixels(0, 0, win_w, win_h, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
    if(getenv("PROBE_DEFAULT_READ"))glBindFramebuffer(GL_FRAMEBUFFER,probe_read_fb);
''')
source = source.replace('glReadPixels(i32(p,0),i32(p,4),i32(p,8),i32(p,12),GL_RGBA,GL_UNSIGNED_BYTE,pixels);', '''GLint probe_read_fb=0;
            glGetIntegerv(GL_FRAMEBUFFER_BINDING,&probe_read_fb);
            if(op==131 && getenv("PROBE_DEFAULT_READ"))glBindFramebuffer(GL_FRAMEBUFFER,0);
            glReadPixels(i32(p,0),i32(p,4),i32(p,8),i32(p,12),GL_RGBA,GL_UNSIGNED_BYTE,pixels);
            if(op==131 && getenv("PROBE_DEFAULT_READ"))glBindFramebuffer(GL_FRAMEBUFFER,probe_read_fb);
''')
source = source.replace('dump_frame(frame_path());', 'if(getenv("PROBE_KEEP_PRIMARY"))dump_frame(frame_path());')
source = source.replace('case 5:  ensure_window(0, 0);', '''case 5:  ensure_window(0, 0);
                 if (getenv("PROBE_FRAMES") && (frames % 30 == 0 || (getenv("PROBE_TARGET") && frames == strtoul(getenv("PROBE_TARGET"),0,10)))) {
                     char path[4096];
                     snprintf(path, sizeof(path), "%s/frame-%06lu-%u.ppm", getenv("PROBE_FRAMES"), frames, current_pid);
                     dump_frame(path);
                 }
''')
source = source.replace('begin_binary_blend(mode,&saved);', '''begin_binary_blend(mode,&saved);
            GLboolean probe_depth=glIsEnabled(GL_DEPTH_TEST), probe_stencil=glIsEnabled(GL_STENCIL_TEST), probe_cull=glIsEnabled(GL_CULL_FACE);
            if(getenv("PROBE_NO_DEPTH"))glDisable(GL_DEPTH_TEST);
            if(getenv("PROBE_NO_STENCIL"))glDisable(GL_STENCIL_TEST);
            if(getenv("PROBE_NO_CULL"))glDisable(GL_CULL_FACE);
            if(getenv("PROBE_DRAW_STATE") && (frames % 120 == 0 || (getenv("PROBE_TARGET") && frames == strtoul(getenv("PROBE_TARGET"),0,10)))){
                GLint fb=0,prog=0,vp[4]={0},tex=0;
                glGetIntegerv(GL_FRAMEBUFFER_BINDING,&fb);glGetIntegerv(GL_CURRENT_PROGRAM,&prog);
                glGetIntegerv(GL_VIEWPORT,vp);glGetIntegerv(GL_TEXTURE_BINDING_2D,&tex);
                fprintf(stderr,"PROBE frame=%lu pid=%u guestprog=%u hostprog=%d mode=%u fb=%d vp=%d,%d,%d,%d texture=%d depth=%d stencil=%d cull=%d count=%d\\n",frames,current_pid,blend->active_program,prog,mode,fb,vp[0],vp[1],vp[2],vp[3],tex,probe_depth,probe_stencil,probe_cull,i32(p,4));
            }
''')
source = source.replace('end_binary_blend(mode,&saved);', '''end_binary_blend(mode,&saved);
            GLenum probe_error=glGetError();
            if(probe_error)fprintf(stderr,"PROBE ERROR frame=%lu pid=%u program=%u error=%#x\\n",frames,current_pid,blend->active_program,probe_error);
            if(probe_depth)glEnable(GL_DEPTH_TEST);
            if(probe_stencil)glEnable(GL_STENCIL_TEST);
            if(probe_cull)glEnable(GL_CULL_FACE);
''')
target = out / 'glhost.c'
target.write_text(source)
subprocess.run(['bash', str(repo / 'tools/mhi2/glforward/build_host.sh'), str(out / 'glhost'), str(target)], check=True)
print(out / 'glhost')
