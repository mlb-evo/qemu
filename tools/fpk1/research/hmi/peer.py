"""Diagnostic KSS peer: tolerate host/guest scheduling stalls without changing payloads."""
import sys
sys.dont_write_bytecode=True
import argparse
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file());sys.path.insert(0,str(REPO/'tools/fpk1'))
import kss_peer
p=argparse.ArgumentParser();p.add_argument('socket');p.add_argument('--timeout',type=float,default=20.0);p.add_argument('--period',type=float,default=.01);a=p.parse_args()
BaseLink=kss_peer.Link
class DiagnosticLink(BaseLink):
 def __init__(self,sock,log,period=.01,timeout=2.):super().__init__(sock,log,period=period,timeout=a.timeout)
 def enter(self,state):
  if self.cycles<5:self.log(f'debug {self.state}->{state}, CC6={int(self.cc6)}')
  super().enter(state)
kss_peer.Link=DiagnosticLink
kss_peer.run(a.socket,a.period)
