import sqlite3
import json
from pathlib import Path

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
if not row:
    print("No runs found in database.")
else:
    row = dict(row)
    print("Available keys in row:", list(row.keys()))
    print(f"Run ID: {row['id']}")
    print(f"Opportunity: {row.get('keyword')} (type: {row.get('opportunity_type')})")
    print(f"Started At: {row.get('started_at')}")
    print(f"Finished At: {row.get('finished_at')}")
    print(f"Status: {row.get('wordpress_status')}")
    print(f"Score: {row.get('score')}")
    print(f"Decision: {row.get('decision')}")
    
    # Let's check payload/generated content
    payload_json = row.get('payload_json')
    if payload_json:
        payload = json.loads(payload_json)
        content = payload.get("content", {})
        audit = payload.get("audit", {})
        print("\nAudit Details:")
        print(f"  Score: {audit.get('score')}")
        print(f"  Decision: {audit.get('decision')}")
        print("  Issues:")
        for issue in audit.get('issues', []):
            print(f"    - {issue}")
        print("  Warnings:")
        for warning in audit.get('warnings', []):
            print(f"    - {warning}")
            
        print("\nContent Details:")
        print(f"  Title: {content.get('title')}")
        print(f"  Excerpt: {repr(content.get('excerpt'))}")
        print(f"  Meta Description: {repr(content.get('meta_description'))}")

conn.close()
