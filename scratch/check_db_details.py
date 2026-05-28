import sqlite3
import json

def check_db():
    conn = sqlite3.connect(".content-machine/content_machine.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- TABLES ---")
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(tables)
    
    print("\n--- RECENT RUNS ---")
    runs = cursor.execute("SELECT id, started_at, finished_at, dry_run, keyword, wordpress_status, wordpress_id FROM runs ORDER BY started_at DESC LIMIT 10").fetchall()
    for r in runs:
        print(dict(r))
        
    print("\n--- RECENT ARTICLES ---")
    articles = cursor.execute("SELECT * FROM articles ORDER BY publish_date DESC LIMIT 10").fetchall()
    for a in articles:
        print(dict(a))
        
    print("\n--- DISTRIBUTION ASSETS ---")
    assets = cursor.execute("SELECT * FROM distribution_assets ORDER BY date_published DESC LIMIT 10").fetchall()
    for a in assets:
        print(dict(a))
        
    print("\n--- BACKLINK TARGETS ---")
    targets = cursor.execute("SELECT * FROM backlink_targets LIMIT 10").fetchall()
    for t in targets:
        print(dict(t))
        
    print("\n--- DAILY REPORTS ---")
    reports = cursor.execute("SELECT * FROM daily_reports ORDER BY date DESC LIMIT 10").fetchall()
    for r in reports:
        print(dict(r))
        
    conn.close()

if __name__ == '__main__':
    check_db()
