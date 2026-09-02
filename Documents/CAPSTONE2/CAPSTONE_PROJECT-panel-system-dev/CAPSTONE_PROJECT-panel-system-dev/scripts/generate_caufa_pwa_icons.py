from pathlib import Path
from PIL import Image, ImageOps

root = Path(__file__).resolve().parent.parent
src = root / 'static' / 'img' / 'isu_caufa_official.png'
if not src.exists():
    raise FileNotFoundError(f'Missing source icon: {src}')

with Image.open(src) as im:
    for size in (180, 192, 512):
        thumb = ImageOps.contain(im, (size, size))
        out = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        out.paste(thumb, ((size - thumb.width) // 2, (size - thumb.height) // 2), thumb if thumb.mode in ('RGBA', 'LA') else None)
        target = root / 'static' / 'img' / f'isu_caufa_official_{size}.png'
        out.save(target)
        print('wrote', target, 'size', target.stat().st_size)
