import re
from pathlib import Path
from html.parser import HTMLParser

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.in_script = True
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.result.append(f"\n\n### [{tag.upper()}] ")

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.in_script = False
        if tag == 'p':
            self.result.append('\n')

    def handle_data(self, data):
        if self.in_script or self.in_style:
            return
        text = data.strip()
        if text:
            self.result.append(text + " ")

    def get_text(self):
        return "".join(self.result)

def clean_file(path_str, out_str):
    p = Path(path_str)
    if not p.exists():
        print(f"File not found: {path_str}")
        return
    content = p.read_text(encoding='utf-8', errors='ignore')
    
    # Strip some header lines before the actual HTML starts
    if '---' in content:
        content = content.split('---', 1)[1]
        
    extractor = HTMLTextExtractor()
    extractor.feed(content)
    text = extractor.get_text()
    
    # Clean up multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    Path(out_str).write_text(text, encoding='utf-8')
    print(f"Cleaned {path_str} -> {out_str}")

if __name__ == '__main__':
    clean_file(
        "/Users/dylanangloher/.gemini/antigravity/brain/5cb25842-f1a4-4d2f-80dc-68e4801fd23e/.system_generated/steps/5496/content.md",
        "/Users/dylanangloher/claude-blog-engine/scratch/yoast_clean.txt"
    )
    clean_file(
        "/Users/dylanangloher/.gemini/antigravity/brain/5cb25842-f1a4-4d2f-80dc-68e4801fd23e/.system_generated/steps/5498/content.md",
        "/Users/dylanangloher/claude-blog-engine/scratch/ahrefs_clean.txt"
    )
