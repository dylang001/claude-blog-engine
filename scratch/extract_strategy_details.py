import json
from pathlib import Path

path = Path("seo-reports/strict-strategy-20260519-165501.json")
data = json.loads(path.read_text(encoding="utf-8"))

clusters = data.get("keyword_map", {}).get("clusters", [])
print(f"Number of clusters: {len(clusters)}")
for idx, c in enumerate(clusters):
    print(f"\nCluster {idx+1}: {c['name']}")
    print(f"Primary Keyword: {c.get('primary_keyword')}")
    print("Opportunities:")
    for op in c.get("opportunities", []):
         print(f" - {op.get('keyword')}: volume={op.get('volume')}, kd={op.get('kd')}, score={op.get('score') or op.get('opportunity_score')}, intent={op.get('intent') or op.get('funnel')}")
