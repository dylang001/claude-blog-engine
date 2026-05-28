import sqlite3

def main():
    conn = sqlite3.connect(".content-machine/content_machine.db")
    cursor = conn.cursor()
    cursor.execute("SELECT keyword, role, status, wordpress_url, score FROM content_plan")
    rows = cursor.fetchall()
    
    print("=== Database Content Plan ===")
    print(f"{'Keyword':<40} | {'Role':<8} | {'Status':<10} | {'Score':<5} | {'URL'}")
    print("-" * 100)
    
    status_counts = {}
    for row in rows:
        keyword, role, status, wp_url, score = row
        wp_url = wp_url or "N/A"
        print(f"{keyword:<40} | {role:<8} | {status:<10} | {score:<5.1f} | {wp_url}")
        status_counts[status] = status_counts.get(status, 0) + 1
        
    print("\n=== Status Counts ===")
    for status, count in status_counts.items():
        print(f"{status}: {count}")
    conn.close()

if __name__ == '__main__':
    main()
