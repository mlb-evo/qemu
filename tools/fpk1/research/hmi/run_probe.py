"""Boot unmodified firmware with validated shaders and an isolated diagnostic KSS peer."""
import sys
sys.dont_write_bytecode=True
import argparse,datetime,json,os,subprocess
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file());SCRIPT=Path(__file__).resolve().parent
sys.path.insert(0,str(REPO/'tools/fpk1'))
import run_stage1_console as console
parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=90);a=parser.parse_args()
out=REPO/'build_fpk1/runs'/('hmi-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
original=subprocess.Popen
class RedirectPeer:
 def __call__(self,args,*pos,**kwargs):
  if isinstance(args,list) and len(args)>1 and str(args[1]).endswith('/kss_peer.py'):args=[args[0],str(SCRIPT/'peer.py'),*args[2:]]
  return original(args,*pos,**kwargs)
subprocess.Popen=RedirectPeer()
os.environ.update(MHI2_GL_WIDTH='1440',MHI2_GL_HEIGHT='540',TEGRA_GR3D_DISCARD='1',PYTHONDONTWRITEBYTECODE='1')
print('HMI run:',out,flush=True)
r=console.run(REPO/'AU_C1_AU736_0378_1280_prod_8S0906961AK_Q7_2018.zip',REPO/'build_fpk1/qemu/qemu-system-arm',a.seconds,icount_shift=0,emmc=REPO/'build_fpk1/media/emmc.img',keep_dir=out,cmdline=console.BOARD_CMDLINE,replacements={n:(REPO/'build_fpk1/bridge'/Path(n).name).read_bytes() for n in ('lib/libEGL.so','lib/libGLESv2.so')},glhost=REPO/'tools/fpk1/research/shader_groups/glhost',gl_frames=out/'frames',viewer=False,kss=True,progress=lambda l:print(f"[{l['t']}] {l['text']}",flush=True))
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
