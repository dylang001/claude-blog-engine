from __future__ import annotations

import re
from html import escape


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-") or "untitled"


def markdown_to_html(markdown: str) -> str:
    try:
        import markdown as md

        return md.markdown(markdown, extensions=["extra", "sane_lists"])
    except Exception:
        html = escape(markdown)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        return "\n\n".join(f"<p>{p}</p>" if p and not p.startswith("<h") else p for p in html.split("\n\n"))


def excerpt(text: str, limit: int = 155) -> str:
    clean = re.sub(r"[#*_>`\[\]\(\)]", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0] + "."
