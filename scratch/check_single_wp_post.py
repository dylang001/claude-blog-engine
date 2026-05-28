import asyncio
from content_machine.config import load_settings
from content_machine.wordpress import WordPressClient

async def main():
    settings = load_settings()
    wp = WordPressClient(settings)
    try:
        post = await wp._request_json("GET", "/posts/3379")
        print("=== WP POST 3379 DETAILS ===")
        print(f"ID: {post.get('id')}")
        print(f"Title: {post.get('title', {}).get('rendered')}")
        print(f"Slug: {post.get('slug')}")
        print(f"Date: {post.get('date')}")
        print(f"Modified: {post.get('modified')}")
        print(f"Status: {post.get('status')}")
    except Exception as e:
        print(f"Error fetching post 3379: {e}")

if __name__ == '__main__':
    asyncio.run(main())
