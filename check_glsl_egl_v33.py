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
tree=ast.parse(Path(__file__).with_name('trench_3d_test.py').read_text())
values={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('VERT','FRAG','SKYVERT','SKYFRAG')}
values['ACTOR_VERT']=(values['VERT']
    .replace('uniform vec3 camera_position;','uniform vec3 camera_position;\nuniform mat4 model;')
    .replace('gl_Position=mvp*vec4(mesh_pos,1.0);','vec4 world_pos=model*vec4(mesh_pos,1.0);\n    gl_Position=mvp*world_pos;')
    .replace('v_world=mesh_pos;','v_world=world_pos.xyz;')
    .replace('v_normal=in_normal;','v_normal=normalize(transpose(inverse(mat3(model)))*in_normal);')
    .replace('v_distance=length(mesh_pos-camera_position);','v_distance=length(world_pos.xyz-camera_position);'))
# Resolve the actor-only fragment modifications exactly as the game does.
for node in tree.body:
    if (isinstance(node,ast.Assign) and len(node.targets)==1 and
        isinstance(node.targets[0],ast.Name) and node.targets[0].id=='ACTOR_FRAG'):
        def static_replace(node):
            assert isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
            assert node.func.attr=='replace'
            base=(values[node.func.value.id] if isinstance(node.func.value,ast.Name)
                  else static_replace(node.func.value))
            return base.replace(ast.literal_eval(node.args[0]),ast.literal_eval(node.args[1]))
        values['ACTOR_FRAG']=static_replace(node.value)
assert 'ACTOR_FRAG' in values
# V3.8 extra VFX programs: compile the actual shader source shipped in the
# game, without importing ModernGL in this EGL smoke-test.
vfx_tree=ast.parse(Path(__file__).with_name('battlefield_events.py').read_text())
for node in vfx_tree.body:
    if (isinstance(node,ast.Assign) and len(node.targets)==1 and
        isinstance(node.targets[0],ast.Name) and
        node.targets[0].id in ('PARTICLE_VERTEX','PARTICLE_FRAGMENT',
                                'PLANE_VERTEX','PLANE_FRAGMENT')):
        values[node.targets[0].id]=ast.literal_eval(node.value)
# Include the GL loader card so startup cannot fail on shader compilation.
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
                 ('PLANE_VERTEX',0x8B31),('PLANE_FRAGMENT',0x8B30),('STARTUP_VERT',0x8B31),('STARTUP_FRAG',0x8B30)]:
    data=values[name].encode();ptr=C.c_char_p(data)
    sh=G.glCreateShader(typ);G.glShaderSource(sh,1,C.byref(ptr),None);G.glCompileShader(sh)
    ok=integer();G.glGetShaderiv(sh,0x8B81,C.byref(ok))
    length=integer();buf=C.create_string_buffer(4096);G.glGetShaderInfoLog(sh,4096,C.byref(length),buf)
    print(name,'OK' if ok.value else 'FAIL',buf.value.decode()[:400]);assert ok.value
    shaders[name]=sh
for a,b in [('VERT','FRAG'),('SKYVERT','SKYFRAG'),('ACTOR_VERT','ACTOR_FRAG'),('PARTICLE_VERTEX','PARTICLE_FRAGMENT'),
            ('PLANE_VERTEX','PLANE_FRAGMENT'),('STARTUP_VERT','STARTUP_FRAG')]:
    prog=G.glCreateProgram();G.glAttachShader(prog,shaders[a]);G.glAttachShader(prog,shaders[b]);G.glLinkProgram(prog)
    ok=integer();G.glGetProgramiv(prog,0x8B82,C.byref(ok))
    length=integer();buf=C.create_string_buffer(4096);G.glGetProgramInfoLog(prog,4096,C.byref(length),buf)
    print('LINK',a,b,'OK' if ok.value else 'FAIL',buf.value.decode()[:400]);assert ok.value
print('V3.8 shaders compile and link in real OpenGL 3.3 (Mesa/EGL)')
