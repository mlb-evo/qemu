"""Compare translations with the hand-written GLSL glhost already ships for some binaries.

Checks the platform-binary parsing (symbol tables, uniform and varying placement) on
programs whose behaviour was confirmed visually. Fragment stages are drawn one point per
pixel over a random destination with each side's own blend; vertex stages are compared
through transform feedback. Usage: compare_known.py
"""
import sys
sys.dont_write_bytecode = True
import ast
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import glrun
from ar20 import GL_TYPES, is_fragment
from translate import translate, platform_fragment_model, platform_vertex_model

REPO = next(p for p in HERE.parents if (p / 'hw/arm/fpk1.c').is_file())
ART = REPO / 'build_fpk1/research-artifacts/shader-translate'
W, H = 64, 32


def hand_translations():
    out = {}
    text = ''
    for name in ('audi_shaders.h', 'known_shaders.h'):
        text += (REPO / 'tools/mhi2/glforward/host' / name).read_text()
    for m in re.finditer(r'\{\s*UINT64_C\(0x([0-9a-f]+)\),\s*(\d+),\s*((?:"(?:[^"\\]|\\.)*"\s*)+)(?:,\s*(\d+))?', text):
        source = ''.join(ast.literal_eval(s) for s in re.findall(r'"(?:[^"\\]|\\.)*"', m.group(3)))
        out[f'{int(m.group(1), 16):016x}-{m.group(2)}'] = (source, int(m.group(4) or 0))
    return out


def blend_state(mode):
    one, zero = glrun.GL_ONE, glrun.GL_ZERO
    if mode == 6:
        return (one, glrun.GL_SRC1_COLOR_EXT, one, glrun.GL_SRC1_ALPHA_EXT)
    if mode in (0, 4):
        return None
    sa, omsa = 0x302, 0x303
    return {1: (one, omsa, one, omsa), 2: (one, omsa, zero, one), 3: (sa, omsa, sa, omsa),
            5: (zero, zero, zero, zero)}[mode]


def decls(source, qualifier):
    out = {}
    for t, names in re.findall(rf'\b{qualifier}\s+(?:(?:lowp|mediump|highp)\s+)?(\w+)\s+([^;]+);', source):
        for n in names.split(','):
            out[n.strip()] = t
    return out


def main():
    hand = hand_translations()
    ctx = glrun.Context(W, H)
    rng = random.Random(7)
    texture = ctx.texture(8, 8, bytes(rng.randrange(256) for _ in range(256)))
    rows = []
    for path in sorted((ART / 'binaries').glob('*.bin')):
        if path.stem not in hand:
            continue
        data = path.read_bytes()
        reference, ref_mode = hand[path.stem]
        try:
            ours, mode, warnings = translate(data)
        except Exception as error:  # report and continue
            rows.append((path.stem, f'translate failed: {error}'))
            continue
        try:
            if is_fragment(data):
                varyings = {**decls(reference, 'varying'), **decls(ours, 'varying')}
                vs = 'attribute vec2 a_pos;' + ''.join(
                    f'attribute {t} a_{n}; varying {t} {n};' for n, t in varyings.items())
                vs += 'void main(){gl_Position=vec4(a_pos,0.0,1.0);gl_PointSize=1.0;' + ''.join(
                    f'{n}=a_{n};' for n in varyings) + '}'
                count = W * H
                attrs = {'a_pos': (2, [c for i in range(count) for c in
                                       ((i % W + .5) / W * 2 - 1, (i // W + .5) / H * 2 - 1)])}
                for n, t in varyings.items():
                    k = {'float': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4}[t]
                    attrs[f'a_{n}'] = (k, [rng.uniform(0, 1) for _ in range(count * k)])
                uniforms = {}
                for n, t in {**decls(reference, 'uniform'), **decls(ours, 'uniform')}.items():
                    if t.startswith('sampler'):
                        uniforms[n] = (t, texture)
                    else:
                        k = {'float': 1, 'int': 1, 'bool': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4}[t]
                        uniforms[n] = (t, [float(rng.randint(0, 1)) if t in ('int', 'bool')
                                           else rng.uniform(0, 1) for _ in range(k)])
                dst = bytes(rng.randrange(256) for _ in range(count * 4))
                a = ctx.draw_points(ctx.program(vs, reference), attrs, uniforms, count, dst, blend_state(ref_mode))
                b = ctx.draw_points(ctx.program(vs, ours), attrs, uniforms, count, dst, blend_state(mode))
                diffs = sorted(abs(x - y) for x, y in zip(a, b))
                channels = [max(abs(a[i] - b[i]) for i in range(c, len(a), 4)) for c in range(4)]
                rows.append((path.stem, f'fragment ref mode {ref_mode} ours {mode}: max {diffs[-1]} '
                             f'p99 {diffs[int(len(diffs) * .99)]} rgba {channels} {warnings or ""}'))
            else:
                fs = 'precision mediump float; void main(){gl_FragColor=vec4(0.0);}'
                varyings = [n for n in decls(reference, 'varying') if n in decls(ours, 'varying')]
                count = 256
                attrs = {}
                for n, t in decls(ours, 'attribute').items():
                    k = {'float': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4}[t]
                    attrs[n] = (k, [rng.uniform(-1, 1) for _ in range(count * k)])
                uniforms = {}
                for n, t in {**decls(reference, 'uniform'), **decls(ours, 'uniform')}.items():
                    k = {'float': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4, 'mat4': 16, 'mat3': 9}[t]
                    uniforms[n] = (t, [rng.uniform(-1, 1) for _ in range(k)])
                per = 4 + sum({'float': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4}[decls(ours, 'varying')[n]]
                              for n in varyings)
                fb = ['gl_Position'] + varyings
                a = ctx.feedback(ctx.program(reference, fs, fb), attrs, uniforms, count, per)
                b = ctx.feedback(ctx.program(ours, fs, fb), attrs, uniforms, count, per)
                err = max(abs(x - y) / max(1.0, abs(x)) for x, y in zip(a, b))
                rows.append((path.stem, f'vertex: max rel {err:.2e} varyings {varyings}'))
        except RuntimeError as error:
            rows.append((path.stem, f'GL error: {str(error)[:200]}'))
    for key, text in rows:
        print(key, text)


if __name__ == '__main__':
    main()
