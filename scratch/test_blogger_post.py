import asyncio
from content_machine.config import load_settings
from content_machine.blogger import BloggerClient

async def main():
    settings = load_settings()
    client = BloggerClient(settings)
    try:
        res = await client.publish_post(
            "Blogger API Connectivity Test",
            "<p>This is a test post to verify that the Blogger API is enabled and working with OAuth credentials.</p>",
            is_draft=True
        )
        print("Success! Created post on Blogger.")
        print("Blogger Post ID:", res.get("id"))
        print("Blogger Post URL:", res.get("url"))
    except Exception as e:
        print("Blogger API test failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
