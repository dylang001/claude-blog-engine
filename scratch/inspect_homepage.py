import json
import re
from html.parser import HTMLParser

with open("tmp_body.json", "r") as f:
    html = json.load(f)

print(f"Total Page HTML length: {len(html)}")

# Basic stats via regex
print("\nElement counts via regex:")
print("Articles:", len(re.findall(r'<article\b', html, re.I)))
print("Unordered lists (ul):", len(re.findall(r'<ul\b', html, re.I)))
print("Ordered lists (ol):", len(re.findall(r'<ol\b', html, re.I)))
print("List items (li):", len(re.findall(r'<li\b', html, re.I)))
print("Images (img):", len(re.findall(r'<img\b', html, re.I)))
print("Paragraphs (p):", len(re.findall(r'<p\b', html, re.I)))
print("Sidebars/Asides:", len(re.findall(r'<aside\b', html, re.I)))
print("Footers:", len(re.findall(r'<footer\b', html, re.I)))

# Let's search for the titles in <article> blocks
article_blocks = re.findall(r'<article\b.*?</article>', html, re.DOTALL | re.IGNORECASE)
if article_blocks:
    print(f"\nFound {len(article_blocks)} articles:")
    for idx, block in enumerate(article_blocks):
        titles = re.findall(r'<h[1-6]\b[^>]*>(.*?)</h[1-6]>', block, re.DOTALL | re.IGNORECASE)
        clean_titles = [re.sub(r'<[^>]+>', '', t).strip() for t in titles]
        print(f"{idx+1}: Titles: {clean_titles}")
else:
    print("\nNo article tags found!")

# Find any headings at all on the page
headings = re.findall(r'<h[1-6]\b[^>]*>(.*?)</h[1-6]>', html, re.DOTALL | re.IGNORECASE)
clean_headings = [re.sub(r'<[^>]+>', '', h).strip() for h in headings]
print("\nFirst 20 headings on the page:")
for h in clean_headings[:20]:
    print(f"- {h}")
