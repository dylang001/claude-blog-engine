import asyncio
from content_machine.config import load_settings
from content_machine.wordpress import WordPressClient

async def main():
    settings = load_settings()
    wp = WordPressClient(settings)
    posts = await wp.list_posts(limit=10)
    print("=== RECENT WORDPRESS POSTS ===")
    for p in posts:
        print(f"ID: {p.get('id')} | Title: {p.get('title', {}).get('rendered')} | Date: {p.get('date')} | Status: {p.get('status')} | Link: {p.get('link')}")

if __name__ == '__main__':
    asyncio.run(main())
