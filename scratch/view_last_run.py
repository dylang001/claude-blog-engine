import sqlite3
import json

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("LATEST RUNS:")
rows = cursor.execute("SELECT id, started_at, keyword, score, decision, wordpress_status FROM runs ORDER BY started_at DESC LIMIT 5").fetchall()
for r in rows:
    print(dict(r))

# Get the absolute latest run's payload
row = cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
if row:
    print(f"\nLATEST RUN PAYLOAD (ID: {row['id']}):")
    try:
        payload = json.loads(row['payload_json'])
        # Print keys
        print("Keys:", list(payload.keys()))
        if "content" in payload:
            content = payload["content"]
            print("Content Keys:", list(content.keys()))
            print("Title:", content.get("title"))
            print("Focus Keyphrase:", content.get("focus_keyphrase"))
            print("Markdown Length:", len(content.get("markdown", "")))
            print("Markdown snippet:")
            print(content.get("markdown", "")[:1000])
    except Exception as e:
        print("Error parsing payload:", e)

conn.close()
