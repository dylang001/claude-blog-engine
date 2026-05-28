import httpx
import xml.etree.ElementTree as ET

def get_post_urls():
    url = "https://ahrefs.com/blog/post-sitemap.xml"
    print(f"Fetching {url} with a longer timeout and streaming...")
    
    # We can stream the response to avoid keeping it all in memory or timing out
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    urls = []
    
    try:
        with httpx.stream("GET", url, headers=headers, timeout=60.0) as r:
            if r.status_code != 200:
                print(f"Status: {r.status_code}")
                return []
                
            # We can use ET.iterparse to parse the XML as it streams!
            # Since XML namespaces are involved:
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            
            # Let's accumulate chunk content or read it
            content = ""
            for chunk in r.iter_text():
                content += chunk
                # If we have enough content to find a few <loc> tags, we can parse them via regex to be fast!
                import re
                locs = re.findall(r"<loc>(https://ahrefs.com/blog/[^<]+)</loc>", content)
                if len(locs) >= 30:
                    urls = locs[:30]
                    break
    except Exception as e:
        print(f"Error during streaming: {e}")
        
    return urls

def main():
    post_urls = get_post_urls()
    print(f"\nFound {len(post_urls)} posts:")
    for u in post_urls:
        print(f" - {u}")

if __name__ == "__main__":
    main()
