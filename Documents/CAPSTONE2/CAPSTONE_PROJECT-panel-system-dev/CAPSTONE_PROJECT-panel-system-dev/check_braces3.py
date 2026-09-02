with open('templates/website/Treasurer/treasurer_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all <script> blocks and find the one containing our functions
print("=== SCRIPT BLOCKS ===")
in_script = False
script_lines = []
for i, line in enumerate(lines):
    if '<script' in line.lower() and 'src=' not in line.lower():
        in_script = True
        script_lines = [(i, line)]
    elif in_script:
        script_lines.append((i, line))
        if '</script>' in line.lower():
            in_script = False
            # Check if this block has our function
            content = ''.join(l for _, l in script_lines)
            if 'fetchFinancialPendingCounts' in content:
                print(f"\nFound big script block starting at line {script_lines[0][0]+1}, ending at {script_lines[-1][0]+1}")
                # Track brace depth
                depth = 0
                for j, l in script_lines:
                    for c in l:
                        if c == '{': depth += 1
                        elif c == '}': depth -= 1
                    if depth < 0:
                        print(f"  Line {j+1}: NEGATIVE DEPTH {depth}! | {l.rstrip()[:100]}")
                print(f"  Final brace depth: {depth}")
                if depth != 0:
                    print("  *** UNBALANCED BRACES ***")
            script_lines = []

if in_script:
    print("WARNING: Ended while still in script tag!")