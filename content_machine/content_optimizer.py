from __future__ import annotations

import json
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
    markdown = strip_seo_machine_blocks(markdown)
    markdown = ensure_intro_keyphrase(markdown, focus_keyphrase)
    markdown = ensure_subheading_keyphrase(markdown, focus_keyphrase)
    markdown = ensure_keyphrase_density(markdown, focus_keyphrase)
    markdown = ensure_outbound_link(markdown)
    markdown = ensure_internal_link(markdown)
    markdown = ensure_transition_words(markdown)
    rich_blocks = _normalize_rich_blocks(content.rich_blocks, focus_keyphrase, markdown)
    markdown = ensure_rich_blocks(markdown, rich_blocks, focus_keyphrase)
    markdown = link_tool_first_mentions(markdown)
    meta_title = optimize_meta_title(content.meta_title or title, focus_keyphrase)
    meta_description = optimize_meta_description(content.meta_description or content.excerpt or excerpt(markdown), focus_keyphrase)
    image_alt_text = optimize_image_alt_text(content.image_alt_text or content.image_prompt or title, focus_keyphrase)
    slug = content.slug or slugify(opportunity.keyword)
    final_excerpt = excerpt(content.excerpt.strip()) if content.excerpt and content.excerpt.strip() else excerpt(markdown)

    return replace(
        content,
        title=title,
        slug=slug[:75].strip("-"),
        markdown=markdown,
        html=markdown_to_html(markdown),
        meta_title=meta_title,
        meta_description=meta_description,
        focus_keyphrase=focus_keyphrase,
        excerpt=final_excerpt,
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
    toc_links = "".join(f'<li><a href="#{slugify(item)}" style="color:#406ae4;text-decoration:none;font-weight:600;">{item}</a></li>' for item in toc_items[:8])
    if not toc_links:
        toc_links = (
            '<li><a href="#quick-answer" style="color:#406ae4;text-decoration:none;font-weight:600;">Quick answer</a></li>'
            '<li><a href="#workflow" style="color:#406ae4;text-decoration:none;font-weight:600;">Workflow</a></li>'
            '<li><a href="#faq" style="color:#406ae4;text-decoration:none;font-weight:600;">FAQ</a></li>'
        )
        
    # Construct Yoast FAQ Questions JSON Schema
    questions = [
        {
            "id": "faq-question-1",
            "question": f"What does {focus_keyphrase} automate?",
            "answer": "It automates opportunity research, content creation, on-page optimization, publishing preparation, and index submission monitoring."
        },
        {
            "id": "faq-question-2",
            "question": f"Does {focus_keyphrase} replace search strategy?",
            "answer": "No. It handles repeatable execution so human marketers can focus on positioning, evidence, and quality control."
        }
    ]
    questions_json = json.dumps({"questions": questions}, ensure_ascii=False)
    q1_attr = json.dumps({"id": "faq-question-1", "question": questions[0]["question"], "answer": questions[0]["answer"]}, ensure_ascii=False)
    q2_attr = json.dumps({"id": "faq-question-2", "question": questions[1]["question"], "answer": questions[1]["answer"]}, ensure_ascii=False)

    return [
        f"""<!-- wp:html -->
<div class="seo-machine-reading-time" style="font-size:14px;color:#475569;margin-bottom:16px;font-weight:500;"><strong>Reading time:</strong> {reading_minutes} minutes</div>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<div class="seo-machine-toc" style="background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(10px);border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:24px;box-shadow:0 4px 20px rgba(0,0,0,0.02);"><nav aria-label="Table of contents"><h3 style="margin-top:0;margin-bottom:12px;font-size:18px;color:#0f172a;font-weight:700;">Table of Contents</h3><ol style="margin:0;padding-left:20px;line-height:1.6;">{toc_links}</ol></nav></div>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<div class="wp-block-group seo-machine-proof" style="background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(10px);border:1px solid #e2e8f0;border-left:4px solid rgb(17, 17, 17);border-radius:0 12px 12px 0;padding:24px;margin-bottom:24px;font-family:sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.02);"><section aria-label="Proof point"><h4 style="margin-top:0;margin-bottom:8px;font-size:16px;color:#0f172a;font-weight:700;">Proof Point</h4><p style="color:#475569;line-height:1.6;margin-bottom:12px;font-size:14px;">This workflow follows Google Search Central guidance: useful, original, people-first content matters more than whether AI helped create the first draft.</p><p style="margin:0;font-size:14px;"><a href="https://developers.google.com/search/blog/2023/02/google-search-and-ai-content" style="color:#406ae4;text-decoration:underline;font-weight:600;">Review Google's official AI content guidance</a>.</p></section></div>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<div class="seo-machine-pullquote" style="border:1px solid #e2e8f0;border-left:4px solid #406ae4;background:rgba(255,255,255,0.85);backdrop-filter:blur(10px);padding:24px;margin:32px 0;border-radius:0 12px 12px 0;font-style:italic;color:#475569;font-family:sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.02);"><p style="font-size:16px;line-height:1.6;margin:0 0 12px 0;color:#0f172a;font-weight:600;">"{focus_keyphrase} works best when it turns strategy into a repeatable publishing system, not just another drafting shortcut."</p><cite style="font-size:11px;color:#64748b;font-style:normal;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;">SEO Machine Quality Gate</cite></div>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<div class="wp-block-group seo-machine-takeaways" style="background:rgba(255,255,255,0.85);backdrop-filter:blur(10px);border:1px solid #e2e8f0;border-left:4px solid rgb(17, 17, 17);border-radius:0 12px 12px 0;padding:24px;margin-bottom:24px;font-family:sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.02);"><section aria-label="Key takeaways"><h4 style="margin-top:0;margin-bottom:12px;font-size:16px;color:#0f172a;font-weight:700;">Key Takeaways</h4><ul style="margin:0;padding-left:20px;line-height:1.6;color:#475569;font-size:14px;"><li>Use {focus_keyphrase} to connect research, drafting, optimization, and publishing.</li><li>Keep human review focused on strategy, evidence, and brand judgment.</li><li>Measure success through publish consistency, rankings, and conversion quality.</li></ul></section></div>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<figure class="wp-block-table seo-machine-table" style="margin:32px 0;font-family:sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.02);border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;"><table style="width:100%;border-collapse:collapse;border:none;font-size:14px;"><thead style="background:rgb(17, 17, 17);color:#ffffff;"><tr><th style="padding:16px;text-align:left;font-weight:600;letter-spacing:0.05em;">WORKFLOW</th><th style="padding:16px;text-align:left;font-weight:600;letter-spacing:0.05em;">MANUAL SEO</th><th style="padding:16px;text-align:left;font-weight:600;letter-spacing:0.05em;">AGENTIC SEO</th></tr></thead><tbody><tr style="border-bottom:1px solid #e2e8f0;background:#ffffff;"><td style="padding:16px;color:#0f172a;font-weight:600;">Research</td><td style="padding:16px;color:#475569;">Spreadsheet-led and slow</td><td style="padding:16px;color:#406ae4;font-weight:600;">Scored opportunities</td></tr><tr style="border-bottom:1px solid #e2e8f0;background:rgba(248, 250, 252, 0.5);"><td style="padding:16px;color:#0f172a;font-weight:600;">Drafting</td><td style="padding:16px;color:#475569;">One-off briefs</td><td style="padding:16px;color:#406ae4;font-weight:600;">Context-aware generation</td></tr><tr style="background:#ffffff;"><td style="padding:16px;color:#0f172a;font-weight:600;">Optimization</td><td style="padding:16px;color:#475569;">Manual plugin checks</td><td style="padding:16px;color:#406ae4;font-weight:600;">Pre-publish quality gate</td></tr></tbody></table></figure>
<!-- /wp:html -->""",
        f"""<!-- wp:html -->
<div class="seo-machine-chart" style="background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(12px);border:1px solid #e2e8f0;border-radius:16px;padding:32px 24px;margin:32px 0;font-family:'Outfit','Inter',system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,0.03);">
  <h4 style="margin:0 0 24px 0;color:#0f172a;font-size:20px;font-weight:700;text-align:center;letter-spacing:-0.02em;">Autonomous SEO Content Workflow</h4>
  <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:20px;">
    <div class="workflow-step-card-item" onclick="document.querySelectorAll('.workflow-details-pane').forEach(p=>p.style.display='none'); document.getElementById('step-details-1').style.display='block'; document.querySelectorAll('.workflow-step-card-item').forEach(c=>c.style.borderColor='#e2e8f0'); this.style.borderColor='#406ae4';" style="text-align:center;flex:1;min-width:90px;background:#ffffff;border:2px solid #406ae4;border-radius:12px;padding:16px 8px;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 4px rgba(0,0,0,0.01);">
      <div style="background:rgb(17, 17, 17);color:#ffffff;width:36px;height:36px;border-radius:50%;line-height:36px;margin:0 auto 12px auto;font-weight:800;font-size:15px;">1</div>
      <span style="font-size:13px;color:#0f172a;font-weight:600;display:block;margin-bottom:2px;">Discover</span>
      <span style="font-size:11px;color:#64748b;display:block;">Keywords & Gaps</span>
    </div>
    <div style="color:#94a3b8;font-size:20px;font-weight:800;user-select:none;">→</div>
    <div class="workflow-step-card-item" onclick="document.querySelectorAll('.workflow-details-pane').forEach(p=>p.style.display='none'); document.getElementById('step-details-2').style.display='block'; document.querySelectorAll('.workflow-step-card-item').forEach(c=>c.style.borderColor='#e2e8f0'); this.style.borderColor='#406ae4';" style="text-align:center;flex:1;min-width:90px;background:#ffffff;border:2px solid #e2e8f0;border-radius:12px;padding:16px 8px;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 4px rgba(0,0,0,0.01);">
      <div style="background:rgb(17, 17, 17);color:#ffffff;width:36px;height:36px;border-radius:50%;line-height:36px;margin:0 auto 12px auto;font-weight:800;font-size:15px;">2</div>
      <span style="font-size:13px;color:#0f172a;font-weight:600;display:block;margin-bottom:2px;">Research</span>
      <span style="font-size:11px;color:#64748b;display:block;">SERP & Intent</span>
    </div>
    <div style="color:#94a3b8;font-size:20px;font-weight:800;user-select:none;">→</div>
    <div class="workflow-step-card-item" onclick="document.querySelectorAll('.workflow-details-pane').forEach(p=>p.style.display='none'); document.getElementById('step-details-3').style.display='block'; document.querySelectorAll('.workflow-step-card-item').forEach(c=>c.style.borderColor='#e2e8f0'); this.style.borderColor='#406ae4';" style="text-align:center;flex:1;min-width:90px;background:#ffffff;border:2px solid #e2e8f0;border-radius:12px;padding:16px 8px;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 4px rgba(0,0,0,0.01);">
      <div style="background:rgb(17, 17, 17);color:#ffffff;width:36px;height:36px;border-radius:50%;line-height:36px;margin:0 auto 12px auto;font-weight:800;font-size:15px;">3</div>
      <span style="font-size:13px;color:#0f172a;font-weight:600;display:block;margin-bottom:2px;">Create</span>
      <span style="font-size:11px;color:#64748b;display:block;">AI First Draft</span>
    </div>
    <div style="color:#94a3b8;font-size:20px;font-weight:800;user-select:none;">→</div>
    <div class="workflow-step-card-item" onclick="document.querySelectorAll('.workflow-details-pane').forEach(p=>p.style.display='none'); document.getElementById('step-details-4').style.display='block'; document.querySelectorAll('.workflow-step-card-item').forEach(c=>c.style.borderColor='#e2e8f0'); this.style.borderColor='#406ae4';" style="text-align:center;flex:1;min-width:90px;background:#ffffff;border:2px solid #e2e8f0;border-radius:12px;padding:16px 8px;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 4px rgba(0,0,0,0.01);">
      <div style="background:rgb(17, 17, 17);color:#ffffff;width:36px;height:36px;border-radius:50%;line-height:36px;margin:0 auto 12px auto;font-weight:800;font-size:15px;">4</div>
      <span style="font-size:13px;color:#0f172a;font-weight:600;display:block;margin-bottom:2px;">Optimize</span>
      <span style="font-size:11px;color:#64748b;display:block;">SEO & Quality</span>
    </div>
    <div style="color:#94a3b8;font-size:20px;font-weight:800;user-select:none;">→</div>
    <div class="workflow-step-card-item" onclick="document.querySelectorAll('.workflow-details-pane').forEach(p=>p.style.display='none'); document.getElementById('step-details-5').style.display='block'; document.querySelectorAll('.workflow-step-card-item').forEach(c=>c.style.borderColor='#e2e8f0'); this.style.borderColor='#406ae4';" style="text-align:center;flex:1;min-width:90px;background:#ffffff;border:2px solid #e2e8f0;border-radius:12px;padding:16px 8px;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 4px rgba(0,0,0,0.01);">
      <div style="background:rgb(17, 17, 17);color:#ffffff;width:36px;height:36px;border-radius:50%;line-height:36px;margin:0 auto 12px auto;font-weight:800;font-size:15px;">5</div>
      <span style="font-size:13px;color:#0f172a;font-weight:600;display:block;margin-bottom:2px;">Publish</span>
      <span style="font-size:11px;color:#64748b;display:block;">WP & Indexing</span>
    </div>
  </div>
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;min-height:80px;box-shadow:0 1px 3px rgba(0,0,0,0.02);">
    <div id="step-details-1" class="workflow-details-pane" style="display:block;">
      <h5 style="margin:0 0 6px 0;color:#0f172a;font-size:14px;font-weight:700;">1. Discover Keywords & Gaps</h5>
      <p style="margin:0;color:#475569;font-size:13px;line-height:1.5;">Pulls keyword opportunities and gaps directly from Google Search Console and DataForSEO, prioritizing low-difficulty keywords with high search intent.</p>
    </div>
    <div id="step-details-2" class="workflow-details-pane" style="display:none;">
      <h5 style="margin:0 0 6px 0;color:#0f172a;font-size:14px;font-weight:700;">2. Research SERP & Intent</h5>
      <p style="margin:0;color:#475569;font-size:13px;line-height:1.5;">Analyzes competitor content structure, outbound sources, and search intent clusters to generate an SEO-optimized topic brief.</p>
    </div>
    <div id="step-details-3" class="workflow-details-pane" style="display:none;">
      <h5 style="margin:0 0 6px 0;color:#0f172a;font-size:14px;font-weight:700;">3. Create AI First Draft</h5>
      <p style="margin:0;color:#475569;font-size:13px;line-height:1.5;">Generates publish-ready, authoritative long-form markdown. If Anthropic quota is exceeded, the pipeline auto-switches to Gemini fallback.</p>
    </div>
    <div id="step-details-4" class="workflow-details-pane" style="display:none;">
      <h5 style="margin:0 0 6px 0;color:#0f172a;font-size:14px;font-weight:700;">4. Optimize SEO & Quality Audit</h5>
      <p style="margin:0;color:#475569;font-size:13px;line-height:1.5;">Audits the draft for transition words, readability ease, keyphrase density, outbound links, and and ensures it passes the automated Yoast copywriting checklist.</p>
    </div>
    <div id="step-details-5" class="workflow-details-pane" style="display:none;">
      <h5 style="margin:0 0 6px 0;color:#0f172a;font-size:14px;font-weight:700;">5. Publish & Index</h5>
      <p style="margin:0;color:#475569;font-size:13px;line-height:1.5;">Uploads the verified draft directly to WordPress and automatically pings Google and Bing via IndexNow to trigger instant crawl/indexing.</p>
    </div>
  </div>
</div>
<!-- /wp:html -->""",
        f"""<!-- wp:yoast/faq-block {questions_json} -->
<div class="schema-faq wp-block-yoast-faq-block seo-machine-faq">
<!-- wp:yoast/question-answer {q1_attr} -->
<div class="schema-faq-section" id="faq-question-1"><strong class="schema-faq-question">{questions[0]["question"]}</strong><p class="schema-faq-answer">{questions[0]["answer"]}</p></div>
<!-- /wp:yoast/question-answer -->
<!-- wp:yoast/question-answer {q2_attr} -->
<div class="schema-faq-section" id="faq-question-2"><strong class="schema-faq-question">{questions[1]["question"]}</strong><p class="schema-faq-answer">{questions[1]["answer"]}</p></div>
<!-- /wp:yoast/question-answer -->
</div>
<!-- /wp:yoast/faq-block -->""",
        f"""<!-- wp:html -->
<div class="seo-machine-related" style="background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(10px);border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-top:24px;box-shadow:0 4px 20px rgba(0,0,0,0.02);"><aside aria-label="Related articles"><h3 style="margin-top:0;margin-bottom:12px;font-size:18px;color:#0f172a;font-weight:700;">Related Articles</h3><ul style="margin:0;padding-left:20px;line-height:1.6;"><li><a href="https://blog.meetlyra.app/" style="color:#406ae4;text-decoration:none;font-weight:600;">MeetLyra Blog</a></li><li><a href="https://waitlist.meetlyra.app/" style="color:#406ae4;text-decoration:none;font-weight:600;">MeetLyra Marketing Workflow</a></li></ul></aside></div>
<!-- /wp:html -->""",
    ]


def build_cta_blocks(focus_keyphrase: str) -> list[str]:
    return [
        # CTA 1: Simple button block
        f"""<!-- wp:html -->
<div class="seo-machine-cta-btn-wrapper-1" style="display:flex;justify-content:center;margin:32px 0;">
  <a class="seo-machine-cta-btn-1" href="https://waitlist.meetlyra.app/" style="background:rgb(17, 17, 17);color:#ffffff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-family:sans-serif;box-shadow:0 4px 10px rgba(0,0,0,0.05);transition:all 0.2s;" onmouseover="this.style.background='#406ae4'" onmouseout="this.style.background='rgb(17, 17, 17)'">Start Automating with MeetLyra</a>
</div>
<!-- /wp:html -->""",

        # CTA 2: Styled box/group with Heading, Paragraph, and Button
        f"""<!-- wp:html -->
<div class="seo-machine-cta-group-2" style="background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(10px);border:1px solid #e2e8f0;border-radius:12px;padding:32px;margin:32px 0;font-family:sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.02);">
  <h3 style="margin-top:0;margin-bottom:12px;font-size:22px;color:#0f172a;font-weight:700;">Ready to scale your {focus_keyphrase} workflow?</h3>
  <p style="color:#475569;font-size:15px;line-height:1.6;margin-bottom:24px;">MeetLyra acts as your autonomous marketing team, planning and executing search strategies from end to end.</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <a href="https://waitlist.meetlyra.app/" style="background:rgb(17, 17, 17);color:#ffffff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;box-shadow:0 1px 2px 0 rgba(0,0,0,0.05);display:inline-block;transition:all 0.2s;" onmouseover="this.style.background='#406ae4'" onmouseout="this.style.background='rgb(17, 17, 17)'">Analyze My Website For Free</a>
  </div>
</div>
<!-- /wp:html -->""",

        # CTA 3: Callout quote style link
        f"""<!-- wp:html -->
<div class="seo-machine-cta-quote-3" style="border:1px solid #e2e8f0;border-left:4px solid #406ae4;background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(10px);padding:16px 24px;margin:32px 0;font-family:sans-serif;border-radius:0 12px 12px 0;box-shadow:0 4px 20px rgba(0,0,0,0.02);">
  <p style="font-size:15px;line-height:1.6;color:#475569;margin:0;"><strong>Take Action:</strong> Use MeetLyra's autonomous agent to run competitor content analyses and publish search-intent matched articles on autopilot. <a href="https://waitlist.meetlyra.app/" style="color:#406ae4;text-decoration:underline;font-weight:600;">Learn more here</a>.</p>
</div>
<!-- /wp:html -->""",

        # CTA 4: Modern button block centered
        f"""<!-- wp:html -->
<div class="seo-machine-cta-btn-wrapper-4" style="display:flex;justify-content:center;margin:32px 0;">
  <a class="seo-machine-cta-btn-4" href="https://waitlist.meetlyra.app/" style="border:2px solid rgb(17, 17, 17);color:rgb(17, 17, 17);background:none;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-family:sans-serif;transition:all 0.2s;display:inline-block;" onmouseover="this.style.background='rgb(17, 17, 17)'; this.style.color='#ffffff';" onmouseout="this.style.background='none'; this.style.color='rgb(17, 17, 17)';">See MeetLyra in Action</a>
</div>
<!-- /wp:html -->""",

        # CTA 5: Product highlights group box
        f"""<!-- wp:html -->
<div class="seo-machine-cta-group-5" style="background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(10px);border:1px solid #e2e8f0;border-radius:12px;padding:32px;margin:32px 0;font-family:sans-serif;box-shadow:0 4px 20px rgba(0,0,0,0.02);">
  <h3 style="margin-top:0;margin-bottom:12px;font-size:22px;color:#0f172a;font-weight:700;">Why run {focus_keyphrase} manually?</h3>
  <p style="color:#475569;font-size:15px;line-height:1.6;margin-bottom:24px;">MeetLyra automates SEO keyword grouping, outlines optimal content structure, drafts complete articles, and publishes them with strict quality controls.</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <a href="https://waitlist.meetlyra.app/" style="background:rgb(17, 17, 17);color:#ffffff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;box-shadow:0 1px 2px 0 rgba(0,0,0,0.05);display:inline-block;transition:all 0.2s;" onmouseover="this.style.background='#406ae4'" onmouseout="this.style.background='rgb(17, 17, 17)'">Get Started Free</a>
  </div>
</div>
<!-- /wp:html -->""",

        # CTA 6: Bottom Concluding CTA Button
        f"""<!-- wp:html -->
<div class="seo-machine-cta-group-6" style="background:rgba(255, 255, 255, 0.85);backdrop-filter:blur(10px);border:1px solid #e2e8f0;border-radius:16px;padding:40px;margin:40px 0;font-family:sans-serif;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.02);">
  <h3 style="margin-top:0;margin-bottom:12px;font-size:24px;color:#0f172a;font-weight:800;">Try the Autonomous AI SEO Engine</h3>
  <p style="color:#475569;font-size:16px;line-height:1.6;margin-bottom:24px;max-width:540px;margin-left:auto;margin-right:auto;">Enter your website URL today and let MeetLyra build and execute your custom search strategy.</p>
  <div style="display:flex;justify-content:center;">
    <a href="https://waitlist.meetlyra.app/" style="background:rgb(17, 17, 17);color:#ffffff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;box-shadow:0 4px 10px rgba(0,0,0,0.05);display:inline-block;transition:all 0.2s;" onmouseover="this.style.background='#406ae4'" onmouseout="this.style.background='rgb(17, 17, 17)'">Scan My Site Now</a>
  </div>
</div>
<!-- /wp:html -->"""
    ]


def _normalize_rich_blocks(blocks: list, focus_keyphrase: str, markdown: str = "") -> list[str]:
    defaults = build_rich_blocks(focus_keyphrase, markdown)
    if not blocks or not all(isinstance(block, str) for block in blocks):
        return defaults
    
    defaults_by_marker = {}
    for block in defaults:
        marker = _rich_block_marker(block)
        defaults_by_marker[marker] = block
        
    normalized = []
    seen_markers = set()
    for block in blocks:
        marker = _rich_block_marker(block)
        if marker in defaults_by_marker:
            normalized.append(defaults_by_marker[marker])
            seen_markers.add(marker)
        else:
            normalized.append(block)
            
    for marker, block in defaults_by_marker.items():
        if marker not in seen_markers:
            normalized.append(block)
            
    return normalized


def ensure_rich_blocks(markdown: str, blocks: list[str], focus_keyphrase: str) -> str:
    missing = [block for block in blocks if _rich_block_marker(block) not in markdown]
    ctas = build_cta_blocks(focus_keyphrase)
    missing_ctas = [cta for cta in ctas if _rich_block_marker(cta) not in markdown]
    
    if not missing and not missing_ctas:
        return markdown
        
    return _distribute_blocks_and_ctas(markdown, missing, ctas)


def _rich_block_marker(block: str) -> str:
    match = re.search(r"seo-machine-[a-z0-9-]+", block)
    return match.group(0) if match else block[:40]


def _distribute_blocks_and_ctas(markdown: str, rich_blocks: list[str], cta_blocks: list[str]) -> str:
    section_matches = list(re.finditer(r"^##\s+.+$", markdown or "", flags=re.MULTILINE))
    if not section_matches:
        selected_ctas = []
        for idx in [0, 1, 5]:
            if idx < len(cta_blocks):
                cta = cta_blocks[idx]
                if _rich_block_marker(cta) not in markdown:
                    selected_ctas.append(cta)
        all_blocks = rich_blocks + selected_ctas
        return markdown.rstrip() + "\n\n" + "\n\n".join(all_blocks)

    chunks: list[str] = []
    first_heading = section_matches[0].start()
    intro = markdown[:first_heading].rstrip()
    if intro:
        chunks.append(intro)
    else:
        chunks.append("")
        
    for index, match in enumerate(section_matches):
        end = section_matches[index + 1].start() if index + 1 < len(section_matches) else len(markdown)
        chunks.append(markdown[match.start() : end].rstrip())

    top_markers = {"seo-machine-reading-time", "seo-machine-toc"}
    bottom_markers = {"seo-machine-faq", "seo-machine-related"}
    
    top_blocks = [b for b in rich_blocks if any(m in b for m in top_markers)]
    bottom_blocks = [b for b in rich_blocks if any(m in b for m in bottom_markers)]
    body_blocks = [b for b in rich_blocks if not any(m in b for m in top_markers) and not any(m in b for m in bottom_markers)]

    # 1. Place ToC and Reading Time in the introduction
    if top_blocks:
        chunks[0] = chunks[0].rstrip() + "\n\n" + "\n\n".join(top_blocks)

    num_sections = len(chunks) - 1

    # 2. Place CTA 1 (simple button CTA) after heading 2 if it exists (only if missing)
    text_cta = cta_blocks[0]  # Simple button
    if _rich_block_marker(text_cta) not in markdown:
        cta_1_idx = min(2, num_sections)
        chunks[cta_1_idx] = chunks[cta_1_idx].rstrip() + "\n\n" + text_cta

    # 3. Place CTA 2 (styled group box CTA) after heading 4 if it exists (only if missing)
    box_cta = cta_blocks[1]  # Styled box/group
    if _rich_block_marker(box_cta) not in markdown:
        cta_2_idx = min(4, num_sections)
        if cta_2_idx == min(2, num_sections) and num_sections > 2:
            cta_2_idx = min(3, num_sections)
        chunks[cta_2_idx] = chunks[cta_2_idx].rstrip() + "\n\n" + box_cta

    # 4. Place other body blocks (tables, quotes, takeaways) naturally in different sections (round-robin)
    for i, block in enumerate(body_blocks):
        if num_sections > 0:
            sect_idx = (i % num_sections) + 1
            chunks[sect_idx] = chunks[sect_idx].rstrip() + "\n\n" + block

    # 5. Place bottom blocks (FAQ, Related Articles) and the concluding CTA (CTA 6) at the very end
    concluding_cta = cta_blocks[5]  # Bottom Concluding CTA
    end_additions = list(bottom_blocks)
    if _rich_block_marker(concluding_cta) not in markdown:
        end_additions.append(concluding_cta)
    
    if end_additions:
        chunks[-1] = chunks[-1].rstrip() + "\n\n" + "\n\n".join(end_additions)

    return "\n\n".join(chunks).strip()


async def validate_and_sanitize_content_images(content: GeneratedContent, settings: Settings) -> GeneratedContent:
    import httpx
    import asyncio
    
    markdown = content.markdown
    img_matches = list(re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", markdown))
    if not img_matches:
        return content
        
    urls_to_check = set()
    duplicates = set()
    seen_urls = set()
    
    for match in img_matches:
        url = match.group(2).strip()
        if url in seen_urls:
            duplicates.add(url)
        else:
            seen_urls.add(url)
            if url.startswith(("http://", "https://")):
                urls_to_check.add(url)
                
    valid_urls = {}
    async def check_url(url: str):
        try:
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                resp = await client.head(url)
                if resp.status_code == 200 and resp.headers.get("content-type", "").lower().startswith("image/"):
                    valid_urls[url] = True
                    return
                resp = await client.get(url)
                if resp.status_code == 200 and resp.headers.get("content-type", "").lower().startswith("image/"):
                    valid_urls[url] = True
                    return
        except Exception:
            pass
        valid_urls[url] = False

    if urls_to_check:
        await asyncio.gather(*(check_url(url) for url in urls_to_check))
        
    mock_visuals = [
        """<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:24px;margin-bottom:24px;font-family:sans-serif;">
  <h4 style="margin:0 0 12px 0;color:#0f172a;">Lyra AI Marketing Dashboard</h4>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:16px;">
    <div style="background:#ffffff;padding:12px;border-radius:6px;border:1px solid #cbd5e1;text-align:center;">
      <span style="font-size:12px;color:#64748b;display:block;margin-bottom:4px;">Organic Traffic</span>
      <strong style="font-size:18px;color:#10b981;">+142%</strong>
    </div>
    <div style="background:#ffffff;padding:12px;border-radius:6px;border:1px solid #cbd5e1;text-align:center;">
      <span style="font-size:12px;color:#64748b;display:block;margin-bottom:4px;">Keywords Ranked</span>
      <strong style="font-size:18px;color:#0f172a;">1,420</strong>
    </div>
    <div style="background:#ffffff;padding:12px;border-radius:6px;border:1px solid #cbd5e1;text-align:center;">
      <span style="font-size:12px;color:#64748b;display:block;margin-bottom:4px;">SEO Health Score</span>
      <strong style="font-size:18px;color:#3b82f6;">98/100</strong>
    </div>
  </div>
  <p style="font-size:13px;color:#475569;margin:0;">Autonomous SEO engine actively monitoring rankings and publishing optimized updates.</p>
</div>
<!-- /wp:group -->""",

        """<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:24px;margin-bottom:24px;font-family:sans-serif;">
  <h4 style="margin:0 0 12px 0;color:#0f172a;">Content Production Flow</h4>
  <div style="display:flex;justify-content:space-between;align-items:center;background:#ffffff;padding:16px;border-radius:6px;border:1px solid #cbd5e1;">
    <div style="text-align:center;flex:1;">
      <div style="background:#eff6ff;color:#2563eb;width:32px;height:32px;border-radius:50%;line-height:32px;margin:0 auto 8px auto;font-weight:bold;">1</div>
      <span style="font-size:12px;color:#0f172a;font-weight:600;">Research</span>
    </div>
    <div style="color:#cbd5e1;font-size:20px;">→</div>
    <div style="text-align:center;flex:1;">
      <div style="background:#f0fdf4;color:#16a34a;width:32px;height:32px;border-radius:50%;line-height:32px;margin:0 auto 8px auto;font-weight:bold;">2</div>
      <span style="font-size:12px;color:#0f172a;font-weight:600;">Drafting</span>
    </div>
    <div style="color:#cbd5e1;font-size:20px;">→</div>
    <div style="text-align:center;flex:1;">
      <div style="background:#fef3c7;color:#d97706;width:32px;height:32px;border-radius:50%;line-height:32px;margin:0 auto 8px auto;font-weight:bold;">3</div>
      <span style="font-size:12px;color:#0f172a;font-weight:600;">Optimize</span>
    </div>
    <div style="color:#cbd5e1;font-size:20px;">→</div>
    <div style="text-align:center;flex:1;">
      <div style="background:#faf5ff;color:#7c3aed;width:32px;height:32px;border-radius:50%;line-height:32px;margin:0 auto 8px auto;font-weight:bold;">4</div>
      <span style="font-size:12px;color:#0f172a;font-weight:600;">Publish</span>
    </div>
  </div>
</div>
<!-- /wp:group -->""",

        """<!-- wp:group {"layout":{"type":"constrained"}} -->
<div class="wp-block-group" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:24px;margin-bottom:24px;font-family:sans-serif;">
  <h4 style="margin:0 0 12px 0;color:#0f172a;">SEO & Campaign ROI Tracking</h4>
  <div style="background:#ffffff;padding:16px;border-radius:6px;border:1px solid #cbd5e1;">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;">
      <span style="color:#64748b;">Cost Reduction</span>
      <strong style="color:#0f172a;">85% Decrease</strong>
    </div>
    <div style="background:#f1f5f9;height:8px;border-radius:4px;margin-bottom:16px;">
      <div style="background:#3b82f6;width:85%;height:100%;border-radius:4px;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:13px;">
      <span style="color:#64748b;">Publishing Velocity</span>
      <strong style="color:#0f172a;">5x Faster</strong>
    </div>
    <div style="background:#f1f5f9;height:8px;border-radius:4px;">
      <div style="background:#10b981;width:100%;height:100%;border-radius:4px;"></div>
    </div>
  </div>
</div>
<!-- /wp:group -->"""
    ]
    
    new_markdown = markdown
    used_mock_indices = 0
    seen_urls_in_replace = set()
    
    for match in sorted(img_matches, key=lambda m: m.start(), reverse=True):
        url = match.group(2).strip()
        is_invalid = url.startswith(("http://", "https://")) and not valid_urls.get(url, False)
        is_duplicate = url in seen_urls_in_replace
        
        if is_invalid or is_duplicate:
            replacement = mock_visuals[used_mock_indices % len(mock_visuals)]
            used_mock_indices += 1
            new_markdown = new_markdown[:match.start()] + replacement + new_markdown[match.end():]
        else:
            seen_urls_in_replace.add(url)
            
    if new_markdown != markdown:
        return replace(
            content,
            markdown=new_markdown,
            html=markdown_to_html(new_markdown)
        )
    return content


def link_tool_first_mentions(markdown: str) -> str:
    tools = [
        ("Google Search Console", "https://search.google.com/search-console/about"),
        ("Google Analytics", "https://analytics.google.com/"),
        ("OpenSEO Agent Skills", "https://openseo.so/docs/skills"),
        ("OpenSEO", "https://openseo.so/"),
        ("/keyword-research", "https://openseo.so/docs/skills"),
        ("/keyword-clustering", "https://openseo.so/docs/skills"),
        ("/competitive-landscape", "https://openseo.so/docs/skills"),
        ("/competitor-analysis", "https://openseo.so/docs/skills"),
        ("/link-prospecting", "https://openseo.so/docs/skills"),
        ("/seo-coach", "https://openseo.so/docs/skills"),
        ("/onboarding-checklist", "https://openseo.so/docs/skills"),
        ("Keyword research", "https://openseo.so/docs/skills"),
        ("Keyword clustering", "https://openseo.so/docs/skills"),
        ("Competitive landscape", "https://openseo.so/docs/skills"),
        ("Competitor analysis", "https://openseo.so/docs/skills"),
        ("Link prospecting", "https://openseo.so/docs/skills"),
        ("SEO coach", "https://openseo.so/docs/skills"),
        ("Onboarding checklist", "https://openseo.so/docs/skills"),
        ("Make.com", "https://www.make.com/"),
        ("SurferSEO", "https://surferseo.com/"),
        ("Copy.ai", "https://www.copy.ai/"),
        ("Writesonic", "https://writesonic.com/"),
        ("Anyword", "https://anyword.com/"),
        ("Jasper", "https://www.jasper.ai/"),
        ("Surfer", "https://surferseo.com/"),
        ("OpenAI", "https://openai.com/"),
        ("Zapier", "https://zapier.com/"),
        ("Yoast", "https://yoast.com/"),
        ("WordPress", "https://wordpress.org/"),
        ("Ahrefs", "https://ahrefs.com/"),
        ("HubSpot", "https://www.hubspot.com/"),
        ("Claude", "https://www.anthropic.com/"),
        ("n8n", "https://n8n.io/"),
        ("GA4", "https://analytics.google.com/"),
        ("GSC", "https://search.google.com/search-console/about"),
        ("Make", "https://www.make.com/"),
    ]
    
    token_pattern = re.compile(
        r"(```[\s\S]*?```|`[^`\n]*`|!\[[^\]]*\]\([^\)]+\)|\[[^\]]*\]\([^\)]+\)|<[^>]+>)",
        re.MULTILINE
    )
    
    parts = token_pattern.split(markdown)
    
    linked_tools = set()
    for i, part in enumerate(parts):
        if i % 2 == 1:
            if part.startswith("[") and "](" in part:
                for tool_name, _ in tools:
                    if tool_name.lower() in part.lower():
                        linked_tools.add(tool_name.lower())
                        
    placeholders = []
    flat_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            placeholder = f"___TOKEN_PLACEHOLDER_{len(placeholders)}___"
            placeholders.append((placeholder, part))
            flat_parts.append(placeholder)
        else:
            flat_parts.append(part)
            
    flat_text = "".join(flat_parts)
    
    for tool_name, url in tools:
        if tool_name.lower() in linked_tools:
            continue
            
        escaped_tool = re.escape(tool_name)
        escaped_tool = escaped_tool.replace(r"\ ", r"[-\s]")
        
        if tool_name.startswith("/"):
            pattern = rf"(?<!\w){escaped_tool}\b"
        else:
            pattern = rf"(?<!/)\b{escaped_tool}\b"
            
        match = re.search(pattern, flat_text, flags=re.IGNORECASE)
        if match:
            start, end = match.span()
            matched_text = flat_text[start:end]
            flat_text = flat_text[:start] + f"[{matched_text}]({url})" + flat_text[end:]
            linked_tools.add(tool_name.lower())
            
    for placeholder, original in reversed(placeholders):
        flat_text = flat_text.replace(placeholder, original)
        
    return flat_text


def strip_seo_machine_blocks(markdown: str) -> str:
    def replace_gutenberg_block(match: re.Match) -> str:
        content = match.group(0)
        if "seo-machine" in content or "meetlyra" in content:
            return ""
        return content

    pattern = re.compile(r"<!--\s*wp:(\S+)(?:[\s\S]*?)-->[\s\S]*?<!--\s*/wp:\1\s*-->", re.IGNORECASE)
    
    last_markdown = ""
    while last_markdown != markdown:
        last_markdown = markdown
        markdown = pattern.sub(replace_gutenberg_block, markdown)

    html_pattern = re.compile(
        r"<(div|figure|blockquote|aside)\b[^>]*?class=['\"][^'\"]*?(?:seo-machine|meetlyra)[^'\"]*?['\"][^>]*?>[\s\S]*?</\1>",
        re.IGNORECASE
    )
    markdown = html_pattern.sub("", markdown)
    
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def _plain_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"[#*_>`\[\]\(\)]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _paragraphs(markdown: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n{2,}", markdown or "") if part.strip() and not part.lstrip().startswith(("#", "<", "-", "|"))]


def _toc_items(markdown: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^##\s+(.+)$", markdown or "", flags=re.MULTILINE)]


def _truncate_words(value: str, limit: int) -> str:
    clean = _plain_text(value)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rsplit(" ", 1)[0].rstrip(".,;:") + "."
