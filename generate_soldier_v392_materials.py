"""Generate the V3.9.2 authored diffuse/normal textile fallback maps (CC0).

Already generated PNGs ship with the delta; this is optional reproducibility,
not an install step. No internet, paid asset or external tool required.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter

OUT=Path(__file__).resolve().parent/'assets'/'enemies'
S=1024
STYLES={
    'uniform':((73,77,62),2718,'cloth'),
    'webbing':((62,64,51),1894,'canvas'),
    'skin':((160,120,99),3911,'skin'),
}

def noise(rng,grain):
    grid=rng.integers(0,256,(grain,grain),dtype=np.uint8)
    return np.asarray(Image.fromarray(grid,'L').resize((S,S),Image.Resampling.BICUBIC),dtype=np.float32)/255-.5

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    yy,xx=np.mgrid[:S,:S].astype('f4')
    for name,(color,seed,style) in STYLES.items():
        rng=np.random.default_rng(seed)
        broad=noise(rng,16);mid=noise(rng,64)
        fine=rng.normal(0.,.19,(S,S)).astype('f4')
        weave=np.sin(xx*.95)*np.sin(yy*1.06)
        warp=.5*np.sin(xx*.50+mid*3)+.4*np.cos(yy*.55+broad*4)
        if style=='cloth':
            stain=np.clip(.54*broad+.33*mid-.04,-.4,.4)
            camo=np.clip((stain-.035)*2.4,-1.,1.)
            rgb=np.array(color,dtype='f4')+(
                18*broad[:,:,None]+11*mid[:,:,None]+3*fine[:,:,None])
            rgb+=camo[:,:,None]*np.array((-13,3,-9),dtype='f4')
            rgb+=weave[:,:,None]*1.5
            height=1.7*weave+1.4*warp+4*mid+2*broad+.3*fine
            normal_strength=.14
        elif style=='canvas':
            dust=np.clip(broad*.55+mid*.35+.04,0.,.32)
            rgb=np.array(color,dtype='f4')+(14*broad+8*mid+3*fine)[:,:,None]
            rgb-=dust[:,:,None]*np.array((18,13,7),dtype='f4')
            rgb+=weave[:,:,None]*2.2
            height=2.4*weave+2.0*warp+3*mid+1.5*broad+.25*fine
            normal_strength=.15
        else:
            pores=rng.normal(0.,1.,(S,S)).astype('f4')
            rgb=np.array(color,dtype='f4')+(9*broad+4*mid+1.7*pores)[:,:,None]
            rgb+=broad[:,:,None]*np.array((3,0,-2),dtype='f4')
            height=.33*pores+.7*mid+.30*broad
            normal_strength=.06
        albedo=np.clip(rgb,0,255).astype('uint8')
        Image.fromarray(albedo,'RGB').save(OUT/(name+'.png'),optimize=True)
        dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*normal_strength
        dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*normal_strength
        norm=np.stack((-dx,-dy,np.ones_like(dx)*2.0),axis=2)
        norm/=np.maximum(1e-5,np.linalg.norm(norm,axis=2,keepdims=True))
        normal=np.clip((norm*.5+.5)*255.,0,255).astype('uint8')
        Image.fromarray(normal,'RGB').save(OUT/(name+'_nor_gl.png'),optimize=True)
        print(name,'albedo', (OUT/(name+'.png')).stat().st_size,
              'normal',(OUT/(name+'_nor_gl.png')).stat().st_size)

if __name__=='__main__':main()
