"""Deterministic low-budget soldier material fallback (no downloaded licensed assets).

Draws a camo-like cloth, dark webbing, and neutral skin. Not a photographic
or historically exact uniform; replaceable when a licensed rigged GLB arrives.
"""
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parent/'assets'/'enemies'
ROOT.mkdir(parents=True,exist_ok=True)
S=512

def cloth(name,colors,seed,patches,scale):
    rng=random.Random(seed)
    im=Image.new('RGB',(S,S),colors[0]); dr=ImageDraw.Draw(im)
    for _ in range(patches):
        x=rng.randrange(-40,S+40); y=rng.randrange(-40,S+40)
        r=rng.randint(scale[0],scale[1]); ry=int(r*rng.uniform(.45,1.5))
        color=colors[rng.randrange(len(colors))]
        poly=[(x+rng.randrange(-r,r),y+rng.randrange(-ry,ry)) for i in range(9)]
        dr.polygon(poly,fill=color)
    # Fabric grain & tiny dirt marks.
    for _ in range(19000):
        x=rng.randrange(S);y=rng.randrange(S)
        base=im.getpixel((x,y)); shade=rng.randrange(-28,16)
        dr.point((x,y),fill=tuple(max(0,min(255,c+shade)) for c in base))
    return im.filter(ImageFilter.GaussianBlur(.40))

cloth('uniform',[(63,70,55),(78,81,64),(91,83,68),(45,53,45),(103,101,81),(63,63,53)],
      1944,1750,(4,24)).save(ROOT/'uniform.png',optimize=True)
cloth('webbing',[(55,60,48),(65,68,54),(79,73,59),(40,43,38),(85,80,62)],
      1945,570,(5,22)).save(ROOT/'webbing.png',optimize=True)
cloth('skin',[(156,119,97),(170,131,107),(144,103,84),(184,144,118)],
      1946,420,(3,20)).save(ROOT/'skin.png',optimize=True)
print('Created 3 skin/uniform fallback texture layers in',ROOT)
