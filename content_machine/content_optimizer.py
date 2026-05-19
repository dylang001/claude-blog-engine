from __future__ import annotations

import re
from dataclasses import replace

from .models import GeneratedContent, Opportunity
from .utils import excerpt, markdown_to_html, slugify


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "your",
}

TRANSITION_WORDS = {
    "also",
    "because",
    "but",
    "finally",
    "first",
    "for example",
    "however",
    "instead",
    "meanwhile",
    "moreover",
    "next",
    "therefore",
    "this means",
    "while",
}


def optimize_content(content: GeneratedContent, opportunity: Opportunity) -> GeneratedContent:
    title = content.title.strip() or opportunity.title
    focus_keyphrase = derive_focus_keyphrase(content.focus_keyphrase or opportunity.keyword)
    markdown = strip_leading_h1(content.markdown)
    markdown = ensure_intro_keyphrase(markdown, focus_keyphrase)
    markdown = ensure_subheading_keyphrase(markdown, focus_keyphrase)
    markdown = ensure_keyphrase_density(markdown, focus_keyphrase)
    markdown = ensure_outbound_link(markdown)
    markdown = ensure_internal_link(markdown)
    markdown = ensure_transition_words(markdown)
    rich_blocks = _normalize_rich_blocks(content.rich_blocks, focus_keyphrase, markdown)
    markdown = ensure_rich_blocks(markdown, rich_blocks)
    meta_title = optimize_meta_title(content.meta_title or title, focus_keyphrase)
    meta_description = optimize_meta_description(content.meta_description or excerpt(markdown), focus_keyphrase)
    image_alt_text = optimize_image_alt_text(content.image_alt_text or content.image_prompt or title, focus_keyphrase)
    slug = content.slug or slugify(opportunity.keyword)

    return replace(
        content,
        title=title,
        slug=slug[:75].strip("-"),
        markdown=markdown,
        html=markdown_to_html(markdown),
        meta_title=meta_title,
        meta_description=meta_description,
        focus_keyphrase=focus_keyphrase,
        excerpt=excerpt(markdown),
        image_alt_text=image_alt_text,
        rich_blocks=rich_blocks,
    )


def strip_leading_h1(markdown: str) -> str:
    return re.sub(r"\A\s*#\s+.+?(?:\n{2,}|\n|$)", "", markdown or "", count=1).lstrip()


def derive_focus_keyphrase(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    if not words:
        return "SEO content"
    phrase: list[str] = []
    for word in words:
        if word.lower() in STOP_WORDS and len(phrase) >= 2:
            break
        if word.lower() not in STOP_WORDS:
            phrase.append(word)
        if len(phrase) == 4:
            break
    if len(phrase) < 2:
        phrase = [w for w in words if w.lower() not in STOP_WORDS][:4]
    return " ".join(phrase[:4]) or " ".join(words[:4])


def optimize_meta_title(current: str, focus_keyphrase: str) -> str:
    suffixes = [
        "SEO Content Systems That Scale",
        "Autonomous SEO Content Guide",
        "Content Automation Guide",
    ]
    if current.startswith(focus_keyphrase) and 45 <= len(current) <= 60:
        return current
    for suffix in suffixes:
        candidate = f"{focus_keyphrase}: {suffix}"
        if 45 <= len(candidate) <= 60:
            return candidate
    return _truncate_words(f"{focus_keyphrase}: {suffixes[0]}", 60)


def optimize_meta_description(current: str, focus_keyphrase: str) -> str:
    clean = _plain_text(current)
    if focus_keyphrase.lower() in clean.lower() and 130 <= len(clean) <= 155:
        return clean
    candidate = (
        f"{focus_keyphrase} helps lean teams research, create, optimize, and publish SEO content "
        "with autonomous workflows and quality controls."
    )
    if len(candidate) < 130:
        candidate += " Built for consistent growth."
    return _truncate_words(candidate, 155)


def optimize_image_alt_text(current: str, focus_keyphrase: str) -> str:
    clean = _plain_text(current)
    if focus_keyphrase.lower() not in clean.lower():
        clean = f"{focus_keyphrase} workflow illustration showing autonomous research, content creation, and SEO optimization."
    return _truncate_words(clean, 180)


def ensure_intro_keyphrase(markdown: str, focus_keyphrase: str) -> str:
    paragraphs = _paragraphs(markdown)
    if not paragraphs:
        return f"{focus_keyphrase} gives lean teams a structured way to plan, write, optimize, and publish SEO content without manual handoffs."
    first = paragraphs[0]
    if focus_keyphrase.lower() in first.lower():
        return markdown
    replacement = f"{focus_keyphrase} gives lean teams a structured way to plan, write, optimize, and publish SEO content without manual handoffs. {first}"
    return markdown.replace(first, replacement, 1)


def ensure_subheading_keyphrase(markdown: str, focus_keyphrase: str) -> str:
    if re.search(rf"^##+\s+.*{re.escape(focus_keyphrase)}", markdown, flags=re.IGNORECASE | re.MULTILINE):
        return markdown
    return f"## {focus_keyphrase}: Quick Answer\n\n{focus_keyphrase} is an autonomous content workflow that combines opportunity research, SEO writing, optimization, publishing, and performance monitoring.\n\n{markdown}"


def ensure_keyphrase_density(markdown: str, focus_keyphrase: str, minimum: int = 5) -> str:
    count = len(re.findall(re.escape(focus_keyphrase), markdown, flags=re.IGNORECASE))
    if count >= minimum:
        return markdown
    additions = []
    for _ in range(minimum - count):
        additions.append(f"{focus_keyphrase} keeps the workflow focused on search intent, quality, and repeatable publishing.")
    return f"{markdown.rstrip()}\n\n" + "\n\n".join(additions)


def ensure_outbound_link(markdown: str) -> str:
    if re.search(r"\]\(https?://(?!blog\.meetlyra\.app|meetlyra\.app)", markdown):
        return markdown
    block = (
        "\n\nFor a useful baseline on search documentation, review "
        "[Google Search Central](https://developers.google.com/search/docs) when validating technical SEO decisions."
    )
    return markdown.rstrip() + block


def ensure_internal_link(markdown: str) -> str:
    if re.search(r"\]\((?:/|https://(?:blog\.)?meetlyra\.app)", markdown):
        return markdown
    return markdown.rstrip() + "\n\n[Explore MeetLyra's autonomous marketing workflow](https://blog.meetlyra.app)."


def ensure_transition_words(markdown: str) -> str:
    return markdown


def build_rich_blocks(focus_keyphrase: str, markdown: str = "") -> list[str]:
    word_count = len(re.findall(r"\b\w+\b", _plain_text(markdown)))
    reading_minutes = max(1, round(word_count / 220)) if word_count else 8
    toc_items = _toc_items(markdown)
    toc_links = "".join(f'<li><a href="#{slugify(item)}">{item}</a></li>' for item in toc_items[:8])
    if not toc_links:
        toc_links = (
            '<li><a href="#quick-answer">Quick answer</a></li>'
            '<li><a href="#workflow">Workflow</a></li>'
            '<li><a href="#faq">FAQ</a></li>'
        )
    return [
        f"""<!-- wp:html -->
<aside class="seo-machine-reading-time" aria-label="Reading time"><strong>Reading time:</strong> {reading_minutes} minutes</aside>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<nav class="seo-machine-toc" aria-label="Table of contents"><h2>Table of Contents</h2><ol>{toc_links}</ol></nav>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<section class="seo-machine-proof" aria-label="Proof point"><h2>Proof Point</h2><p>This workflow follows Google Search Central guidance: useful, original, people-first content matters more than whether AI helped create the first draft.</p><p><a href="https://developers.google.com/search/blog/2023/02/google-search-and-ai-content">Review Google's AI content guidance</a>.</p></section>
<!-- /wp:html -->""",
        f"""<!-- wp:quote {{"className":"seo-machine-pullquote"}} -->
<blockquote class="wp-block-quote seo-machine-pullquote"><p>{focus_keyphrase} works best when it turns strategy into a repeatable publishing system, not just another drafting shortcut.</p><cite>SEO Machine quality gate</cite></blockquote>
<!-- /wp:quote -->""",
        f"""<!-- wp:html -->
<section class="seo-machine-takeaways" aria-label="Key takeaways"><h2>Key Takeaways</h2><ul><li>Use {focus_keyphrase} to connect research, drafting, optimization, and publishing.</li><li>Keep human review focused on strategy, evidence, and brand judgment.</li><li>Measure success through publish consistency, rankings, and conversion quality.</li></ul></section>
<!-- /wp:html -->""",
        """<!-- wp:html -->
<figure class="seo-machine-table"><table><thead><tr><th>Workflow</th><th>Manual SEO</th><th>Agentic SEO</th></tr></thead><tbody><tr><td>Research</td><td>Spreadsheet-led and slow</td><td>Scored opportunities</td></tr><tr><td>Drafting</td><td>One-off briefs</td><td>Context-aware generation</td></tr><tr><td>Optimization</td><td>Manual plugin checks</td><td>Pre-publish quality gate</td></tr></tbody></table></figure>
<!-- /wp:html -->""",
        """<!-- wp:html -->
<section class="seo-machine-chart" aria-label="SEO content workflow chart"><h2>Autonomous SEO Workflow</h2><ol><li><strong>Discover</strong><span style="width:72%"></span></li><li><strong>Research</strong><span style="width:84%"></span></li><li><strong>Create</strong><span style="width:78%"></span></li><li><strong>Optimize</strong><span style="width:90%"></span></li><li><strong>Publish</strong><span style="width:68%"></span></li></ol></section>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<section class="seo-machine-faq" aria-label="FAQ"><h2>FAQ: {focus_keyphrase}</h2><details><summary>What does it automate?</summary><p>It automates opportunity research, content creation, on-page optimization, publishing preparation, and monitoring.</p></details><details><summary>Does it replace strategy?</summary><p>No. It handles repeatable execution so humans can focus on positioning, evidence, and quality control.</p></details></section>
<!-- /wp:html -->""",
        """<!-- wp:html -->
<aside class="seo-machine-related" aria-label="Related articles"><h2>Related Articles</h2><ul><li><a href="https://blog.meetlyra.app/">MeetLyra blog</a></li><li><a href="https://meetlyra.app/">MeetLyra marketing workflow</a></li></ul></aside>
<!-- /wp:html -->""",
    ]


def _normalize_rich_blocks(blocks: list, focus_keyphrase: str, markdown: str = "") -> list[str]:
    defaults = build_rich_blocks(focus_keyphrase, markdown)
    if not blocks or not all(isinstance(block, str) for block in blocks):
        return defaults
    merged = list(blocks)
    existing = "\n".join(merged)
    for block in defaults:
        marker = _rich_block_marker(block)
        if marker not in existing:
            merged.append(block)
            existing += "\n" + block
    return merged


def ensure_rich_blocks(markdown: str, blocks: list[str]) -> str:
    existing = markdown
    missing = [block for block in blocks if _rich_block_marker(block) not in existing]
    if not missing:
        return markdown
    return _insert_blocks_throughout(markdown, missing)


def _plain_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"[#*_>`\[\]\(\)]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _paragraphs(markdown: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n{2,}", markdown or "") if part.strip() and not part.lstrip().startswith(("#", "<", "-", "|"))]


def _toc_items(markdown: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^##\s+(.+)$", markdown or "", flags=re.MULTILINE)]


def _rich_block_marker(block: str) -> str:
    match = re.search(r"seo-machine-[a-z0-9-]+", block)
    return match.group(0) if match else block[:40]


def _insert_blocks_throughout(markdown: str, blocks: list[str]) -> str:
    section_matches = list(re.finditer(r"^##\s+.+$", markdown or "", flags=re.MULTILINE))
    if not section_matches:
        return markdown.rstrip() + "\n\n" + "\n\n".join(blocks)

    chunks: list[str] = []
    first_heading = section_matches[0].start()
    intro = markdown[:first_heading].rstrip()
    if intro:
        chunks.append(intro)
    for index, match in enumerate(section_matches):
        end = section_matches[index + 1].start() if index + 1 < len(section_matches) else len(markdown)
        chunks.append(markdown[match.start() : end].rstrip())

    top_markers = {"seo-machine-reading-time", "seo-machine-toc"}
    top_blocks = [block for block in blocks if _rich_block_marker(block) in top_markers]
    body_blocks = [block for block in blocks if _rich_block_marker(block) not in top_markers]

    if top_blocks:
        chunks[0] = chunks[0].rstrip() + "\n\n" + "\n\n".join(top_blocks)
    for index, block in enumerate(body_blocks):
        target = min(index + 1, len(chunks) - 1)
        chunks[target] = chunks[target].rstrip() + "\n\n" + block

    return "\n\n".join(chunks).strip()


def _truncate_words(value: str, limit: int) -> str:
    clean = _plain_text(value)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rsplit(" ", 1)[0].rstrip(".,;:") + "."
