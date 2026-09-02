with open('templates/website/Treasurer/treasurer_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Find the big inline script block (no src=, has our functions)
in_script = False
script_start = None
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('<script') and 'src=' not in line.lower() and 'src=' not in stripped.lower():
        in_script = True
        script_start = i
    elif in_script and '</script>' in stripped:
        script_end = i
        content = ''.join(lines[script_start:i+1])
        if 'fetchFinancialPendingCounts' in content:
            print(f"Big script block: lines {script_start+1} to {script_end+1}")
            # Track brace depth through this block
            depth = 0
            for j in range(script_start, script_end + 1):
                line_text = lines[j]
                for c in line_text:
                    if c == '{': depth += 1
                    elif c == '}': depth -= 1
                if depth < 0:
                    print(f"  Line {j+1}: NEGATIVE depth ({depth}) | {line_text.rstrip()[:100]}")
                    depth = 0
            print(f"  Final brace depth: {depth}")
            if depth != 0:
                # Find where unclosed blocks are - scan backwards
                print("  Scanning backwards for unclosed braces...")
                depth = 0
                for j in range(script_end, script_start - 1, -1):
                    line_text = lines[j]
                    for c in reversed(line_text):
                        if c == '}': depth += 1
                        elif c == '{': depth -= 1
                    if depth > 0 and depth <= 2:
                        print(f"  Line {j+1}: backward depth {depth} | {line_text.rstrip()[:100]}")
        in_script = False