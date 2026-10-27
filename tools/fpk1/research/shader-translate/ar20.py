"""Decode NVIDIA Tegra (AR20) shader binaries: container, fragment and vertex programs.

Local research decoder. Field layouts follow grate's docs/fragment-shader-isa.md and
docs/vertex-shader-isa.md; anything not covered there is rejected rather than guessed.
"""
import sys
sys.dont_write_bytecode = True
import struct

GL_TYPES = {
    0x1406: ('float', 1), 0x8b50: ('vec2', 2), 0x8b51: ('vec3', 3), 0x8b52: ('vec4', 4),
    0x8b5a: ('mat2', 4), 0x8b5b: ('mat3', 9), 0x8b5c: ('mat4', 16),
    0x1404: ('int', 1), 0x8b53: ('ivec2', 2), 0x8b54: ('ivec3', 3), 0x8b55: ('ivec4', 4),
    0x8b56: ('bool', 1), 0x8b57: ('bvec2', 2), 0x8b58: ('bvec3', 3), 0x8b59: ('bvec4', 4),
    0x8b5e: ('sampler2D', 1), 0x8b60: ('samplerCube', 1),
}


class Unsupported(ValueError):
    pass


def program_section(data):
    """Section 19 of a platform binary; a cgc container's code; else the data itself."""
    if data[8:12] == bytes.fromhex('18000100'):
        return sections(data)[19][1]
    if data[:4] in (b'\x5e\x1b\x00\x00', b'\x5d\x1b\x00\x00'):
        length, offset = struct.unpack_from('<2I', data, 24)
        return data[offset:offset + length]
    return data


def stream_words(data):
    """The host1x command stream of the program section."""
    data = program_section(data)
    at = data.find(b'AR20-BIN')
    if at >= 0:
        rows, count = struct.unpack_from('<2I', data, at + 8)
        start = at + 16
    else:
        rows = count = None
        start = 0
    words = struct.unpack_from('<' + 'I' * ((len(data) - start) // 4), data, start)
    return words, rows, count


def host1x(words):
    """Yield (method, value) register writes of a host1x stream."""
    i = 0
    while i < len(words):
        cmd = words[i]
        i += 1
        op, method, count = cmd >> 28, (cmd >> 16) & 0xfff, cmd & 0xffff
        if op == 1:
            for j in range(count):
                yield method + j, words[i + j]
            i += count
        elif op == 2:
            for j in range(count):
                yield method, words[i + j]
            i += count
        elif op == 3:
            for j in range(16):
                if count & (1 << j):
                    yield method + j, words[i]
                    i += 1
        elif op == 4:
            yield method, count
        elif op == 0 and cmd == 0:
            break
        else:
            raise Unsupported(f'host1x opcode {cmd:#010x}')


# -- fragment program ----------------------------------------------------------

FRAGMENT_ARRAYS = {0x541: 0x540, 0x601: 0x600, 0x604: 0x603, 0x701: 0x700,
                   0x801: 0x800, 0x804: 0x803, 0x806: 0x805, 0x901: 0x900}


def fragment_arrays(words):
    arrays = {k: [] for k in FRAGMENT_ARRAYS}
    regs = {}
    for method, value in host1x(words):
        if method in arrays:
            arr = arrays[method]
            index = regs.get(FRAGMENT_ARRAYS[method], 0)
            while len(arr) <= index:
                arr.append(0)
            arr[index] = value
            regs[FRAGMENT_ARRAYS[method]] = index + 1
        else:
            regs[method] = value
    return arrays, regs


def alu_operand(v):
    return dict(reg=v >> 6, half=(v >> 5) & 1, minus_one=(v >> 4) & 1, fx10=(v >> 3) & 1,
                abs=(v >> 2) & 1, neg=(v >> 1) & 1, x2=v & 1)


def alu_instruction(ins):
    d = ins & 63
    return dict(raw=ins, opcode=ins >> 62, send=(ins >> 61) & 1, recv=(ins >> 60) & 1,
                add_disable=(ins >> 59) & 1, scale=(ins >> 57) & 3, sat=(ins >> 56) & 1,
                cond=(ins >> 54) & 3, dst=(ins >> 47) & 127, high=(ins >> 46) & 1,
                low=(ins >> 45) & 1,
                a=alu_operand((ins >> 32) & 8191), b=alu_operand((ins >> 19) & 8191),
                c=alu_operand((ins >> 6) & 8191),
                d=dict(sel='C' if d & 32 else 'B', half=(d >> 4) & 1, minus_one=(d >> 3) & 1,
                       enabled=(d >> 2) & 1, abs=(d >> 1) & 1, fx10=d & 1))


def mfu_instruction(hi, lo):
    def mul(v):
        return dict(dst=(v >> 8) & 7, src1=(v >> 4) & 15, src0=v & 15)
    var = []
    for k in range(4):
        v = (lo >> (7 * k)) & 127
        var.append(dict(row=v >> 3, op=(v >> 1) & 3, sat=v & 1))
    return dict(raw=(hi << 32) | lo, reg=hi >> 26, sfu=(hi >> 22) & 15,
                mul1=mul((hi >> 11) & 0x7ff), mul0=mul(hi & 0x7ff), unknown=(lo >> 28) & 15,
                var=var)


def schedule(entry):
    return entry >> 2, entry & 3


def decode_fragment(data):
    words, rows, count = stream_words(data)
    arrays, regs = fragment_arrays(words)
    n = count if count is not None else max(len(arrays[0x601]), len(arrays[0x801]))
    batches = []
    for i in range(n):
        get = lambda m: arrays[m][i] if i < len(arrays[m]) else 0
        mfu = []
        address, number = schedule(get(0x601))
        for j in range(number):
            hi, lo = arrays[0x604][2 * (address + j):2 * (address + j) + 2]
            mfu.append(mfu_instruction(hi, lo))
        alu = []
        address, number = schedule(get(0x801))
        for j in range(number):
            raw = arrays[0x804][8 * (address + j):8 * (address + j) + 8]
            alu.append([(raw[2 * k] << 32) | raw[2 * k + 1] for k in range(4)])
        batches.append(dict(pseq=get(0x541), mfu=mfu, tex=get(0x701), alu=alu,
                            complement=get(0x806), dw=get(0x901)))
    return dict(rows=rows, count=n, batches=batches, regs=regs)


def fp20(v):
    """Decode a 20-bit float (1 sign, 6 exponent bias 31, 13 mantissa)."""
    sign = -1.0 if v & 0x80000 else 1.0
    exponent = (v >> 13) & 63
    mantissa = v & 0x1fff
    if exponent == 0 and mantissa == 0:
        return 0.0 * sign
    if exponent == 0:
        return sign * mantissa / 8192.0 * 2.0 ** -30
    return sign * (1 + mantissa / 8192.0) * 2.0 ** (exponent - 31)


def fx10(v):
    v &= 0x3ff
    return (v - 0x400 if v & 0x200 else v) / 256.0


# -- vertex program ------------------------------------------------------------

def decode_vertex_words(data):
    if data[:4] == b'\x5d\x1b\x00\x00':
        # A cgc container holds the raw VLIW words rather than a host1x upload.
        code = program_section(data)
        w = struct.unpack('<%dI' % (len(code) // 4), code)
        return [(w[i] << 96) | (w[i + 1] << 64) | (w[i + 2] << 32) | w[i + 3]
                for i in range(0, len(w) - 3, 4)]
    words, _rows, _count = stream_words(data)
    program = []
    for method, value in host1x(words):
        if method == 0x206:
            program.append(value)
    if len(program) % 4:
        raise Unsupported('vertex program is not a whole number of instructions')
    return [(program[i] << 96) | (program[i + 1] << 64) | (program[i + 2] << 32) | program[i + 3]
            for i in range(0, len(program), 4)]


def bits(v, lo, hi):
    return (v >> lo) & ((1 << (hi - lo + 1)) - 1)


def vertex_instruction(v):
    def src(neg, swz, reg, typ):
        return dict(neg=bits(v, neg, neg), swizzle=bits(v, swz, swz + 7),
                    reg=bits(v, reg, reg + 5), type=bits(v, typ, typ + 1))
    return dict(
        raw=v, export_vector=bits(v, 126, 126), cond_write=bits(v, 125, 125),
        export_relative=bits(v, 124, 124), attr_relative=bits(v, 123, 123),
        sat=bits(v, 122, 122), cond_reg=bits(v, 121, 121), bit120=bits(v, 120, 120),
        abs=(bits(v, 117, 117), bits(v, 118, 118), bits(v, 119, 119)),
        vdst=bits(v, 111, 116), cond_set=bits(v, 110, 110), cond_check=bits(v, 109, 109),
        pred=(bits(v, 108, 108), bits(v, 107, 107), bits(v, 106, 106)),
        pred_swizzle=bits(v, 98, 105), addr_select=bits(v, 96, 97),
        sop=bits(v, 91, 95), vop=bits(v, 86, 90), const=bits(v, 76, 85), attr=bits(v, 72, 75),
        A=src(71, 63, 57, 55), B=src(54, 46, 40, 38), C=src(37, 29, 23, 21),
        smask=bits(v, 17, 20), vmask=bits(v, 13, 16), sdst=bits(v, 7, 12),
        export=bits(v, 2, 6), const_relative=bits(v, 1, 1), end=bits(v, 0, 0))


# -- platform binary container -------------------------------------------------

def sections(data):
    count = struct.unpack_from('<I', data, 16)[0]
    out = {}
    for i in range(count):
        kind, off, n, size = struct.unpack_from('<4I', data, 20 + 16 * i)
        if kind and kind < 64:
            out[kind] = (n, data[off * 4:off * 4 + size])
    return out


def records(blob, step):
    return [struct.unpack_from('<' + 'I' * (step // 4), blob, i)
            for i in range(0, len(blob) - step + 1, step)]


def is_fragment(data):
    return b'AR20-BIN' in data
