from pathlib import Path
import re
import subprocess
import tempfile
import os

html_path = Path(r'c:\Users\USER\Downloads\CAPSTONE_PROJECT-panel-system-dev\CAPSTONE_PROJECT-panel-system-dev\templates\website\Treasurer\treasurer_dashboard.html')
html = html_path.read_text(encoding='utf-8')
blocks = re.findall(r'<script\b([^>]*)>(.*?)</script>', html, re.S | re.I)
print('script tags:', len(blocks))

for idx, (attrs, chunk) in enumerate(blocks, 1):
    if not chunk.strip():
        print('block', idx, 'empty')
        continue
    attrs_lower = attrs.lower()
    if 'src=' in attrs_lower or 'type="application/json"' in attrs_lower or "type='application/json'" in attrs_lower:
        print('block', idx, 'skipped', attrs.strip())
        continue

    # Remove Django template tags only when they appear outside JS strings.
    out = []
    i = 0
    quote = None
    escape = False
    while i < len(chunk):
        ch = chunk[i]
        if quote:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue

        if ch in ('"', "'", '`'):
            quote = ch
            out.append(ch)
            i += 1
            continue

        if chunk.startswith('{%', i):
            j = chunk.find('%}', i + 2)
            if j != -1:
                out.append('""')
                i = j + 2
                continue
        if chunk.startswith('{{', i):
            j = chunk.find('}}', i + 2)
            if j != -1:
                out.append('""')
                i = j + 2
                continue
        out.append(ch)
        i += 1

    cleaned = ''.join(out)
    fd, path = tempfile.mkstemp(suffix='.js')
    os.close(fd)
    Path(path).write_text(cleaned, encoding='utf-8')
    try:
        result = subprocess.run(['node', '--check', path], capture_output=True, text=True)
        if result.returncode != 0:
            print('FAILED BLOCK', idx, attrs.strip())
            print(result.stderr.strip() or result.stdout.strip())
            print('--- chunk start ---')
            print(chunk[:1800])
            print('--- chunk tail ---')
            lines = cleaned.splitlines()
            start = max(0, len(lines) - 40)
            for i in range(start, len(lines)):
                print(f'{i+1}: {lines[i]}')
            break
    finally:
        os.unlink(path)
else:
    print('all inline application scripts parse successfully')
