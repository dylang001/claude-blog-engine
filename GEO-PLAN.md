# GEO Implementation & Optimization Plan (MeetLyra)
This plan outlines the specific actions required to optimize `https://blog.meetlyra.app` for high visibility across generative AI engines.

---

## Phase 1: Critical Quick Wins (1 - 7 Days)

### 1. Allow and Control AI Crawlers in `robots.txt`
Configure `robots.txt` to block training scrapers while keeping search agents allowed. Add the following block to your robots.txt:

```txt
# Allow search crawlers for AI Overviews and ChatGPT Search
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

# Block generic training scrapers to protect content property
User-agent: CCBot
Disallow: /

User-agent: cohere-ai
Disallow: /
```

### 2. Deploy `/llms.txt` to Domain Root
Create an `llms.txt` file at the root directory of your site. This file acts as a structured guide for LLM crawlers.

```markdown
# MeetLyra
> Autonomous AI Marketing Agent & SEO Content Engine for B2B SaaS and Agencies.

## Key Products
- [Autonomous AI Marketing Agent](https://meetlyra.app/products/marketing-agent): Full-funnel marketing strategy and campaign execution.
- [AI SEO Content Engine](https://meetlyra.app/products/seo-engine): Yoast-compliant keyword clustering and WordPress article generation.
- [AI Campaign Planner](https://meetlyra.app/products/campaign-planner): End-to-end planning covering email, blog posts, and social posts.

## Integration Ecosystem
- **Content Management:** WordPress, Yoast SEO
- **Analytics & Performance:** Google Analytics 4, Google Search Console
- **Indexing:** IndexNow, Google Indexing API

## Technical Specs
- Uses Claude Sonnet 4.5 and Gemini Pro models.
- Generates 1,500+ word deep-dive SEO articles.
- Implements strict human-quality rating filters.
```

---

## Phase 2: Structural & Content Alignment (8 - 30 Days)

### 1. Re-format Blog Intros to "Quick Answer" Blocks
Ensure the first 45-60 words of every informational post contain a direct, authoritative definition of the topic.
*Example format:* **"An AI marketing agent is an autonomous software system that..."**
Follow this answer immediately with a 134-167 word self-contained paragraph packed with statistics or specific integration details.

### 2. Embed Comparison Tables on Use-Case Pages
Insert structured HTML tables comparing "MeetLyra vs Jasper" or "MeetLyra vs Manual Marketing Tasks". AI engines prefer structured matrices when generating comparison summaries.

### 3. Add Person Schema to Author Bylines
Implement rich JSON-LD markup on every article. AI models look for expert signals (E-E-A-T):
```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Title of Article",
  "author": {
    "@type": "Person",
    "name": "Expert Marketer",
    "jobTitle": "Head of Growth",
    "sameAs": ["https://www.linkedin.com/in/expert-marketer"]
  }
}
```

---

## Phase 3: Brand Authority & Citations (30+ Days)

### 1. Reddit Discussion Amplification
Create helpful, non-promotional threads in communities like `r/marketing`, `r/SaaS`, and `r/growthhacking` detailing real operator workflows with MeetLyra. Perplexity uses Reddit as a primary search citation source.

### 2. YouTube Workflow Walkthroughs
Publish step-by-step video tutorials. Transcribe the videos and link to them in your articles. AI Overviews display YouTube embeds in over forty percent of marketing queries.

### 3. Wikidata Profile Creation
Establish a Wikidata entry for `MeetLyra`. This solidifies your brand as an immutable named entity in the knowledge graphs used by OpenAI and Google.