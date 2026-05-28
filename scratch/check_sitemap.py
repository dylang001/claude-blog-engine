import httpx
import xml.etree.ElementTree as ET

def main():
    sitemap_url = "https://ahrefs.com/blog/sitemap_index.xml"
    print(f"Fetching sitemap index: {sitemap_url}")
    try:
        resp = httpx.get(sitemap_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print("Failed to fetch!")
            return
            
        root = ET.fromstring(resp.content)
        # Parse sitemaps
        sitemaps = []
        for sitemap in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap"):
            loc = sitemap.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc is not None:
                sitemaps.append(loc.text)
                
        print(f"Found {len(sitemaps)} sub-sitemaps:")
        for idx, sm in enumerate(sitemaps):
            print(f"{idx+1}. {sm}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
