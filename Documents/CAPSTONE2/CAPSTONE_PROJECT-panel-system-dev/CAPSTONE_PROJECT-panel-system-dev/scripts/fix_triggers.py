"""Remove hx-trigger="load" from all tabs except dashboard-overview."""
import re

path = r'templates/website/Treasurer/treasurer_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Match ANY div with hx-get="/hx/treasurer/module/..." and hx-trigger="load"
# regardless of attribute order
def fix_trigger(m):
    full = m.group(0)
    if 'dashboard-overview' in full:
        return full  # keep overview as-is
    # Remove hx-trigger="load" and hx-swap="innerHTML"
    full = re.sub(r'\s+hx-trigger="[^"]*"', '', full)
    full = re.sub(r'\s+hx-swap="[^"]*"', '', full)
    return full

content = re.sub(
    r'<div[^>]*hx-get="/hx/treasurer/module/[^/]*/"[^>]*hx-trigger="[^"]*"[^>]*>',
    fix_trigger,
    content
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
