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
    "as a result",
    "because",
    "but",
    "consequently",
    "finally",
    "first",
    "for example",
    "for instance",
    "furthermore",
    "however",
    "in addition",
    "in contrast",
    "in other words",
    "instead",
    "likewise",
    "meanwhile",
    "moreover",
    "nevertheless",
    "next",
    "on the other hand",
    "similarly",
    "specifically",
    "still",
    "that said",
    "therefore",
    "this means",
    "thus",
    "while",
    "yet",
}


def optimize_content(content: GeneratedContent, opportunity: Opportunity) -> GeneratedContent:
    title = content.title.strip() or opportunity.title
    focus_keyphrase = derive_focus_keyphrase(content.focus_keyphrase or opportunity.keyword)
    markdown = strip_leading_h1(content.markdown)
    markdown = ensure_intro_keyphrase(markdown, focus_keyphrase)
    markdown = ensure_geo_quick_answer(markdown, focus_keyphrase)
    markdown = ensure_subheading_keyphrase(markdown, focus_keyphrase)
    markdown = ensure_keyphrase_density(markdown, focus_keyphrase)
    markdown = ensure_outbound_link(markdown)
    markdown = ensure_internal_link(markdown)
    markdown = sanitize_meetlyra_links(markdown)
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
        excerpt=excerpt(content.excerpt or markdown),
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


def is_gutenberg_html(text: str) -> bool:
    return "<!-- wp:" in text or "<p>" in text


def ensure_intro_keyphrase(markdown: str, focus_keyphrase: str) -> str:
    if is_gutenberg_html(markdown):
        p_match = re.search(r"<p>(.*?)</p>", markdown or "", flags=re.DOTALL)
        if p_match:
            first_content = p_match.group(1)
            plain_first = _plain_text(first_content)
            if focus_keyphrase.lower() in plain_first.lower():
                return markdown
            injected = f"{focus_keyphrase} gives lean teams a structured way to plan, write, optimize, and publish SEO content without manual handoffs. {first_content}"
            start, end = p_match.span(1)
            return markdown[:start] + injected + markdown[end:]
        else:
            return f"<!-- wp:paragraph -->\n<p>{focus_keyphrase} gives lean teams a structured way to plan, write, optimize, and publish SEO content without manual handoffs.</p>\n<!-- /wp:paragraph -->\n\n{markdown}"
    else:
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
    if re.search(rf"<h[2-6]\b[^>]*>.*{re.escape(focus_keyphrase)}.*</h[2-6]>", markdown, flags=re.IGNORECASE | re.DOTALL):
        return markdown
    
    if is_gutenberg_html(markdown):
        heading_block = (
            f'<!-- wp:heading {{"level":2}} -->\n'
            f"<h2>{focus_keyphrase}: Quick Answer</h2>\n"
            f"<!-- /wp:heading -->\n"
            f"<!-- wp:paragraph -->\n"
            f"<p>{focus_keyphrase} is an autonomous content workflow that combines opportunity research, SEO writing, optimization, publishing, and performance monitoring.</p>\n"
            f"<!-- /wp:paragraph -->"
        )
        return f"{heading_block}\n\n{markdown}"
    else:
        return f"## {focus_keyphrase}: Quick Answer\n\n{focus_keyphrase} is an autonomous content workflow that combines opportunity research, SEO writing, optimization, publishing, and performance monitoring.\n\n{markdown}"


def ensure_keyphrase_density(markdown: str, focus_keyphrase: str, minimum: int = 5) -> str:
    count = len(re.findall(re.escape(focus_keyphrase), markdown, flags=re.IGNORECASE))
    if count >= minimum:
        return markdown
    additions = []
    for _ in range(minimum - count):
        if is_gutenberg_html(markdown):
            additions.append(f"<!-- wp:paragraph -->\n<p>{focus_keyphrase} keeps the workflow focused on search intent, quality, and repeatable publishing.</p>\n<!-- /wp:paragraph -->")
        else:
            additions.append(f"{focus_keyphrase} keeps the workflow focused on search intent, quality, and repeatable publishing.")
    return f"{markdown.rstrip()}\n\n" + "\n\n".join(additions)


def ensure_outbound_link(markdown: str) -> str:
    if re.search(r"\]\(https?://(?!blog\.meetlyra\.app|meetlyra\.app)", markdown) or re.search(r'href=["\']https?://(?!blog\.meetlyra\.app|meetlyra\.app)', markdown):
        return markdown
    
    if is_gutenberg_html(markdown):
        block = (
            '\n\n<!-- wp:paragraph -->\n'
            '<p>For a useful baseline on search documentation, review '
            '<a href="https://developers.google.com/search/docs" rel="nofollow">Google Search Central</a> when validating technical SEO decisions.</p>\n'
            '<!-- /wp:paragraph -->'
        )
    else:
        block = (
            "\n\nFor a useful baseline on search documentation, review "
            "[Google Search Central](https://developers.google.com/search/docs) when validating technical SEO decisions."
        )
    return markdown.rstrip() + block


def ensure_internal_link(markdown: str) -> str:
    if re.search(r"\]\((?:/|https://(?:blog\.)?meetlyra\.app)", markdown) or re.search(r'href=["\'](?:/|https://(?:blog\.)?meetlyra\.app)', markdown):
        return markdown
    
    if is_gutenberg_html(markdown):
        block = (
            '\n\n<!-- wp:paragraph -->\n'
            '<p><a href="https://blog.meetlyra.app">Explore MeetLyra\'s autonomous marketing workflow</a>.</p>\n'
            '<!-- /wp:paragraph -->'
        )
    else:
        block = (
            "\n\n[Explore MeetLyra's autonomous marketing workflow](https://blog.meetlyra.app)."
        )
    return markdown.rstrip() + block


def ensure_geo_quick_answer(markdown: str, focus_keyphrase: str) -> str:
    """Inject a GEO quick-answer block after the first paragraph if not already present.

    AI search engines (Perplexity, ChatGPT) extract self-contained 134-167 word passages.
    This block acts as a structured, citable definition passage for the focus keyphrase.
    """
    if "seo-machine-quick-answer" in markdown:
        return markdown

    quick_answer_block = (
        f'\n\n<!-- wp:html -->\n'
        f'<section class="seo-machine-quick-answer" aria-label="Quick answer">\n'
        f'  <h2>What is {focus_keyphrase}?</h2>\n'
        f'  <p>{focus_keyphrase} is a structured approach to automating marketing content research, '
        f'creation, optimisation, and publishing. It connects keyword opportunity scoring, '
        f'long-form SEO writing, Yoast-compliant quality checks, and WordPress publishing '
        f'into a single repeatable pipeline. Teams using {focus_keyphrase} replace manual '
        f'content briefing, editing, and scheduling workflows with an autonomous system that '
        f'runs checks on readability, internal linking, schema markup, and keyword density '
        f'before any article reaches a live URL. The pipeline integrates with Google Search '
        f'Console for performance tracking, Google Analytics 4 for traffic attribution, and '
        f'IndexNow for instant search engine notification. It is designed for B2B SaaS '
        f'operators and lean marketing teams who need consistent organic growth without '
        f'expanding headcount.</p>\n'
        f'</section>\n'
        f'<!-- /wp:html -->'
    )

    if is_gutenberg_html(markdown):
        # Insert after the first closing </p> tag
        first_p_end = markdown.find("</p>")
        if first_p_end != -1:
            # Find the end of the surrounding block comment if present
            block_end = markdown.find("<!-- /wp:paragraph -->", first_p_end)
            if block_end != -1:
                insert_at = block_end + len("<!-- /wp:paragraph -->")
                return markdown[:insert_at] + quick_answer_block + markdown[insert_at:]
            return markdown[:first_p_end + 4] + quick_answer_block + markdown[first_p_end + 4:]
    else:
        # Plain markdown: insert after first paragraph (double newline)
        first_break = markdown.find("\n\n")
        if first_break != -1:
            return markdown[:first_break] + "\n\n" + quick_answer_block + markdown[first_break:]

    return markdown


def sanitize_meetlyra_links(markdown: str) -> str:
    # Match meetlyra.app or www.meetlyra.app with optional path/subpages,
    # but ignore blog.meetlyra.app and waitlist.meetlyra.app.
    # Replace them with the waitlist URL.
    pattern = r'(https?://(?:www\.)?meetlyra\.app(?:\/[^\s\)"\']*)?)'
    
    def replacer(match):
        url = match.group(1)
        if "blog.meetlyra.app" in url or "waitlist.meetlyra.app" in url:
            return url
        return "https://waitlist.meetlyra.app"

    return re.sub(pattern, replacer, markdown)


def ensure_transition_words(markdown: str, target_ratio: float = 0.30) -> str:
    """Inject transition words at the start of sentences that lack them, up to target_ratio.

    This works on Gutenberg HTML by operating sentence-by-sentence within <p> tags.
    We only inject into short/medium-length sentences to keep transitions natural.
    """
    if not markdown:
        return markdown

    # Only operate on paragraph content to avoid corrupting headings/blocks
    plain = _plain_text(markdown)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", plain) if s.strip()]
    if not sentences:
        return markdown

    hits = sum(1 for s in sentences if any(w in s.lower() for w in TRANSITION_WORDS))
    current_ratio = hits / len(sentences)
    if current_ratio >= target_ratio:
        return markdown

    # How many sentences need a transition word added?
    needed = int(target_ratio * len(sentences)) - hits
    if needed <= 0:
        return markdown

    # Cycle through a short list of natural starters to inject
    starters = [
        "However, ", "Additionally, ", "For example, ", "That said, ",
        "Furthermore, ", "In contrast, ", "As a result, ", "Similarly, ",
    ]
    starter_index = 0

    def _inject_into_paragraph(p_html: str) -> str:
        nonlocal needed, starter_index
        if needed <= 0:
            return p_html
        # Extract inner text of <p>...</p>
        inner_match = re.match(r"(^\s*<p[^>]*>)(.*)(</p>\s*$)", p_html, flags=re.DOTALL)
        if not inner_match:
            return p_html
        open_tag, inner, close_tag = inner_match.groups()
        # Only inject if this paragraph doesn't already start with a transition word
        inner_lower = _plain_text(inner).lower()
        if any(inner_lower.startswith(w) for w in TRANSITION_WORDS):
            return p_html
        # Only inject on medium-length paragraphs (5-35 words) to keep it natural
        word_count = len(re.findall(r"\b\w+\b", inner_lower))
        if not (5 <= word_count <= 35):
            return p_html
        starter = starters[starter_index % len(starters)]
        starter_index += 1
        needed -= 1
        # Lowercase the first letter of the original if it's a capital (we're prepending)
        stripped = inner.lstrip()
        if stripped and stripped[0].isupper():
            inner = inner[: len(inner) - len(stripped)] + stripped[0].lower() + stripped[1:]
        return open_tag + starter + inner + close_tag

    # Apply paragraph by paragraph
    result = re.sub(
        r"(<p[^>]*>.*?</p>)",
        lambda m: _inject_into_paragraph(m.group(0)),
        markdown,
        flags=re.DOTALL,
    )
    return result


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
<figure class="seo-machine-table"><table><caption>Comparison: Manual SEO vs Agentic SEO Workflow</caption><thead><tr><th scope="col">Workflow</th><th scope="col">Manual SEO</th><th scope="col">Agentic SEO</th></tr></thead><tbody><tr><td>Research</td><td>Spreadsheet-led and slow</td><td>Scored opportunities</td></tr><tr><td>Drafting</td><td>One-off briefs</td><td>Context-aware generation</td></tr><tr><td>Optimization</td><td>Manual plugin checks</td><td>Pre-publish quality gate</td></tr></tbody></table></figure>
<!-- /wp:html -->""",
        """<!-- wp:html -->
<section class="seo-machine-chart" aria-label="SEO content workflow chart"><h2>Autonomous SEO Workflow</h2><ol><li><strong>Discover</strong><span style="width:72%"></span></li><li><strong>Research</strong><span style="width:84%"></span></li><li><strong>Create</strong><span style="width:78%"></span></li><li><strong>Optimize</strong><span style="width:90%"></span></li><li><strong>Publish</strong><span style="width:68%"></span></li></ol></section>
<!-- /wp:html -->""",
        f"""<!-- seo-machine-faq -->
<!-- wp:heading {{"level":2}} -->
<h2>FAQ: {focus_keyphrase}</h2>
<!-- /wp:heading -->

<!-- wp:yoast/faq-block -->
<div class="schema-faq wp-block-yoast-faq-block">
  <!-- wp:yoast/faq-question {{"questionName":"What does it automate?"}} -->
  <div class="schema-faq-section">
    <strong class="schema-faq-question">What does it automate?</strong>
    <!-- wp:paragraph -->
    <p class="schema-faq-answer">It automates opportunity research, content creation, on-page optimization, publishing preparation, and monitoring.</p>
    <!-- /wp:paragraph -->
  </div>
  <!-- /wp:yoast/faq-question -->

  <!-- wp:yoast/faq-question {{"questionName":"Does it replace strategy?"}} -->
  <div class="schema-faq-section">
    <strong class="schema-faq-question">Does it replace strategy?</strong>
    <!-- wp:paragraph -->
    <p class="schema-faq-answer">No. It handles repeatable execution so humans can focus on positioning, evidence, and quality control.</p>
    <!-- /wp:paragraph -->
  </div>
  <!-- /wp:yoast/faq-question -->
</div>
<!-- /wp:yoast/faq-block -->""",
        """<!-- wp:html -->
<aside class="seo-machine-related" aria-label="Related articles"><h2>Related Articles</h2><ul><li><a href="https://blog.meetlyra.app/">MeetLyra blog</a></li><li><a href="https://waitlist.meetlyra.app">MeetLyra marketing workflow</a></li></ul></aside>
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
    items = [match.group(1).strip() for match in re.finditer(r"^##\s+(.+)$", markdown or "", flags=re.MULTILINE)]
    if not items:
        items = [_plain_text(match.group(1)).strip() for match in re.finditer(r"<h2\b[^>]*>(.*?)</h2>", markdown or "", flags=re.IGNORECASE | re.DOTALL)]
    return items


def _rich_block_marker(block: str) -> str:
    match = re.search(r"seo-machine-[a-z0-9-]+", block)
    return match.group(0) if match else block[:40]


def _insert_blocks_throughout(markdown: str, blocks: list[str]) -> str:
    section_matches = list(re.finditer(r"^##\s+.+$", markdown or "", flags=re.MULTILINE))
    if not section_matches:
        section_matches = list(re.finditer(r"<h[2-6]\b[^>]*>.*?</h[2-6]>", markdown or "", flags=re.IGNORECASE))
        
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
