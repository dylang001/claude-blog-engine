import asyncio
from googleapiclient.discovery import build
from content_machine.config import load_settings
from content_machine.google_auth import get_google_credentials

async def main():
    settings = load_settings()
    blog_id = getattr(settings, "blogger_blog_id", "").strip()
    if not blog_id:
        print("BLOGGER_BLOG_ID is not configured.")
        return
        
    credentials, auth_mode = get_google_credentials(settings, ["https://www.googleapis.com/auth/blogger"])
    
    import asyncio
    loop = asyncio.get_event_loop()
    
    def _list_posts():
        service = build("blogger", "v3", credentials=credentials, cache_discovery=False)
        items = []
        for status in ["LIVE", "DRAFT", "SCHEDULED"]:
            try:
                res = service.posts().list(blogId=blog_id, status=status).execute()
                items.extend(res.get("items", []))
            except Exception as e:
                print(f"Error listing status {status}: {e}")
        return items
        
    items = await loop.run_in_executor(None, _list_posts)
    print("=== ALL BLOGGER POSTS ===")
    for item in items:
        print(f"ID: {item.get('id')} | Title: {item.get('title')} | Published: {item.get('published')} | Status: {item.get('status')} | URL: {item.get('url')}")

if __name__ == "__main__":
    asyncio.run(main())
