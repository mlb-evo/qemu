"""Minimal headless GLES 3 runner (ctypes, EGL surfaceless) for shader comparisons."""
import sys
sys.dont_write_bytecode = True
import ctypes as C
import struct

egl = C.CDLL('libEGL.so.1')
gl = C.CDLL('libGLESv2.so.2')

EGL_PLATFORM_SURFACELESS_MESA = 0x31DD
GL_FRAGMENT_SHADER, GL_VERTEX_SHADER = 0x8B30, 0x8B31
GL_COMPILE_STATUS, GL_LINK_STATUS = 0x8B81, 0x8B82
GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_FLOAT = 0x8892, 0x88E4, 0x1406
GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE = 0x0DE1, 0x1908, 0x1401
GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_NEAREST = 0x2801, 0x2800, 0x2600
GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_REPEAT = 0x2802, 0x2803, 0x2901
GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 = 0x8D40, 0x8CE0
GL_POINTS, GL_BLEND, GL_TEXTURE0 = 0, 0x0BE2, 0x84C0
GL_ONE, GL_ZERO, GL_FUNC_ADD = 1, 0, 0x8006
GL_SRC1_COLOR_EXT, GL_SRC1_ALPHA_EXT = 0x88F9, 0x8589
GL_TRANSFORM_FEEDBACK_BUFFER, GL_INTERLEAVED_ATTRIBS = 0x8C8E, 0x8C8C
GL_RASTERIZER_DISCARD, GL_MAP_READ_BIT = 0x8C89, 0x0001

gl.glMapBufferRange.restype = C.c_void_p
gl.glGetUniformLocation.restype = C.c_int
gl.glGetAttribLocation.restype = C.c_int
gl.glCreateShader.restype = C.c_uint
gl.glCreateProgram.restype = C.c_uint
gl.glGetString.restype = C.c_char_p


class Context:
    def __init__(self, width=256, height=64):
        egl.eglGetPlatformDisplay.restype = C.c_void_p
        egl.eglCreateContext.restype = C.c_void_p
        display = egl.eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, None, None)
        major, minor = C.c_int(), C.c_int()
        if not egl.eglInitialize(C.c_void_p(display), C.byref(major), C.byref(minor)):
            raise RuntimeError('eglInitialize failed')
        attrs = (C.c_int * 5)(0x3033, 0x0400 | 0x0001, 0x3040, 0x0040, 0x3038)
        config, count = C.c_void_p(), C.c_int()
        egl.eglChooseConfig(C.c_void_p(display), attrs, C.byref(config), 1, C.byref(count))
        egl.eglBindAPI(0x30A0)
        ctx_attrs = (C.c_int * 3)(0x3098, 3, 0x3038)
        context = egl.eglCreateContext(C.c_void_p(display), config, None, ctx_attrs)
        if not egl.eglMakeCurrent(C.c_void_p(display), None, None, C.c_void_p(context)):
            raise RuntimeError('eglMakeCurrent failed')
        self.width, self.height = width, height
        self.fbo_texture = self.texture(width, height, bytes(width * height * 4))
        fbo = C.c_uint()
        gl.glGenFramebuffers(1, C.byref(fbo))
        gl.glBindFramebuffer(GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D,
                                  self.fbo_texture, 0)
        gl.glViewport(0, 0, width, height)
        vao = C.c_uint()
        gl.glGenVertexArrays(1, C.byref(vao))
        gl.glBindVertexArray(vao)

    def texture(self, w, h, rgba):
        t = C.c_uint()
        gl.glGenTextures(1, C.byref(t))
        gl.glBindTexture(GL_TEXTURE_2D, t)
        gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba)
        for p, v in ((GL_TEXTURE_MIN_FILTER, 0x2601), (GL_TEXTURE_MAG_FILTER, 0x2601),
                     (GL_TEXTURE_WRAP_S, GL_REPEAT), (GL_TEXTURE_WRAP_T, GL_REPEAT)):
            gl.glTexParameteri(GL_TEXTURE_2D, p, v)
        return t.value

    def shader(self, kind, source):
        s = gl.glCreateShader(kind)
        text = C.c_char_p(source.encode())
        gl.glShaderSource(s, 1, C.byref(text), None)
        gl.glCompileShader(s)
        ok = C.c_int()
        gl.glGetShaderiv(s, GL_COMPILE_STATUS, C.byref(ok))
        if not ok.value:
            log = C.create_string_buffer(8192)
            gl.glGetShaderInfoLog(s, 8192, None, log)
            raise RuntimeError('compile failed: ' + log.value.decode(errors='replace'))
        return s

    def program(self, vs, fs, feedback=None):
        p = gl.glCreateProgram()
        gl.glAttachShader(p, self.shader(GL_VERTEX_SHADER, vs))
        gl.glAttachShader(p, self.shader(GL_FRAGMENT_SHADER, fs))
        if feedback:
            names = (C.c_char_p * len(feedback))(*[n.encode() for n in feedback])
            gl.glTransformFeedbackVaryings(p, len(feedback), names, GL_INTERLEAVED_ATTRIBS)
        gl.glLinkProgram(p)
        ok = C.c_int()
        gl.glGetProgramiv(p, GL_LINK_STATUS, C.byref(ok))
        if not ok.value:
            log = C.create_string_buffer(8192)
            gl.glGetProgramInfoLog(p, 8192, None, log)
            raise RuntimeError('link failed: ' + log.value.decode(errors='replace'))
        return p

    def set_uniforms(self, p, uniforms):
        """uniforms: name -> (gltype name, list of floats)."""
        gl.glUseProgram(p)
        unit = 0
        for name, (kind, values) in uniforms.items():
            loc = gl.glGetUniformLocation(p, name.encode())
            if loc < 0:
                continue
            if kind.startswith('sampler'):
                gl.glActiveTexture(GL_TEXTURE0 + unit + 1)
                gl.glBindTexture(GL_TEXTURE_2D, values)
                gl.glUniform1i(loc, unit + 1)
                unit += 1
                continue
            arr = (C.c_float * len(values))(*values)
            n = len(values)
            if kind in ('int', 'bool'):
                gl.glUniform1i(loc, int(values[0]))
            elif kind.startswith('mat'):
                fn = {'mat2': gl.glUniformMatrix2fv, 'mat3': gl.glUniformMatrix3fv,
                      'mat4': gl.glUniformMatrix4fv}[kind]
                fn(loc, 1, 0, arr)
            else:
                fn = [None, gl.glUniform1fv, gl.glUniform2fv, gl.glUniform3fv, gl.glUniform4fv][
                    {'float': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4}[kind]]
                fn(loc, 1, arr)

    def attributes(self, p, attributes, count):
        """attributes: name -> (components, list of count*components floats)."""
        buffers = []
        for name, (size, values) in attributes.items():
            loc = gl.glGetAttribLocation(p, name.encode())
            if loc < 0:
                continue
            b = C.c_uint()
            gl.glGenBuffers(1, C.byref(b))
            gl.glBindBuffer(GL_ARRAY_BUFFER, b)
            arr = (C.c_float * len(values))(*values)
            gl.glBufferData(GL_ARRAY_BUFFER, C.sizeof(arr), arr, GL_STATIC_DRAW)
            gl.glEnableVertexAttribArray(loc)
            gl.glVertexAttribPointer(loc, size, GL_FLOAT, 0, 0, None)
            buffers.append((b, loc))
        return buffers

    def release(self, buffers):
        for b, loc in buffers:
            gl.glDisableVertexAttribArray(loc)
            gl.glDeleteBuffers(1, C.byref(C.c_uint(b.value)))

    def draw_points(self, p, attributes, uniforms, count, destination, blend):
        """Draw `count` points; blend is None, (src, dst, srca, dsta)."""
        gl.glBindTexture(GL_TEXTURE_2D, self.fbo_texture)
        gl.glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.width, self.height, GL_RGBA,
                           GL_UNSIGNED_BYTE, destination)
        self.set_uniforms(p, uniforms)
        buffers = self.attributes(p, attributes, count)
        if blend:
            gl.glEnable(GL_BLEND)
            gl.glBlendEquation(GL_FUNC_ADD)
            gl.glBlendFuncSeparate(*blend)
        else:
            gl.glDisable(GL_BLEND)
        gl.glDrawArrays(GL_POINTS, 0, count)
        self.release(buffers)
        out = C.create_string_buffer(self.width * self.height * 4)
        gl.glReadPixels(0, 0, self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, out)
        return out.raw

    def feedback(self, p, attributes, uniforms, count, floats_per_vertex):
        self.set_uniforms(p, uniforms)
        buffers = self.attributes(p, attributes, count)
        tf = C.c_uint()
        gl.glGenBuffers(1, C.byref(tf))
        gl.glBindBuffer(GL_TRANSFORM_FEEDBACK_BUFFER, tf)
        size = count * floats_per_vertex * 4
        gl.glBufferData(GL_TRANSFORM_FEEDBACK_BUFFER, size, None, GL_STATIC_DRAW)
        gl.glBindBufferBase(GL_TRANSFORM_FEEDBACK_BUFFER, 0, tf)
        gl.glEnable(GL_RASTERIZER_DISCARD)
        gl.glBeginTransformFeedback(GL_POINTS)
        gl.glDrawArrays(GL_POINTS, 0, count)
        gl.glEndTransformFeedback()
        gl.glDisable(GL_RASTERIZER_DISCARD)
        ptr = gl.glMapBufferRange(GL_TRANSFORM_FEEDBACK_BUFFER, 0, size, GL_MAP_READ_BIT)
        data = C.string_at(ptr, size)
        gl.glUnmapBuffer(GL_TRANSFORM_FEEDBACK_BUFFER)
        gl.glDeleteBuffers(1, C.byref(tf))
        self.release(buffers)
        return struct.unpack('<%df' % (size // 4), data)
