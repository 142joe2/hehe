with open('templates/website/Treasurer/treasurer_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the big script block
script_start = None
script_end = None
for i in range(len(lines)):
    if '<script' in lines[i].lower() and 'src=' not in lines[i].lower():
        if not script_start:
            script_start = i
        else:
            # Already found start, now find end
            pass
    if script_start is not None and '</script>' in lines[i].lower() and i > script_start:
        script_end = i
        break

print(f"Script: lines {script_start+1} to {script_end+1}")

# Track depth and find where it goes wrong
depth = 0
for i in range(script_start, script_end + 1):
    line = lines[i]
    line_depth = depth
    for c in line:
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
    if depth < 0:
        print(f"Line {i+1}: depth went negative ({depth}) | {line.rstrip()[:120]}")
        depth = 0  # reset to find next issue

print(f"Final depth: {depth}")

# Now find where depth ends up at 2 - scan backwards from end
print("\n=== Scanning from end to find unclosed blocks ===")
depth = 0
for i in range(script_end, script_start - 1, -1):
    line = lines[i]
    for c in reversed(line):
        if c == '}':
            depth += 1
        elif c == '{':
            depth -= 1
    if depth > 0:
        print(f"Line {i+1}: backward depth = {depth} | {line.rstrip()[:120]}")
    if depth >= 2:  # We need to find 2 unclosed
        pass