"""Headless real OpenGL 3.3 shader compilation via Mesa/EGL ctypes."""
from pathlib import Path
import ast,ctypes as C,os
os.environ.setdefault('EGL_PLATFORM','surfaceless')
E=C.CDLL('libEGL.so.1');G=C.CDLL('libGL.so.1')
void=C.c_void_p;uint=C.c_uint;integer=C.c_int
E.eglGetDisplay.restype=void;E.eglGetDisplay.argtypes=[void]
E.eglInitialize.restype=uint;E.eglInitialize.argtypes=[void,C.POINTER(integer),C.POINTER(integer)]
E.eglBindAPI.restype=uint;E.eglBindAPI.argtypes=[uint]
E.eglChooseConfig.restype=uint;E.eglChooseConfig.argtypes=[void,C.POINTER(integer),C.POINTER(void),integer,C.POINTER(integer)]
E.eglCreateContext.restype=void;E.eglCreateContext.argtypes=[void,void,void,C.POINTER(integer)]
E.eglMakeCurrent.restype=uint;E.eglMakeCurrent.argtypes=[void,void,void,void]
display=E.eglGetDisplay(None);a=integer();b=integer()
assert E.eglInitialize(display,C.byref(a),C.byref(b)),'eglInitialize'
assert E.eglBindAPI(0x30A2),'eglBindAPI'
attrs=(integer*13)(0x3024,8,0x3023,8,0x3022,8,0x3040,8,0x3033,1,0x3025,16,0x3038)
config=void();n=integer()
assert E.eglChooseConfig(display,attrs,C.byref(config),1,C.byref(n)) and n.value,'eglChooseConfig'
context=E.eglCreateContext(display,config,None,(integer*7)(0x3098,3,0x30FB,3,0x30FD,1,0x3038))
assert context,'eglCreateContext'
assert E.eglMakeCurrent(display,None,None,context),'eglMakeCurrent'
G.glCreateShader.restype=uint;G.glCreateShader.argtypes=[uint]
G.glShaderSource.argtypes=[uint,integer,C.POINTER(C.c_char_p),C.POINTER(integer)]
G.glCompileShader.argtypes=[uint]
G.glGetShaderiv.argtypes=[uint,uint,C.POINTER(integer)]
G.glGetShaderInfoLog.argtypes=[uint,integer,C.POINTER(integer),C.c_char_p]
G.glCreateProgram.restype=uint
G.glAttachShader.argtypes=[uint,uint]
G.glLinkProgram.argtypes=[uint]
G.glGetProgramiv.argtypes=[uint,uint,C.POINTER(integer)]
G.glGetProgramInfoLog.argtypes=[uint,integer,C.POINTER(integer),C.c_char_p]
G.glGetUniformLocation.argtypes=[uint,C.c_char_p]
G.glGetUniformLocation.restype=integer
# Import only source constants; stub visual imports so this also runs headless.
import sys,types,importlib
sys.path.insert(0,str(Path(__file__).parent))
sys.modules.setdefault('moderngl',types.ModuleType('moderngl'))
sys.modules.setdefault('pygame',types.ModuleType('pygame'))
game=importlib.import_module('trench_3d_test')
shadow=importlib.import_module('shadow_lighting')
rig=importlib.import_module('rig_renderer')
gltf=importlib.import_module('gltf_actor')
battle=importlib.import_module('battlefield_events')
values={name:getattr(game,name) for name in ('VERT','FRAG','SKYVERT','SKYFRAG','ACTOR_VERT','ACTOR_FRAG')}
values.update({name:getattr(battle,name) for name in ('PARTICLE_VERTEX','PARTICLE_FRAGMENT','PLANE_VERTEX','PLANE_FRAGMENT')})
values['SHADOW_VERT']=shadow.SHADOW_VERT
values['SHADOW_FRAG']=shadow.SHADOW_FRAG
values['SKIN_VERT']=rig.SKIN_VERT
values['SKIN_SHADOW_VERT']=rig.SKIN_SHADOW_VERT
values['SKIN_SHADOW_FRAG']=rig.SKIN_SHADOW_FRAG
values['GLTF_SKIN_VERTEX']=gltf.SKINNED_VERTEX
values['GLTF_SKIN_FRAGMENT']=gltf.SKINNED_FRAGMENT
values['GLTF_SHADOW_VERTEX']=gltf.SKINNED_SHADOW_VERTEX
values['GLTF_SHADOW_FRAGMENT']=gltf.SKINNED_SHADOW_FRAGMENT
# Startup shaders are inline literals inside the startup constructor.
tree=ast.parse(Path(__file__).with_name('trench_3d_test.py').read_text())
for node in ast.walk(tree):
    if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
        and node.func.attr=='program' and len(node.keywords)==2
        and all(k.arg in ('vertex_shader','fragment_shader') for k in node.keywords)):
        kw={k.arg:k.value for k in node.keywords}
        if all(isinstance(v,ast.Constant) and isinstance(v.value,str) for v in kw.values()):
            values['STARTUP_VERT']=ast.literal_eval(kw['vertex_shader'])
            values['STARTUP_FRAG']=ast.literal_eval(kw['fragment_shader'])
assert 'STARTUP_VERT' in values and 'STARTUP_FRAG' in values
shaders={}

for name,typ in [('VERT',0x8B31),('FRAG',0x8B30),('SKYVERT',0x8B31),('SKYFRAG',0x8B30),('ACTOR_VERT',0x8B31),('ACTOR_FRAG',0x8B30),
                 ('PARTICLE_VERTEX',0x8B31),('PARTICLE_FRAGMENT',0x8B30),
                 ('PLANE_VERTEX',0x8B31),('PLANE_FRAGMENT',0x8B30),('SHADOW_VERT',0x8B31),('SHADOW_FRAG',0x8B30),('SKIN_VERT',0x8B31),('SKIN_SHADOW_VERT',0x8B31),('SKIN_SHADOW_FRAG',0x8B30),('GLTF_SKIN_VERTEX',0x8B31),('GLTF_SKIN_FRAGMENT',0x8B30),('GLTF_SHADOW_VERTEX',0x8B31),('GLTF_SHADOW_FRAGMENT',0x8B30),('STARTUP_VERT',0x8B31),('STARTUP_FRAG',0x8B30)]:
    data=values[name].encode();ptr=C.c_char_p(data)
    sh=G.glCreateShader(typ);G.glShaderSource(sh,1,C.byref(ptr),None);G.glCompileShader(sh)
    ok=integer();G.glGetShaderiv(sh,0x8B81,C.byref(ok))
    length=integer();buf=C.create_string_buffer(4096);G.glGetShaderInfoLog(sh,4096,C.byref(length),buf)
    print(name,'OK' if ok.value else 'FAIL',buf.value.decode()[:400]);assert ok.value
    shaders[name]=sh
for a,b in [('VERT','FRAG'),('SKYVERT','SKYFRAG'),('ACTOR_VERT','ACTOR_FRAG'),('PARTICLE_VERTEX','PARTICLE_FRAGMENT'),
            ('PLANE_VERTEX','PLANE_FRAGMENT'),('SHADOW_VERT','SHADOW_FRAG'),('SKIN_VERT','ACTOR_FRAG'),('SKIN_SHADOW_VERT','SKIN_SHADOW_FRAG'),('GLTF_SKIN_VERTEX','GLTF_SKIN_FRAGMENT'),('GLTF_SHADOW_VERTEX','GLTF_SHADOW_FRAGMENT'),('STARTUP_VERT','STARTUP_FRAG')]:
    prog=G.glCreateProgram();G.glAttachShader(prog,shaders[a]);G.glAttachShader(prog,shaders[b]);G.glLinkProgram(prog)
    ok=integer();G.glGetProgramiv(prog,0x8B82,C.byref(ok))
    length=integer();buf=C.create_string_buffer(4096);G.glGetProgramInfoLog(prog,4096,C.byref(length),buf)
    print('LINK',a,b,'OK' if ok.value else 'FAIL',buf.value.decode()[:400]);assert ok.value
    if a=='GLTF_SKIN_VERTEX':
        required=['joint_palette','base_color','base_tint','shadow_mode',
                  'shadow_sun','shadow_moon','shadow_lamp',
                  'shadow_sun_mvp','shadow_moon_mvp','shadow_lamp_mvp',
                  'shadow_lamp_index','model','mvp','camera_position']
        for key in required:
            location=G.glGetUniformLocation(prog,key.encode('ascii'))
            assert location>=0, f'GLB renderer requires uniform {key}'
        print('GLTF PLAYER + SHADOW UNIFORMS: OK')
    if a=='GLTF_SHADOW_VERTEX':
        required=['joint_palette','model','light_mvp']
        for key in required:
            location=G.glGetUniformLocation(prog,key.encode('ascii'))
            assert location>=0, f'GLB shadow renderer requires uniform {key}'
        print('GLTF SHADOW UNIFORMS: OK')
print('V3.9.7 game, glTF 4-weight skinning and shadow shaders compiled and linked in real OpenGL 3.3 (Mesa/EGL)')
