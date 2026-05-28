import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from content_machine.config import load_settings
from content_machine.wordpress import WordPressClient
from content_machine.utils import excerpt

async def main():
    settings = load_settings()
    wp = WordPressClient(settings)
    
    print("Fetching post 3343 with context=edit...")
    try:
        post = await wp._request_json("GET", "/posts/3343", params={"context": "edit"})
        print("Post fetched successfully.")
    except Exception as e:
        print(f"Error fetching post: {e}")
        return
        
    raw_excerpt = post.get("excerpt", {}).get("raw", "")
    rendered_excerpt = post.get("excerpt", {}).get("rendered", "")
    print(f"Raw excerpt from WordPress: {repr(raw_excerpt)}")
    print(f"Rendered excerpt from WordPress: {repr(rendered_excerpt)}")
    
    raw_content = post.get("content", {}).get("raw", "")
    
    # Sanitize excerpt
    clean = excerpt(raw_excerpt or rendered_excerpt)
    if not clean or "<!--" in clean or "<" in clean:
        print("Raw excerpt was malformed or empty. Regenerating from content...")
        clean = excerpt(raw_content)
        
    print(f"Sanitized excerpt to update: {repr(clean)}")
    
    print("Updating post 3343 on WordPress...")
    try:
        res = await wp._request_json("POST", "/posts/3343", json={"excerpt": clean})
        print(f"Post updated successfully! ID: {res.get('id')}, Status: {res.get('status')}")
    except Exception as e:
        print(f"Error updating post: {e}")

if __name__ == "__main__":
    asyncio.run(main())
