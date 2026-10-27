"""Translate NVIDIA Tegra (AR20) shader binaries into GLSL ES 1.00 for glhost.

Local research. The translation is mechanical: every AR20 instruction becomes GLSL that
computes the same value, so no recovered source is needed. Fragment programs on Tegra
read the render target (PSEQ) to blend in the shader; that dependency is tracked
symbolically and expressed with dual-source blending (glhost blend mode 6):

    result = gl_FragColor + destination * gl_SecondaryFragColorEXT

which is exact for any blend that is linear in the destination, per channel. Programs
that do not read the destination overwrite it (mode 4), as Tegra has no blend unit.

Usage: translate.py BINARY... --output DIR   (writes <key>.glsl and <key>.blend)
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import re
import struct
from pathlib import Path

from ar20 import (GL_TYPES, Unsupported, alu_instruction, decode_fragment,
                  decode_vertex_words, fp20, fx10, is_fragment, records, sections,
                  vertex_instruction)


def glsl_float(value):
    if value != value or value in (float('inf'), float('-inf')):
        raise Unsupported('non-finite constant')
    text = repr(float(value))
    if 'e' in text:
        text = '%.9e' % value
    return text if text[0] != '-' else f'({text})'


COMPONENTS = 'xyzw'


def component_exprs(name, gltype, count=1):
    """GLSL scalar expressions for each component of a symbol, in register order."""
    base, size = GL_TYPES[gltype]
    out = []
    for element in range(count):
        ref = f'{name}[{element}]' if count > 1 else name
        if base in ('float', 'int', 'bool'):
            out.append(f'float({ref})' if base != 'float' else ref)
        elif base.startswith(('vec', 'ivec', 'bvec')):
            n = int(base[-1])
            for k in range(n):
                comp = f'{ref}.{COMPONENTS[k]}'
                out.append(comp if base.startswith('vec') else f'float({comp})')
        elif base.startswith('mat'):
            n = int(base[-1])
            for col in range(n):
                for k in range(n):
                    out.append(f'{ref}[{col}].{COMPONENTS[k]}')
        else:
            raise Unsupported(f'uniform type {base}')
    return out


def declaration(qualifier, name, gltype, count=1):
    base = GL_TYPES[gltype][0]
    suffix = f'[{count}]' if count > 1 else ''
    precision = '' if base in ('bool', 'bvec2', 'bvec3', 'bvec4') else 'highp '
    return f'{qualifier} {precision}{base} {name}{suffix};'


def varying_declarations(varyings, used=None):
    """Declare varyings once each; elements of an array arrive as separate `name[i]`."""
    sizes, types, order = {}, {}, []
    for v in varyings:
        m = re.fullmatch(r'(\w+)\[(\d+)\]', v['name'])
        base, index = (m.group(1), int(m.group(2))) if m else (v['name'], None)
        if used is not None and v['name'] not in used:
            if index is None or not any(u.startswith(base + '[') for u in used):
                continue
        if base not in types:
            order.append(base)
            types[base] = v['type']
        sizes[base] = max(sizes.get(base, 0), (index + 1) if index is not None else 0)
    return [declaration('varying', b, types[b], sizes[b] or 1) for b in order]


# -- containers ----------------------------------------------------------------------

def symbol_name(names, offset):
    return names[offset:].split(b'\0')[0].decode('latin-1')


def platform_fragment_model(data):
    sec = sections(data)
    names = sec[1][1]
    s13 = struct.unpack('<%dI' % (len(sec[13][1]) // 4), sec[13][1]) if 13 in sec else ()
    model = dict(varyings=[], uniforms=[], samplers={}, constants={})
    for w in records(sec.get(4, (0, b''))[1], 28):
        model['varyings'].append(dict(name=symbol_name(names, w[0]), type=w[3], count=w[4],
                                      layout=w[5], row=w[6]))
    sampler_names = {}
    for w in records(sec.get(14, (0, b''))[1], 8):
        sampler_names[symbol_name(names, w[1])] = (w[0] >> 8) & 0xff
    for w in records(sec.get(8, (0, b''))[1], 32):
        name, gltype, count = symbol_name(names, w[0]), w[1], w[2]
        location = s13[w[3]] if w[3] < len(s13) else 0xf001
        kind = location & 0xff
        if GL_TYPES[gltype][0] in ('sampler2D', 'samplerCube'):
            unit = sampler_names.get(name, location >> 16 if kind == 3 else None)
            if unit is not None and kind != 1:
                model['samplers'][unit] = dict(name=name, type=gltype)
            model['uniforms'].append(dict(name=name, type=gltype, count=count, placement=None))
            continue
        # One or two pieces: kind | first component << 8 | (count - 1) << 12 | slot << 16.
        # fp20 pieces take one register per component, fx10 pieces one half.
        placement = []
        pieces = [location] + ([s13[w[3] + 1]] if w[3] + 1 < len(s13) and s13[w[3] + 1] else [])
        for piece in pieces:
            kind, first, n, start = piece & 0xff, (piece >> 8) & 15, ((piece >> 12) & 15) + 1, piece >> 16
            if kind == 1:
                continue
            for k in range(n):
                if kind in (5, 14):
                    placement.append((first + k, 32 + start // 2 + k, 'f'))
                elif kind in (8, 9):
                    half = start + k
                    placement.append((first + k, 32 + half // 2, 'lh'[half & 1]))
                else:
                    raise Unsupported(f'uniform {name} location {piece:#x}')
        model['uniforms'].append(dict(name=name, type=gltype, count=count,
                                      placement=placement or None))
    if 18 in sec:
        blob = sec[18][1]
        for i, word in enumerate(struct.unpack('<%dI' % (len(blob) // 4), blob)):
            model['constants'][32 + i] = word
    return model


def platform_vertex_model(data):
    sec = sections(data)
    names = sec[1][1]
    s13 = struct.unpack('<%dI' % (len(sec[13][1]) // 4), sec[13][1]) if 13 in sec else ()
    model = dict(attributes=[], varyings=[], uniforms=[], constants={})
    for w in records(sec.get(2, (0, b''))[1], 16):
        model['attributes'].append(dict(name=symbol_name(names, w[0]), type=w[1], index=w[2]))
    for w in records(sec.get(3, (0, b''))[1], 24):
        model['varyings'].append(dict(name=symbol_name(names, w[0]), type=w[3], count=w[4],
                                      export=w[5]))
    for w in records(sec.get(8, (0, b''))[1], 32):
        name, gltype, count = symbol_name(names, w[0]), w[1], w[2]
        location = s13[w[3]] if w[3] < len(s13) else 0xf001
        kind = location & 0xff
        if kind == 1:
            placement = None
        elif kind == 4:
            placement = location >> 16
        else:
            raise Unsupported(f'vertex uniform {name} location {location:#x}')
        model['uniforms'].append(dict(name=name, type=gltype, count=count, placement=placement))
    if 18 in sec:
        blob = sec[18][1]
        for i in range(len(blob) // 16):
            model['constants'][i] = struct.unpack_from('<4f', blob, 16 * i)
    return model


# -- fragment ------------------------------------------------------------------------

class NonLinear(Unsupported):
    pass


class Val:
    """A scalar affine in the destination colour: base + sum(d[k] * DST[k])."""

    def __init__(self, base, d=None):
        self.base = base
        self.d = d if d and any(x is not None for x in d) else None

    @property
    def dependent(self):
        return self.d is not None


ZERO, ONE = '0.0', '1.0'


class FragmentTranslator:
    def __init__(self, data, model):
        self.program = decode_fragment(data)
        self.model = model
        self.lines = []
        self.temps = 0
        self.warnings = []
        self.used_varyings = set()
        self.used_uniforms = set()
        self.used_samplers = set()
        self.needs_coord = False
        self.discard = False
        self.output = None
        self.regs = {}
        self.alu_result = [{'l': Val(ZERO), 'h': Val(ZERO), 'f': Val(ZERO)} for _ in range(4)]
        self.cond = {}
        self._layout_varyings()
        self._layout_uniforms()

    # bookkeeping
    def warn(self, text):
        if text not in self.warnings:
            self.warnings.append(text)

    def temp(self, expr):
        if re.fullmatch(r'[\w.\[\]()-]+', expr) and not expr.startswith('('):
            return expr
        name = f't{self.temps}'
        self.temps += 1
        self.lines.append(f'  float {name}={expr};')
        return name

    def emit(self, line):
        self.lines.append('  ' + line)

    def _layout_varyings(self):
        self.tram = {}
        for v in self.model['varyings']:
            if v['count'] == 0:
                continue  # eliminated by the compiler
            if v['count'] != 1:
                raise Unsupported(f'varying array {v["name"]}')
            exprs = component_exprs(v['name'], v['type'])
            for k in range(len(exprs)):
                nibble = (v['layout'] >> (4 * k)) & 15
                kind, comp = nibble >> 2, nibble & 3
                if kind:
                    self.tram[(v['row'], comp, kind)] = (v['name'], exprs[k])

    def _layout_uniforms(self):
        self.ureg = {}
        for u in self.model['uniforms']:
            if u['placement'] is None:
                continue
            exprs = component_exprs(u['name'], u['type'], u['count'])
            for comp, reg, sel in u['placement']:
                if comp < len(exprs):
                    self.ureg.setdefault((reg, sel), (u['name'], exprs[comp]))

    # registers
    def reg(self, r):
        return self.regs.setdefault(r, {'l': Val(ZERO), 'h': Val(ZERO), 'f': Val(ZERO), 'kind': None})

    def write_full(self, r, v):
        self.regs[r] = {'l': v, 'h': v, 'f': v, 'kind': 'fp20'}

    def write_half(self, r, half, v):
        state = dict(self.reg(r))
        state[half] = v
        if state['kind'] != 'fx10':
            other = 'h' if half == 'l' else 'l'
            if state['kind'] == 'fp20':
                state[other] = state['f']
        state['kind'] = 'fx10'
        state['f'] = state['l']
        self.regs[r] = state

    def read_reg(self, r, sel, packet_imm):
        """sel: 'f' (fp20), 'l' or 'h' (fx10 half)."""
        if r < 16 or 16 <= r < 24:
            state = self.reg(r)
            if sel == 'f' and state['kind'] == 'fx10':
                self.warn(f'fp20 read of fx10 register r{r}')
            if r >= 16:
                self.warn(f'global register r{r}')
            return state[sel]
        if 24 <= r < 28:
            return self.alu_result[r - 24][sel]
        if 28 <= r < 31:
            if packet_imm is None:
                raise Unsupported(f'immediate r{r} without immediates')
            word = packet_imm[r - 28]
            if sel == 'f':
                return Val(glsl_float(fp20(word)))
            return Val(glsl_float(fx10(word >> (10 if sel == 'h' else 0))))
        if r == 31:
            if sel == 'f':
                self.warn('fp20 read of r31')
                return Val(ZERO)
            return Val(ONE if sel == 'h' else ZERO)
        if 32 <= r < 64:
            hit = self.ureg.get((r, sel)) or self.ureg.get((r, 'f'))
            if sel == 'f' and hit is None and (r, 'l') in self.ureg:
                hit = self.ureg[(r, 'l')]
                self.warn(f'fp20 read of fx10 uniform r{r}')
            if hit:
                self.used_uniforms.add(hit[0])
                return Val(hit[1])
            values = self.model.get('constant_values', {})
            if (r, sel) in values or (r, 'f') in values:
                return Val(glsl_float(values.get((r, sel), values.get((r, 'f')))))
            if r in self.model['constants']:
                word = self.model['constants'][r]
                if sel == 'f':
                    return Val(glsl_float(fp20(word)))
                return Val(glsl_float(fx10(word >> (10 if sel == 'h' else 0))))
            self.warn(f'uniform register r{r}.{sel} has no binding')
            return Val(ZERO)
        if 64 <= r < 72:
            return self.cond.get((r, 'h' if sel == 'h' else 'l'), Val(ZERO))
        if r in (72, 73):
            self.needs_coord = True
            # pos.x = 8192 + x; pos.y = 8192 + (height - 1) - y with a top-left origin,
            # which equals 8192 + y in GL's bottom-left convention.
            return Val(f'(8192.0+floor(gl_FragCoord.{"xy"[r - 72]}))')
        if r == 75:
            return Val('(gl_FrontFacing?1.0:-1.0)')
        raise Unsupported(f'ALU source register {r}')

    def operand(self, o, packet_imm):
        sel = ('h' if o['half'] else 'l') if o['fx10'] else 'f'
        v = self.read_reg(o['reg'], sel, packet_imm)
        if o['abs']:
            v = self.unary(v, 'abs({})')
        if o['x2']:
            v = self.scale(v, '2.0')
        if o['minus_one']:
            v = self.add(v, Val('(-1.0)'))
        if o['neg']:
            v = self.scale(v, '(-1.0)')
        return v

    def operand_d(self, x, packet_imm):
        d = x['d']
        if not d['enabled']:
            return Val(ONE)
        src = x['b'] if d['sel'] == 'B' else x['c']
        sel = ('h' if d['half'] else 'l') if d['fx10'] else 'f'
        v = self.read_reg(src['reg'], sel, packet_imm)
        if d['abs']:
            v = self.unary(v, 'abs({})')
        if d['minus_one']:
            v = self.add(v, Val('(-1.0)'))
        return v

    # affine arithmetic
    def unary(self, v, fmt):
        if v.dependent:
            raise NonLinear('nonlinear function of the destination colour')
        return Val(self.temp(fmt.format(v.base)))

    def scale(self, v, factor):
        base = ZERO if v.base == ZERO else self.temp(f'{v.base}*{factor}')
        d = [None if c is None else self.temp(f'{c}*{factor}') for c in v.d] if v.d else None
        return Val(base, d)

    def add(self, a, b):
        if a.base == ZERO:
            base = b.base
        elif b.base == ZERO:
            base = a.base
        else:
            base = self.temp(f'{a.base}+{b.base}')
        d = None
        if a.d or b.d:
            d = []
            for k in range(4):
                x = a.d[k] if a.d else None
                y = b.d[k] if b.d else None
                d.append(x if y is None else y if x is None else self.temp(f'{x}+{y}'))
        return Val(base, d)

    def mul(self, a, b):
        if a.dependent and b.dependent:
            raise NonLinear('product of two destination-dependent values')
        if b.dependent:
            a, b = b, a
        if b.base == ONE:
            return a
        if b.base == ZERO or a.base == ZERO and not a.dependent:
            return Val(ZERO)
        base = ZERO if a.base == ZERO else self.temp(f'{a.base}*{b.base}')
        d = [None if c is None else self.temp(f'{c}*{b.base}') for c in a.d] if a.d else None
        return Val(base, d)

    def binary(self, fmt, a, b):
        if a.dependent or b.dependent:
            raise NonLinear('nonlinear function of the destination colour')
        return Val(self.temp(fmt.format(a.base, b.base)))

    def saturate(self, v):
        if v.dependent:
            # The render target is unsigned normalised, so a final clamp is implicit;
            # intermediate clamps of blend terms are no-ops for inputs within [0, 1].
            self.warn('saturate of destination-dependent value dropped')
            return v
        return Val(self.temp(f'clamp({v.base},0.0,1.0)'))

    # units
    def run(self):
        p = self.program
        rows = p['rows'] or 1
        batches = p['batches']
        for start in range(0, len(batches), rows):
            group = batches[start:start + rows]
            for r, b in enumerate(group):
                self.row = r
                if b['pseq']:
                    self.pseq(b['pseq'])
                for m in b['mfu']:
                    self.mfu(m)
                if b['tex']:
                    self.tex(b['tex'])
            for r, b in enumerate(group):
                self.row = r
                for packet in b['alu']:
                    self.alu(packet)
            for r, b in enumerate(group):
                self.row = r
                if b['dw']:
                    self.dw(b['dw'])
        if self.output is None:
            raise Unsupported('program never writes a colour')

    def row_reg(self, k):
        return 4 * self.row + k

    def pseq(self, word):
        if word & ~0x000f000a != 0x00800000:
            raise Unsupported(f'PSEQ {word:#010x}')
        if (word >> 16) & 15 != 1:
            return  # depth/stencil readback for a late test after discard
        a, b = (self.row_reg(2), self.row_reg(3)) if word & 2 else (self.row_reg(0), self.row_reg(1))
        dst = lambda k: Val(ZERO, [ONE if j == k else None for j in range(4)])
        self.write_half(a, 'l', dst(0))
        self.write_half(a, 'h', dst(1))
        self.write_half(b, 'l', dst(2))
        self.write_half(b, 'h', dst(3))

    def mfu(self, m):
        sfu, reg = m['sfu'], m['reg']
        sfu_value = None
        if sfu:
            standard = (sfu == 1 and reg == 4 and m['mul0'] == dict(dst=1, src1=11, src0=10)
                        and m['mul1'] == dict(dst=1, src1=12, src0=10))
            if standard:
                pass
            elif reg < 4:
                v = self.reg(self.row_reg(reg))['f']
                if v.dependent:
                    raise NonLinear('special function of the destination colour')
                fmt = {1: '1.0/{}', 2: 'inversesqrt({})', 3: 'log2({})', 4: 'exp2({})',
                       5: 'sqrt({})', 6: 'sin({})', 7: 'cos({})', 8: 'fract({})',
                       9: '{}', 10: '{}', 11: '{}'}.get(sfu)
                if fmt is None:
                    raise Unsupported(f'SFU opcode {sfu}')
                sfu_value = Val(self.temp(fmt.format(v.base)))
                self.write_full(self.row_reg(reg), sfu_value)
            else:
                raise Unsupported(f'SFU on r{reg}')
        for mul in (m['mul0'], m['mul1']):
            if mul == dict(dst=0, src1=0, src0=0) or (sfu == 1 and reg == 4 and mul['dst'] == 1):
                continue
            if not 4 <= mul['dst'] <= 7:
                raise Unsupported(f'MFU multiplier {mul}')

            def source(s):
                if s < 4:
                    return self.reg(self.row_reg(s))['f']
                if s == 10 and sfu_value is not None:
                    return sfu_value
                if s == 13:
                    return Val(ONE)
                raise Unsupported(f'MFU multiplier source {s}')
            self.write_full(self.row_reg(mul['dst'] - 4), self.mul(source(mul['src0']), source(mul['src1'])))
        if m['unknown']:
            raise Unsupported('MFU bits 28..31')
        for k, var in enumerate(m['var']):
            if not var['op']:
                continue
            target = self.row_reg(k)
            if var['op'] == 1:
                v = self.varying(var['row'], k, 3)
                if var['sat']:
                    v = self.saturate(v)
                self.write_full(target, v)
            elif var['op'] == 2:
                lo, hi = self.varying(var['row'], k, 1), self.varying(var['row'], k, 2)
                if var['sat']:
                    lo, hi = self.saturate(lo), self.saturate(hi)
                self.write_half(target, 'l', lo)
                self.write_half(target, 'h', hi)
            else:
                raise Unsupported(f'interpolation opcode {var["op"]}')

    def varying(self, row, comp, kind):
        hit = self.tram.get((row, comp, kind))
        if hit is None:
            self.warn(f'TRAM {row}.{COMPONENTS[comp]} kind {kind} has no varying')
            return Val(ZERO)
        self.used_varyings.add(hit[0])
        return Val(hit[1])

    def tex(self, word):
        if not word & 0x400:
            return
        if word & ~0x1c3f:
            raise Unsupported(f'TEX {word:#x}')
        unit = word & 15
        coords = [2, 3, 0, 1] if word & 0x10 else [0, 1, 2, 3]
        dst = (2, 3) if word & 0x20 else (0, 1)
        sampler = self.model['samplers'].get(unit)
        if sampler is None:
            raise Unsupported(f'texture unit {unit} has no sampler')
        self.used_samplers.add(unit)
        c = [self.reg(self.row_reg(k))['f'] for k in coords]
        cube = GL_TYPES[sampler['type']][0] == 'samplerCube'
        used = [0, 1] + ([2] if cube else []) + ([3] if word & 0x1000 else [])
        if any(c[k].dependent for k in used):
            raise NonLinear('texture coordinate depends on the destination colour')
        if word & 0x800 and not cube:
            # Seen only on render-target filter taps; the sampled layout is unchanged.
            self.warn('TEX bit 11 treated as a plain 2D sample')
        if cube:
            call = f'textureCube({sampler["name"]},vec3({c[0].base},{c[1].base},{c[2].base})'
        else:
            call = f'texture2D({sampler["name"]},vec2({c[0].base},{c[1].base})'
        if word & 0x1000:
            call += f',{c[3].base}'
        name = f'x{self.temps}'
        self.temps += 1
        self.emit(f'vec4 {name}={call});')
        a, b = self.row_reg(dst[0]), self.row_reg(dst[1])
        self.write_half(a, 'l', Val(f'{name}.r'))
        self.write_half(a, 'h', Val(f'{name}.g'))
        self.write_half(b, 'l', Val(f'{name}.b'))
        self.write_half(b, 'h', Val(f'{name}.a'))

    def alu(self, packet):
        xs = [alu_instruction(raw) for raw in packet]
        uses_imm = any(x[o]['reg'] in (28, 29, 30) for x in xs[:3] for o in 'abc') or any(
            x['d']['enabled'] and (x['b'] if x['d']['sel'] == 'B' else x['c'])['reg'] in (28, 29, 30)
            for x in xs[:3])
        imm = None
        if uses_imm:
            raw = packet[3]
            value = ((raw & 0xffffffff) << 32) | (raw >> 32)
            imm = [(value >> 4) & 0xfffff, (value >> 24) & 0xfffff, (value >> 44) & 0xfffff]
            xs = xs[:3]
        results = [None] * len(xs)
        products = [None] * len(xs)
        for j, x in enumerate(xs):
            if x['recv']:
                continue
            products[j] = self.alu_core(x, imm, None)
        for j, x in enumerate(xs):
            if x['recv']:
                source = (j - 1) % 4
                if products[source] is None:
                    raise Unsupported('accumulation chain')
                products[j] = self.alu_core(x, imm, products[source][0])
        totals = [p[0] if p else None for p in products]
        for j in (3, 2, 1):
            if j < len(xs) and xs[j]['send']:
                target = {1: 0, 2: 0, 3: 2}[j]
                totals[target] = self.add(totals[target], totals[j])
        writes = []
        for j, x in enumerate(xs):
            value = totals[j]
            pair = products[j][1]
            value = self.finish(x, value)
            if pair is not None:
                pair = tuple(self.finish(x, v) for v in pair)
            results[j] = (value, pair)
            writes.append((x, value, pair))
        for j, (value, pair) in enumerate(results):
            if pair is not None:
                lo, hi = pair
                self.alu_result[j] = {'l': lo, 'h': hi, 'f': lo}
            else:
                self.alu_result[j] = {'l': value, 'h': value, 'f': value}
        for x, value, pair in writes:
            self.write(x, value, pair)

    def alu_core(self, x, imm, accumulated):
        a = self.operand(x['a'], imm)
        b = self.operand(x['b'], imm)
        c = accumulated if accumulated is not None else self.operand(x['c'], imm)
        d = self.operand_d(x, imm)
        op = x['opcode']
        if x['add_disable']:
            if op != 0:
                raise Unsupported('add disable on a non-MAD')
            ab, cd = self.mul(a, b), self.mul(c, d)
            lo, hi = (cd, ab) if x['high'] and not x['low'] else (ab, cd)
            return lo, (lo, hi)
        if op == 0:
            return self.add(self.mul(a, b), self.mul(c, d)), None
        if op == 1:
            return self.binary('min({},{})', self.mul(a, b), self.mul(c, d)), None
        if op == 2:
            return self.binary('max({},{})', self.mul(a, b), self.mul(c, d)), None
        cd = self.mul(c, d)
        if a.dependent or b.dependent or cd.dependent:
            raise NonLinear('select on the destination colour')
        return Val(self.temp(f'({a.base}<0.0?{b.base}:{cd.base})')), None

    def finish(self, x, v):
        if x['scale']:
            v = self.scale(v, {1: '2.0', 2: '4.0', 3: '0.5'}[x['scale']])
        if x['sat']:
            v = self.saturate(v)
        if x['cond']:
            if v.dependent:
                raise NonLinear('condition on the destination colour')
            test = {1: '==', 2: '>', 3: '>='}[x['cond']]
            v = Val(self.temp(f'({v.base}{test}0.0?1.0:0.0)'))
        return v

    def write(self, x, value, pair):
        r = x['dst']
        if r == 31:
            return
        if r == 76:
            if value.dependent:
                raise NonLinear('discard on the destination colour')
            self.emit(f'if({value.base}!=0.0) discard;')
            self.discard = True
            return
        if 64 <= r < 72:
            if value.dependent:
                raise NonLinear('condition register from the destination colour')
            flag = Val(self.temp(f'({value.base}!=0.0?1.0:0.0)'))
            self.cond[(r, 'h' if x['high'] else 'l')] = flag
            return
        if not (r < 24):
            raise Unsupported(f'ALU destination r{r}')
        if pair is not None:
            self.write_half(r, 'l', pair[0])
            self.write_half(r, 'h', pair[1])
        elif x['high'] and x['low']:
            self.write_full(r, value)
        elif x['high']:
            self.write_half(r, 'h', value)
        elif x['low']:
            self.write_half(r, 'l', value)

    def dw(self, word):
        if not word & 1:
            return
        if (word >> 2) & 15 != 1:
            return  # depth, stencil and coverage stores are the late test's business
        if word not in (0x00028005, 0x00020005):
            raise Unsupported(f'DW {word:#010x}')
        a, b = (self.row_reg(2), self.row_reg(3)) if word & 0x8000 else (self.row_reg(0), self.row_reg(1))
        ra, rb = self.reg(a), self.reg(b)
        self.output = [ra['l'], ra['h'], rb['l'], rb['h']]

    def source(self):
        self.run()
        color = self.output
        dependent = any(v.dependent for v in color)
        if dependent:
            for c, v in enumerate(color):
                if v.d and any(v.d[k] is not None for k in range(4) if k != c):
                    raise NonLinear('cross-channel destination dependency')
        out = ['  gl_FragColor=vec4(' + ','.join(v.base for v in color) + ');']
        if dependent:
            out.append('  gl_SecondaryFragColorEXT=vec4(' + ','.join(
                (v.d[c] if v.d and v.d[c] is not None else ZERO) for c, v in enumerate(color)) + ');')
        head = []
        if dependent:
            head.append('#extension GL_EXT_blend_func_extended : require')
        head.append('precision highp float;')
        declared = set()
        head.extend(varying_declarations(self.model['varyings'], self.used_varyings))
        for u in self.model['uniforms']:
            if u['name'] in declared:
                continue
            is_sampler = GL_TYPES[u['type']][0].startswith('sampler')
            used = (u['name'] in self.used_uniforms or
                    is_sampler and any(s['name'] == u['name'] for k, s in self.model['samplers'].items()
                                       if k in self.used_samplers))
            if used:
                declared.add(u['name'])
                head.append(declaration('uniform', u['name'], u['type'], u['count']))
        body = ['void main(){'] + self.lines + out + ['}']
        return '\n'.join(head + body) + '\n', (6 if dependent else 4)


# -- vertex --------------------------------------------------------------------------

VECTOR_OPS = {
    1: 'mov', 2: 'mul', 3: 'add', 4: 'mad', 5: 'dp3', 6: 'dph', 7: 'dp4', 8: 'dst',
    9: 'min', 10: 'max', 11: 'slt', 12: 'sge', 14: 'frc', 15: 'flr', 16: 'seq', 17: 'sfl',
    18: 'sgt', 19: 'sle', 20: 'sne', 21: 'str', 22: 'ssg',
}
SCALAR_OPS = {1: 'mov', 2: 'rcp', 3: 'rcc', 4: 'rsq', 5: 'exp', 6: 'log', 13: 'lg2',
              14: 'ex2', 15: 'sin', 16: 'cos', 9: 'bra'}


class VertexTranslator:
    def __init__(self, data, model):
        self.code = [vertex_instruction(v) for v in decode_vertex_words(data)]
        self.model = model
        self.warnings = []

    def constant_register(self, index):
        comps = list(self.model['constants'].get(index, (0.0, 0.0, 0.0, 0.0)))
        comps = [glsl_float(x) for x in comps]
        for u in self.model['uniforms']:
            if u['placement'] is None:
                continue
            exprs = component_exprs(u['name'], u['type'], u['count'])
            base = GL_TYPES[u['type']][0]
            stride = int(base[-1]) if base.startswith('mat') else None
            for k, expr in enumerate(exprs):
                if stride:
                    reg = u['placement'] // 4 + k // stride
                    comp = u['placement'] % 4 + k % stride
                elif base in ('float', 'int', 'bool') and u['count'] > 1:
                    reg, comp = u['placement'] // 4 + k, u['placement'] % 4
                else:
                    per = len(component_exprs(u['name'], u['type'])) if u['count'] > 1 else None
                    if per:
                        reg = u['placement'] // 4 + k // per
                        comp = u['placement'] % 4 + k % per
                    else:
                        flat = u['placement'] + k
                        reg, comp = flat // 4, flat % 4
                if reg == index and comp < 4:
                    comps[comp] = expr
                    self.used_uniforms.add(u['name'])
        return f'vec4({",".join(comps)})'

    def source(self):
        self.used_uniforms = set()
        code = []
        for i, x in enumerate(self.code):
            code.append(x)
            if x['end']:
                break
        branches = any(x['sop'] == 9 for x in code)
        attrs = {a['index']: a for a in self.model['attributes']}
        lines = []
        used_attrs, used_consts, used_regs, exported = set(), set(), set(), set()

        def swz(value):
            return ''.join(COMPONENTS[(value >> (6 - 2 * k)) & 3] for k in range(4))

        def src(x, which):
            s = x[which]
            t = s['type']
            if t == 1:
                name = f'r{s["reg"]}'
                used_regs.add(s['reg'])
            elif t == 2 or t == 0:
                if x['attr_relative']:
                    raise Unsupported('relative attribute addressing')
                name = f'v{x["attr"]}'
                used_attrs.add(x['attr'])
            else:
                if x['const_relative']:
                    raise Unsupported('relative constant addressing')
                name = f'c{x["const"]}'
                used_consts.add(x['const'])
            expr = f'{name}.{swz(s["swizzle"])}'
            if x['abs'][' ABC'.index(which) - 1]:
                expr = f'abs({expr})'
            if s['neg']:
                expr = f'(-{expr})'
            return expr

        def mask(m):
            return ''.join(COMPONENTS[k] for k in range(4) if m & (8 >> k))

        def predicate(x, comp):
            pred = x['pred']
            cr = f'cr{x["cond_reg"]}.{COMPONENTS[(x["pred_swizzle"] >> (6 - 2 * comp)) & 3]}'
            tests = [t for t, on in zip((f'{cr}>0.0', f'{cr}==0.0', f'{cr}<0.0'), pred) if on]
            if len(tests) == 3:
                return 'true'
            if not tests:
                return 'false'
            return '(' + '||'.join(tests) + ')'

        for i, x in enumerate(code):
            body = []
            if x['export_relative']:
                raise Unsupported('relative export addressing')
            vop, sop = x['vop'], x['sop']
            if vop not in (0,) and vop not in VECTOR_OPS:
                raise Unsupported(f'vector opcode {vop}')
            if sop not in (0,) and sop not in SCALAR_OPS:
                raise Unsupported(f'scalar opcode {sop}')
            if vop:
                a, b, c = src(x, 'A'), src(x, 'B'), src(x, 'C')
                expr = {
                    'mov': a, 'mul': f'{a}*{b}', 'add': f'{a}+{c}', 'mad': f'{a}*{b}+{c}',
                    'dp3': f'vec4(dot({a}.xyz,{b}.xyz))', 'dph': f'vec4(dot({a},vec4({b}.xyz,1.0)))',
                    'dp4': f'vec4(dot({a},{b}))',
                    'dst': f'vec4(1.0,{a}.y*{b}.y,{a}.z,{b}.w)',
                    'min': f'min({a},{b})', 'max': f'max({a},{b})',
                    'slt': f'vec4(lessThan({a},{b}))', 'sge': f'vec4(greaterThanEqual({a},{b}))',
                    'frc': f'fract({a})', 'flr': f'floor({a})', 'seq': f'vec4(equal({a},{b}))',
                    'sfl': 'vec4(0.0)', 'sgt': f'vec4(greaterThan({a},{b}))',
                    'sle': f'vec4(lessThanEqual({a},{b}))', 'sne': f'vec4(notEqual({a},{b}))',
                    'str': 'vec4(1.0)', 'ssg': f'sign({a})',
                }[VECTOR_OPS[vop]]
                if x['sat']:
                    expr = f'clamp({expr},0.0,1.0)'
                body.append(f'vv=vec4({expr});')
            if sop and sop != 9:
                c = src(x, 'C') + '.x'
                expr = {
                    'mov': None, 'rcp': f'1.0/{c}',
                    'rcc': f'sign({c})*clamp(1.0/abs({c}),5.421011e-20,1.844674e19)',
                    'rsq': f'inversesqrt({c})', 'lg2': f'log2({c})', 'ex2': f'exp2({c})',
                    'sin': f'sin({c})', 'cos': f'cos({c})',
                    'exp': None, 'log': None,
                }[SCALAR_OPS[sop]]
                if SCALAR_OPS[sop] == 'mov':
                    full = src(x, 'C')
                elif SCALAR_OPS[sop] == 'exp':
                    full = f'vec4(exp2(floor({c})),fract({c}),exp2({c}),1.0)'
                elif SCALAR_OPS[sop] == 'log':
                    full = (f'vec4(floor(log2(abs({c}))),abs({c})/exp2(floor(log2(abs({c})))),'
                            f'log2(abs({c})),1.0)')
                else:
                    full = f'vec4({expr})'
                if x['sat']:
                    full = f'clamp({full},0.0,1.0)'
                body.append(f'sv={full};')
            # writes
            writes = []
            if vop:
                if x['vdst'] != 63 and x['vmask']:
                    writes.append(('vv', f'r{x["vdst"]}', x['vmask']))
                    used_regs.add(x['vdst'])
                if x['export'] != 31 and x['export_vector']:
                    writes.append(('vv', f'o{x["export"]}', x['vmask']))
            if sop and sop != 9:
                if x['sdst'] != 63 and x['smask'] and not (vop and x['sdst'] == x['vdst']
                                                            and x['vdst'] != 63):
                    writes.append(('sv', f'r{x["sdst"]}', x['smask']))
                    used_regs.add(x['sdst'])
                elif vop and x['sdst'] == x['vdst'] and x['vdst'] != 63 and x['smask']:
                    rest = x['smask'] & ~x['vmask']
                    if rest:
                        writes.append(('sv', f'r{x["sdst"]}', rest))
                        used_regs.add(x['sdst'])
                if x['export'] != 31 and not x['export_vector']:
                    writes.append(('sv', f'o{x["export"]}', x['smask']))
            for value, target, m in writes:
                if target.startswith('o'):
                    exported.add(int(target[1:]))
                if x['cond_check']:
                    for k in range(4):
                        if m & (8 >> k):
                            body.append(f'if({predicate(x, k)}) {target}.{COMPONENTS[k]}={value}.{COMPONENTS[k]};')
                else:
                    body.append(f'{target}.{mask(m)}={value}.{mask(m)};')
            if x['cond_write'] and x['cond_set']:
                value, m = ('vv', x['vmask']) if vop else ('sv', x['smask'])
                if vop or (sop and sop != 9):
                    for k in range(4):
                        if m & (8 >> k):
                            body.append(f'cr{x["cond_reg"]}.{COMPONENTS[k]}={value}.{COMPONENTS[k]};')
            if sop == 9:
                target = x['C']['swizzle']
                if target <= i:
                    raise Unsupported('backward branch')
                body.append(f'if({predicate(x, 0)}) pc={float(target)};')
            elif x['cond_write'] and not x['cond_set'] and not x['cond_check']:
                raise Unsupported('condition write without set')
            if branches:
                lines.append(f'  if(pc<={float(i)}){{' + ''.join(body) + '}')
            else:
                lines.extend('  ' + b for b in body)

        head = ['precision highp float;']
        for idx in sorted(used_attrs):
            a = attrs.get(idx)
            if a is None:
                raise Unsupported(f'attribute register v{idx} has no attribute')
            head.append(declaration('attribute', a['name'], a['type']))
        head.extend(varying_declarations(self.model['varyings']))
        for v in self.model['varyings']:
            if v['count'] > 1:
                raise Unsupported(f'varying array {v["name"]}')
            if v['count']:
                exported.add(v['export'])
        consts = [f'  vec4 c{k}={self.constant_register(k)};' for k in sorted(used_consts)]
        for u in self.model['uniforms']:
            if u['name'] in self.used_uniforms:
                head.append(declaration('uniform', u['name'], u['type'], u['count']))
        init = ['void main(){', '  vec4 vv=vec4(0.0),sv=vec4(0.0),cr0=vec4(0.0),cr1=vec4(0.0);']
        if branches:
            init.append('  float pc=0.0;')
        for k in sorted(used_regs):
            init.append(f'  vec4 r{k}=vec4(0.0);')
        for k in sorted(exported | {0}):
            init.append(f'  vec4 o{k}=vec4(0.0);')
        for idx in sorted(used_attrs):
            a = attrs[idx]
            n = GL_TYPES[a['type']][1]
            pad = {1: ',0.0,0.0,1.0', 2: ',0.0,1.0', 3: ',1.0', 4: ''}[n]
            init.append(f'  vec4 v{idx}=vec4({a["name"]}{pad});')
        tail = ['  gl_Position=o0;']
        for v in self.model['varyings']:
            n = GL_TYPES[v['type']][1]
            if v['count']:
                tail.append(f'  {v["name"]}=o{v["export"]}.{"xyzw"[:n]};')
            else:
                tail.append(f'  {v["name"]}={GL_TYPES[v["type"]][0]}(0.0);')
        return '\n'.join(head + init + consts + lines + tail + ['}']) + '\n', 0


def translate(data, model=None):
    if is_fragment(data):
        model = model or platform_fragment_model(data)
        translator = FragmentTranslator(data, model)
    else:
        model = model or platform_vertex_model(data)
        translator = VertexTranslator(data, model)
    source, blend = translator.source()
    return source, blend, translator.warnings


def fnv(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('binaries', nargs='+', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--report', type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = []
    for path in args.binaries:
        data = path.read_bytes()
        key = f'{fnv(data):016x}-{len(data)}'
        row = dict(key=key, stage='fragment' if is_fragment(data) else 'vertex')
        try:
            source, blend, warnings = translate(data)
        except Unsupported as error:
            row.update(ok=False, error=f'{type(error).__name__}: {error}')
        else:
            (args.output / f'{key}.glsl').write_text(source)
            (args.output / f'{key}.blend').write_text(f'{blend}\n')
            row.update(ok=True, blend=blend, warnings=warnings)
        report.append(row)
    ok = sum(r['ok'] for r in report)
    print(f'translated {ok}/{len(report)}')
    for r in report:
        if not r['ok']:
            print(' ', r['key'], r['stage'], r['error'])
    if args.report:
        args.report.write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
