---
description: Write a full SEO article with research, images, schema markup, and publishing checklist
argument-hint: ["topic keyword" or blank for next in pipeline]
allowed-tools: Bash WebFetch WebSearch Read Write
---

You are running the Blog Engine content generation pipeline. Your job is to produce one complete, publish-ready blog article from a keyword in the pipeline. Follow every step exactly and in order.

---

## INPUTS THIS SKILL NEEDS FROM THE USER

Before starting, show the user this checklist:

```
Blog Engine — Article Writer

What you'll need:
  [env]  DATAFORSEO_LOGIN         your DataForSEO account email
  [env]  DATAFORSEO_PASSWORD      your DataForSEO account password
  [env]  ANTHROPIC_API_KEY        your Anthropic API key

Optional (improves quality if available):
  [env]  FIRECRAWL_API_KEY        better competitor scraping (free tier: firecrawl.dev)
  [env]  TAVILY_API_KEY           deeper topic research (free tier: tavily.com)
  [env]  YOUTUBE_API_KEY          video insights (console.cloud.google.com)
  [env]  OPENAI_API_KEY           DALL-E thumbnail + mid-article images

Missing optional keys are skipped automatically — the article is still complete.
Starting now...
```

---

## BEFORE YOU START

**Load config and keyword data:**

Read these three files. If any are missing, stop with the indicated message:

1. `.claude/blog-config.json` — if missing: `"Run /user:blog-onboard first."`
2. `.claude/blog-keywords.json` — if missing: `"Run /user:blog-topics first."`
3. `.claude/blog-clusters.json` — if missing: `"Run /user:blog-topics first."`

**Select the topic:**

If the user passed `$ARGUMENTS`:

- **If it's a number (1–10)** (e.g. `/user:blog-write 3`):
  - Treat it as a 1-based index into `topics.pipeline` sorted by `opportunity_score` descending
  - Select the item at that position (1 = highest scored, 10 = tenth)
  - If the index is out of range: stop — `"Only {n} topics in pipeline. Run /user:blog-topics to add more."`

- **If it's a keyword string** (e.g. `/user:blog-write "salesforce google sheets integration"`):
  - Search `topics.pipeline` in blog-config.json for a matching keyword (case-insensitive)
  - If NOT found in pipeline: search `blog-keywords.json` for the keyword, and if found, use that record directly (it's an off-pipeline write)
  - If not found anywhere: stop — `"Keyword not found in your keyword database. Run /user:blog-topics or check spelling."`

For any matched pipeline item:
- If status is `queued`: use it
- If status is `in_progress`: ask user "This topic is already in progress. Continue generating?"
- If status is `done`: stop — `"This topic has already been written."`

If NO argument was passed:
- Find the first item in `topics.pipeline` with `status: "queued"`, sorted by `opportunity_score` descending
- If no queued items exist: stop — `"Pipeline is empty. Run /user:blog-topics to generate new topics."`

Store the selected keyword record as `{topic}`.

**Update pipeline status to in_progress:**

Read blog-config.json, find the matching pipeline item, set `status: "in_progress"`. Write the file back.

**Check required credentials:**

```bash
[ -f .env ] && source .env
echo "DATAFORSEO: ${DATAFORSEO_LOGIN:-MISSING}"
echo "ANTHROPIC: ${ANTHROPIC_API_KEY:-MISSING}"
echo "---optional---"
echo "FIRECRAWL: ${FIRECRAWL_API_KEY:-MISSING}"
echo "TAVILY: ${TAVILY_API_KEY:-MISSING}"
echo "YOUTUBE: ${YOUTUBE_API_KEY:-MISSING}"
echo "OPENAI: ${OPENAI_API_KEY:-MISSING}"
```

If DATAFORSEO or ANTHROPIC are missing, stop and tell the user:
> "Missing API keys in `.env`. Open `.env` in your project root and fill in: {list missing keys}. Save and re-run."

For optional keys, store which are available:
- `{has_firecrawl}` = true/false
- `{has_tavily}` = true/false
- `{has_youtube}` = true/false
- `{has_openai}` = true/false

Tell the user:
```
Writing article for: "{topic.keyword}"
  Cluster:  {topic.cluster_name}
  Funnel:   {topic.funnel}
  Score:    {topic.opportunity_score}
  Action:   {topic.action}

  APIs available: DataForSEO ✓  Anthropic ✓  Firecrawl {✓/✗}  Tavily {✓/✗}  YouTube {✓/✗}  DALL-E {✓/✗}
```

---

## STEP 1 — Context Assembly

Type: Code only. No API. No LLM.

Pull all data for this keyword from the three JSON files into one master context object.

From `blog-config.json`:
- `business_profile` ← `business` object
- `icp` ← build from `business.icp_signals`: `{ role: roles[0], core_pain: pain_points[0], goal: "inferred from product_type + pain_point", sophistication: "inferred from roles" }`
- `brand_voice` ← `{ tone: business.brand_voice_signals, avoid: [] }`
- `competitors` ← `competitors` array
- `target_market` ← derive from `business.target_geography` (e.g. "Global" → "us", "US-focused" → "us")
- `dataforseo_location_code` ← map target_market using the same table from /user:blog-topics (us→2840, uk→2826, etc.)

From `blog-keywords.json` — find the record matching `{topic.keyword}`:
- `keyword`, `volume`, `kd`, `cpc`, `intent`, `funnel`, `cluster`, `opportunity_score`
- `user_ranking_position`, `user_ranking_url`, `competitor_rankings`, `status`

From `blog-clusters.json` — find the cluster matching `{topic.cluster_id}`:
- `secondary_keywords` ← collect all supporting keyword strings from this cluster (exclude the topic keyword itself). Take top 5 by opportunity score from blog-keywords.json.

If `{topic}` came from the pipeline, also pull:
- `related_keywords` from the pipeline item (these are the top 3 pre-selected in /user:blog-topics Step 10)

Merge `related_keywords` and `secondary_keywords` into one deduplicated list. Cap at 8 keywords.

Build the master context object:

```json
{
  "keyword": "...",
  "volume": 0,
  "kd": 0,
  "cpc": 0.0,
  "intent": "...",
  "funnel": "...",
  "cluster_id": "...",
  "opportunity_score": 0.0,
  "status": "...",
  "article_type": null,
  "proposed_title": null,
  "user_ranking_position": null,
  "user_ranking_url": null,
  "competitor_rankings": {},
  "secondary_keywords": [],
  "business_profile": {},
  "icp": {},
  "brand_voice": {},
  "target_market": "...",
  "dataforseo_location_code": 0
}
```

`article_type` and `proposed_title` are null at this stage — the outline generator (Step 4) will determine these based on SERP analysis and funnel stage.

Store as `{ctx}`. This object is passed into every subsequent step.

Tell the user: `"Step 1 complete: context assembled"`

---

## STEP 2 — Live Research (Parallel)

Steps 2a, 2b, and 2c fire simultaneously. Use parallel Bash background processes with temp files for each.

---

### STEP 2A — SERP Scrape + Competitor Article Analysis

**Call 1 — DataForSEO Advanced SERP:**

```bash
[ -f .env ] && source .env
DATAFORSEO_CREDS=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

curl -s -X POST "https://api.dataforseo.com/v3/serp/google/organic/live/advanced" \
  -H "Authorization: Basic $DATAFORSEO_CREDS" \
  -H "Content-Type: application/json" \
  -d '[{
    "keyword": "{ctx.keyword}",
    "location_code": {ctx.dataforseo_location_code},
    "language_code": "en",
    "depth": 10,
    "search_param": "inurl:blog"
  }]'
```

> NOTE: `search_param: "inurl:blog"` filters to blog content only. This costs ~5x the base rate (~$0.015 per call). If the response returns fewer than 3 organic results, re-run the same call WITHOUT `search_param` to get general results instead.

From the response, extract:
- Top 3 `organic` type items → save their URLs as `{serp_urls}`
- All `people_also_ask` type items → save questions as `{paa_questions}`
- Any `featured_snippet` type item → flag URL and note format

**Call 2 — Scrape top 3 ranking articles (parallel):**

If `{has_firecrawl}` is true, use Firecrawl for each URL:

```bash
# Fire all 3 in parallel
for i in 0 1 2; do
  (curl -s -X POST "https://api.firecrawl.dev/v1/scrape" \
    -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"{serp_url_$i}\", \"formats\": [\"markdown\"], \"onlyMainContent\": true}" \
    > /tmp/serp_scrape_$i.json) &
done
wait
```

If `{has_firecrawl}` is false, use WebFetch on each URL instead. WebFetch is built-in and requires no API key.

From each scraped page, extract: H1, all H2 headings, all H3 headings, approximate word count (count words in the markdown), meta description if available.

Store:

```json
{
  "serp_data": {
    "top_3_structures": [
      {
        "url": "...",
        "h1": "...",
        "h2s": ["..."],
        "h3s": ["..."],
        "word_count": 0
      }
    ],
    "paa_questions": ["..."],
    "featured_snippet_present": true,
    "featured_snippet_url": "...",
    "average_word_count": 0
  }
}
```

Calculate `{target_word_count}` = `average_word_count × 1.25` (round to nearest 50). Minimum 1500, maximum 4000.

---

### STEP 2B — Topic Research

If `{has_tavily}` is true, use the Tavily batch search:

```bash
curl -s -X POST "https://api.tavily.com/search" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "'"$TAVILY_API_KEY"'",
    "queries": [
      {"query": "{ctx.keyword} news update 2024 2025", "search_depth": "basic", "max_results": 3},
      {"query": "{ctx.keyword} expert opinion best practice", "search_depth": "basic", "max_results": 3},
      {"query": "{ctx.keyword} common mistakes problems issues", "search_depth": "basic", "max_results": 3}
    ]
  }'
```

> NOTE FOR TESTING: Check whether the Tavily API uses `queries` (batch) or requires separate calls per query. If batch is not supported, fire 3 parallel calls with individual `query` fields instead.

If `{has_tavily}` is false, use WebSearch (built-in) to run three searches:
- `"{ctx.keyword} news update 2024 2025"`
- `"{ctx.keyword} expert opinion best practice"`
- `"{ctx.keyword} common mistakes problems"`

For each search, take the most relevant result.

Store:

```json
{
  "topic_research": {
    "recent_news": {
      "insight": "string — summarize the key finding in one sentence",
      "source": "URL",
      "source_name": "publication name"
    },
    "expert_opinion": {
      "insight": "string",
      "source": "URL",
      "source_name": "string"
    },
    "common_mistakes": {
      "insight": "string",
      "source": "URL",
      "source_name": "string"
    }
  }
}
```

If any query returns no useful result, store `null` for that field. The outline generator will skip null research slots.

---

### STEP 2C — YouTube Transcript Pull (Optional)

Skip this entire step if `{has_youtube}` is false. Store `youtube_insights: null` and continue.

**Sub-call 1 — Find relevant videos:**

```bash
curl -s "https://www.googleapis.com/youtube/v3/search?q=$(printf '%s' '{ctx.keyword}' | jq -sRr @uri)&type=video&maxResults=5&order=relevance&videoDuration=medium&key=$YOUTUBE_API_KEY"
```

Take top 2 video IDs from `items[].id.videoId`.

**Sub-call 2 — Extract transcripts:**

Check if `youtube-transcript-api` Python package is available:

```bash
python3 -c "from youtube_transcript_api import YouTubeTranscriptApi; print('OK')" 2>/dev/null
```

If not available, try installing it:
```bash
pip3 install youtube-transcript-api 2>/dev/null
```

If still not available, skip Step 2c entirely. Store `youtube_insights: null`.

If available, extract transcripts for both videos:

```bash
python3 -c "
from youtube_transcript_api import YouTubeTranscriptApi
import json, sys

video_ids = ['{video_id_1}', '{video_id_2}']
transcripts = []
for vid in video_ids:
    try:
        t = YouTubeTranscriptApi.get_transcript(vid, languages=['en'])
        text = ' '.join([e['text'] for e in t])
        transcripts.append(text)
    except:
        pass
combined = ' '.join(transcripts)[:8000]
print(combined)
"
```

If no transcripts are retrieved, store `youtube_insights: null` and skip Sub-call 3.

**Sub-call 3 — Haiku summarization:**

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 500,
    "messages": [{
      "role": "user",
      "content": "You are extracting useful insights from YouTube video transcripts on the topic of {ctx.keyword}.\n\nTranscripts:\n{combined_transcripts}\n\nExtract 2 concrete insights, examples, or practitioner tips from these transcripts that would add genuine value to a blog article on this topic.\n\nRules:\n- Only extract insights that are specific and concrete — not generic advice\n- Do not fabricate anything not present in the transcripts\n- Each insight should be something a reader would find genuinely useful or surprising\n- Include the video title and channel for attribution\n\nReturn only valid JSON. No explanation. No markdown code blocks.\nStart with { and end with }.\n\n{\"youtube_insights\": [{\"insight\": \"string\", \"video_title\": \"string\", \"channel\": \"string\"}]}"
    }]
  }'
```

Parse and store `{youtube_insights}`.

---

After all parallel steps complete, tell the user:

```
Step 2 complete: live research gathered
  SERP articles scraped:  {n} ({n} via Firecrawl / {n} via WebFetch)
  PAA questions found:    {n}
  Topic research:         {available_count}/3 research angles found
  YouTube insights:       {n} insights (or "skipped — no API key")
  Target word count:      {target_word_count}
```

---

## STEP 3 — SERP Gap Analysis

Type: Claude Haiku. 1 call.

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 800,
    "messages": [{
      "role": "user",
      "content": "You are an SEO content strategist analyzing search results to find content gaps.\n\nTarget keyword: {ctx.keyword}\nSearch intent: {ctx.intent}\nTarget reader: {ctx.icp.role}\n\nTop 3 currently ranking article H2 structures:\n{serp_data.top_3_structures_as_json}\n\nPeople Also Ask questions on this SERP:\n{paa_questions_as_json}\n\nIdentify:\n1. What angles or subtopics all top 3 articles are covering\n2. What angles or questions are NOT being covered well or at all\n3. Which PAA question represents the best featured snippet opportunity because no current result answers it directly and concisely\n4. What the recommended differentiating angle is for a new article targeting this keyword to beat the current results\n\nReturn only valid JSON. No explanation. No markdown formatting.\nDo not wrap in code blocks. Start with { and end with }.\n\n{\"covered_by_all\": [\"string\"], \"gaps_identified\": [\"string\"], \"featured_snippet_opportunity\": \"string — the specific PAA question\", \"differentiating_angle\": \"string — one sentence describing the unique angle\"}"
    }]
  }'
```

Parse and store as `{serp_gap}`.

Tell the user: `"Step 3 complete: SERP gap analysis done — differentiating angle: {serp_gap.differentiating_angle}"`

---

## STEP 4 — Outline Generation

Type: Claude Sonnet. 1 call. Most important call in the pipeline.

This call receives the full master context + SERP gap + all research. It determines `article_type` and `proposed_title` based on intent/funnel/SERP analysis.

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 4000,
    "messages": [{
      "role": "user",
      "content": "You are a senior SEO content strategist creating a detailed article outline.\nThis outline will be passed to a writer who generates the full article section\nby section. Every instruction must be specific enough that the writer needs\nno additional context to execute it.\n\nArticle parameters:\n- Target keyword: {ctx.keyword}\n- Secondary keywords to distribute naturally: {ctx.secondary_keywords}\n- Target word count: {target_word_count}\n- Target reader: {ctx.icp.role}\n- Reader pain point: {ctx.icp.core_pain}\n- Reader goal: {ctx.icp.goal}\n- Reader sophistication: {ctx.icp.sophistication}\n- Brand voice: {ctx.brand_voice.tone}\n- Words and phrases to avoid: {ctx.brand_voice.avoid}\n- Funnel stage: {ctx.funnel}\n- Search intent: {ctx.intent}\n\nBusiness context:\n- Business: {ctx.business_profile.business_name}\n- Product: {ctx.business_profile.product_type}\n- Key differentiator: {ctx.business_profile.key_differentiator}\n\nContent strategy:\n- Differentiating angle: {serp_gap.differentiating_angle}\n- Content gaps to address: {serp_gap.gaps_identified}\n- Featured snippet opportunity: {serp_gap.featured_snippet_opportunity}\n- Average competitor word count: {serp_data.average_word_count}\n\nTopic research available to assign to sections:\n- Recent news: {topic_research.recent_news}\n- Expert opinion: {topic_research.expert_opinion}\n- Common mistakes: {topic_research.common_mistakes}\n\nYouTube insights available to assign to sections:\n{youtube_insights}\n\nFirst, determine the article type and title:\n- Based on intent, funnel, and keyword, choose the article type. Examples: How-To Guide, Comparison, Listicle, Ultimate Guide, How-To + Comparison, Deep Dive, Tutorial.\n- Write a proposed title (H1) that includes the target keyword, matches the article type, and would make the target reader click.\n\nRules for the outline:\n- Target keyword must appear in H1 and at least two H2s\n- Every H2 must have a clear purpose statement explaining what that section accomplishes\n- Assign specific secondary keywords to specific sections\n- Specify exact word count per section summing to total target\n- Specify image placements: thumbnail always at top, second image above the H2 where article transitions into solution content (typically section 3 or 4)\n- For each image specify which H2 it sits above and what it should depict\n- Specify product plug placement — which section, exact framing, how it connects to surrounding content. Product plug must not be in first or last section.\n- Assign topic research items and YouTube insights to specific sections where they fit naturally — do not force all in\n- Featured snippet opportunity question must be addressed in a dedicated section formatted for a direct concise answer\n- Introduction must not open with a generic sentence — specify exact hook angle based on reader pain point\n- Include FAQ section using PAA questions\n- Conclusion must help reader make a decision, not summarize the article\n- Specify CTA framing matched to funnel stage: BOFU=direct trial CTA, MOFU=explore CTA, TOFU=related content CTA\n\nReturn only valid JSON. No explanation. No markdown code blocks.\nStart with { and end with }.\n\n{\"article_type\": \"string\", \"meta_title\": \"string — under 60 chars, keyword near front\", \"meta_description\": \"string — 150 to 155 chars, includes keyword, has a hook\", \"url_slug\": \"string — clean, keyword-present, no stop words\", \"h1\": \"string\", \"target_word_count\": 0, \"introduction\": {\"hook_angle\": \"string — specific instruction for how to open\", \"topic_research_to_include\": \"recent_news | expert_opinion | common_mistakes | null\", \"youtube_insight_to_include\": \"string or null\", \"word_count\": 150}, \"sections\": [{\"h2\": \"string\", \"purpose\": \"string — what this section accomplishes for the reader\", \"h3s\": [\"string\"], \"secondary_keywords\": [\"string — keywords assigned to this section\"], \"word_count\": 0, \"image\": {\"position\": \"above_this_section\", \"depicts\": \"string — what the image should show\", \"image_number\": 2} | null, \"product_plug\": {\"include\": true, \"framing\": \"string — exact framing instruction\"} | null, \"topic_research_to_include\": \"recent_news | expert_opinion | common_mistakes | null\", \"youtube_insight_to_include\": \"string or null\", \"special_instruction\": \"string or null\"}], \"faq\": {\"questions\": [\"string\"], \"word_count\": 300}, \"conclusion\": {\"instruction\": \"string — specific framing\", \"cta\": \"string — exact CTA matched to funnel stage\", \"word_count\": 150}}"
    }]
  }'
```

Parse the response and store as `{outline}`.

Tell the user:
```
Step 4 complete: outline generated
  Article type:  {outline.article_type}
  Title (H1):   {outline.h1}
  Sections:     {section_count} H2s + FAQ + Conclusion
  Word target:  {outline.target_word_count}
```

---

## STEP 5 — Article Generation

Type: Claude Sonnet. 1 call. Full article generated in one shot using the outline as blueprint.

Image placeholders are embedded at positions specified in the outline. If `{has_openai}` is false, these placeholders are removed in Step 7 instead of replaced with images.

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 8000,
    "messages": [{
      "role": "user",
      "content": "You are an expert SEO content writer generating a complete, publish-ready blog article.\nFollow the outline and every instruction below precisely. Do not deviate from the\nstructure, word counts, or content instructions specified.\n\n=== ARTICLE PARAMETERS ===\n\nTarget keyword: {ctx.keyword}\nSecondary keywords (distribute naturally throughout): {ctx.secondary_keywords}\nArticle type: {outline.article_type}\nTitle (H1): {outline.h1}\nTarget word count: {outline.target_word_count}\nTarget reader: {ctx.icp.role}\nReader pain point: {ctx.icp.core_pain}\nReader goal: {ctx.icp.goal}\nReader sophistication: {ctx.icp.sophistication}\n\n=== BRAND VOICE ===\n\nTone: {ctx.brand_voice.tone}\nWords and phrases to NEVER use: {ctx.brand_voice.avoid}\nWriting style rules:\n- Short paragraphs of 2–3 sentences maximum\n- Lead with outcomes and specifics, not generalizations\n- Write for someone who skims — H2s and first sentences of each paragraph must carry the meaning\n- No filler phrases like \"In this article we will\", \"Now that we have covered\", \"It is worth noting\"\n- No generic openers — the first sentence must be specific and immediately relevant to the reader\n\n=== BUSINESS CONTEXT ===\n\nBusiness: {ctx.business_profile.business_name}\nProduct: {ctx.business_profile.product_type}\nKey differentiator: {ctx.business_profile.key_differentiator}\n\n=== TOPIC RESEARCH (cite sources inline where used) ===\n\nRecent news: {topic_research.recent_news.insight} (Source: {topic_research.recent_news.source_name})\nExpert opinion: {topic_research.expert_opinion.insight} (Source: {topic_research.expert_opinion.source_name})\nCommon mistake: {topic_research.common_mistakes.insight} (Source: {topic_research.common_mistakes.source_name})\nYouTube insight 1: {youtube_insights[0].insight} ({youtube_insights[0].channel})\nYouTube insight 2: {youtube_insights[1].insight} ({youtube_insights[1].channel})\n\nUse these where they fit naturally. Do not force all of them in. Do not fabricate\nany statistics or claims beyond what is provided above. If a research field is null, skip it.\n\n=== SERP DIFFERENTIATION ===\n\nWhat competitors are already covering (do not just repeat these):\n{serp_gap.covered_by_all}\n\nGaps to fill that competitors are missing:\n{serp_gap.gaps_identified}\n\nDifferentiating angle for this article:\n{serp_gap.differentiating_angle}\n\nFeatured snippet opportunity (answer this directly and concisely in the relevant section):\n{serp_gap.featured_snippet_opportunity}\n\n=== PRODUCT PLUG RULES ===\n\nProduct to mention: {ctx.business_profile.business_name}\nPlacement: the section specified in the outline with product_plug.include = true\nFraming: use the framing instruction from the outline\nRules:\n- 2–3 sentences maximum\n- Written as a genuine recommendation connected to the reader's specific pain, not a sales pitch\n- Do not use superlatives or marketing language\n- The product mention must feel earned — the reader should have felt the pain before the product appears\n- Do not mention the product in the introduction, conclusion, or any section before the designated plug section\n- One mention only — do not repeat the product name elsewhere in the article\n\n=== IMAGE PLACEHOLDERS ===\n\nOutput the following placeholder tags at exactly the positions specified.\nDo not describe the images. Do not add any text around the placeholders. Just the tag on its own line.\n\n{{IMAGE_THUMBNAIL}} — first line of the article before the H1, always\n{{IMAGE_MID_ARTICLE}} — on its own line directly above the H2 section that the outline specifies with image.image_number = 2\n\n=== ARTICLE STRUCTURE ===\n\nFollow this outline exactly. Every H2 and H3 must appear in the order specified.\nWord counts per section are targets — stay within 10% of each.\n\n{outline_as_json}\n\n=== SEO REQUIREMENTS ===\n\n- Target keyword must appear within the first 100 words of the introduction\n- Target keyword must appear naturally in at least 2 H2 headings\n- Secondary keywords must be distributed across sections — do not cluster them\n- FAQ section must use H3 for each question\n- The featured snippet opportunity question must be the first FAQ question, answered with a direct 2–3 sentence response optimised for Google snippet format\n- Do not keyword stuff — if a keyword does not fit naturally in a section skip it\n\n=== INTRODUCTION RULES ===\n\nHook angle: {outline.introduction.hook_angle}\nWord count: {outline.introduction.word_count}\n- Open with the hook angle above — do not deviate from it\n- Do not open with a question\n- Do not open with \"In today's world\", \"In this article\", or any generic setup sentence\n- Target keyword must appear within the first 100 words\n- Make the reader feel understood in the first two sentences\n- Weave in the assigned topic research item naturally with source cited inline\n- End with a clear transition into what the article covers\n- No bullet points in the introduction\n\n=== CONCLUSION RULES ===\n\nFraming: {outline.conclusion.instruction}\nCTA: {outline.conclusion.cta}\nWord count: {outline.conclusion.word_count}\nFunnel stage: {ctx.funnel}\n- Do not summarize the article — the reader just read it\n- Help the reader make a decision based on their specific situation\n- BOFU: direct free trial or get started CTA\n- MOFU: softer learn more or explore CTA\n- TOFU: content upgrade or related resource CTA\n- Maximum 2 paragraphs before the CTA\n- CTA as its own final sentence or short paragraph\n- No bullet points in the conclusion\n\n=== OUTPUT FORMAT ===\n\n- Write in markdown\n- H1 using #, H2 using ##, H3 using ###\n- Image placeholders on their own line with no surrounding text\n- Comparison tables as markdown tables\n- No bold mid-sentence — bold only for labels or table headers\n- Inline source citations as: (Source: Name, Year) immediately after the cited claim\n- Do not add any preamble before the article or any commentary after it\n- Start your response with {{IMAGE_THUMBNAIL}} on the very first line"
    }]
  }'
```

Parse the response. Extract `content[0].text` as `{article_markdown}`.

Count the actual word count by splitting on whitespace.

Tell the user:
```
Step 5 complete: article generated
  Actual word count: {actual_word_count} (target: {target_word_count})
  Sections:         {section_count} H2s + FAQ + Conclusion
```

---

## STEP 6 — Image Generation (Optional)

Skip this entire step if `{has_openai}` is false. Tell the user: `"Step 6 skipped: no OPENAI_API_KEY — article will be text-only"`. Jump to Step 7.

If `{has_openai}` is true:

**6a — Generate image prompts + alt text (2 parallel Haiku calls):**

**Image 1 — Thumbnail:**

Extract the introduction text from `{article_markdown}` (everything between `{{IMAGE_THUMBNAIL}}` and the first `##`).

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 300,
    "messages": [{
      "role": "user",
      "content": "Generate a DALL-E image prompt and SEO alt text for a blog article thumbnail.\n\nArticle title: {outline.h1}\nTarget keyword: {ctx.keyword}\nArticle introduction: {article_introduction_text}\nTarget reader: {ctx.icp.role}\nBrand tone: {ctx.brand_voice.tone}\n\nThe image should:\n- Be professional and clean, suitable for a B2B SaaS blog\n- Visually represent the article topic without any text overlaid\n- Use a modern, minimal flat design aesthetic\n- Not include any people'"'"'s faces\n- Work well at 1792x1024 resolution\n\nReturn only valid JSON. No explanation. Start with { and end with }.\n\n{\"dalle_prompt\": \"string\", \"alt_text\": \"string — descriptive, includes target keyword naturally, under 125 characters\"}"
    }]
  }' > /tmp/img_prompt_1.json &
```

**Image 2 — Mid-article illustration:**

Find the H2 section where `image.image_number = 2` in the outline. Extract the corresponding text from `{article_markdown}`.

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 300,
    "messages": [{
      "role": "user",
      "content": "Generate a DALL-E image prompt and SEO alt text for a mid-article illustration.\n\nSection this image introduces: {image_section_h2}\nTarget keyword: {ctx.keyword}\nSection content: {image_section_text}\nTarget reader: {ctx.icp.role}\nBrand tone: {ctx.brand_voice.tone}\n\nThe image should:\n- Visually represent the core concept of this specific section\n- Be professional and clean, suitable for a B2B SaaS blog\n- Use a modern, minimal flat design aesthetic\n- Not include any people'"'"'s faces\n- No text overlaid on the image\n- Work well at 1792x1024 resolution\n\nReturn only valid JSON. No explanation. Start with { and end with }.\n\n{\"dalle_prompt\": \"string\", \"alt_text\": \"string — descriptive, includes target keyword naturally, under 125 characters\"}"
    }]
  }' > /tmp/img_prompt_2.json &

wait
```

Parse both prompt files.

**6b — Generate images (2 parallel DALL-E calls):**

```bash
# Fire both DALL-E calls in parallel
(curl -s -X POST "https://api.openai.com/v1/images/generations" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dall-e-3",
    "prompt": "{image_1_dalle_prompt}",
    "n": 1,
    "size": "1792x1024",
    "quality": "standard",
    "style": "natural"
  }' > /tmp/dalle_1.json) &

(curl -s -X POST "https://api.openai.com/v1/images/generations" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dall-e-3",
    "prompt": "{image_2_dalle_prompt}",
    "n": 1,
    "size": "1792x1024",
    "quality": "standard",
    "style": "natural"
  }' > /tmp/dalle_2.json) &

wait
```

Parse both responses. Extract image URLs from `data[0].url`.

**6c — Download images locally:**

Create the output directory and download both images:

```bash
mkdir -p "./blog-posts/{date}-{slug}/images"

curl -s -o "./blog-posts/{date}-{slug}/images/thumbnail.png" "{dalle_1_url}"
curl -s -o "./blog-posts/{date}-{slug}/images/mid-article.png" "{dalle_2_url}"
```

> NOTE: OpenAI image URLs expire after 1 hour. Download immediately.

Store the local paths and alt texts:
- `{image_1_path}` = `images/thumbnail.png` (relative to article folder)
- `{image_1_alt}` = alt text from Haiku
- `{image_2_path}` = `images/mid-article.png`
- `{image_2_alt}` = alt text from Haiku

Tell the user: `"Step 6 complete: 2 images generated and saved"`

---

## STEP 7 — Image Placeholder Replacement + Article Finalization

Type: Code only. No API. No LLM.

**If `{has_openai}` is true and images were generated:**

Replace placeholders with standard markdown image syntax:
- `{{IMAGE_THUMBNAIL}}` → `![{image_1_alt}](images/thumbnail.png)`
- `{{IMAGE_MID_ARTICLE}}` → `![{image_2_alt}](images/mid-article.png)`

**If `{has_openai}` is false (no images generated):**

Do NOT delete the placeholder lines. Replace them with descriptive HTML comments so the user knows exactly what image to source themselves and where it goes:

- `{{IMAGE_THUMBNAIL}}` →
  `<!-- THUMBNAIL IMAGE: {outline.sections[image_1].image.depicts} — recommended size 1792x1024. Upload this as your blog's featured image / hero image. -->`

- `{{IMAGE_MID_ARTICLE}}` →
  `<!-- MID-ARTICLE IMAGE: {outline.sections[image_2].image.depicts} — place above the "{image_section_h2}" section. Recommended size 1792x1024. -->`

This way even without DALL-E, the user has clear guidance on what image to add and where.

Store the final article as `{final_article}`.

---

## STEP 8 — Schema Markup Generation

Type: Claude Haiku. 1 call.

Extract the FAQ section from `{final_article}` — everything between `## FAQ` (or similar heading) and the next `##` or end of file.

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 1000,
    "messages": [{
      "role": "user",
      "content": "Generate structured data schema markup for the following article.\n\nArticle title: {outline.h1}\nMeta description: {outline.meta_description}\nBusiness name: {ctx.business_profile.business_name}\nURL slug: {outline.url_slug}\nPublish date: {today_date}\n\nFAQ section content:\n{faq_content}\n\nGenerate two schema objects:\n1. Article schema (type: Article)\n2. FAQPage schema using the FAQ questions and answers above\n\nReturn only valid JSON. No explanation. No markdown code blocks.\nStart with { and end with }.\n\n{\"article_schema\": {\"@context\": \"https://schema.org\", \"@type\": \"Article\", \"headline\": \"string\", \"description\": \"string\", \"author\": {\"@type\": \"Organization\", \"name\": \"string\"}, \"datePublished\": \"string\", \"dateModified\": \"string\"}, \"faq_schema\": {\"@context\": \"https://schema.org\", \"@type\": \"FAQPage\", \"mainEntity\": [{\"@type\": \"Question\", \"name\": \"string\", \"acceptedAnswer\": {\"@type\": \"Answer\", \"text\": \"string\"}}]}}"
    }]
  }'
```

Parse and store as `{schema_markup}`.

---

## STEP 9 — Meta Assets Generation

Type: Claude Haiku. 1 call.

Extract the first paragraph from `{final_article}` (first block of text after the H1).

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "max_tokens": 500,
    "messages": [{
      "role": "user",
      "content": "Generate SEO meta assets for the following article.\n\nArticle title: {outline.h1}\nFirst paragraph: {first_paragraph}\nTarget keyword: {ctx.keyword}\nArticle type: {outline.article_type}\nBrand voice: {ctx.brand_voice.tone}\n\nReturn only valid JSON. No explanation. No markdown code blocks.\nStart with { and end with }.\n\n{\"meta_title\": \"string — under 60 characters, keyword in first half\", \"meta_description\": \"string — 150 to 155 characters exactly, includes keyword, ends with hook or benefit\", \"url_slug\": \"string — lowercase hyphenated, keyword present, no stop words, under 60 characters\", \"social_excerpt\": \"string — 1 to 2 sentences for LinkedIn or Twitter, generates curiosity or conveys immediate value\"}"
    }]
  }'
```

Parse and store as `{meta_assets}`. These override the outline's meta_title and meta_description if different — the article-informed versions from Step 9 are more accurate than the outline's pre-article guesses.

---

## STEP 10 — Final Assembly + Save + Tracking Update

Type: Code only. No API. No LLM.

Get today's date:
```bash
date +%Y-%m-%d
```

The article folder structure:

```
blog-posts/
  {date}-{slug}/
    article.md          ← PURE article content. Open, preview, copy into CMS body.
    publish-kit.md      ← Publishing checklist: meta, schema, images, social, keywords.
    images/
      thumbnail.png     ← Featured image (if generated)
      mid-article.png   ← Mid-article illustration (if generated)
```

---

**10a — Create the article folder:**

```bash
mkdir -p "./blog-posts/{date}-{slug}/images"
```

---

**10b — Write `article.md` — pure content, no frontmatter:**

This file is the article and ONLY the article. No YAML. No metadata. The user opens this file, previews it in any markdown editor, and what they see is what they publish.

Write `./blog-posts/{date}-{slug}/article.md`:

```markdown
{final_article}
```

That's it. Just the article content with images already embedded at the right positions (either as `![alt](images/file.png)` if generated, or as `<!-- IMAGE: ... -->` comments if not).

The user's workflow is: open `article.md` → preview → copy body into CMS. No parsing needed.

---

**10c — Write `publish-kit.md` — everything else as a checklist:**

Write `./blog-posts/{date}-{slug}/publish-kit.md`:

```markdown
# Publishing Kit — {outline.h1}

> Generated by Blog Engine · {ISO_TIMESTAMP}
> Keyword: {ctx.keyword} · Funnel: {ctx.funnel} · Article type: {outline.article_type}

---

## 1. CMS Fields

Copy each value below into the corresponding field in your CMS:

**Page title / Meta title:**
```
{meta_assets.meta_title}
```

**Meta description:**
```
{meta_assets.meta_description}
```

**URL slug:**
```
{meta_assets.url_slug}
```

---

## 2. Article body

Open `article.md` in this folder. Copy the entire content into your CMS body / editor field.

Images are already embedded in the markdown at the correct positions:
- **Thumbnail** (top of article) → also upload as your CMS "featured image" / hero
- **Mid-article image** → already positioned above the right H2 section

If images show as `<!-- IMAGE: ... -->` comments, you need to source them yourself.
The comment describes exactly what the image should depict and where it goes.

---

## 3. Featured image

Upload as your blog post's featured / hero / thumbnail image:

| File | Alt text |
|------|----------|
| `images/thumbnail.png` | {image_1_alt or "— not generated (no OPENAI_API_KEY)"} |

---

## 4. Social sharing

Copy this when posting on LinkedIn, Twitter/X, or other social platforms:

```
{meta_assets.social_excerpt}
```

---

## 5. Schema markup

Paste the following JSON-LD into your CMS's "Custom code" / "Head scripts" section.
If your CMS doesn't support this, skip it — it helps with rich results in Google.

**Article schema:**
```json
{schema_markup.article_schema}
```

**FAQ schema:**
```json
{schema_markup.faq_schema}
```

---

## 6. SEO checklist

Before publishing, verify:

- [ ] Meta title is under 60 characters: `{meta_assets.meta_title}` ({char_count} chars)
- [ ] Meta description is 150–155 characters: ({char_count} chars)
- [ ] URL slug matches: `{meta_assets.url_slug}`
- [ ] Featured image uploaded
- [ ] Article previews correctly in your CMS
- [ ] Internal links added to related articles in your cluster: **{ctx.cluster_name}**
- [ ] Schema markup pasted into head scripts (optional)

---

## 7. Keyword reference

**Primary keyword:** {ctx.keyword}
**Secondary keywords (should appear naturally in the article):**
{secondary_keywords as bulleted list}

**Target cluster:** {ctx.cluster_name}
**Pillar topic in this cluster:** {cluster pillar keyword}
**Funnel stage:** {ctx.funnel}
**Search volume:** {ctx.volume}/mo · **KD:** {ctx.kd} · **CPC:** ${ctx.cpc}

---

## 8. Article stats

| Metric | Value |
|--------|-------|
| Word count | {actual_word_count} |
| Target word count | {target_word_count} |
| Sections | {section_count} H2s + FAQ + Conclusion |
| Images | {image_count} ({generated_or_placeholder}) |
| Opportunity score | {ctx.opportunity_score} |
| Generated at | {ISO_TIMESTAMP} |
```

If images were not generated (`{has_openai}` is false), in section 3 of publish-kit.md replace the file reference with:

```markdown
## 3. Featured image

No image was generated (OPENAI_API_KEY not set).
Source a featured image yourself — it should depict:
> {outline.sections[image_1].image.depicts}

Recommended size: 1792 x 1024 px.
```

---

**10d — Update blog-config.json pipeline tracking:**

Read `.claude/blog-config.json`.

Find the matching pipeline item (by keyword). Update it:
```json
{
  "status": "done",
  "written_at": "{ISO_TIMESTAMP}",
  "article_path": "./blog-posts/{date}-{slug}/article.md"
}
```

Move the item from `topics.pipeline` to `topics.used`.

Write the file back.

---

**10e — Update CONTENT-PLAN.md:**

Read `CONTENT-PLAN.md`. Find the matching row in the `## Pipeline` table. Update its Status column from `queued` to `written`.

In the `## Written` table, add a new row:

```
| {n} | {keyword} | {cluster_name} | {funnel} | {today_date} | [article](./blog-posts/{date}-{slug}/article.md) |
```

If the Written table currently only has the placeholder `*(none yet)*` row, remove it first.

Write the file back.

---

## STEP 11 — Output to User

Show a structured summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ARTICLE GENERATED — {ctx.business_profile.business_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Title:       {outline.h1}
  Type:        {outline.article_type}
  Keyword:     {ctx.keyword}
  Funnel:      {ctx.funnel}
  Word count:  {actual_word_count} (target: {target_word_count})
  Images:      {2 generated / text-only with placement guides}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ./blog-posts/{date}-{slug}/

    article.md        ← Open this. This IS the article.
                         Images already in the right spots.
                         Copy the whole thing into your CMS body field.

    publish-kit.md    ← Open when ready to publish.
                         Meta title, description, URL slug,
                         social excerpt, schema markup, SEO checklist.
                         Go through it step by step.

    images/           ← Upload thumbnail.png as featured image.
      thumbnail.png      mid-article.png is already placed in the article.
      mid-article.png    (or see image guides in article.md if not generated)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUICK PUBLISH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Meta title:       {meta_assets.meta_title}
  Meta description: {meta_assets.meta_description}
  URL slug:         /{meta_assets.url_slug}
  Social:           {meta_assets.social_excerpt}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  This topic:  moved to "written" in CONTENT-PLAN.md
  Remaining:   {remaining_queued_count} topics queued

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Write the next queued post:
    /user:blog-write

  Or pick a specific topic:
    /user:blog-write "{next_queued_keyword}"

  Review your full content plan:
    Open CONTENT-PLAN.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
