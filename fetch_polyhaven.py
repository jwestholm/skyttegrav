"""Fetch optional CC0 Poly Haven earth materials for the Skyttegrav prototype.

Run: python3 fetch_polyhaven.py
     python3 fetch_polyhaven.py --check      # local files, no network
     python3 fetch_polyhaven.py --doctor     # network/API check
     python3 fetch_polyhaven.py --force      # redownload even existing maps

The 3D game never downloads assets itself, and works offline with built-in textures.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, UnidentifiedImageError

BASE = Path(__file__).resolve().parent
OUT = BASE / 'assets' / 'polyhaven'
API = 'https://api.polyhaven.com/files/'
ASSETS = ('brown_mud', 'brown_mud_02', 'mud_forest', 'roots')
MAPS = ('diff', 'nor_gl')
USER_AGENT = 'Skyttegrav-Material-Downloader/2.5.1 (+https://polyhaven.com/)'


def open_url(url, timeout=25):
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def walk_records(node, path=()):
    """Yield (tree path, file record), ignoring non-file metadata and dependencies."""
    if isinstance(node, dict):
        if isinstance(node.get('url'), str) and node['url'].startswith(('https://', 'http://')):
            yield path, node
        else:
            for key, value in node.items():
                yield from walk_records(value, path + (str(key),))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk_records(value, path + (str(index),))


def choose(tree, map_type):
    """Pick a 1K (or 2K) image matching one exact Poly Haven map type."""
    candidates = []
    for path, record in walk_records(tree):
        url = record['url']
        lower_url = url.lower().split('?', 1)[0]
        suffix = Path(lower_url).suffix
        if suffix not in ('.png', '.jpg', '.jpeg', '.webp'):
            continue
        search = '/'.join(path).lower() + '/' + Path(lower_url).name
        if not re.search(r'(?:^|[_/])' + re.escape(map_type) + r'(?:[_/.]|$)', search):
            continue
        if map_type == 'nor_gl' and 'nor_dx' in search:
            continue
        resolution = 0 if re.search(r'(?:^|[_/])1k(?:[_/.]|$)', search) else 1 if re.search(r'(?:^|[_/])2k(?:[_/.]|$)', search) else 3
        fmt_rank = {'.png': 0, '.jpg': 1, '.jpeg': 1, '.webp': 2}[suffix]
        candidates.append(((resolution, fmt_rank, len(url)), url))
    return min(candidates)[1] if candidates else None


def check_local():
    success = True
    for asset in ASSETS:
        for kind in MAPS:
            path = OUT / f'{asset}_{kind}.png'
            exists = path.is_file() and path.stat().st_size > 0
            print(f'{"OK     " if exists else "MISSING"} {path.relative_to(BASE)}')
            success &= exists
    if not success:
        print('\nIngen automatisk nedladdning sker när spelet startas.')
        print('Kör: python3 fetch_polyhaven.py')
    return success


def doctor():
    print('Poly Haven API diagnostic (makes one network request):')
    host = 'api.polyhaven.com'
    try:
        addresses = sorted({result[4][0] for result in socket.getaddrinfo(host, 443)})
        print('DNS OK:', ', '.join(addresses[:4]))
    except OSError as exc:
        print('DNS FAILED:', exc)
        return False
    try:
        raw = open_url(API + ASSETS[0])
        tree = json.loads(raw)
        print('API OK:', len(raw), 'bytes of file metadata')
        for kind in MAPS:
            found = choose(tree, kind)
            print(kind, 'OK' if found else 'MISSING IN API RESPONSE', found or '')
        return True
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        print(f'API FAILED: {type(exc).__name__}: {exc}')
        print('Testa även: curl -IL https://api.polyhaven.com/files/brown_mud')
        return False


def fetch_all(force=False):
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {'provider': 'https://polyhaven.com/', 'license': 'CC0', 'assets': {}}
    succeeded = 0
    failed = 0
    for asset in ASSETS:
        targets = {key: OUT / f'{asset}_{key}.png' for key in MAPS}
        needed = [kind for kind in MAPS if force or not targets[kind].is_file()]
        if not needed:
            print(f'{asset}: both maps already present (use --force to replace)')
            succeeded += len(MAPS)
            continue
        print(f'{asset}: reading {API + asset}', flush=True)
        try:
            tree = json.loads(open_url(API + asset))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            print(f'  API ERROR ({type(exc).__name__}): {exc}')
            failed += len(needed)
            continue
        manifest['assets'][asset] = {}
        for kind in MAPS:
            if kind not in needed:
                succeeded += 1
                continue
            url = choose(tree, kind)
            if not url:
                print(f'  {kind}: no matching 1K/2K PNG/JPEG in API result')
                failed += 1
                continue
            print(f'  {kind}: downloading {url}', flush=True)
            try:
                raw = open_url(url, timeout=60)
                with Image.open(BytesIO(raw)) as im:
                    im.load()
                    converted = im.convert('RGB').resize((512, 512),
                        Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
                    # Atomic replacement: no half-written image if download/process fails.
                    temp_path = targets[kind].with_suffix('.tmp.png')
                    converted.save(temp_path, format='PNG')
                    temp_path.replace(targets[kind])
                print(f'  SAVED: {targets[kind]}')
                succeeded += 1
                manifest['assets'][asset][kind] = {'source_url': url, 'file': targets[kind].name}
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnidentifiedImageError) as exc:
                print(f'  DOWNLOAD ERROR ({type(exc).__name__}): {exc}')
                failed += 1
    (OUT / 'SOURCES.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Finished: {succeeded} available maps, {failed} errors.')
    if failed:
        print('Run: python3 fetch_polyhaven.py --doctor')
        print('You can also download individual maps manually from polyhaven.com')
        print('and save them as: assets/polyhaven/<asset>_diff.png or <asset>_nor_gl.png')
    print('Restart trench_3d_test.py to load any available maps.')
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true', help='show installed maps (offline)')
    group.add_argument('--doctor', action='store_true', help='check DNS and official API')
    group.add_argument('--force', action='store_true', help='redownload maps')
    args = parser.parse_args()
    ok = check_local() if args.check else doctor() if args.doctor else fetch_all(args.force)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
