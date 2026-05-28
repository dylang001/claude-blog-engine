import sqlite3
import json

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
if row:
    print(f"RUN ID: {row['id']}")
    payload = json.loads(row['payload_json'])
    content = payload.get("content", {})
    print("Content Markdown Length:", len(content.get("markdown", "")))
    print("Content Markdown content:")
    print(content.get("markdown", ""))
conn.close()
