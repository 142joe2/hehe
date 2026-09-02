from pathlib import Path
import re
import subprocess
import tempfile
import os

html_path = Path(r'c:\Users\USER\Downloads\CAPSTONE_PROJECT-panel-system-dev\CAPSTONE_PROJECT-panel-system-dev\templates\website\Treasurer\treasurer_dashboard.html')
html = html_path.read_text(encoding='utf-8')

script_blocks = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.S | re.I)
print('script blocks:', len(script_blocks))

for idx, chunk in enumerate(script_blocks, 1):
    cleaned = re.sub(r'\{%.*?%\}', ' ', chunk, flags=re.S)
    cleaned = re.sub(r'\{\{.*?\}\}', 'null', cleaned, flags=re.S)
    if not cleaned.strip():
        print('block', idx, 'empty')
        continue
    fd, path = tempfile.mkstemp(suffix='.js')
    os.close(fd)
    Path(path).write_text(cleaned, encoding='utf-8')
    try:
        result = subprocess.run(['node', '--check', path], capture_output=True, text=True)
        if result.returncode != 0:
            print('FAILED BLOCK', idx)
            print(result.stderr.strip() or result.stdout.strip())
            print('--- chunk tail ---')
            lines = cleaned.splitlines()
            start = max(0, len(lines) - 60)
            for i in range(start, len(lines)):
                print(f'{i+1}: {lines[i]}')
            break
    finally:
        os.unlink(path)
else:
    print('all inline blocks parse successfully')
