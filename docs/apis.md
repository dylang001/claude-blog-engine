# API Keys Setup

## Required

### DataForSEO

Used by all three skills — competitor discovery, keyword research, SERP analysis.

1. Sign up at [dataforseo.com](https://dataforseo.com) (free trial includes credits)
2. Your login email and password are your API credentials

```bash
export DATAFORSEO_LOGIN="your@email.com"
export DATAFORSEO_PASSWORD="yourpassword"
```

Alternatively, set a pre-encoded Basic Auth token:

```bash
export DATAFORSEO_AUTH_BASE64="$(printf '%s' 'your@email.com:yourpassword' | base64)"
```

**Endpoints used:**
| Skill | Endpoint | Cost |
|-------|----------|------|
| ``blog-onboard`` | `serp/google/organic/live/regular` | ~$0.003/request |
| ``blog-topics`` | `dataforseo_labs/google/ranked_keywords/live` | ~$0.05/request |
| ``blog-topics`` | `keywords_data/google_ads/keywords_for_keywords/live` | ~$0.05/request |
| ``blog-topics`` | `dataforseo_labs/google/bulk_keyword_difficulty/live` | ~$0.02/request |
| ``blog-write`` | `serp/google/organic/live/advanced` | ~$0.004/request |

Typical cost per full cycle (onboard + topics + write): **~$0.30 - $0.50**

---

### Anthropic API

Used by ``blog-topics`` and ``blog-write`` for LLM calls (classification, clustering, outline, article generation).

1. Get your key at [console.anthropic.com](https://console.anthropic.com)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Models used:**
| Task | Model | Skill |
|------|-------|-------|
| Seed keyword generation | Claude Haiku | ``blog-topics`` |
| Intent classification | Claude Haiku | ``blog-topics`` |
| Cluster grouping | Claude Sonnet | ``blog-topics`` |
| SERP gap analysis | Claude Haiku | ``blog-write`` |
| Outline generation | Claude Sonnet | ``blog-write`` |
| Article generation | Claude Sonnet | ``blog-write`` |
| Image prompt generation | Claude Haiku | ``blog-write`` |
| Schema markup | Claude Haiku | ``blog-write`` |
| Meta assets | Claude Haiku | ``blog-write`` |

---

## Optional

These keys enhance ``blog-write`` article quality. Each has a graceful fallback — the skill works without them.

### Firecrawl

Better page scraping for SERP competitor content analysis.

1. Sign up at [firecrawl.dev](https://firecrawl.dev) (free tier available)

```bash
export FIRECRAWL_API_KEY="fc-..."
```

**Fallback:** Uses Claude Code's built-in `WebFetch` tool instead. Works fine for most pages but may miss JavaScript-rendered content.

---

### Tavily

Deeper topic research — pulls relevant articles, stats, and data points for your article topic.

1. Sign up at [tavily.com](https://tavily.com) (free tier available)

```bash
export TAVILY_API_KEY="tvly-..."
```

**Fallback:** Uses Claude Code's built-in `WebSearch` tool. Still effective but less structured results.

---

### YouTube Data API

Pulls video transcripts for topic research — finds insights from popular YouTube content in your niche.

1. Enable YouTube Data API v3 at [console.cloud.google.com](https://console.cloud.google.com)
2. Create an API key

```bash
export YOUTUBE_API_KEY="AIza..."
```

**Also requires:** `youtube-transcript-api` Python package (installed automatically if missing)

**Fallback:** Skipped entirely. Article is written without video insights.

---

### Banana Claude / Gemini Images

Generates article images through the Banana Claude creative-director pattern
using Gemini image models.

1. Get your key from Google AI Studio.

```bash
export GEMINI_API_KEY="..."
export BANANA_MODEL="gemini-3.1-flash-image-preview"
export BANANA_ASPECT_RATIO="16:9"
export BANANA_RESOLUTION="2K"
```

**Fallback:** Image positions are marked with descriptive HTML comments in the article:
```html
<!-- THUMBNAIL IMAGE: description — recommended size 1792x1024 -->
```
You can use these descriptions to create images manually or with any image tool.

---

### IndexNow

Notifies supported search engines when a post is published or refreshed.

```bash
export INDEXNOW_KEY="32-character-random-key"
export INDEXNOW_KEY_LOCATION="https://example.com/indexnow-key.txt"
export INDEXNOW_ENGINES="bing,yandex,seznam,indexnow"
```

The updated WordPress bridge serves the key file at `/indexnow-key.txt`.
After uploading the bridge, run:

```bash
python -m content_machine indexnow --configure-wordpress
python -m content_machine indexnow --verify
```

**Fallback:** If IndexNow is not configured, publishing still works; the worker
just skips immediate IndexNow notifications.

---

## All Keys at a Glance

```bash
# Add to ~/.zshrc or ~/.bashrc

# Required
export DATAFORSEO_LOGIN="your@email.com"
export DATAFORSEO_PASSWORD="yourpassword"
# Or:
export DATAFORSEO_AUTH_BASE64="base64-login-password-token"
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional
export FIRECRAWL_API_KEY="fc-..."
export TAVILY_API_KEY="tvly-..."
export YOUTUBE_API_KEY="AIza..."
export GEMINI_API_KEY="..."
export INDEXNOW_KEY="32-character-random-key"
export INDEXNOW_KEY_LOCATION="https://example.com/indexnow-key.txt"
export INDEXNOW_ENGINES="bing,yandex,seznam,indexnow"
```

After adding, run `source ~/.zshrc` (or restart your terminal) to load them.
