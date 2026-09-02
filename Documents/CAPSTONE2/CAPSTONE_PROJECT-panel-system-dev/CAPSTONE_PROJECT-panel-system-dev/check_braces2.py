with open('templates/website/Treasurer/treasurer_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the second <script> tag
script_start = None
script_num = 0
for i, line in enumerate(lines):
    if '<script' in line.lower():
        script_num += 1
        if script_num == 2:
            script_start = i
            break

if script_start is None:
    print("Script 2 not found")
    exit()

# Find </script> for script 2
script_end = None
for i in range(script_start + 1, len(lines)):
    if '</script>' in lines[i].lower():
        script_end = i
        break

if script_end is None:
    print("No </script> found for script 2!")
    exit()

print(f"Script 2: line {script_start+1} to {script_end+1} ({script_end - script_start + 1} lines)")

# Track brace depth
depth = 0
last_significant_depth = 0
for i in range(script_start, script_end + 1):
    line = lines[i]
    for c in line:
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1

print(f"Final brace depth: {depth}")
if depth > 0:
    print("Script ends with unclosed braces!")
    print(f"Need {depth} more '}}' to close")
elif depth < 0:
    print(f"Script has {abs(depth)} extra '}}'")
else:
    print("Script is balanced.")

# Now check: the error was "Uncaught SyntaxError: Unexpected token '}' at line 5832:7"
# Browser line numbers differ from file line numbers due to Turbo/HTML.
# But let's find potential orphaned braces by looking for places where depth drops too fast.