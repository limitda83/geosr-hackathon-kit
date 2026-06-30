#!/usr/bin/env python3
"""Inject image binaries from a reference HWPX into a built HWPX.

Usage:
    python3 inject_images.py --hwpx result.hwpx --reference reference.hwpx \
        --images image1,image2

    # Or auto-detect: copy ALL BinData/* from reference into result
    python3 inject_images.py --hwpx result.hwpx --reference reference.hwpx --all
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path


def get_media_type(filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower()
    return {
        'jpg': 'image/jpg', 'jpeg': 'image/jpg',
        'png': 'image/png', 'gif': 'image/gif',
        'bmp': 'image/bmp', 'tif': 'image/tiff', 'tiff': 'image/tiff',
        'svg': 'image/svg+xml',
    }.get(ext, 'application/octet-stream')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hwpx', required=True)
    ap.add_argument('--reference', required=True)
    ap.add_argument('--images', help='Comma-separated image IDs (e.g. image1,image2)')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    hwpx = Path(args.hwpx).resolve()
    ref  = Path(args.reference).resolve()

    if not hwpx.is_file():
        print(f'ERROR: {hwpx} not found', file=sys.stderr); return 2
    if not ref.is_file():
        print(f'ERROR: {ref} not found', file=sys.stderr); return 2
    if not args.images and not args.all:
        print('ERROR: specify --images or --all', file=sys.stderr); return 2

    # ── 레퍼런스에서 대상 이미지 추출 ──────────────────────
    ref_bindata = {}
    with zipfile.ZipFile(ref, 'r') as zref:
        for name in zref.namelist():
            if name.startswith('BinData/') and name != 'BinData/':
                stem = Path(name).stem
                ref_bindata[stem] = (name, zref.read(name))

    if args.all:
        targets = dict(ref_bindata)
    else:
        wanted = [s.strip() for s in args.images.split(',') if s.strip()]
        targets = {}
        for w in wanted:
            if w in ref_bindata:
                targets[w] = ref_bindata[w]
            else:
                print(f'WARN: {w} not found in reference BinData/', file=sys.stderr)

    if not targets:
        print('ERROR: no images selected', file=sys.stderr); return 1

    # ── 직접 zip-to-zip 복사 (임시 파일 거치지 않음) ─────────
    tmp = hwpx.with_suffix('.injtmp.hwpx')

    with zipfile.ZipFile(hwpx, 'r') as zin, \
         zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:

        # mimetype 첫 번째, ZIP_STORED
        zout.writestr(zipfile.ZipInfo('mimetype'),
                      zin.read('mimetype'),
                      compress_type=zipfile.ZIP_STORED)

        # 기존 파일 모두 복사
        existing_bindata = set()
        for item in zin.infolist():
            if item.filename == 'mimetype':
                continue
            data = zin.read(item.filename)

            if item.filename == 'Contents/content.hpf':
                # manifest 업데이트
                text = data.decode('utf-8')
                entries = ''
                for stem, (refname, imgdata) in targets.items():
                    fname = Path(refname).name
                    mtype = get_media_type(fname)
                    if stem not in text:
                        entries += (f'<opf:item id="{stem}" href="BinData/{fname}"'
                                    f' media-type="{mtype}" isEmbeded="1"/>')
                if entries:
                    text = re.sub(r'(</opf:manifest)', entries + r'\1', text)
                data = text.encode('utf-8')

            if item.filename.startswith('BinData/'):
                existing_bindata.add(Path(item.filename).stem)

            zout.writestr(item.filename, data)

        # 새 이미지 추가
        for stem, (refname, imgdata) in targets.items():
            fname = Path(refname).name
            arc_name = f'BinData/{fname}'
            if stem not in existing_bindata:
                zout.writestr(arc_name, imgdata)
                print(f'  + {arc_name} ({len(imgdata):,} bytes)')
            else:
                print(f'  (skip {arc_name}, already exists)')

    tmp.replace(hwpx)
    print(f'\nINJECTED {len(targets)} image(s) into {hwpx}')
    print(f'  size: {hwpx.stat().st_size:,} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
