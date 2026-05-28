import httpx
import re

def main():
    url = "https://blog.meetlyra.app/"
    print(f"Fetching homepage: {url}")
    resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"})
    print(f"Status code: {resp.status_code}")
    if resp.status_code == 200:
        html = resp.text
        # Look for article headings or links
        # WordPress usually lists posts in h2 or h3 elements with class entry-title or post-title
        headings = re.findall(r'<h[23]\b[^>]*class="[^"]*(?:entry-title|post-title|title)[^"]*"[^>]*>(.*?)</h[23]>', html, re.DOTALL | re.IGNORECASE)
        if not headings:
            # Try general h2/h3 headings
            headings = re.findall(r'<h2\b[^>]*>(.*?)</h2>', html, re.DOTALL | re.IGNORECASE)
            
        print("\n=== HEADINGS FOUND ON HOMEPAGE ===")
        for h in headings:
            clean = re.sub(r'<[^>]+>', '', h).strip()
            print(f"- {clean}")
            
        # Let's search for time or date elements
        dates = re.findall(r'<time\b[^>]*datetime="([^"]+)"[^>]*>(.*?)</time>', html, re.DOTALL | re.IGNORECASE)
        print("\n=== DATES FOUND ON HOMEPAGE ===")
        for dt, text in dates:
            print(f"- Datetime: {dt} | Text: {text.strip()}")
    else:
        print("Failed to fetch homepage")

if __name__ == '__main__':
    main()
