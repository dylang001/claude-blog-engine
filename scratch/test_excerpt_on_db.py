import sqlite3
import json
from content_machine.utils import excerpt

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

row = cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
payload = json.loads(row['payload_json'])
content = payload.get("content", {})
markdown = content.get("markdown", "")

print("Length of markdown:", len(markdown))
print("\nFirst 500 chars of markdown:")
print(repr(markdown[:500]))

# Let's run excerpt on it
result_excerpt = excerpt(markdown)
print("\nResult of excerpt(markdown):")
print(repr(result_excerpt))

# Let's run excerpt on html
html = content.get("html", "")
result_excerpt_html = excerpt(html)
print("\nResult of excerpt(html):")
print(repr(result_excerpt_html))

conn.close()
