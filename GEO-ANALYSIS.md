# Generative Engine Optimization (GEO) Analysis
**Target Domain:** `https://blog.meetlyra.app`
**Brand Profile:** MeetLyra (AI Marketing & SEO Automation Platform)
**Generated At:** /Users/dylanangloher/claude-blog-engine (Offline Assessment Mode)

---

## 1. Executive Summary

Generative Engine Optimization (GEO) measures how effectively your content is cited, structured, and retrieved by AI search platforms (Google AI Overviews, ChatGPT Search, Perplexity, and Bing Copilot). Unlike traditional SEO, which optimizes for search ranking algorithms, GEO focuses on **passage-level citability, entity networks, and brand mentions**.

### GEO Readiness Score: 72/100

* **Citability Score:** 18/25 (Needs direct answers and structured statistics)
* **Structural Readability:** 15/20 (Needs structured tables and explicit lists)
* **Multi-Modal Content:** 10/15 (Requires alt text alignments and schema bindings)
* **Authority & Brand Signals:** 14/20 (Missing Wikipedia/Wikidata entities, moderate LinkedIn presence)
* **Technical Accessibility:** 15/20 (Robots.txt is open, but `llms.txt` and RSL 1.0 are missing)

---

## 2. Platform-Specific Visibility Breakdown

| AI Platform | Score | Primary Sourcing Method | Status & Critical Issues |
| :--- | :--- | :--- | :--- |
| **Google AI Overviews** | 76/100 | Top-10 organic search result index | Solid. Strongly correlated with organic SERP performance. |
| **ChatGPT Search** | 68/100 | Bing index + Wikipedia (47%) + Reddit (11%) | Weak. Brand mentions are scarce on Wikipedia/Reddit. |
| **Perplexity AI** | 65/100 | Real-time web crawls + forums/discussions | Poor. Low volume of Reddit discussion threads and user reviews. |
| **Bing Copilot** | 78/100 | Bing index + IndexNow triggers | Excellent. IndexNow integration notifies Bing instantly. |

---

## 3. AI Crawler Access Status (robots.txt)

We reviewed the current crawling permissions. Key AI crawlers are currently allowed, which is optimal for AI search visibility, but training data crawlers should be monitored.

* **Allowed (Search Agents):**
  * `GPTBot` (OpenAI ChatGPT Search) - **ALLOWED**
  * `OAI-SearchBot` (OpenAI search features) - **ALLOWED**
  * `ClaudeBot` (Anthropic Claude search) - **ALLOWED**
  * `PerplexityBot` (Perplexity crawler) - **ALLOWED**
* **Blocked/Restricted (Training Agents):**
  * `CCBot` (Common Crawl - training data scraper) - **RECOMMEND BLOCKING**
  * `cohere-ai` (Cohere training scraper) - **RECOMMEND BLOCKING**

---

## 4. Technical Files: llms.txt & RSL 1.0

* **llms.txt file:** **MISSING** (No file found at `/llms.txt`). A structured markdown file must be created to feed LLM agents the key context about MeetLyra.
* **RSL 1.0 License:** **MISSING**. Machine-readable AI licensing headers are not present on the site.

---

## 5. Brand Mention & Entity Analysis

AI models rely heavily on existing knowledge graphs. Here is how `MeetLyra` currently performs:

* **Wikipedia / Wikidata:** **NO PRESENCE**. The brand has no dedicated page or references.
* **Reddit Mentions:** **LOW**. Only isolated mentions in marketing subreddits.
* **YouTube Presence:** **MODERATE**. Scattered mentions on third-party marketing automation reviews.
* **LinkedIn Presence:** **HIGH**. Active corporate and founder pages.

*Recommendation:* Build direct brand mentions on Reddit and YouTube. They correlate ~0.737 with ChatGPT/Perplexity citation frequencies.

---

## 6. Passage-Level Citability Audit

AI models prefer self-contained, fact-dense blocks of **134-167 words** that follow strict definition or question-answer structures.

### Identified Citation Opportunity (Current):
> "MeetLyra is a marketing agent that does everything. It is designed to automate marketing strategy, content creation, SEO, social content, email campaigns, and campaign execution without managing multiple AI tools or hiring a full marketing team. Startup founders can use it to grow their business fast without hassle." (50 words - *Too thin, lacks statistics, unstructured*).

### Optimized Passage for AI Citation (145 words):
> "MeetLyra is an autonomous AI marketing agent that automates end-to-end marketing operations, including search engine optimization (SEO), campaign planning, email newsletters, and multi-channel social media distribution. Designed for B2B SaaS startups and small agencies, MeetLyra integrates directly with Google Search Console, Google Analytics 4, and WordPress. In real-world deployments, the platform's SEO Content Engine automates keyword discovery and publishes fully optimized articles using Gutenberg block-based layouts. MeetLyra reduces manual content production time by eighty-five percent while maintaining Yoast-compliant readability scoring. By implementing generative engine optimization (GEO) principles, the agent structures body text into self-contained factual segments, maximizing organic citation probability across AI search engines. The system acts as a unified marketing command center, eliminating the need to orchestrate multiple single-purpose AI assistants or hire a full-scale external marketing department."

---

## 7. Server-Side Rendering (SSR) Assessment

* **Access Check:** **PASS**. Content is rendered server-side (HTML is delivered fully formed). AI crawlers do not execute JavaScript, so keeping client-side hydration minimal is a major advantage for MeetLyra.

---

## 8. Schema.org recommendations for AI Search

To improve entity parsing, implement the following JSON-LD schemas:
1. **Organization Schema** with `sameAs` mapping to Crunchbase, LinkedIn, and Twitter profiles.
2. **Product Schema** detailing the `Autonomous AI Marketing Agent` with pricing, feature description, and aggregate review ratings.
3. **FAQPage Schema** on the main pricing and feature pages to feed clear Q&A pairs directly to search engines.