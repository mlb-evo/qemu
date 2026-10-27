"""Small local GLES3 transform-feedback probe; native outputs live under build_fpk1."""
import sys
sys.dont_write_bytecode=True
import ctypes as C,os,shlex,subprocess
from pathlib import Path
REPO=next(p for p in Path(__file__).resolve().parents if (p/'hw/arm/fpk1.c').is_file())
OUT=REPO/'build_fpk1/research-artifacts/shader_groups';OUT.mkdir(exist_ok=True)
SOURCE=r'''
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <stdio.h>
#include <stdlib.h>
static char message[8192];
const char *probe_error(void){return message;}
int probe_init(void){EGLDisplay d=eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA,NULL,NULL);EGLint maj,min,n;EGLConfig cfg;EGLint a[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_NONE},pb[]={EGL_WIDTH,8,EGL_HEIGHT,8,EGL_NONE},ca[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};if(!eglInitialize(d,&maj,&min)||!eglChooseConfig(d,a,&cfg,1,&n)||!n)return 0;EGLSurface s=eglCreatePbufferSurface(d,cfg,pb);EGLContext c=eglCreateContext(d,cfg,EGL_NO_CONTEXT,ca);return eglMakeCurrent(d,s,s,c);}
static GLuint shader(GLenum type,const char *text){GLuint s=glCreateShader(type);glShaderSource(s,1,&text,NULL);glCompileShader(s);GLint ok;glGetShaderiv(s,GL_COMPILE_STATUS,&ok);if(!ok){glGetShaderInfoLog(s,sizeof(message),NULL,message);glDeleteShader(s);return 0;}return s;}
unsigned probe_build(const char *vs,int na,const char **attrs,int nv,const char **vary){GLuint v=shader(GL_VERTEX_SHADER,vs),f=shader(GL_FRAGMENT_SHADER,"precision mediump float;void main(){gl_FragColor=vec4(1.0);}");if(!v||!f)return 0;GLuint p=glCreateProgram();glAttachShader(p,v);glAttachShader(p,f);for(int i=0;i<na;i++)glBindAttribLocation(p,i,attrs[i]);glTransformFeedbackVaryings(p,nv,vary,GL_INTERLEAVED_ATTRIBS);glLinkProgram(p);glDeleteShader(v);glDeleteShader(f);GLint ok;glGetProgramiv(p,GL_LINK_STATUS,&ok);if(!ok){glGetProgramInfoLog(p,sizeof(message),NULL,message);glDeleteProgram(p);return 0;}return p;}
int probe_uniform(unsigned p,const char *name,int size,const float *data){glUseProgram(p);GLint at=glGetUniformLocation(p,name);if(at<0)return 0;if(size==1)glUniform1fv(at,1,data);else if(size==2)glUniform2fv(at,1,data);else if(size==3)glUniform3fv(at,1,data);else if(size==4)glUniform4fv(at,1,data);else if(size==16)glUniformMatrix4fv(at,1,GL_FALSE,data);else return -1;return glGetError()? -1:1;}
int probe_run(unsigned p,int count,int na,const int *sizes,int ni,const float *input,int no,float *output){glUseProgram(p);GLuint buffers[2];glGenBuffers(2,buffers);glBindBuffer(GL_ARRAY_BUFFER,buffers[0]);glBufferData(GL_ARRAY_BUFFER,count*ni*sizeof(float),input,GL_DYNAMIC_DRAW);int offset=0;for(int i=0;i<na;i++){glVertexAttribPointer(i,sizes[i],GL_FLOAT,GL_FALSE,ni*sizeof(float),(void *)(long)(offset*sizeof(float)));glEnableVertexAttribArray(i);offset+=sizes[i];}glBindBuffer(GL_TRANSFORM_FEEDBACK_BUFFER,buffers[1]);glBufferData(GL_TRANSFORM_FEEDBACK_BUFFER,count*no*sizeof(float),NULL,GL_DYNAMIC_READ);glBindBufferBase(GL_TRANSFORM_FEEDBACK_BUFFER,0,buffers[1]);glEnable(GL_RASTERIZER_DISCARD);glBeginTransformFeedback(GL_POINTS);glDrawArrays(GL_POINTS,0,count);glEndTransformFeedback();glDisable(GL_RASTERIZER_DISCARD);glFinish();const float *mapped=glMapBufferRange(GL_TRANSFORM_FEEDBACK_BUFFER,0,count*no*sizeof(float),GL_MAP_READ_BIT);if(!mapped)return 0;for(int i=0;i<count*no;i++)output[i]=mapped[i];glUnmapBuffer(GL_TRANSFORM_FEEDBACK_BUFFER);for(int i=0;i<na;i++)glDisableVertexAttribArray(i);glDeleteBuffers(2,buffers);return glGetError()==GL_NO_ERROR;}
void probe_delete(unsigned p){glDeleteProgram(p);}
'''
def open_probe():
 source=OUT/'gpu_probe.c';library=OUT/'gpu_probe.dylib'
 if not source.exists() or source.read_text()!=SOURCE or not library.exists():
  source.write_text(SOURCE);flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','egl','glesv2'],text=True))
  subprocess.run([os.environ.get('CC','cc'),'-shared','-fPIC','-O2',str(source),'-o',str(library),*flags],check=True)
 lib=C.CDLL(str(library));fp=C.POINTER(C.c_float);cp=C.POINTER(C.c_char_p)
 lib.probe_error.restype=C.c_char_p
 lib.probe_build.argtypes=[C.c_char_p,C.c_int,cp,C.c_int,cp];lib.probe_build.restype=C.c_uint
 lib.probe_uniform.argtypes=[C.c_uint,C.c_char_p,C.c_int,fp]
 lib.probe_run.argtypes=[C.c_uint,C.c_int,C.c_int,C.POINTER(C.c_int),C.c_int,fp,C.c_int,fp]
 lib.probe_delete.argtypes=[C.c_uint]
 if not lib.probe_init():raise RuntimeError('GLES3 probe initialization failed')
 return lib
