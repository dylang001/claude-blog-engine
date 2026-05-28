import json
from pathlib import Path

path = Path("seo-reports/strict-strategy-20260519-165501.json")
data = json.loads(path.read_text(encoding="utf-8"))

print("=== KEYWORD MAP ===")
kmap = data.get("keyword_map", {})
print(f"kmap type: {type(kmap)}")
if isinstance(kmap, dict):
    print("Keys:", list(kmap.keys()))
    for k, v in list(kmap.items())[:3]:
        print(f" - {k}: {str(v)[:150]}...")
elif isinstance(kmap, list):
    print("Length:", len(kmap))
    for item in kmap[:5]:
        print(item)

print("\n=== SITE STRUCTURE ===")
struct = data.get("site_structure", {})
print(f"struct type: {type(struct)}")
print("Keys:", list(struct.keys()))
for k, v in struct.items():
    print(f" - {k}: {str(v)[:150]}...")

print("\n=== BLOGGING PLAN ===")
blog = data.get("blogging_plan", {})
print(f"blog type: {type(blog)}")
print("Keys:", list(blog.keys()))
for k, v in blog.items():
    print(f" - {k}: {str(v)[:150]}...")

print("\n=== COMPETITOR RESEARCH ===")
comp = data.get("competitor_research", {})
print(f"comp type: {type(comp)}")
print("Keys:", list(comp.keys()))
for k, v in comp.items():
    print(f" - {k}: {str(v)[:150]}...")
