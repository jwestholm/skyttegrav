"""Reproducible procedural high-resolution FALLBACK textures for Skyttegrav.

Run: python3 generate_detail_textures.py
Requires only numpy and pillow. No network. Images are generated locally and
are NOT claimed to be photographic or from Poly Haven. Their role is to keep the
V2.7 delta functional while optional CC0 photographic maps are downloaded.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

OUT=Path(__file__).resolve().parent/'assets'/'detail'
SIZE=1024
STYLES={
 'pine_bark':      ('bark',(61,51,39), 2121),
 'bark_willow':    ('bark',(76,66,52), 2202),
 'wood_planks':    ('plank',(84,67,46), 2313),
 'wood_planks_grey':('plank',(78,76,67), 2414),
 'mossy_rock':     ('rock',(71,70,62), 2515),
 'wood_planks_dirt':('plank',(62,51,40), 2616),
 'sandbag_mud':    ('canvas',(70,65,50), 2717),
}

def smooth_noise(rng,grid,n=SIZE):
    g=rng.random((grid,grid),dtype=np.float32)
    im=Image.fromarray(np.uint8(g*255),'L').resize((n,n),Image.Resampling.BICUBIC)
    return np.asarray(im,dtype=np.float32)/255-.5

def maps(style,palette,seed):
    rng=np.random.default_rng(seed)
    yy,xx=np.mgrid[0:SIZE,0:SIZE].astype(np.float32)
    broad=smooth_noise(rng,8); mid=smooth_noise(rng,35); detail=smooth_noise(rng,170)
    if style=='bark':
        # Fractured ridges largely aligned with trunk grain; different phase per
        # Y gives twisting and knots, not perfect vertical stripes.
        flow=xx/15.0+8*mid+5*broad
        crack=np.cos(flow*.68+3*broad)**13
        coarse=8*np.sin(xx*.22+yy*.021+mid*5)
        height=2.2*broad+3.5*mid+1.0*detail+coarse*.40-crack*19
        stain=-13*(broad>.19).astype(np.float32)
        rgb=np.array(palette,dtype=np.float32)[None,None,:]+height[:,:,None]*np.array([1.05,.92,.72])+stain[:,:,None]
    elif style=='plank':
        knots=np.exp(-(((xx-SIZE*.31)/83)**2+((yy-SIZE*.46)/45)**2))
        grain=np.sin(xx*.26+yy*.017+9*mid+knots*19)
        grain2=np.sin(xx*.63+yy*.014+5*detail)
        coarse=20*broad+8*mid+5*detail+9*grain+3*grain2
        aging=-14*(broad>.21).astype(np.float32)
        height=coarse+aging
        rgb=np.array(palette,dtype=np.float32)[None,None,:]+height[:,:,None]*np.array([1.1,1.02,.84])
        # dark cracks and old nail marks
        crackmask=(np.abs(np.sin(xx*.028+yy*.0009+3*broad))>.997).astype(np.float32)
        rgb-=15*crackmask[:,:,None]
    elif style=='rock':
        ridge=np.abs(2*mid+.6*broad)
        fract=np.sin(xx*.032+yy*.065+20*broad+11*mid)
        height=24*broad+17*mid+7*detail-9*ridge+8*fract
        moss=np.clip(broad*.8+mid*.55-.12,0,.42)
        rgb=np.array(palette,dtype=np.float32)[None,None,:]+height[:,:,None]*np.array([.92,1,.98])
        rgb+=moss[:,:,None]*np.array([-22,22,-8])
    else:
        weave=(np.sin(xx*.55)*np.sin(yy*.56))*2.5
        height=12*broad+9*mid+4*detail+weave
        rgb=np.array(palette,dtype=np.float32)[None,None,:]+height[:,:,None]*np.array([1.1,1,.75])
        stains=(broad>.13).astype(np.float32)
        rgb-=8*stains[:,:,None]
    rgb=np.clip(rgb,3,235).astype(np.uint8)
    # Approximate tangential OpenGL normal map from height differences.
    # No claims of physical PBR correctness for these procedural fallbacks.
    h=np.clip(height,-45,45)
    dx=(np.roll(h,-1,1)-np.roll(h,1,1))*.045
    dy=(np.roll(h,-1,0)-np.roll(h,1,0))*.045
    vec=np.stack((-dx,-dy,np.ones_like(dx)*2.1),axis=2)
    vec/=np.maximum(.0001,np.linalg.norm(vec,axis=2,keepdims=True))
    normal=np.clip((vec*.5+.5)*255,0,255).astype(np.uint8)
    return rgb,normal

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name,(style,palette,seed) in STYLES.items():
        rgb,normal=maps(style,palette,seed)
        Image.fromarray(rgb,'RGB').save(OUT/f'{name}.png',compress_level=6)
        Image.fromarray(normal,'RGB').save(OUT/f'{name}_nor_gl.png',compress_level=6)
        print(name,'1024px diffuse+OpenGL normal')

if __name__=='__main__':main()
