"""Deterministic, fully local tree-material authoring (no external downloads).

Generates 1K organic tree bark albedo + OpenGL tangent-space normals and a
1K RGBA cutout canopy atlas. The images are distributed with the game; this
script is optional for rebuilds, and does not run during world streaming.
"""
from __future__ import annotations
from pathlib import Path
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
PIL_RESAMPLING = getattr(Image, 'Resampling', Image)


SIZE=1024


def _smooth_random(rng, cells_x, cells_y):
    grid=rng.random((cells_y,cells_x)).astype(np.float32)
    img=Image.fromarray(np.uint8(grid*255),'L').resize((SIZE,SIZE),PIL_RESAMPLING.BICUBIC)
    return np.asarray(img,dtype=np.float32)/255.-.5


def bark(seed:int, warm:bool):
    rng=np.random.default_rng(seed)
    y,x=np.mgrid[:SIZE,:SIZE].astype(np.float32)/SIZE
    broad=_smooth_random(rng,15,34)
    medium=_smooth_random(rng,41,70)
    fine=_smooth_random(rng,164,206)
    warp=.026*broad+.013*medium
    phase=2*math.pi*(x*(11. if warm else 21.) + warp*9.0 +
                      .05*np.sin(y*11.7+x*2.9))
    ridges=(np.cos(phase)*.5+.5)**(9 if warm else 6)
    secondary=(np.cos(phase*2.1+.6*np.sin(y*19.7))*.5+.5)**10
    high=1.2*broad+.61*medium+.25*fine-.9*ridges-.24*secondary
    high=np.clip(high,-1.1,1.2)
    colors=np.array((132,113,88) if warm else (73,69,54),dtype=np.float32)
    shade=high*47.0 + .7*np.cos(phase+.8)*18.0
    rgb=np.clip(colors[None,None,:]+shade[:,:,None]*np.array((1.10,.99,.79)),0,255)
    # Patchy lichen near crevices (not an evenly tiled bright-green noise).
    lichen=_smooth_random(rng,22,18)
    moss=np.clip((lichen-.18)*3.8,0.,.42)
    rgb=rgb*(1-moss[:,:,None])+np.array((80,93,63))[None,None,:]*moss[:,:,None]
    # Thin directional bark grain differentiates light bark from mud.
    grain=np.sin(y*465+x*5+medium*6)*2.2
    rgb=np.uint8(np.clip(rgb+grain[:,:,None],0,255))
    gy,gx=np.gradient(high)
    strength=8.8 if warm else 11.0
    n=np.stack((-gx*strength,-gy*strength,np.ones_like(gx)),axis=-1)
    n/=np.linalg.norm(n,axis=-1,keepdims=True)
    normal=np.uint8(np.clip((n*.5+.5)*255,0,255))
    return Image.fromarray(rgb,'RGB'),Image.fromarray(normal,'RGB')


def _leaf(draw, x, y, dx, dy, size, shade, specie):
    # Real tapered leaf: petiole -> broad middle -> sharp tip; odd numbers
    # of points rather than solid disks avoid the old lollipop silhouettes.
    l=math.hypot(dx,dy)
    if l<.0001:return
    ux,uy=dx/l,dy/l
    vx,vy=-uy,ux
    broad=size*(.20 if specie=='needle' else .36)
    farx=x+ux*size;fary=y+uy*size
    pts=[(x,y),
         (x+ux*size*.45+vx*broad,y+uy*size*.45+vy*broad),
         (farx,fary),
         (x+ux*size*.48-vx*broad*.81,y+uy*size*.48-vy*broad*.81)]
    draw.polygon(pts,fill=shade)
    draw.line(((x+ux*size*.12,y+uy*size*.12),(x+ux*size*.82,y+uy*size*.82)),
              fill=tuple(min(255,int(c*1.14)) for c in shade[:3])+(shade[3],),width=1)


def leaf_atlas(seed=1944):
    """Four authored leaf/shoot silhouettes in a 2x2, 16px padded atlas."""
    rand=random.Random(seed)
    scale=2
    canvas=Image.new('RGBA',(SIZE*scale,SIZE*scale))
    d=ImageDraw.Draw(canvas)
    tile=SIZE*scale//2
    themes=(
        ('leaf',((45,69,36),(79,100,51),(96,103,48),(113,108,58))),
        ('leaf',((59,71,32),(91,93,41),(127,115,52),(94,75,36))),
        ('needle',((28,58,39),(42,70,40),(58,83,47),(77,88,45))),
        ('leaf',((45,58,36),(69,78,44),(110,95,52),(81,66,44))),
    )
    for index,(specie,palette) in enumerate(themes):
        ox=(index%2)*tile; oy=(index//2)*tile
        cx=ox+tile*.5; cy=oy+tile*.70
        # A branch silhouette with visible stems. Each tile has gaps, not a
        # filled polygon or a square of green pixels.
        for stem in range(15 if specie=='needle' else 24):
            ang=(stem/(15 if specie=='needle' else 24)-.5)*math.pi*1.35+rand.uniform(-.21,.21)
            radius=rand.uniform(tile*.21,tile*.39)
            sx=cx+math.cos(ang)*radius*.30
            sy=cy-math.sin(ang)*radius*.17
            ex=cx+math.cos(ang)*radius
            ey=cy-math.sin(ang)*radius*.70-tile*.10
            bend=(sx+ex)*.5+rand.uniform(-tile*.04,tile*.04)
            by=(sy+ey)*.5
            d.line(((cx,cy),(sx,sy),(bend,by),(ex,ey)),
                   fill=(53,46,29,240) if specie!='needle' else (42,43,30,245),
                   width=rand.randint(2,4)*scale)
            leaf_count=22 if specie=='needle' else 10
            for n in range(leaf_count):
                f=(n+.6)/leaf_count
                px=sx+(ex-sx)*f+rand.uniform(-4,4)*scale
                py=sy+(ey-sy)*f+rand.uniform(-4,4)*scale
                side=(-1 if n%2 else 1)
                dx=math.cos(ang+side*.75);dy=-math.sin(ang+side*.75)
                sz=rand.uniform(7,15)*scale if specie=='needle' else rand.uniform(16,32)*scale
                color=rand.choice(palette)
                rgba=(color[0]+rand.randrange(-5,6),color[1]+rand.randrange(-5,6),
                      color[2]+rand.randrange(-5,6),255)
                _leaf(d,px,py,dx,dy,sz,rgba,specie)
        # Individual stray leaves break symmetry and rectangular edges.
        if specie!='needle':
            for _ in range(35):
                px=cx+rand.uniform(-.37,.37)*tile
                py=cy+rand.uniform(-.52,.10)*tile
                if px<ox+tile*.07 or px>ox+tile*.93 or py<oy+tile*.07 or py>oy+tile*.93:continue
                c=rand.choice(palette)
                _leaf(d,px,py,rand.uniform(-1,1),rand.uniform(-1.3,-.1),
                      rand.uniform(14,27)*scale,(*c,255),'leaf')
    # Controlled downsampling creates stable alpha-cutout edges under mipmaps.
    return canvas.resize((SIZE,SIZE),PIL_RESAMPLING.LANCZOS)


def generate(folder:Path|str):
    out=Path(folder);out.mkdir(parents=True,exist_ok=True)
    for name,seed,warm in [('pine_bark',31415,False),('willow_bark',27182,True)]:
        image,normal=bark(seed,warm)
        image.save(out/(name+'.png'),optimize=True)
        normal.save(out/(name+'_nor_gl.png'),optimize=True)
    leaf_atlas().save(out/'foliage_cards.png',optimize=True)
    return out


if __name__=='__main__':
    print('Wrote',generate(Path(__file__).resolve().parent/'assets'/'trees'))
