import sqlite3
import json

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

rows = cursor.execute("SELECT id, keyword, started_at, wordpress_status, payload_json FROM runs ORDER BY started_at DESC LIMIT 10").fetchall()
print(f"Total recent runs: {len(rows)}")
for idx, row in enumerate(rows):
    payload = json.loads(row['payload_json'])
    content = payload.get("content", {})
    wp_excerpt = payload.get("excerpt", "") or content.get("excerpt", "")
    print(f"{idx+1}: ID={row['id']} Keyword={row['keyword']} Status={row['wordpress_status']} StartedAt={row['started_at']}")
    print(f"   Excerpt: {repr(wp_excerpt)}")
    print(f"   Meta Desc: {repr(content.get('meta_description', ''))}")
    print("-" * 50)

conn.close()
