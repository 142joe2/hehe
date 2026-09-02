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
    if 'src=' in attrs_lower or 'type="application/json"' in attrs_lower or 'type=\'application/json\'' in attrs_lower:
        print('block', idx, 'skipped', attrs.strip())
        continue
    cleaned = re.sub(r'\{%.*?%\}', '""', chunk, flags=re.S)
    cleaned = re.sub(r'\{\{.*?\}\}', '""', cleaned, flags=re.S)
    if not cleaned.strip():
        print('block', idx, 'empty after cleanup')
        continue
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
