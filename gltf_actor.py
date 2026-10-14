"""Optional real glTF 2.0 GLB humanoid preview with four-weight GPU skinning.

Strict scope: an artist-authored rigged GLB with one skinned mesh node,
embedded PNG/JPEG base-colour textures, and optional TRS animation clips.
This does not replace EnemyDirector, game hitboxes or SoldierBrain.
Model lives entirely on GPU after startup; only a 4xN floating joint palette
texture changes during animation. All original rendering works without an
asset at assets/characters/soldier.glb.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import io
import json
import math
from pathlib import Path
import struct

import numpy as np

from shadow_lighting import SHADOW_GLSL

_COMPONENTS = {5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}
_WIDTHS={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}


def _mat_from_gltf(v):
    return np.asarray(v,dtype=np.float64).reshape((4,4)).T.copy()


def _quat_matrix(q):
    q=np.asarray(q,dtype=np.float64)
    n=float(np.dot(q,q))
    if n<1e-12:return np.eye(3,dtype=np.float64)
    x,y,z,w=q/math.sqrt(n)
    return np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
                     (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
                     (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))),dtype=np.float64)


def _q_slerp(a,b,t):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
    a/=max(np.linalg.norm(a),1e-12);b/=max(np.linalg.norm(b),1e-12)
    d=float(np.dot(a,b))
    if d<0:b=-b;d=-d
    if d>.9995:
        x=a+(b-a)*t
        return x/max(np.linalg.norm(x),1e-12)
    theta=math.acos(max(-1.,min(1.,d)))
    sine=math.sin(theta)
    return (math.sin((1-t)*theta)/sine)*a+(math.sin(t*theta)/sine)*b


def _trs(node):
    return (np.asarray(node.get('translation',(0,0,0)),dtype=np.float64),
            np.asarray(node.get('rotation',(0,0,0,1)),dtype=np.float64),
            np.asarray(node.get('scale',(1,1,1)),dtype=np.float64))


def _compose(t,r,s):
    m=np.eye(4,dtype=np.float64)
    m[:3,:3]=_quat_matrix(r)*np.asarray(s,dtype=np.float64)[None,:]
    m[:3,3]=t
    return m


class GLBError(ValueError):pass


class GLBDocument:
    """Limited but rigorous glTF 2.0 reader; no external paths or network."""
    def __init__(self,path):
        path=Path(path)
        blob=path.read_bytes()
        if len(blob)<20 or blob[:4]!=b'glTF':raise GLBError('Not a GLB 2.0 file')
        magic,version,length=struct.unpack_from('<4sII',blob,0)
        if version!=2 or length!=len(blob):raise GLBError('invalid GLB length/version')
        offset=12;chunks=[]
        while offset+8<=len(blob):
            size,typ=struct.unpack_from('<I4s',blob,offset);offset+=8
            if offset+size>len(blob):raise GLBError('truncated GLB chunk')
            chunks.append((typ,blob[offset:offset+size]));offset+=size
        if offset!=len(blob) or not chunks or chunks[0][0]!=b'JSON':
            raise GLBError('missing GLB JSON chunk')
        self.json=json.loads(chunks[0][1].decode('utf8').rstrip(' \x00'))
        if str(self.json.get('asset',{}).get('version'))!='2.0':
            raise GLBError('glTF 2.0 required')
        binary=next((chunk for typ,chunk in chunks[1:] if typ==b'BIN\x00'),None)
        self.buffers=[]
        for i,b in enumerate(self.json.get('buffers',[])):
            uri=b.get('uri')
            if uri is None:
                if i!=0 or binary is None:raise GLBError('missing GLB embedded buffer')
                contents=binary
            elif uri.startswith('data:'):
                contents=base64.b64decode(uri.split(',',1)[1])
            else:raise GLBError('external buffers not supported: pack a single GLB')
            if len(contents)<b['byteLength']:raise GLBError('truncated GLB buffer')
            self.buffers.append(contents)

    def view_bytes(self,index):
        item=self.json['bufferViews'][index]
        buffer=self.buffers[item['buffer']]
        start=item.get('byteOffset',0);size=item['byteLength']
        if start<0 or start+size>len(buffer):raise GLBError('out-of-bounds buffer view')
        return buffer[start:start+size]

    def accessor(self,index):
        a=self.json['accessors'][index]
        if 'sparse' in a or 'bufferView' not in a:
            raise GLBError('sparse or implicit accessors not supported')
        dt=np.dtype(_COMPONENTS[a['componentType']])
        cols=_WIDTHS[a['type']];count=int(a['count']);stride_item=dt.itemsize*cols
        view=self.json['bufferViews'][a['bufferView']]
        stride=int(view.get('byteStride',stride_item))
        raw=self.view_bytes(a['bufferView'])
        start=int(a.get('byteOffset',0))
        if count<1 or stride<stride_item or start<0 or start+(count-1)*stride+stride_item>len(raw):
            raise GLBError('accessor outside buffer view')
        array=np.ndarray((count,cols),dtype=dt,buffer=raw,offset=start,
                         strides=(stride,dt.itemsize)).copy()
        if a.get('normalized'):
            if dt.kind=='u':array=array.astype('f4')/float(np.iinfo(dt).max)
            elif dt.kind=='i':array=np.maximum(-1.,array.astype('f4')/float(np.iinfo(dt).max))
        if a['type']=='SCALAR':return array[:,0]
        if a['type']=='MAT4':return array.reshape((-1,4,4)).transpose((0,2,1)).copy()
        return array

    def image_bytes(self,index):
        image=self.json['images'][index]
        if 'bufferView' in image:return self.view_bytes(image['bufferView'])
        uri=image.get('uri','')
        if uri.startswith('data:'):return base64.b64decode(uri.split(',',1)[1])
        raise GLBError('external images not supported: pack textures into GLB')


@dataclass(frozen=True)
class Primitive:
    vertices:np.ndarray
    indices:np.ndarray
    albedo:bytes | None
    color:tuple


class GLBCharacter:
    """Animation and rig CPU bookkeeping; GPU handles ALL vertex deformation."""
    def __init__(self,path):
        self.doc=GLBDocument(path)
        gl=self.doc.json
        self.nodes=gl.get('nodes',[])
        matches=[(i,n) for i,n in enumerate(self.nodes) if 'mesh' in n and 'skin' in n]
        if len(matches)!=1:raise GLBError('expected one skinned mesh node in GLB')
        self.mesh_node,self.mesh_spec=matches[0]
        self.skin=gl['skins'][self.mesh_spec['skin']]
        self.joints=tuple(self.skin['joints']);self.joint_count=len(self.joints)
        if self.joint_count<1 or self.joint_count>128:raise GLBError('expected 1..128 joints')
        if 'inverseBindMatrices' in self.skin:
            self.inverse_bind=self.doc.accessor(self.skin['inverseBindMatrices']).astype('f8')
        else:self.inverse_bind=np.tile(np.eye(4),(self.joint_count,1,1))
        if len(self.inverse_bind)!=self.joint_count:raise GLBError('wrong inverse bind count')
        self.parents={child:i for i,n in enumerate(self.nodes) for child in n.get('children',[])}
        self.bind_trs=[_trs(n) for n in self.nodes]
        # A mesh may have several material primitives but ONE common skeleton.
        self.primitives=[]
        for pr in gl['meshes'][self.mesh_spec['mesh']]['primitives']:
            if pr.get('mode',4)!=4:raise GLBError('triangle primitives required')
            attr=pr['attributes']
            if not all(k in attr for k in ('POSITION','JOINTS_0','WEIGHTS_0')):
                raise GLBError('skinned POSITION, JOINTS_0, WEIGHTS_0 required')
            pos=self.doc.accessor(attr['POSITION']).astype('f4')
            normal=(self.doc.accessor(attr['NORMAL']).astype('f4') if 'NORMAL' in attr
                    else np.tile(np.array([0,1,0],dtype='f4'),(len(pos),1)))
            uv=(self.doc.accessor(attr['TEXCOORD_0']).astype('f4') if 'TEXCOORD_0' in attr
                else np.zeros((len(pos),2),dtype='f4'))
            joint=self.doc.accessor(attr['JOINTS_0']).astype('i4')
            weight=self.doc.accessor(attr['WEIGHTS_0']).astype('f4')
            if pos.shape[1]!=3 or joint.shape!=(len(pos),4) or weight.shape!=(len(pos),4):
                raise GLBError('invalid skin vertex format')
            if (joint<0).any() or (joint>=self.joint_count).any():
                raise GLBError('joint index outside skin')
            weight=np.maximum(weight,0.)
            den=weight.sum(axis=1,keepdims=True)
            if np.any(den<1e-6):raise GLBError('zero-weight skinned vertex')
            weight/=den
            vertices=np.concatenate((pos,normal,uv,joint.astype('f4'),weight),axis=1).astype('f4')
            idx=(self.doc.accessor(pr['indices']).astype('u4') if 'indices' in pr
                 else np.arange(len(pos),dtype='u4'))
            if len(idx)%3 or np.max(idx)>=len(pos):raise GLBError('invalid triangle indices')
            mat=gl.get('materials',[])
            mt=mat[pr.get('material',0)] if mat else {}
            pbr=mt.get('pbrMetallicRoughness',{})
            bc=pbr.get('baseColorFactor',[.65,.63,.57,1.])
            tex_info=pbr.get('baseColorTexture')
            texture=None
            if tex_info:
                tx=gl['textures'][tex_info['index']]
                texture=self.doc.image_bytes(tx['source'])
            self.primitives.append(Primitive(vertices,idx,texture,tuple(bc[:4])))
        self.clips={}
        for ani in gl.get('animations',[]):
            name=ani.get('name') or ('clip'+str(len(self.clips)))
            channels=[]
            for ch in ani.get('channels',[]):
                path=ch.get('target',{}).get('path')
                target=ch.get('target',{}).get('node')
                if path not in ('translation','rotation','scale') or target is None:continue
                sampler=ani['samplers'][ch['sampler']]
                t=self.doc.accessor(sampler['input']).astype('f8')
                values=self.doc.accessor(sampler['output']).astype('f8')
                interp=sampler.get('interpolation','LINEAR')
                if interp=='CUBICSPLINE':
                    if len(values)!=len(t)*3:raise GLBError('invalid cubic sampler')
                    values=values[1::3]  # documented linear approximation in preview
                    interp='LINEAR'
                if len(t)!=len(values) or len(t)<1 or np.any(np.diff(t)<0):
                    raise GLBError('invalid animation times')
                channels.append((target,path,t,values,interp))
            self.clips[name]=channels
        self.clip_names=tuple(self.clips)
        mins=[];maxs=[]
        for part in self.primitives:
            mins.append(part.vertices[:,:3].min(axis=0))
            maxs.append(part.vertices[:,:3].max(axis=0))
        self.local_min=np.min(mins,axis=0);self.local_max=np.max(maxs,axis=0)
        # Grounding uses the transformed rest pose in scene/model space.
        world=self._node_globals(self.bind_trs)[self.mesh_node]
        corners=np.array([[x,y,z,1.] for x in (self.local_min[0],self.local_max[0])
                          for y in (self.local_min[1],self.local_max[1])
                          for z in (self.local_min[2],self.local_max[2])],dtype='f8')
        bb=(world@corners.T).T[:,:3]
        self.height=max(.001,float(bb[:,1].max()-bb[:,1].min()))
        self.floor_offset=float(bb[:,1].min())
        if not all(np.isfinite(v) for v in (self.height,self.floor_offset)):
            raise GLBError('non-finite character bounds')

    def _node_globals(self,trs):
        result={}
        def get(n):
            if n in result:return result[n]
            m=_compose(*trs[n])
            if n in self.parents:m=get(self.parents[n])@m
            result[n]=m;return m
        for i in range(len(self.nodes)):get(i)
        return result

    def choose_clip(self,pose):
        candidates={
          'stand':('idle','stand','breath'),
          'walk':('walk',), 'run':('run','sprint'),
          'crouch':('crouch','duck'), 'kneel':('kneel',),
          'prone':('prone','crawl'), 'supine_sleep':('sleep','lie'),
          'fear_curl':('fear','cover','hurt'), 'aim':('aim','rifle','shoot'),
          'fire':('fire','shoot'), 'spade_attack':('melee','attack'),
          'dead':('death','die','dead'),
        }.get(pose,('idle',))
        for word in candidates:
            for clip in self.clip_names:
                if word in clip.lower():return clip
        for clip in self.clip_names:
            if 'idle' in clip.lower():return clip
        return self.clip_names[0] if self.clip_names else None

    def local_pose(self,clip=None,at_time=0.0,loop=True):
        """Sample local-node translations/rotations/scales, without CPU skinning."""
        trs=[(x.copy(),y.copy(),z.copy()) for x,y,z in self.bind_trs]
        if clip is not None:
            chans=self.clips.get(clip,())
            duration=max((float(times[-1]) for _,_,times,_,_ in chans),default=0.)
            t=(float(at_time)%duration if loop else min(float(at_time),duration)) if duration>1e-6 else 0.0
            for target,path,times,values,interp in chans:
                hi=int(np.searchsorted(times,t,side='right'))
                a=max(0,min(len(times)-1,hi-1));b=max(0,min(len(times)-1,hi))
                f=0.0 if b==a or interp=='STEP' else max(0.,min(1.,(t-times[a])/max(1e-8,times[b]-times[a])))
                if path=='rotation':value=_q_slerp(values[a],values[b],f)
                else:value=(1.-f)*values[a]+f*values[b]
                which={'translation':0,'rotation':1,'scale':2}[path]
                cur=list(trs[target]);cur[which]=np.asarray(value,dtype='f8');trs[target]=tuple(cur)
        return trs

    @staticmethod
    def blend_pose(before,after,t):
        """Preserves normalized joint rotations between authored animation clips."""
        if len(before)!=len(after) or not 0<=t<=1 or not math.isfinite(t):
            raise ValueError('invalid animation blending request')
        return [((1-t)*a[0]+t*b[0], _q_slerp(a[1],b[1],t), (1-t)*a[2]+t*b[2])
                for a,b in zip(before,after)]

    def matrices_for_pose(self,trs):
        glob=self._node_globals(trs)
        inverse_mesh=np.linalg.inv(glob[self.mesh_node])
        palette=np.stack([(inverse_mesh@glob[node]@inv).astype('f4')
                          for node,inv in zip(self.joints,self.inverse_bind)])
        if not np.isfinite(palette).all():raise GLBError('invalid bone transforms')
        return palette,glob[self.mesh_node].astype('f4')

    def matrices(self,clip=None,at_time=0.0):
        return self.matrices_for_pose(self.local_pose(clip,at_time))


SKINNED_VERTEX = '''#version 330
in vec3 in_pos;
in vec3 in_normal;
in vec2 in_uv;
in vec4 in_joints;
in vec4 in_weights;
uniform sampler2D joint_palette;
uniform mat4 mvp;
uniform mat4 model;
uniform vec3 camera_position;
out vec3 v_normal;
out vec2 v_uv;
out vec3 v_world;
out float v_distance;
mat4 J(int n){
    n=clamp(n,0,textureSize(joint_palette,0).y-1);
    return mat4(texelFetch(joint_palette,ivec2(0,n),0),
                texelFetch(joint_palette,ivec2(1,n),0),
                texelFetch(joint_palette,ivec2(2,n),0),
                texelFetch(joint_palette,ivec2(3,n),0));
}
void main(){
    mat4 skin=J(int(in_joints.x+.5))*in_weights.x
            +J(int(in_joints.y+.5))*in_weights.y
            +J(int(in_joints.z+.5))*in_weights.z
            +J(int(in_joints.w+.5))*in_weights.w;
    vec4 w=model*skin*vec4(in_pos,1.0);
    gl_Position=mvp*w;
    v_world=w.xyz;
    v_uv=in_uv;
    v_normal=normalize(mat3(model)*mat3(skin)*in_normal);
    v_distance=length(w.xyz-camera_position);
}
'''

SKINNED_FRAGMENT='''#version 330
in vec3 v_normal;
in vec2 v_uv;
in vec3 v_world;
in float v_distance;
uniform vec3 camera_position;
uniform vec3 sun_direction;
uniform vec3 moon_direction;
uniform float fog_strength;
uniform sampler2D base_color;
uniform vec4 base_tint;
uniform int shadow_mode;
'''
# Shadow source declares its own shadow_mode: remove duplicate above.
SKINNED_FRAGMENT=SKINNED_FRAGMENT.replace('uniform int shadow_mode;\n','')+SHADOW_GLSL+'''
out vec4 f_color;
void main(){
    vec3 n=normalize(v_normal);
    vec3 sun=normalize(sun_direction);
    vec3 moon=normalize(moon_direction);
    float s=max(dot(n,sun),0.0),m=max(dot(n,moon),0.0);
    float sa=shadow_mode!=0?shadow_pcf(shadow_sun,shadow_sun_mvp,v_world,.0016):1.0;
    float mo=shadow_mode!=0?shadow_pcf(shadow_moon,shadow_moon_mvp,v_world,.0016):1.0;
    // Use the SAME three shadow resources as the native trench shader.
    // Keeping lamp uniforms active also makes ShadowRenderer.setup_material
    // safe when F1 switches to the optional GLB model.
    float la=(shadow_mode!=0 && shadow_lamp_index>=0) ?
             shadow_pcf(shadow_lamp,shadow_lamp_mvp,v_world,.0030) : 1.0;
    vec4 col=texture(base_color,v_uv)*base_tint;
    vec3 light=vec3(.32)+vec3(.59,.49,.39)*s*sa
               +vec3(.16,.20,.28)*m*mo+vec3(.028,.018,.009)*la;
    float fog=1.-exp(-max(0.,v_distance-8.)*.015*fog_strength);
    f_color=vec4(mix(col.rgb*light,vec3(.43,.42,.42),clamp(fog,0.,.85)),col.a);
}
'''

SKINNED_SHADOW_VERTEX=SKINNED_VERTEX.replace('uniform mat4 mvp;','uniform mat4 light_mvp;').replace(
    'gl_Position=mvp*w;','gl_Position=light_mvp*w;')
SKINNED_SHADOW_FRAGMENT='#version 330\nvoid main() {}\n'


class GLBSkinnedRenderer:
    """Drop-in optional renderer; GLB preview first, opt-in live later."""
    is_skeletal=True
    def __init__(self,ctx,path,sun,moon):
        from PIL import Image
        import moderngl
        self.ctx=ctx;self.asset=GLBCharacter(path)
        self.program=ctx.program(vertex_shader=SKINNED_VERTEX,fragment_shader=SKINNED_FRAGMENT)
        self.shadow_program=ctx.program(vertex_shader=SKINNED_SHADOW_VERTEX,
                                        fragment_shader=SKINNED_SHADOW_FRAGMENT)
        self.program['joint_palette'].value=5
        self.shadow_program['joint_palette'].value=5
        self.program['base_color'].value=0
        self.program['sun_direction'].value=sun
        self.program['moon_direction'].value=moon
        self.program['shadow_mode'].value=0
        self.program['shadow_lamp_index'].value=-1
        self.joint_texture=ctx.texture((4,self.asset.joint_count),4,dtype='f4')
        self.joint_texture.filter=(moderngl.NEAREST,moderngl.NEAREST)
        self.joint_texture.repeat_x=False;self.joint_texture.repeat_y=False
        self.buffers=[];self.items=[]
        for part in self.asset.primitives:
            buf=ctx.buffer(np.ascontiguousarray(part.vertices).tobytes())
            ind=ctx.buffer(np.ascontiguousarray(part.indices).tobytes())
            vao=ctx.vertex_array(self.program,[(buf,'3f 3f 2f 4f 4f',
                      'in_pos','in_normal','in_uv','in_joints','in_weights')],ind)
            shvao=ctx.vertex_array(self.shadow_program,[(buf,'3f 3f 2f 4f 4f',
                      'in_pos','in_normal','in_uv','in_joints','in_weights')],ind)
            if part.albedo:
                im=Image.open(io.BytesIO(part.albedo)).convert('RGBA')
                # GLB texcoords originate top left for common glTF images.
                tex=ctx.texture(im.size,4,im.tobytes())
            else:tex=ctx.texture((1,1),4,b'\xff\xff\xff\xff')
            tex.filter=(moderngl.LINEAR,moderngl.LINEAR)
            tex.build_mipmaps()
            self.items.append((vao,shvao,tex,part.color))
            self.buffers.extend([buf,ind])
        self.gpu_bytes=sum(b.size for b in self.buffers)
        self._clip_state={}  # actor-id -> last visible pose + transition start
        print('GLB rig:',self.asset.joint_count,'bones',len(self.items),'meshes',
              len(self.asset.clip_names),'animation clips')

    def reset_preview(self):
        """Fresh F1 session: do not inherit a previous pose's death clip."""
        self._clip_state.clear()

    def collect_instances(self,agents,position_at,heading_at):
        out=[]
        current_ids={a.spec.enemy_id for a in agents}
        # The endless world must NOT retain transforms for evicted enemies.
        for key in list(self._clip_state):
            if key not in current_ids:self._clip_state.pop(key,None)
        for actor in agents:
            preview=getattr(actor,'pose_preview',None)
            pose=(preview if preview else
                'dead' if actor.dead else
                'fire' if actor.state=='firing' else
                'aim' if actor.state=='aiming' else
                'run' if actor.state=='rushing' else
                'crouch' if actor.state in ('hiding','cover') else
                'walk' if getattr(actor,'gait_speed_mps',0.)>.27 else 'stand')
            clip=self.asset.choose_clip(pose)
            now=max(0.,float(getattr(actor,'total_time',0.)))
            uid=actor.spec.enemy_id
            state=self._clip_state.get(uid)
            if state is None:
                state=(clip,now,None,None)
            elif state[0]!=clip:
                # Interrupts start from the actual last visible local skeleton.
                source=state[3]
                state=(clip,now,source,source)
            age=max(0.,now-state[1])
            target=self.asset.local_pose(clip,age,loop=pose not in ('dead',))
            source=state[2]
            if source is not None and age<.38:
                f=min(1.,age/.38)
                f=f*f*(3.-2.*f)
                target=self.asset.blend_pose(source,target,f)
            self._clip_state[uid]=(state[0],state[1],state[2],target)
            pal,mesh=self.asset.matrices_for_pose(target)
            pos=position_at(actor.spec)
            heading=heading_at(actor.route_m)
            from enemy_system import actor_facing
            heading=actor_facing(actor,heading)
            c,s=math.cos(heading),math.sin(heading)
            root=np.eye(4,dtype='f4')
            root[:3,:3]=((c,0,s),(0,1,0),(-s,0,c))
            root[:3,3]=pos
            scale=min(2.7,max(.5,1.78/self.asset.height))
            ss=np.diag([scale,scale,scale,1.]).astype('f4')
            ss[1,3]=-self.asset.floor_offset*scale
            model=root@ss@mesh
            out.append((model,pal,actor))
        return out

    def _setup_skin(self,program,model,palette):
        program['model'].write(model.T.tobytes())
        # 4 texels = 4 columns per mat4, indexed by joint in the shader.
        data=np.ascontiguousarray(palette.transpose((0,2,1)),dtype='f4')
        self.joint_texture.write(data.tobytes())
        self.joint_texture.use(location=5)

    def draw(self,agents,position_at,heading_at,projection_view,eye,
             fog_strength,normal_enabled,lights,instances=None):
        import moderngl
        if instances is None:instances=self.collect_instances(agents,position_at,heading_at)
        self.program['mvp'].write(np.asarray(projection_view,dtype='f4').T.tobytes())
        self.program['camera_position'].value=eye
        self.program['fog_strength'].value=float(fog_strength)
        for model,palette,actor in instances:
            self._setup_skin(self.program,model,palette)
            for vao,_,tex,tint in self.items:
                self.program['base_tint'].value=tint
                tex.use(location=0)
                vao.render(moderngl.TRIANGLES)

    def draw_skeletal_shadows(self,light_mvp,instances):
        import moderngl
        self.shadow_program['light_mvp'].write(np.asarray(light_mvp,dtype='f4').T.tobytes())
        for model,palette,actor in instances:
            self._setup_skin(self.shadow_program,model,palette)
            for _,vao,_,_ in self.items:vao.render(moderngl.TRIANGLES)

    def release(self):
        for va,sv,tx,_ in self.items:
            va.release();sv.release();tx.release()
        for buf in self.buffers:buf.release()
        self.joint_texture.release()
        self.program.release();self.shadow_program.release()
