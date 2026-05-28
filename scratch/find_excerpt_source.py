import sqlite3
import json

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
payload = json.loads(row['payload_json'])

print("Database Run Excerpt:")
print(repr(payload.get("content", {}).get("excerpt")))

print("\nDatabase Run Meta Description:")
print(repr(payload.get("content", {}).get("meta_description")))

print("\nDatabase Run HTML body (first 1000 chars):")
print(payload.get("content", {}).get("html", "")[:1000])

conn.close()
