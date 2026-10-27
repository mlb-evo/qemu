"""Diagnostic KSS peer, with optional explicit active-design experiment."""
import sys
sys.dont_write_bytecode=True
import argparse
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file());sys.path.insert(0,str(REPO/'tools/fpk1'))
import kss_peer
p=argparse.ArgumentParser();p.add_argument('socket');p.add_argument('--timeout',type=float,default=20.0);p.add_argument('--period',type=float,default=.01);p.add_argument('--active-design',type=int,choices=(0,1));a=p.parse_args()
BaseLink=kss_peer.Link
class DiagnosticLink(BaseLink):
 def __init__(self,sock,log,period=.01,timeout=2.):super().__init__(sock,log,period=period,timeout=a.timeout)
 def enter(self,state):
  if self.cycles<5:self.log(f'debug {self.state}->{state}, CC6={int(self.cc6)}')
  super().enter(state)
kss_peer.Link=DiagnosticLink
if a.active_design is not None:
 BaseKss=kss_peer.Kss
 class DesignKss(BaseKss):
  def queue_config(self,log=False):
   super().queue_config(log=log)
   # Original KSS producer 0x10509f0 writes four identical design bytes;
   # GSS's 0x3cd receiver copies all four unchanged. Explicit fixture only.
   payload=bytes([a.active_design])*4
   if log:self.log(f'tx RTE BAP_DesignChange EXPERIMENT id=0x3cd value={payload.hex()} status=0')
   self.queue(*kss_peer.ipc.rte_signal(0x3cd,payload))
 kss_peer.Kss=DesignKss
kss_peer.run(a.socket,a.period)
