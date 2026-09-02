"""Strip the outer <section> wrapper from HTMX partial templates."""
import re
from pathlib import Path

partial_dir = Path("templates/htmx/treasurer")

for f in sorted(partial_dir.glob("*.html")):
    content = f.read_text(encoding="utf-8").strip()

    # Remove outer <section ...> tag and closing </section>
    # Match: optional whitespace + <section ...> ... </section>
    m = re.match(
        r'<section\b[^>]*>\s*(.*?)\s*</section>\s*$',
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        inner = m.group(1).strip()
        f.write_text(inner, encoding="utf-8")
        print(f"  Stripped: {f.name} ({len(content)} -> {len(inner)} chars)")
    else:
        # Try without closing </section> (multi-line attribute case)
        m2 = re.match(
            r'<section\b[^>]*>(.*)',
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if m2 and content.rstrip().endswith("</section>"):
            # The regex didn't match due to newlines in tag attrs
            # Use a simpler approach: find first > after <section, then last </section>
            start = content.index(">") + 1
            end = content.rindex("</section>")
            inner = content[start:end].strip()
            f.write_text(inner, encoding="utf-8")
            print(f"  Stripped (alt): {f.name} ({len(content)} -> {len(inner)} chars)")
        else:
            print(f"  SKIPPED (no section wrapper): {f.name}")

print("\nDone.")
