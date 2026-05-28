import json
from pathlib import Path

path = Path("seo-reports/strict-strategy-20260519-165501.json")
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
    print("KEYS IN STRICT STRATEGY:")
    print(list(data.keys()))
    if "opportunities" in data:
        print(f"Number of opportunities: {len(data['opportunities'])}")
        for kw in data["opportunities"][:15]:
            print(f"- {kw.get('keyword')}: volume={kw.get('volume')}, kd={kw.get('kd')}, score={kw.get('score')}")
    elif "keywords" in data:
         print(f"Number of keywords: {len(data['keywords'])}")
         for kw in data["keywords"][:15]:
             print(f"- {kw.get('keyword')}: volume={kw.get('volume')}, kd={kw.get('kd')}")
    else:
         # just print first few items of the data if list
         if isinstance(data, list):
             print(f"Number of items: {len(data)}")
             for kw in data[:15]:
                 print(f"- {kw.get('keyword')}: volume={kw.get('volume') or kw.get('avg_monthly_searches')}, kd={kw.get('kd')}")
else:
    print("Path does not exist")
