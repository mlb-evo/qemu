"""Build translator models from cgc containers produced by the emulated libcgdrv.

The platform binaries shipped in the firmware carry their own symbol tables; a cgc
container from CgDrv_Compile carries the same facts in a different layout. GLSL types
come from the test source, since the container encodes precision into its type codes.
"""
import sys
sys.dont_write_bytecode = True
import re
import struct

from ar20 import GL_TYPES

TYPE_CODES = {name: code for code, (name, _size) in GL_TYPES.items()}


def declarations(source, qualifier):
    out = {}
    pattern = (rf'\b{qualifier}\s+(?:(?:lowp|mediump|highp)\s+)?(\w+)\s+([^;]+);')
    for gltype, names in re.findall(pattern, source):
        for item in names.split(','):
            m = re.match(r'\s*(\w+)\s*(?:\[(\d+)\])?', item)
            out[m.group(1)] = (TYPE_CODES[gltype], int(m.group(2) or 1))
    return out


def symbols(data):
    header = struct.unpack_from('<12I', data, 0)
    out = []
    for i in range(header[3]):
        s = struct.unpack_from('<12I', data, 48 + 48 * i)
        name = data[s[4]:].split(b'\0')[0].decode()
        out.append(dict(name=name, datatype=s[0], resource=s[1], kind=s[2], location=s[3],
                        values=s[5], direction=s[8], flags=s[10]))
    return header, out


def fragment_model(data, source):
    header, syms = symbols(data)
    varyings = declarations(source, 'varying')
    uniforms = declarations(source, 'uniform')
    bar = struct.unpack_from('<4I', data, header[5])
    tram = {}
    for i in range(bar[0]):
        _zero, semantic, row, layout = struct.unpack_from('<BBHH', data, bar[1] + 6 * i)
        tram.setdefault(semantic, []).append((row, layout))
    model = dict(varyings=[], uniforms=[], samplers={}, constants={}, constant_values={})
    for s in syms:
        if s['kind'] == 0x1005 and s['direction'] == 0x1001 and s['name'] in varyings:
            gltype, count = varyings[s['name']]
            for row, layout in tram.get(s['location'], []):
                model['varyings'].append(dict(name=s['name'], type=gltype, count=count,
                                              layout=layout, row=row))
        elif s['kind'] == 0x1006:
            # Location: slot | component mask << 8 | fx10 << 15. Only the components in
            # the mask are stored, consecutively: registers for fp20, halves for fx10.
            start = s['location'] & 0xff
            mask = (s['location'] >> 8) & 15
            fx = (s['location'] >> 15) & 1
            slots = []
            for k in range(4):
                if mask & (1 << k):
                    n = len(slots)
                    slots.append((k, 32 + start // 2 + n, 'f') if not fx else
                                 (k, 32 + (start + n) // 2, 'lh'[(start + n) & 1]))
            if s['name'].startswith('@new_uniform') or s['name'].startswith('internal-'):
                values = struct.unpack_from('<4f', data, s['values'])
                for k, reg, sel in slots:
                    model['constant_values'][(reg, sel)] = values[k]
                continue
            if s['name'] not in uniforms:
                continue
            gltype, count = uniforms[s['name']]
            if GL_TYPES[gltype][0].startswith('sampler'):
                model['samplers'][s['resource'] & 0xff] = dict(name=s['name'], type=gltype)
                model['uniforms'].append(dict(name=s['name'], type=gltype, count=count,
                                              placement=None))
            else:
                model['uniforms'].append(dict(name=s['name'], type=gltype, count=count,
                                              placement=slots))
    return model


def vertex_model(data, source):
    _header, syms = symbols(data)
    attributes = declarations(source, 'attribute')
    varyings = declarations(source, 'varying')
    uniforms = declarations(source, 'uniform')
    model = dict(attributes=[], varyings=[], uniforms=[], constants={})
    for s in syms:
        if s['kind'] == 0x1005 and s['direction'] == 0x1001 and s['name'] in attributes:
            model['attributes'].append(dict(name=s['name'], type=attributes[s['name']][0],
                                            index=(s['resource'] & 0xff) - 0x41))
        elif s['kind'] == 0x1005 and s['direction'] == 0x1002 and s['name'] in varyings:
            gltype, count = varyings[s['name']]
            model['varyings'].append(dict(name=s['name'], type=gltype, count=count,
                                          export=s['location']))
        elif s['kind'] == 0x1007 or s['name'].startswith('@new_uniform'):
            model['constants'][s['location']] = struct.unpack_from('<4f', data, s['values'])
        elif s['kind'] == 0x1006 and s['name'] in uniforms:
            gltype, count = uniforms[s['name']]
            model['uniforms'].append(dict(name=s['name'], type=gltype, count=count,
                                          placement=4 * s['location']))
    return model
