from pathlib import Path
import re
text = Path(r'c:\Users\USER\Downloads\CAPSTONE_PROJECT-panel-system-dev\CAPSTONE_PROJECT-panel-system-dev\templates\website\Treasurer\treasurer_dashboard.html').read_text(encoding='utf-8')
for i, m in enumerate(re.finditer(r'<script([^>]*)>(.*?)</script>', text, re.S | re.I), 1):
    attrs = m.group(1)
    body = m.group(2)
    if not body.strip():
        continue
    print(i, 'attrs=', attrs.strip(), 'body-start=', body.strip()[:160].replace('\n', ' '))
