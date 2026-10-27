"""Print a decoded AR20 fragment program in a compact, field-explicit form."""
import sys
sys.dont_write_bytecode = True
from ar20 import decode_fragment, alu_instruction, fp20, fx10

SFU = ['nop', 'rcp', 'rsq', 'lg2', 'ex2', 'sqrt', 'sin', 'cos', 'frc', 'preex2', 'presin', 'precos']
ALU = ['mad', 'min', 'max', 'cmp']


def opnd(o):
    s = f"r{o['reg']}"
    if o['fx10']:
        s += '.h' if o['half'] else '.l'
    elif o['half']:
        s += '.H?'
    if o['minus_one']: s += '-1'
    if o['abs']: s = f'|{s}|'
    if o['x2']: s += '*2'
    if o['neg']: s = '-' + s
    return s


def show(data):
    p = decode_fragment(data)
    print('rows', p['rows'], 'count', p['count'])
    for i, b in enumerate(p['batches']):
        print(f'--- {i}: pseq {b["pseq"]:08x} tex {b["tex"]:08x} dw {b["dw"]:08x} comp {b["complement"]:08x}')
        for m in b['mfu']:
            v = ' '.join(f"{['nop','var1','var2','v3'][x['op']]}{'s' if x['sat'] else ''}:t{x['row']}" for x in m['var'])
            print(f"  MFU sfu {SFU[m['sfu']] if m['sfu']<len(SFU) else m['sfu']} r{m['reg']} mul0 {m['mul0']} mul1 {m['mul1']} unk {m['unknown']} | {v}")
        for k, packet in enumerate(b['alu']):
            for j, raw in enumerate(packet):
                x = alu_instruction(raw)
                if j == 3 and False: pass
                d = x['d']
                ds = f"rD({d['sel']}{'.h' if d['half'] else '.l'}{' fx' if d['fx10'] else ''}{' -1' if d['minus_one'] else ''}{' abs' if d['abs'] else ''})" if d['enabled'] else 'rD=1'
                flags = ''.join(f' {n}' for n in ('send', 'recv', 'add_disable', 'sat') if x[n])
                if x['scale']: flags += f" scale{x['scale']}"
                if x['cond']: flags += f" cond{x['cond']}"
                print(f"  ALU{k}.{j} {raw:016x} {ALU[x['opcode']]} r{x['dst']}.{'h' if x['high'] else '_'}{'l' if x['low'] else '_'} = {opnd(x['a'])}, {opnd(x['b'])}, {opnd(x['c'])}, {ds}{flags}")


if __name__ == '__main__':
    for path in sys.argv[1:]:
        print('==', path)
        show(open(path, 'rb').read())
