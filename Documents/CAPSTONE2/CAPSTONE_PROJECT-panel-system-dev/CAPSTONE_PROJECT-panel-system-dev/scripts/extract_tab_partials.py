"""
Extract each dashboard-module section into its own partial template
for HTMX lazy-loading. Run from the project root.
"""
import re
import os
from pathlib import Path

TEMPLATE_DIR = Path("templates/website/Treasurer")
TEMPLATE_FILE = TEMPLATE_DIR / "treasurer_dashboard.html"
PARTIAL_DIR = Path("templates/htmx/treasurer")
PARTIAL_DIR.mkdir(parents=True, exist_ok=True)

content = TEMPLATE_FILE.read_text(encoding="utf-8")

# Find all dashboard-module sections
# Pattern: <section id="..." class="dashboard-module ..."> ... </section>
# We need to track depth to handle nested sections correctly

sections = []
stack = []
i = 0
section_start = None
section_id = None
depth = 0

while i < len(content):
    # Check for section open tag
    m = re.match(r'<section\s+([^>]*?)>', content[i:], re.IGNORECASE | re.DOTALL)
    if m:
        attrs = m.group(1)
        if 'dashboard-module' in attrs:
            id_m = re.search(r'id=["\']([^"\']+)["\']', attrs)
            if id_m and section_start is None:
                section_start = i
                section_id = id_m.group(1)
                depth = 1
                i += m.end()
                continue
        # Any section increases depth if we're inside a dashboard-module
        if section_start is not None:
            depth += 1
        i += m.end()
        continue

    # Check for section close tag
    m = re.match(r'</section\s*>', content[i:], re.IGNORECASE)
    if m:
        if section_start is not None:
            depth -= 1
            if depth == 0:
                # End of dashboard-module section
                section_content = content[section_start:i + m.end()]
                sections.append({
                    'id': section_id,
                    'content': section_content,
                    'start': section_start,
                    'end': i + m.end(),
                })
                section_start = None
                section_id = None
        i += m.end()
        continue

    i += 1

print(f"Found {len(sections)} dashboard-module sections:")
total_extracted = 0
total_original = len(content)

# Process in reverse order so positions don't shift
sections.reverse()

for sec in sections:
    sid = sec['id']
    print(f"  {sid}: {len(sec['content'])} chars (pos {sec['start']}-{sec['end']})")

    # Determine if this is the default active section
    is_active = 'active' in sec['content'].split('\n')[0] if sec['content'] else False

    # Write partial template
    partial_path = PARTIAL_DIR / f"{sid}.html"
    partial_path.write_text(sec['content'].strip(), encoding="utf-8")
    print(f"    -> wrote {partial_path}")
    total_extracted += len(sec['content'])

    # Replace section with placeholder
    placeholder = f'<div id="{sid}" class="dashboard-module module-fade-in{" active" if is_active else ""}" hx-get="/hx/treasurer/module/{sid}/" hx-trigger="load" hx-swap="innerHTML"></div>'
    content = content[:sec['start']] + placeholder + content[sec['end']:]

TEMPLATE_FILE.write_text(content, encoding="utf-8")
print(f"\nDone. Extracted {total_extracted} chars, template now {len(content)} chars")
print(f"Template reduced by {(1 - len(content)/total_original)*100:.1f}%")
