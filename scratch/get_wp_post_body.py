import asyncio
from content_machine.config import load_settings
from content_machine.wordpress import WordPressClient

async def main():
    settings = load_settings()
    client = WordPressClient(settings)
    posts = await client.list_posts(limit=5)
    print(f"Found {len(posts)} posts:")
    for post in posts:
        print(f"ID: {post['id']}, Slug: {post['slug']}, Title: {post['title']['rendered']}, Status: {post['status']}")
        # print first 500 chars of content
        content_html = post['content']['rendered']
        print(f"Content Length: {len(content_html)}")
        
        # Check for unclosed comments in content
        open_count = content_html.count("<!--")
        close_count = content_html.count("-->")
        print(f"HTML comments: open={open_count}, close={close_count}")
        if open_count != close_count:
            print("WARNING: Unbalanced HTML comments!")
            
        print("-" * 50)
        
        # Save content of the most recent post
        if post == posts[0]:
            with open("scratch/latest_wp_post_content.html", "w") as f:
                f.write(content_html)
            print("Saved latest post content to scratch/latest_wp_post_content.html")

if __name__ == "__main__":
    asyncio.run(main())
