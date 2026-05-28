import re

with open("scratch/latest_wp_post_content.html", "r") as f:
    html = f.read()

print(f"Total Post HTML length: {len(html)}")

# Find all occurrences of <!-- and -->
comments = []
for m in re.finditer(r'<!--|-->', html):
    comments.append((m.group(0), m.start()))

print(f"Total comment markers found: {len(comments)}")

# Trace open/close
open_stack = []
unbalanced = []

for marker, pos in comments:
    if marker == "<!--":
        open_stack.append(pos)
    else:
        if open_stack:
            open_stack.pop()
        else:
            unbalanced.append(("extra close", pos))

for pos in open_stack:
    unbalanced.append(("unclosed open", pos))

print(f"Unbalanced comments: {len(unbalanced)}")
for k, (type_, pos) in enumerate(unbalanced[:20]):
    snippet = html[max(0, pos-100):min(len(html), pos+100)]
    print(f"{k+1}: {type_} at position {pos}")
    print(f"Context: {repr(snippet)}")
    print("-" * 50)
