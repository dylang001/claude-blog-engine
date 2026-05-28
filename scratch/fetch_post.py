import asyncio
import json
from content_machine.config import load_settings
from content_machine.wordpress import WordPressClient

async def main():
    settings = load_settings()
    client = WordPressClient(settings)
    
    post = await client.find_post_by_slug("jasper-pricing")
    if not post:
        print("Post not found!")
        return
        
    print(f"ID: {post.get('id')}")
    print(f"Slug: {post.get('slug')}")
    print(f"Title: {post.get('title', {}).get('rendered')}")
    print(f"Featured Media ID: {post.get('featured_media')}")
    
    # Save the full post JSON and content to verify
    with open("scratch/post_details.json", "w") as f:
        json.dump(post, f, indent=2)
    
    content = post.get('content', {}).get('rendered', '')
    with open("scratch/post_content.html", "w") as f:
        f.write(content)
        
    print("Post details saved to scratch/post_details.json and content saved to scratch/post_content.html")

if __name__ == "__main__":
    asyncio.run(main())
