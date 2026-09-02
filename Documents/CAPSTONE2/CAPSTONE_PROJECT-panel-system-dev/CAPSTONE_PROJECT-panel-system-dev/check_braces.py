with open('templates/website/Treasurer/treasurer_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the second <script> tag (the big one with all the JS)
script_start = None
script_num = 0
for i, line in enumerate(lines):
    if '<script' in line:
        script_num += 1
        if script_num == 2:
            script_start = i
            break

if script_start is None:
    print("Script 2 not found")
    exit()

print(f"Script 2 starts at line {script_start+1}")

# Track brace balance from script start
depth = 0
for i in range(script_start, len(lines)):
    line = lines[i]
    for c in line:
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
    if depth < 0:
        print(f"Line {i+1}: NEGATIVE depth {depth} - EXTRA '}}'! || {lines[i].rstrip()}")
        # Show surrounding context
        for j in range(max(script_start, i-3), min(len(lines), i+5)):
            marker = " >>> " if j == i else "      "
            print(f"{marker}Line {j+1}: {lines[j].rstrip()}")
        break

if depth >= 0:
    print(f"Final depth: {depth} (balanced or still open)")