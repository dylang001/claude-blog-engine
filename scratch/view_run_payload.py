import sqlite3
import json

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT * FROM runs WHERE id = 'd3268258-de6f-4f4d-8bb5-4bb93dd428bf'").fetchone()
if not row:
    print("Run not found.")
else:
    payload = json.loads(row['payload_json'])
    # Print the opportunity metadata and research keys to check if parent_pillar URL was injected.
    print("OPPORTUNITY:")
    print(json.dumps(payload.get("opportunity"), indent=2))
    
    print("\nRESEARCH KEYS:")
    research = payload.get("content", {}) # Wait, research is not stored directly in payload unless we check it. Let's check what's in payload
    print(list(payload.keys()))
    
    print("\nCONTENT KEYS:")
    print(list(payload.get("content", {}).keys()))
    
    # print the whole HTML of the content
    print("\nHTML CONTENT:")
    print(payload.get("content", {}).get("html", ""))
    
conn.close()
