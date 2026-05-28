import json
import re

with open("tmp_body.json", "r") as f:
    html = json.load(f)

# Find where the first article starts and ends
article_start = html.find("<article")
if article_start == -1:
    print("No article tag found")
    exit(1)

# Let's extract the first article block by counting nested tags or just finding </article>
# Wait, let's find the first </article> tag
article_end = html.find("</article>", article_start)
if article_end == -1:
    print("No closing article tag found")
    exit(1)

article_html = html[article_start : article_end + len("</article>")]
print(f"First Article HTML length: {len(article_html)}")

# Find all tags in this article
tags = re.findall(r'<(/?[a-zA-Z0-9]+)\b[^>]*>', article_html)

# Trace tags balance
tag_stack = []
unbalanced = []

void_tags = {"img", "br", "hr", "input", "meta", "link", "col", "source", "embed", "param", "track", "wbr"}

for tag in tags:
    tag_name = tag.lower()
    if tag_name in void_tags:
        continue
    if tag_name.startswith("/"):
        # Closing tag
        opening_name = tag_name[1:]
        if tag_stack and tag_stack[-1] == opening_name:
            tag_stack.pop()
        else:
            unbalanced.append((f"Close tag </{opening_name}> without match", len(tag_stack)))
    else:
        # Opening tag
        tag_stack.append(tag_name)

print(f"Stack at end: {tag_stack}")
print(f"Unbalanced actions: {unbalanced}")

with open("scratch/first_article_body.html", "w") as f:
    f.write(article_html)
print("Saved first article HTML to scratch/first_article_body.html")
