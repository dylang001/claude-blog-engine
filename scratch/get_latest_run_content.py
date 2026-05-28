import sqlite3
import json

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
if not row:
    print("No runs found in the database.")
else:
    print("=" * 60)
    print(f"RUN ID: {row['id']}")
    print(f"KEYWORD: {row['keyword']}")
    print(f"STARTED AT: {row['started_at']}")
    print(f"DECISION: {row['decision']}")
    print(f"SCORE: {row['score']}")
    print(f"WORDPRESS STATUS: {row['wordpress_status']}")
    print("=" * 60)
    
    payload = json.loads(row['payload_json'])
    content = payload.get("content", {})
    
    print(f"TITLE: {content.get('title')}")
    print(f"SLUG: {content.get('slug')}")
    print(f"FOCUS KEYPHRASE: {content.get('focus_keyphrase')}")
    print(f"META TITLE: {content.get('meta_title')}")
    print(f"META DESCRIPTION: {content.get('meta_description')}")
    print(f"IMAGE PROMPT: {content.get('image_prompt')}")
    print(f"IMAGE ALT TEXT: {content.get('image_alt_text')}")
    print(f"SCHEMA: {json.dumps(content.get('schema_json'), indent=2)}")
    print("=" * 60)
    print("BODY EXCERPT:")
    body = content.get("markdown", "")
    lines = body.split("\n")
    for line in lines[:30]:
        print(line)
    print("...")
    print("=" * 60)

conn.close()
