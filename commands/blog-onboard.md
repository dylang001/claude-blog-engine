---
description: One-time business onboarding — scrapes your website, builds business profile, finds 3 competitors via SERP
argument-hint: [your-website-url]
allowed-tools: Bash WebFetch Read Write
---

You are running the Blog Engine onboarding flow. Your job is to build a complete business profile by analyzing the user's website and finding their direct competitors. Follow these steps exactly and in order.

---

## BEFORE YOU START

### 1. Check for existing business profile

Check if `.claude/blog-config.json` already exists by attempting to read it.

If it exists and has a non-empty `business.business_name`:
- Ask: > "A business profile already exists for **{business_name}** (onboarded on {onboarded_at}). Do you want to overwrite it with a fresh onboarding?"
- Only proceed if they confirm. Otherwise exit.

### 2. Set up API keys via .env file

Check if a `.env` file exists in the project root by attempting to read it.

**If `.env` does NOT exist**, create it now with this exact content:

```
# Blog Engine — API Keys
# Fill in the required keys below, then tell Claude you're done.

# Required
DATAFORSEO_LOGIN=your@email.com
DATAFORSEO_PASSWORD=yourpassword
ANTHROPIC_API_KEY=sk-ant-...

# Optional — improve /blog-write article quality
FIRECRAWL_API_KEY=           # better page scraping  (firecrawl.dev — free tier)
TAVILY_API_KEY=              # deeper topic research  (tavily.com — free tier)
YOUTUBE_API_KEY=             # video insights         (console.cloud.google.com)
OPENAI_API_KEY=              # DALL-E article images  (platform.openai.com)
```

After creating `.env`, also protect it from accidental git commits. Check if `.gitignore` exists:
- If it exists and does NOT already contain `.env`, append `.env` to it
- If it does NOT exist, create it with just `.env`

Then tell the user:

> "I've created a `.env` file in your project root and added it to `.gitignore` so your keys stay private. Open `.env` and fill in at minimum:
> - `DATAFORSEO_LOGIN` — your DataForSEO email (free account at dataforseo.com)
> - `DATAFORSEO_PASSWORD` — your DataForSEO password
> - `ANTHROPIC_API_KEY` — your key from console.anthropic.com
>
> The optional keys can be added any time before running `/blog-write`.
> **Reply here when you've saved the file and I'll continue.**"

Wait for the user to confirm before proceeding.

**If `.env` already exists**, read it silently and continue (do not show it to the user).

---

## STEP 0 — Get the Website URL

If the user passed a URL as `$ARGUMENTS`, use that directly. Skip asking.

If no argument was provided, ask:
> "What is your website URL? (e.g. https://yoursite.com)"

Wait for their response. Store it as `{user_website_url}`. Strip trailing slashes.

---

## STEP 1 — Scrape the Website

Tell the user: `Scraping {user_website_url}...`

Use WebFetch to retrieve the website content from `{user_website_url}`.

Also attempt to fetch these additional pages if they exist (use WebFetch on each, ignore errors silently):
- `{user_website_url}/about`
- `{user_website_url}/pricing`
- `{user_website_url}/features`
- `{user_website_url}/product`

Concatenate all successfully fetched content into a single block: `{scraped_content}`.

If the main URL fetch fails entirely, tell the user:
> "Could not reach {user_website_url}. Please check the URL and try again."
Then stop.

---

## STEP 2 — Extract Business Profile

Tell the user: `Extracting business profile...`

Using the scraped content, produce the business profile JSON by reasoning through the following extraction prompt. Think step by step internally, then output only the final JSON.

**Extraction prompt:**

You are analyzing a SaaS company's website to extract structured business information for an SEO content strategist.

Below is the website content:
<website_content>
{scraped_content}
</website_content>

Extract the following information. If something is not clearly stated on the website, make a reasonable inference based on context. Do not leave fields empty — use your best judgment and mark inferred fields with "inferred": true.

Return only valid JSON, no explanation, no markdown formatting.

```
{
  "business_name": "string — company name",
  "website": "string — domain only, no https or www",
  "product_type": "string — one sentence describing what the product is",
  "primary_use_case": "string — the main thing users do with this product",
  "key_features": ["string", "string", "string"],
  "integrations": ["string"],
  "business_model": "string — B2B SaaS / B2C / Marketplace / Agency tool / etc",
  "target_geography": "string — Global / US-focused / specific region if mentioned",
  "pricing_model": "string — subscription / freemium / usage-based / not mentioned",
  "key_differentiator": "string — what makes this product different, in one sentence",
  "icp_signals": {
    "roles": ["string"],
    "industries": ["string"],
    "company_size": "string — SMB / Mid-market / Enterprise / not specified",
    "pain_points": ["string"]
  },
  "brand_voice_signals": "string — describe the tone of the website copy in one sentence",
  "inferred_fields": ["string"]
}
```

Store the parsed result as `{business_profile}`.

---

## STEP 3A — SERP Competitor Search

Build a search keyword from the business profile:
- Use `{business_profile.product_type}` as the base
- Format it as: `"{product_type} software"` (e.g. "email marketing automation software")
- If product_type is vague, fall back to: `"best {primary_use_case} tools"`

Check for DataForSEO credentials by running:

```bash
[ -f .env ] && source .env
echo "LOGIN=${DATAFORSEO_LOGIN:+set} PASSWORD=${DATAFORSEO_PASSWORD:+set}"
```

If either variable is not printed as `set`, tell the user:
> "DataForSEO credentials are missing or still contain placeholder values in `.env`.
> Open `.env` in your project root, fill in `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`, save, and reply here."
Then stop.

Tell the user: `Finding competitors via SERP...`

Make the following API call using Bash with curl:

```bash
[ -f .env ] && source .env
DATAFORSEO_CREDS=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

curl -s -X POST "https://api.dataforseo.com/v3/serp/google/organic/live/regular" \
  -H "Authorization: Basic $DATAFORSEO_CREDS" \
  -H "Content-Type: application/json" \
  -d '[{
    "keyword": "{search_keyword}",
    "location_code": 2840,
    "language_code": "en",
    "depth": 10
  }]'
```

Parse the response. Extract the `items` array from `tasks[0].result[0].items`.

For each item, keep only: `domain`, `title`, `description` (or `snippet`).

Store this as `{serp_results}`. If the API call fails or returns an error status, show the error and stop.

---

## STEP 3B — LLM Competitor Filter

Tell the user: `Filtering competitors...`

Using the SERP results, identify 3 direct competitors by reasoning through the following filter prompt:

**Filter prompt:**

You are identifying direct competitors for a business from a list of search results.

The business being analyzed:
- Name: {business_profile.business_name}
- Product: {business_profile.product_type}
- Domain: {business_profile.website}

Here are the search results:
{serp_results}

Rules:
- Exclude the user's own domain: {business_profile.website}
- Exclude review sites, comparison sites, and aggregators: g2.com, capterra.com, trustpilot.com, getapp.com, softwareadvice.com, producthunt.com, medium.com, reddit.com
- Exclude generic platforms that are not direct competitors: google.com, microsoft.com, apple.com, youtube.com
- Prefer companies whose core product or service directly competes with the analyzed business
- Return exactly 3 competitors. If fewer than 3 clear direct competitors exist, fill remaining slots with the closest indirect competitors from the list
- Return only the root domain without https or www

Return raw JSON only. No markdown. No code blocks. Start with { and end with }.

```
{
  "competitors": [
    {
      "domain": "string",
      "company_name": "string",
      "reason": "string — one sentence why this is a direct competitor"
    }
  ]
}
```

Store the result as `{competitor_data}`.

---

## STEP 4 — Save to Config

Get the current timestamp:
```bash
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

Create the `.claude/` directory if it doesn't exist:
```bash
mkdir -p .claude/exports
```

Write the following JSON to `.claude/blog-config.json`:

```json
{
  "version": "1.0",
  "onboarded_at": "{ISO_TIMESTAMP}",
  "business": {business_profile},
  "competitors": {competitor_data.competitors},
  "topics": {
    "last_research_run": null,
    "total_keywords": 0,
    "cluster_count": 0,
    "pipeline": [],
    "used": []
  }
}
```

---

## STEP 5 — Create Scaffold Files

Create two empty scaffold files so the user sees the full structure immediately — before running `/user:blog-topics`.

**5a — Create `CONTENT-PLAN.md` in the project root:**

Write this file (do not overwrite if it already exists — check first with Read):

```markdown
# Content Plan — {business_name}

> Managed by Blog Engine · Created: {current_date}
> Run `/user:blog-topics` to populate this plan with researched keyword opportunities.

---

## Pipeline

Topics queued for writing. Populated after running `/user:blog-topics`.

| # | Topic | Cluster | Funnel | Vol/mo | KD | Score | Action | Status |
|---|-------|---------|--------|--------|----|-------|--------|--------|
| — | *(run `/user:blog-topics` to populate)* | | | | | | | |

---

## Written

Articles completed via `/user:blog-write`. Updated automatically when an article is written.

| # | Topic | Cluster | Funnel | Written | Article URL |
|---|-------|---------|--------|---------|-------------|
| — | *(none yet)* | | | | |

---

## Keyword Clusters

Topic clusters populated after running `/user:blog-topics`.

*(none yet — run `/user:blog-topics` to generate clusters)*

---

## Business Profile

- **Business:** {business_name}
- **Product:** {product_type}
- **ICP:** {icp_roles} at {company_size} companies
- **Differentiator:** {key_differentiator}
- **Competitors:** {competitor_1_domain}, {competitor_2_domain}, {competitor_3_domain}

---

## Files

| File | What it contains |
|------|-----------------|
| `CONTENT-PLAN.md` | This file — human-readable pipeline tracker |
| `.claude/exports/` | Keyword CSVs stamped by date — open in Excel or Google Sheets |
| `.claude/blog-keywords.json` | Full keyword data (engine file) |
| `.claude/blog-clusters.json` | Cluster map (engine file) |
| `.claude/blog-config.json` | Pipeline state — do not edit manually |
```

For `{icp_roles}`, join `business_profile.icp_signals.roles` as a comma-separated string. For competitor domains, use the first 3 from `{competitor_data.competitors}`.

**5b — The `.claude/exports/` folder** is already created in Step 4. No further action needed — CSVs will be written here by `/user:blog-topics`.

---

## STEP 6 — Confirmation Summary

After saving, show the user a clean summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Onboarding complete — {business_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Business Profile
    Product:        {product_type}
    Model:          {business_model}
    ICP:            {roles joined by ", "} at {company_size} companies
    Differentiator: {key_differentiator}

  Competitors Found
    1. {competitor_1.company_name} ({competitor_1.domain})
       {competitor_1.reason}
    2. {competitor_2.company_name} ({competitor_2.domain})
       {competitor_2.reason}
    3. {competitor_3.company_name} ({competitor_3.domain})
       {competitor_3.reason}

  Files Created
    .claude/blog-config.json    business profile + pipeline state
    .claude/exports/            keyword CSVs will be saved here
    CONTENT-PLAN.md             your content tracker — open this anytime

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NEXT STEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Run keyword research to populate your content plan:
    /user:blog-topics         (defaults to US)
    /user:blog-topics uk      (UK market)
    /user:blog-topics in      (India market)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If any fields were inferred from the website, add:
> "Note: {N} fields were inferred from context (marked in blog-config.json). Review if needed."
