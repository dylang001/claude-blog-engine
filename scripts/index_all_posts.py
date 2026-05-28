import asyncio
import sqlite3
from pathlib import Path
from content_machine.config import load_settings
from content_machine.indexnow import IndexNowClient
from content_machine.indexing import GoogleIndexingClient

async def main():
    settings = load_settings()
    db_path = settings.state_db
    if not db_path.exists():
        print(f"State database not found at: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT wordpress_url FROM published_items WHERE wordpress_url IS NOT NULL")
    urls = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not urls:
        print("No published blog post URLs found in the state database.")
        return

    print(f"Found {len(urls)} published blog post URLs:")
    for url in urls:
        print(f" - {url}")

    print("\nSubmitting URLs via IndexNow...")
    indexnow = IndexNowClient(settings)
    indexnow_results = await indexnow.submit(urls)
    for res in indexnow_results:
        print(f"Engine {res.engine}: Success={res.success}, Status={res.status}, Message={res.message}")

    print("\nSubmitting URLs via Google Indexing API...")
    google_indexing = GoogleIndexingClient(settings)
    for url in urls:
        idx_res = await google_indexing.notify(url, action="URL_UPDATED")
        print(f"URL: {url} | Success={idx_res.get('success')} | Error={idx_res.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
