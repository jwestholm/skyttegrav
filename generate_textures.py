"""Generate deterministic seamless 512x512 terrain textures; Pillow + NumPy."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
SIZE=512
OUT=Path(__file__).resolve().parent/'assets'
OUT.mkdir(exist_ok=True)

def generate(name,seed,base,texture):
    rng=np.random.default_rng(seed)
    a=np.zeros((SIZE,SIZE),np.float32)
    for grid,weight in [(4,0.28),(8,0.20),(16,0.16),(32,0.12),(64,0.09),(128,0.07),(256,0.05),(512,0.03)]:
        raw=(rng.random((grid,grid))*255).astype('uint8')
        im=Image.fromarray(raw,'L').resize((SIZE,SIZE),Image.BICUBIC)
        a+=(np.asarray(im,dtype=np.float32)/255-.5)*weight
    a=np.clip(a,-.35,.35)
    result=np.empty((SIZE,SIZE,3),np.uint8)
    for i in range(3): result[:,:,i]=np.clip(base[i]+a*180,0,255).astype('uint8')
    im=Image.fromarray(result,'RGB'); d=ImageDraw.Draw(im,'RGBA')
    for j in range(texture):
        x=int(rng.integers(0,SIZE));y=int(rng.integers(0,SIZE))
        r=int(rng.choice([1,1,1,2,2,3,4,5,6,8],p=[.16,.16,.16,.14,.12,.10,.07,.05,.03,.01]))
        bright=int(rng.integers(-58,64)); color=tuple(max(0,min(255,c+bright)) for c in base)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(*color,int(rng.integers(50,200))))
    # tileable seams: blend 12 pixel strip with opposite border
    arr=np.array(im,dtype=np.float32); w=12
    for k in range(w):
        t=(k+1)/(w+1)
        blended=arr[:,k,:]*(1-t)+arr[:,SIZE-w+k,:]*t
        arr[:,k,:]=blended;arr[:,SIZE-w+k,:]=blended
    for k in range(w):
        t=(k+1)/(w+1)
        blended=arr[k,:,:]*(1-t)+arr[SIZE-w+k,:,:]*t
        arr[k,:,:]=blended;arr[SIZE-w+k,:,:]=blended
    Image.fromarray(np.clip(arr,0,255).astype('uint8')).save(OUT/name)

for args in [('clay.png',21,(76,69,59),9000),('gravel.png',42,(110,96,79),12500),('loam.png',13,(90,72,55),7000),('humus.png',17,(53,48,38),10000),('mud.png',89,(65,57,46),11000)]:
    generate(*args)
print('Generated',', '.join(x.name for x in OUT.glob('*.png')))
