import pytest
from content_machine.utils import excerpt
from content_machine.wordpress import (
    gutenbergize_lists,
    gutenbergize_code_blocks,
    _normalize_faq_blocks,
    gutenbergize_html_content,
    _replace_image_placeholders,
)

def test_excerpt_cleans_html_and_comments():
    raw_text = "<!-- wp:paragraph --><p>This is a <strong>cool</strong> post with #markdown and <a href='/link'>HTML</a> tags.</p><!-- /wp:paragraph -->"
    clean_excerpt = excerpt(raw_text, limit=100)
    assert "wp:paragraph" not in clean_excerpt
    assert "<p>" not in clean_excerpt
    assert "<strong>" not in clean_excerpt
    assert "#" not in clean_excerpt
    assert clean_excerpt == "This is a cool post with markdown and HTML tags."

def test_excerpt_handles_malformed_unclosed_comments():
    raw_text = "<!-- wp:paragraph --<pThe best AI marketing agent in 2026: A Founder's Guide"
    clean_excerpt = excerpt(raw_text, limit=100)
    assert "wp:paragraph" not in clean_excerpt
    assert "<!--" not in clean_excerpt
    assert "<" not in clean_excerpt
    assert "pThe best" in clean_excerpt


def test_gutenbergize_lists_simple():
    raw_list = "<ul><li>Item 1</li><li>Item 2</li></ul>"
    formatted = gutenbergize_lists(raw_list)
    assert "<!-- wp:list -->" in formatted
    assert "<!-- wp:list-item -->" in formatted
    assert "<!-- /wp:list-item -->" in formatted
    assert "<!-- /wp:list -->" in formatted
    assert "<!-- wp:list -->\n<ul>" in formatted

def test_gutenbergize_lists_ordered():
    raw_list = "<ol><li>First</li><li>Second</li></ol>"
    formatted = gutenbergize_lists(raw_list)
    assert '<!-- wp:list {"ordered":true} -->' in formatted
    assert "<!-- wp:list-item -->" in formatted

def test_gutenbergize_lists_nested():
    raw_list = "<ul><li>Outer<ul><li>Inner</li></ul></li></ul>"
    formatted = gutenbergize_lists(raw_list)
    # Check we have two wp:list blocks
    assert formatted.count("<!-- wp:list -->") == 2
    assert formatted.count("<!-- /wp:list -->") == 2
    assert formatted.count("<!-- wp:list-item -->") == 2

def test_gutenbergize_code_blocks():
    raw_code = "<pre><code>print('hello')</code></pre>"
    formatted = gutenbergize_code_blocks(raw_code)
    assert "<!-- wp:code -->" in formatted
    assert 'class="wp-block-code"' in formatted
    assert "<!-- /wp:code -->" in formatted

def test_normalize_faq_blocks():
    raw_faq = """<!-- wp:yoast/faq-block -->
<!-- wp:yoast/faq-question -->
<h3>What is Lyra?</h3>
<p>Lyra is an autonomous AI agent.</p>
<!-- /wp:yoast/faq-question -->
<!-- /wp:yoast/faq-block -->"""
    
    normalized = _normalize_faq_blocks(raw_faq)
    assert '<!-- wp:yoast/faq-block -->' in normalized
    assert 'class="schema-faq wp-block-yoast-faq-block"' in normalized
    assert '<!-- wp:yoast/faq-question {"questionName": "What is Lyra?"} -->' in normalized
    assert 'class="schema-faq-section"' in normalized
    assert '<strong class="schema-faq-question">What is Lyra?</strong>' in normalized
    assert '<!-- wp:paragraph -->' in normalized
    assert '<p class="schema-faq-answer">Lyra is an autonomous AI agent.</p>' in normalized

def test_gutenbergize_html_content_preserves_blocks():
    content = """
<!-- wp:html -->
<section class="seo-machine-takeaways">
  <ul>
    <li>Takeaway 1</li>
  </ul>
</section>
<!-- /wp:html -->

<p>Normal paragraph text.</p>

<ul>
  <li>Normal list item</li>
</ul>
"""
    processed = gutenbergize_html_content(content)
    # The list inside wp:html should NOT be gutenbergized
    # Find the position of the wp:html comment
    html_block_part = processed.split("<!-- /wp:html -->")[0]
    assert "<!-- wp:list -->" not in html_block_part
    
    # The normal list outside wp:html SHOULD be gutenbergized
    normal_part = processed.split("<!-- /wp:html -->")[1]
    assert "<!-- wp:list -->" in normal_part
    assert "<!-- wp:list-item -->" in normal_part

def test_replace_image_placeholders():
    html_content = """<!-- wp:image {"id":234,"sizeSlug":"large","linkDestination":"none"} -->
<figure class="wp-block-image size-large"><img src="https://blog.meetlyra.app/wp-content/uploads/2026/05/best-ai-marketing-agent.jpg" alt="An AI marketing agent" class="wp-image-234"/><figcaption>A caption</figcaption></figure>
<!-- /wp:image -->"""
    
    replaced = _replace_image_placeholders(html_content, media_id=987, media_url="https://blog.meetlyra.app/wp-content/uploads/2026/05/actual-image.png")
    assert '"id":987' in replaced
    assert 'src="https://blog.meetlyra.app/wp-content/uploads/2026/05/actual-image.png"' in replaced
    assert 'class="wp-image-987"' in replaced
