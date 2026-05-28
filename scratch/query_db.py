import sqlite3

db_path = ".content-machine/content_machine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("CONTENT PLAN ROWS:")
rows = cursor.execute("SELECT * FROM content_plan").fetchall()
for r in rows:
    print(dict(r))

conn.close()
