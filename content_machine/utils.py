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
    # 1. Clean HTML comments (including Gutenberg block comments)
    clean = re.sub(r"<!--.*?-->", "", text or "", flags=re.DOTALL)
    # 2. Strip any remaining/unclosed comment delimiters and contents (e.g. <!-- wp:...)
    clean = re.sub(r"<!--[^<]*", "", clean)
    # 3. Strip HTML tags
    clean = re.sub(r"<[^>]+>", "", clean)
    # 4. Strip markdown symbols
    clean = re.sub(r"[#*_>`\[\]\(\)]", "", clean)
    # 5. Prevent layout-breaking HTML characters by stripping any leftover comment markers/brackets
    clean = clean.replace("<!--", "").replace("-->", "").replace("<", "").replace(">", "")
    # 6. Normalize whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0] + "."


def load_agent_instructions(name: str) -> str:
    """Load and parse instructions from a claude-seo agent markdown file."""
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "claude-seo", "agents", f"{name}.md")
    if not os.path.exists(path):
        # Try fallbacks
        path_fallback = os.path.join(os.getcwd(), "claude-seo", "agents", f"{name}.md")
        if not os.path.exists(path_fallback):
            return ""
        path = path_fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]
        return content.strip()
    except Exception:
        return ""


async def retry_async(func, *args, retries=3, delay=2, backoff=2, exceptions=(Exception,), **kwargs):
    """Retry an async function multiple times with exponential backoff."""
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    current_delay = delay
    for attempt in range(retries):
        try:
            return await func(*args, **kwargs)
        except exceptions as exc:
            if attempt == retries - 1:
                logger.error(f"Function {getattr(func, '__name__', str(func))} failed after {retries} attempts: {exc}")
                raise
            logger.warning(
                f"Function {getattr(func, '__name__', str(func))} failed with {exc}. "
                f"Retrying in {current_delay}s (attempt {attempt + 1}/{retries})..."
            )
            await asyncio.sleep(current_delay)
            current_delay *= backoff
