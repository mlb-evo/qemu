"""Check the translator against the firmware's own compiler, on the host GPU.

Each case is GLSL compiled by the emulated libcgdrv into AR20, translated back to GLSL,
and both programs are run on identical random inputs: fragment cases as one point per
pixel over a random destination (with the case's blend), vertex cases through transform
feedback. Run with the research venv (unicorn): roundtrip.py [-k NAME]
"""
import sys
sys.dont_write_bytecode = True
import argparse
import random
import re
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'cgdrv-experiment')]

import cgbin
import glrun
from ar20 import GL_TYPES, Unsupported
from translate import translate

W, H = 128, 64
BLEND = {
    'premultiplied': ('GL_ONE', 'GL_ONE_MINUS_SRC_ALPHA'),
    'alpha': ('GL_SRC_ALPHA', 'GL_ONE_MINUS_SRC_ALPHA'),
    'additive': ('GL_ONE', 'GL_ONE'),
    'multiply': ('GL_DST_COLOR', 'GL_ZERO'),
    'modulate': ('GL_ZERO', 'GL_SRC_COLOR'),
    'screen': ('GL_ONE', 'GL_ONE_MINUS_SRC_COLOR'),
}
GL_ENUM = {'GL_ZERO': 0, 'GL_ONE': 1, 'GL_SRC_COLOR': 0x300, 'GL_ONE_MINUS_SRC_COLOR': 0x301,
           'GL_SRC_ALPHA': 0x302, 'GL_ONE_MINUS_SRC_ALPHA': 0x303, 'GL_DST_COLOR': 0x306}

F = 'precision mediump float;\n'
FH = 'precision highp float;\n'
FRAGMENT_CASES = {
    'texture_modulate': (F + 'varying vec2 uv; uniform sampler2D t; uniform vec4 color;'
                         'void main(){gl_FragColor=texture2D(t,uv)*color;}', None),
    'mix_two_textures': (F + 'varying vec2 uv; varying vec3 uv2; varying vec4 col;'
                         'uniform sampler2D tex,tex2; uniform vec4 color; uniform float k;'
                         'void main(){vec4 a=texture2D(tex,uv);vec4 b=texture2D(tex2,uv2.xy*uv2.z);'
                         'gl_FragColor=mix(a,b,k)*col+color*k;}', None),
    'premultiplied_blend': (F + 'varying vec2 uv; uniform sampler2D t; uniform float o;'
                            'void main(){vec4 c=texture2D(t,uv);gl_FragColor=vec4(c.rgb*c.a*o,c.a*o);}',
                            'premultiplied'),
    'alpha_blend': (F + 'varying vec2 uv; varying vec4 c; uniform sampler2D t;'
                    'void main(){gl_FragColor=texture2D(t,uv)*c;}', 'alpha'),
    'additive_blend': (F + 'varying vec4 c; uniform lowp vec4 k;'
                       'void main(){gl_FragColor=c*k;}', 'additive'),
    'multiply_blend': (F + 'varying vec4 c; void main(){gl_FragColor=c;}', 'multiply'),
    'modulate_blend': (F + 'varying vec4 c; void main(){gl_FragColor=c*0.5+0.25;}', 'modulate'),
    'screen_blend': (F + 'varying vec4 c; void main(){gl_FragColor=c;}', 'screen'),
    'dot_constants': (FH + 'varying vec4 a; varying vec4 b;'
                      'void main(){gl_FragColor=vec4(dot(a,b)*0.25,a.x*0.3+0.7,sin(a.y*3.0)*0.5+0.5,exp2(b.x)-1.0);}',
                      None),
    'math_functions': (FH + 'varying vec4 a; uniform float p;'
                       'void main(){gl_FragColor=vec4(pow(a.x,p*2.0),sqrt(a.y),inversesqrt(a.z+0.5)*0.5,log2(a.w+1.0));}',
                       None),
    'trig_wide': (FH + 'varying vec4 a;'
                  'void main(){gl_FragColor=vec4(sin(a.x*20.0-10.0),cos(a.y*20.0-10.0),sin(a.z*6.0),cos(a.w))*0.5+0.5;}',
                  None),
    'fract_floor': (FH + 'varying vec4 a;'
                    'void main(){vec4 x=a*7.3-2.0;gl_FragColor=vec4(fract(x.x),floor(x.y)*0.1+0.5,mod(x.z,1.5),abs(x.w)*0.2);}',
                    None),
    'step_smoothstep': (F + 'varying vec4 a; uniform float e;'
                        'void main(){gl_FragColor=vec4(step(e,a.x),smoothstep(0.2,0.8,a.y),clamp(a.z*3.0-1.0,0.0,1.0),sign(a.w-0.5)*0.5+0.5);}',
                        None),
    'min_max_select': (F + 'varying vec4 a; varying vec4 b;'
                       'void main(){gl_FragColor=vec4(min(a.x,b.x),max(a.y,b.y),a.z>b.z?a.w:b.w,a.x<0.5?0.2:0.9);}',
                       None),
    'discard': (F + 'varying vec4 a; uniform float th;'
                'void main(){if(a.w<th) discard; gl_FragColor=a;}', None),
    'discard_blend': (F + 'varying vec2 uv; uniform sampler2D t;'
                      'void main(){vec4 c=texture2D(t,uv); if(c.a<0.3) discard; gl_FragColor=c;}',
                      'premultiplied'),
    'uniform_mix_precisions': (F + 'varying vec4 a; uniform lowp vec4 lc; uniform mediump vec3 mc;'
                               'uniform highp vec2 hc; uniform float f1; uniform lowp float f2;'
                               'void main(){gl_FragColor=vec4(a.x*lc.x+mc.y*f2,a.y*lc.y+hc.x*f1,a.z*lc.z+mc.z,lc.w*hc.y);}',
                               None),
    'lowp_varyings': (F + 'varying lowp vec4 c; varying lowp vec2 d; varying mediump vec2 uv;'
                      'uniform sampler2D t;'
                      'void main(){gl_FragColor=texture2D(t,uv)*c+vec4(d,d.x*d.y,0.0);}', None),
    'bias_and_proj': (F + 'varying vec4 q; uniform sampler2D t;'
                      'void main(){gl_FragColor=texture2D(t,q.xy,q.z)*0.5+texture2DProj(t,q.xyw*vec3(1.0,1.0,0.5)+vec3(0.0,0.0,0.75))*0.5;}',
                      None),
    'many_taps': (F + 'varying vec2 uv; uniform sampler2D t; uniform vec2 off;'
                  'void main(){gl_FragColor=(texture2D(t,uv+off)+texture2D(t,uv-off)+texture2D(t,uv+off*2.0)'
                  '+texture2D(t,uv-off*2.0)+texture2D(t,uv+off*3.0)+texture2D(t,uv-off*3.0))/6.0;}', None),
    'luminance_premultiplied': (F + 'varying vec2 uv; uniform sampler2D t; uniform lowp float o;'
                                'void main(){vec4 c=texture2D(t,uv);float l=dot(c.rgb,vec3(0.3,0.59,0.11));'
                                'gl_FragColor=vec4(vec3(l)*c.a*o,c.a*o);}', 'premultiplied'),
    'long_program': (FH + 'varying vec4 a; varying vec4 b; uniform vec4 u1,u2,u3; uniform float s;'
                     'void main(){vec4 x=a*u1+b*u2; vec4 y=x*x-u3; float d=dot(y,x)+length(a.xy-b.zw);'
                     'vec4 z=normalize(vec4(x.xyz,1.0)); gl_FragColor=clamp(vec4(d*s,z.x,z.y*0.5+0.5,fract(d)),0.0,1.0);}',
                     None),
}

VERTEX_CASES = {
    'mvp': ('attribute vec4 pos; uniform mat4 mvp; void main(){gl_Position=mvp*pos;}'),
    'mvp_varyings': ('attribute vec4 pos; attribute vec2 uv; attribute float w;'
                     'uniform mat4 mvp; uniform vec4 tint; uniform float k;'
                     'varying vec2 vuv; varying vec4 vcol; varying float vw;'
                     'void main(){gl_Position=mvp*pos; vuv=uv*k+0.25; vcol=tint*w; vw=w>0.5?sin(w):1.5;}'),
    'branches': ('attribute vec4 pos; uniform float mode; uniform vec4 a,b; varying vec4 v;'
                 'void main(){gl_Position=pos; if(mode>0.5){v=a*pos.x;}else if(mode>0.25){v=b+pos.y;}'
                 'else{v=vec4(pos.z);}}'),
    'functions': ('attribute vec4 pos; uniform vec3 l; varying vec4 v; varying vec3 n;'
                  'void main(){gl_Position=vec4(normalize(pos.xyz),1.0); n=cross(pos.xyz,l);'
                  'v=vec4(dot(pos.xyz,l),length(pos),exp2(pos.w),log2(abs(pos.x)+1.0));}'),
    'trig_compare': ('attribute vec4 pos; uniform float t; varying vec4 v;'
                     'void main(){gl_Position=pos; v=vec4(sin(pos.x*t),cos(pos.y+t),step(pos.z,0.0),'
                     'max(pos.w,t)*min(pos.x,0.3)+fract(pos.y*3.7)+floor(pos.z*2.5));}'),
    'mat3_normal': ('attribute vec3 normal; attribute vec4 pos; uniform mat3 nm; uniform mat4 mvp;'
                    'varying vec3 vn; varying float d;'
                    'void main(){gl_Position=mvp*pos; vn=nm*normal; d=clamp(dot(vn,vec3(0.0,0.0,1.0)),0.0,1.0);}'),
}


def compile_cg(driver, source, stage):
    result = driver.compile(source, stage)
    if not result.ok:
        raise RuntimeError(f'cgdrv: {result.error} {result.diagnostics}'.strip())
    return result.binary


def random_values(rng, kind, lo=0.0, hi=1.0):
    n = GL_TYPES[cgbin.TYPE_CODES[kind]][1]
    if kind in ('int', 'bool'):
        return [float(rng.randint(0, 1))]
    return [rng.uniform(lo, hi) for _ in range(n)]


def fragment_case(ctx, driver, name, source, blend, rng, texture):
    pragma = ''
    if blend:
        src, dst = BLEND[blend]
        pragma = f'#pragma profilepragma blendoperation(gl_FragColor, GL_FUNC_ADD, {src}, {dst})\n'
    binary = compile_cg(driver, pragma + source, 'fragment')
    model = cgbin.fragment_model(binary, source)
    translated, mode, warnings = translate(binary, model)
    varyings = cgbin.declarations(source, 'varying')
    uniforms = cgbin.declarations(source, 'uniform')
    vs = ['attribute vec2 a_pos;']
    body = ['gl_Position=vec4(a_pos,0.0,1.0);gl_PointSize=1.0;']
    for v, (code, _count) in varyings.items():
        t = GL_TYPES[code][0]
        vs.append(f'attribute {t} a_{v}; varying {t} {v};')
        body.append(f'{v}=a_{v};')
    vs = '\n'.join(vs) + '\nvoid main(){' + ''.join(body) + '}\n'
    count = W * H
    attributes = {'a_pos': (2, [c for i in range(count) for c in
                                ((i % W + 0.5) / W * 2 - 1, (i // W + 0.5) / H * 2 - 1)])}
    for v, (code, _count) in varyings.items():
        n = GL_TYPES[code][1]
        attributes[f'a_{v}'] = (n, [rng.uniform(0.0, 1.0) for _ in range(count * n)])
    values = {}
    for u, (code, _count) in uniforms.items():
        kind = GL_TYPES[code][0]
        values[u] = (kind, texture if kind.startswith('sampler') else random_values(rng, kind))
    destination = bytes(rng.randrange(256) for _ in range(count * 4))
    original = ctx.program(vs, source)
    ours = ctx.program(vs, translated)
    gl_blend = None
    if blend:
        s, d = (GL_ENUM[x] for x in BLEND[blend])
        gl_blend = (s, d, s, d)
    expected = ctx.draw_points(original, attributes, values, count, destination, gl_blend)
    ours_blend = ((glrun.GL_ONE, glrun.GL_SRC1_COLOR_EXT, glrun.GL_ONE, glrun.GL_SRC1_ALPHA_EXT)
                  if mode == 6 else None)
    got = ctx.draw_points(ours, attributes, values, count, destination, ours_blend)
    if len(set(expected[i:i + 4] for i in range(0, len(expected), 4))) < count // 8:
        raise RuntimeError('reference image is nearly constant')
    diffs = sorted(abs(a - b) for a, b in zip(expected, got))
    return dict(max=diffs[-1], p99=diffs[int(len(diffs) * 0.99)], mode=mode, warnings=warnings,
                bad=sum(d > 8 for d in diffs) / len(diffs),
                source=translated)


def vertex_case(ctx, driver, name, source, rng):
    binary = compile_cg(driver, source, 'vertex')
    model = cgbin.vertex_model(binary, source)
    translated, _mode, warnings = translate(binary, model)
    attributes_decl = cgbin.declarations(source, 'attribute')
    varyings = cgbin.declarations(source, 'varying')
    uniforms = cgbin.declarations(source, 'uniform')
    fs = 'precision mediump float; void main(){gl_FragColor=vec4(0.0);}'
    feedback = ['gl_Position'] + list(varyings)
    per_vertex = 4 + sum(GL_TYPES[c][1] for c, _n in varyings.values())
    count = 512
    attributes = {}
    for a, (code, _n) in attributes_decl.items():
        n = GL_TYPES[code][1]
        attributes[a] = (n, [rng.uniform(-1.0, 1.0) for _ in range(count * n)])
    values = {u: (GL_TYPES[c][0], random_values(rng, GL_TYPES[c][0], -1.0, 1.0))
              for u, (c, _n) in uniforms.items()}
    expected = ctx.feedback(ctx.program(source, fs, feedback), attributes, values, count, per_vertex)
    got = ctx.feedback(ctx.program(translated, fs, feedback), attributes, values, count, per_vertex)
    err = max(abs(a - b) / max(1.0, abs(a)) for a, b in zip(expected, got))
    if len(set(expected)) < count // 4:
        raise RuntimeError('transform feedback captured too few distinct values')
    return dict(max=err, warnings=warnings, source=translated)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-k', help='only cases whose name contains this')
    ap.add_argument('--show', action='store_true', help='print translated sources')
    args = ap.parse_args()
    from cgdrv_harness.cgdrv import CgDriver
    driver = CgDriver()
    ctx = glrun.Context(W, H)
    rng = random.Random(1234)
    texture = ctx.texture(8, 8, bytes(rng.randrange(256) for _ in range(8 * 8 * 4)))
    failures = 0
    for name, (source, blend) in FRAGMENT_CASES.items():
        if args.k and args.k not in name:
            continue
        try:
            r = fragment_case(ctx, driver, name, source, blend, rng, texture)
            ok = r['p99'] <= 2 and r['bad'] <= 0.002
            print(f'{"ok  " if ok else "FAIL"} fragment {name}: max {r["max"]} p99 {r["p99"]} '
                  f'bad {r["bad"]:.4f} '
                  f'mode {r["mode"]} {r["warnings"] or ""}')
        except (Unsupported, RuntimeError) as error:
            ok, r = False, {}
            print(f'FAIL fragment {name}: {type(error).__name__}: {error}')
        failures += not ok
        if args.show and r:
            print(r['source'])
    for name, source in VERTEX_CASES.items():
        if args.k and args.k not in name:
            continue
        try:
            r = vertex_case(ctx, driver, name, source, rng)
            ok = r['max'] <= 2e-3
            print(f'{"ok  " if ok else "FAIL"} vertex {name}: max rel {r["max"]:.2e} {r["warnings"] or ""}')
        except (Unsupported, RuntimeError) as error:
            ok, r = False, {}
            print(f'FAIL vertex {name}: {type(error).__name__}: {error}')
        failures += not ok
        if args.show and r:
            print(r['source'])
    print('failures:', failures)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
