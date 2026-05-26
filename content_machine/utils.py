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
    # Strip HTML comments
    clean = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", "", clean)
    # Strip markdown images first
    clean = re.sub(r"!\[.*?\]\(.*?\)", "", clean)
    # Strip markdown links, keeping anchor text
    clean = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", clean)
    # Strip headers, list items, etc.
    clean = re.sub(r"^[#*>\-+]+\s*", "", clean, flags=re.MULTILINE)
    # Strip bold, italic markers, inline code
    clean = re.sub(r"[`*_~]", "", clean)
    # Normalize spaces
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= limit:
        return clean
    truncated = clean[: limit - 1].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:!? ") + "..."


def repair_json_quotes(text: str) -> str:
    """Repair unescaped double quotes inside JSON string values.
    Uses a state machine to distinguish structural JSON quotes from
    unescaped literal quotes inside values.
    """
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
        return text

    json_str = text[start:end+1]
    repaired = []

    state = "STRUCTURAL"
    i = 0
    length = len(json_str)

    while i < length:
        char = json_str[i]

        if state == "STRUCTURAL":
            if char == '"':
                state = "STRING"
                repaired.append(char)
            else:
                repaired.append(char)
            i += 1
        elif state == "STRING":
            if char == '\\':
                if i + 1 < length:
                    repaired.append(json_str[i:i+2])
                    i += 2
                else:
                    repaired.append(char)
                    i += 1
            elif char == '"':
                next_non_ws = None
                look_ahead = i + 1
                while look_ahead < length:
                    next_char = json_str[look_ahead]
                    if not next_char.isspace():
                        next_non_ws = next_char
                        break
                    look_ahead += 1

                if next_non_ws in (':', ',', '}', ']'):
                    state = "STRUCTURAL"
                    repaired.append(char)
                else:
                    repaired.append('\\"')
                i += 1
            else:
                repaired.append(char)
                i += 1

    return text[:start] + "".join(repaired) + text[end+1:]

