import json
from html.parser import HTMLParser

class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_tag = None
        self.tags = ["h1", "h2", "h3", "p", "li"]
        self.text_list = []

    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            self.current_tag = tag

    def handle_endtag(self, tag):
        if tag == self.current_tag:
            self.current_tag = None

    def handle_data(self, data):
        if self.current_tag and data.strip():
            self.text_list.append((self.current_tag, data.strip()))

file_path = "/Users/dylanangloher/.gemini/antigravity/brain/5cb25842-f1a4-4d2f-80dc-68e4801fd23e/.system_generated/steps/3508/content.md"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

parser = SimpleHTMLParser()
parser.feed(content)

for tag, text in parser.text_list:
    print(f"[{tag}]: {text}")

