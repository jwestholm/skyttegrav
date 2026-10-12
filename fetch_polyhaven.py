"""Download a small, optional CC0 Poly Haven material set for Skyttegrav.

Powered by Poly Haven: https://polyhaven.com/ . Uses the official public API.
Run once: python3 fetch_polyhaven.py
The game runs without these assets, falling back to local textures.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from PIL import Image
from io import BytesIO

OUT = Path(__file__).resolve().parent / 'assets' / 'polyhaven'
ASSETS = ('brown_mud', 'brown_mud_02', 'mud_forest', 'roots')
API = 'https://api.polyhaven.com/files/'

def variants(node, path=()):
    if isinstance(node,dict):
        if isinstance(node.get('url'),str):
            yield path,node
        else:
            for k,v in node.items():
                yield from variants(v,path+(str(k),))

def choose(tree,normal):
    found=[]
    for path,record in variants(tree):
        url=record['url']; low='/'.join(path).lower()+' '+url.lower()
        if not url.lower().split('?')[0].endswith(('.jpg','.jpeg','.png','.webp')):
            continue
        if normal:
            if not ('nor_gl' in low or 'normal_gl' in low or 'normal' in low and 'dx' not in low):continue
        else:
            if not ('diff' in low or 'color' in low or 'albedo' in low):continue
        # Prefer 1K/2K rasters, avoid huge 8K maps for our 512px prototype.
        res=0 if '1k' in low else 1 if '2k' in low else 10
        fmt=0 if url.lower().split('?')[0].endswith('.png') else 1
        gl=0 if 'nor_gl' in low or not normal else 1
        found.append(((res,gl,fmt,len(url)),url))
    return min(found)[1] if found else None

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest={}
    for asset in ASSETS:
        print(f'{asset}: querying Poly Haven...')
        try:
            with urlopen(API+asset,timeout=20) as response:
                tree=json.load(response)
            manifest[asset]={}
            for key,normal in [('diff',False),('nor_gl',True)]:
                url=choose(tree,normal)
                if not url:
                    print('  missing map:',key)
                    continue
                with urlopen(url,timeout=45) as response:
                    raw=response.read()
                with Image.open(BytesIO(raw)) as img:
                    target=OUT/f'{asset}_{key}.png'
                    img.convert('RGB').resize((512,512),Image.Resampling.LANCZOS if hasattr(Image,'Resampling') else Image.LANCZOS).save(target)
                manifest[asset][key]={'source_url':url,'file':target.name,'license':'CC0'}
                print('  saved',target)
        except (URLError,OSError,ValueError,KeyError) as exc:
            print('  WARNING: Download skipped:',exc)
    (OUT/'SOURCES.json').write_text(json.dumps({'provider':'https://polyhaven.com/','license':'CC0','assets':manifest},indent=2)+'\n')
    print('Done. Restart the game to use installed materials.')

if __name__=='__main__':main()
