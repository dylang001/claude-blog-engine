---
description: Keyword research, clustering, opportunity scoring, and Week 1 topic selection (10 topics)
argument-hint: [us|uk|in|au|ca|de|sg]
allowed-tools: Bash WebFetch Read Write
---

You are running the Blog Engine keyword research and topic clustering flow. This produces the full keyword universe your business should target, organized into content clusters with opportunity scores, and selects 10 topics for the user to write this week.

Follow every step exactly and in order. Do not skip steps unless explicitly marked as optional.

**IMPORTANT:** All data processing uses the pipeline script at `$HOME/.claude/blog-scripts/topics_pipeline.py`. Set this variable at the start:

```bash
PIPELINE="$HOME/.claude/blog-scripts/topics_pipeline.py"
```

Do NOT write inline Python. Every data transformation step has a corresponding subcommand in the pipeline script.

---

## INPUTS THIS SKILL NEEDS FROM THE USER

Before starting, show the user this checklist. Do not ask for anything yet — just display it:

```
Blog Engine — Topics Setup

What you'll need:
  [env]  DATAFORSEO_LOGIN         your DataForSEO account email
  [env]  DATAFORSEO_PASSWORD      your DataForSEO account password
  [env]  ANTHROPIC_API_KEY        your Anthropic API key (sk-ant-...)
  [arg]  location (optional)      target country: us / uk / in / au / ca / de / sg
                                  defaults to us if not provided
  [mid]  Domain Rating (DR)       checked once mid-run — takes ~30 seconds
                                  check at: https://ahrefs.com/website-authority-checker

Everything else is pulled automatically from your blog-config.json.
Starting now...
```

---

## BEFORE YOU START

Read `.claude/blog-config.json`.

If it does not exist or `business.business_name` is empty, stop and tell the user:
> "No business profile found. Run `/user:blog-onboard https://yoursite.com` first, then re-run `/user:blog-topics`."

Extract and store these values from the config — you will use them throughout:
- `{business_name}` ← `business.business_name`
- `{website}` ← `business.website` (root domain, no https/www)
- `{product_type}` ← `business.product_type`
- `{key_differentiator}` ← `business.key_differentiator`
- `{integrations}` ← `business.integrations` joined as comma-separated string
- `{icp_role}` ← `business.icp_signals.roles[0]` (first role, or "marketing professional" if empty)
- `{icp_pain}` ← `business.icp_signals.pain_points[0]` (first pain point)
- `{competitors}` ← `competitors` array (list of domain strings)

**Load already-used keywords to prevent repeats on re-runs:**

Read `topics.pipeline` and `topics.used` from `blog-config.json`. Build a JSON array of excluded keyword strings:
- Add the `keyword` field from every item in `topics.pipeline` (status: queued or in_progress)
- Add the `keyword` field from every item in `topics.used`
- Also add all `supporting_keywords` from each pipeline/used item

Write this array to `/tmp/blog_excluded.json`. This is passed to the filter step later.

If `topics.pipeline` or `topics.used` are non-empty, tell the user:
> "Found {n} keywords already in your pipeline or marked as used — these will be excluded from this run."

Check credentials via Bash:
```bash
[ -f .env ] && source .env
echo "LOGIN: ${DATAFORSEO_LOGIN:-MISSING}"
echo "PASS: ${DATAFORSEO_PASSWORD:-MISSING}"
echo "ANTHROPIC: ${ANTHROPIC_API_KEY:-MISSING}"
```

If any are MISSING, stop and tell the user:
> "Missing API keys in `.env`. Open `.env` in your project root and fill in: {list missing keys}. Save and re-run `/blog-topics`."

---

## LOCATION CODE

If the user passed an argument (e.g. `$ARGUMENTS` = `uk`), map it to a location code:
- `us` or empty → 2840
- `uk` → 2826
- `in` → 2356
- `au` → 2036
- `ca` → 2124
- `de` → 2276
- `sg` → 2702

Store as `{location_code}`. Default to 2840 if no argument or unrecognized.

Tell the user: `"Running keyword research for location: {location_label} ({location_code})"`

---

## STEP 2 — Pull User's Existing Keyword Rankings

```bash
[ -f .env ] && source .env
DATAFORSEO_CREDS=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

curl -s -X POST "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live" \
  -H "Authorization: Basic $DATAFORSEO_CREDS" \
  -H "Content-Type: application/json" \
  -d '[{
    "target": "{website}",
    "location_code": {location_code},
    "language_code": "en",
    "limit": 500
  }]' > /tmp/blog_user_ranked.json
```

> NOTE: Do NOT use `order_by` or `filters` params — they cause 40501 errors on this endpoint.

Parse with the pipeline script:

```bash
python3 $PIPELINE parse-ranked /tmp/blog_user_ranked.json \
  --domain "{website}" \
  --source user_existing \
  --output /tmp/blog_user_kw.json
```

If the API returns 0 items, that's fine for new domains — continue with an empty array.

Tell the user: `"Step 2 complete: {count} existing keyword rankings found for {website}"`

---

## STEP 3 — Pull Competitor Keywords

Run all competitor domains in parallel (one curl per competitor):

```bash
[ -f .env ] && source .env
DATAFORSEO_CREDS=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

(curl -s -X POST "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live" \
  -H "Authorization: Basic $DATAFORSEO_CREDS" \
  -H "Content-Type: application/json" \
  -d '[{"target": "{competitor_1_domain}", "location_code": {location_code}, "language_code": "en", "limit": 200}]' \
  > /tmp/blog_comp_1.json) &

(curl -s -X POST "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live" \
  -H "Authorization: Basic $DATAFORSEO_CREDS" \
  -H "Content-Type: application/json" \
  -d '[{"target": "{competitor_2_domain}", "location_code": {location_code}, "language_code": "en", "limit": 200}]' \
  > /tmp/blog_comp_2.json) &

(curl -s -X POST "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live" \
  -H "Authorization: Basic $DATAFORSEO_CREDS" \
  -H "Content-Type: application/json" \
  -d '[{"target": "{competitor_3_domain}", "location_code": {location_code}, "language_code": "en", "limit": 200}]' \
  > /tmp/blog_comp_3.json) &

wait
```

Parse each with the pipeline script:

```bash
python3 $PIPELINE parse-ranked /tmp/blog_comp_1.json --domain "{competitor_1_domain}" --source competitor --output /tmp/blog_comp_1_kw.json
python3 $PIPELINE parse-ranked /tmp/blog_comp_2.json --domain "{competitor_2_domain}" --source competitor --output /tmp/blog_comp_2_kw.json
python3 $PIPELINE parse-ranked /tmp/blog_comp_3.json --domain "{competitor_3_domain}" --source competitor --output /tmp/blog_comp_3_kw.json
```

Tell the user: `"Step 3 complete: competitor keywords collected across 3 competitors"`

---

## STEP 4A — Generate Seed Keywords

Build the API payload as a file to avoid JSON escaping issues:

```bash
[ -f .env ] && source .env
python3 -c "
import json
payload = {
    'model': 'claude-haiku-4-5-20251001',
    'max_tokens': 1000,
    'messages': [{'role': 'user', 'content': '''You are an SEO strategist generating seed keyword phrases for a content strategy.

Business context:
Business: {business_name}
Product: {product_type}
Key differentiator: {key_differentiator}
Integrations: {integrations}
Target customer role: {icp_role}
Their core pain: {icp_pain}

Generate 30 seed keyword phrases this target customer would search for on Google.

Think across these angles:
- The daily problems they face described in their own words
- The tools they use and want to connect, replace, or compare
- Competitor and integration brand names combined with use case terms
- The outcomes they want to achieve
- Workflow or process terms specific to their role

Rules:
- Each seed should be 2-5 words
- Do not use {business_name} as a seed
- No duplicates
- Phrases should reflect how a non-technical practitioner would search

Return only valid JSON, no explanation, no markdown formatting.
{\"seeds\": [\"string\", \"string\", \"string\"]}'''}]
}
with open('/tmp/blog_seed_payload.json', 'w') as f:
    json.dump(payload, f)
"

curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d @/tmp/blog_seed_payload.json > /tmp/blog_seed_response.json
```

Parse the response. Extract `content[0].text`, parse as JSON to get `seeds[]`. Store the 30 seed strings.

Tell the user: `"Step 4a complete: 30 seed keywords generated"`

---

## STEP 4B — Expand Each Seed

Fire all 30 seed expansion calls in parallel. Build the bash command from the seed list:

```bash
[ -f .env ] && source .env
DATAFORSEO_CREDS=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

mkdir -p /tmp/blog_seeds

# One curl per seed, all in parallel
i=0
for seed in "{seed_1}" "{seed_2}" ... "{seed_30}"; do
  (curl -s -X POST "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_keywords/live" \
    -H "Authorization: Basic $DATAFORSEO_CREDS" \
    -H "Content-Type: application/json" \
    -d "[{\"keywords\": [\"$seed\"], \"location_code\": {location_code}, \"language_code\": \"en\", \"limit\": 30}]" \
    > /tmp/blog_seeds/seed_$i.json) &
  i=$((i+1))
done
wait
```

Parse all results with the pipeline script:

```bash
python3 $PIPELINE parse-seeds \
  --dir /tmp/blog_seeds \
  --count 30 \
  --output /tmp/blog_seed_kw.json
```

Tell the user: `"Step 4b complete: {count} seed-expanded keywords collected"`

---

## STEP 4C — Bulk KD Lookup for Seed-Expanded Keywords

Extract keyword strings from the seed file for the bulk KD API:

```bash
[ -f .env ] && source .env
DATAFORSEO_CREDS=$(echo -n "$DATAFORSEO_LOGIN:$DATAFORSEO_PASSWORD" | base64)

KEYWORDS=$(python3 -c "
import json
with open('/tmp/blog_seed_kw.json') as f:
    print(json.dumps([k['keyword'] for k in json.load(f)]))
")

curl -s -X POST "https://api.dataforseo.com/v3/dataforseo_labs/google/bulk_keyword_difficulty/live" \
  -H "Authorization: Basic $DATAFORSEO_CREDS" \
  -H "Content-Type: application/json" \
  -d "[{\"keywords\": $KEYWORDS, \"location_code\": {location_code}, \"language_code\": \"en\"}]" \
  > /tmp/blog_bulk_kd.json
```

Write KD back onto seed keywords:

```bash
python3 $PIPELINE write-kd /tmp/blog_seed_kw.json /tmp/blog_bulk_kd.json \
  --output /tmp/blog_seed_kw.json
```

Tell the user: `"Step 4c complete: KD populated for seed-expanded keywords"`

---

## STEP 5 — Merge + Deduplicate

```bash
python3 $PIPELINE merge \
  /tmp/blog_user_kw.json \
  /tmp/blog_comp_1_kw.json \
  /tmp/blog_comp_2_kw.json \
  /tmp/blog_comp_3_kw.json \
  /tmp/blog_seed_kw.json \
  --output /tmp/blog_all_kw.json
```

Tell the user: `"Step 5 complete: {count} unique keywords after merge and deduplication"`

---

## STEP 5.5 — Get Domain Rating (DR)

Tell the user:
> "To filter keywords by difficulty, I need your website's Domain Rating (DR).
>
> Check it here: https://ahrefs.com/website-authority-checker
> Enter your domain ({website}) and look for the **DR** (Domain Rating) score.
>
> What is your DR? (Enter a number between 0–100, or type 'skip' to use a default of 30)"

Wait for their response.
- If they enter a number: store as `{user_dr}`
- If they type 'skip' or anything non-numeric: use `{user_dr}` = 30

KD ceiling = `{user_dr}` + 15.

---

## STEP 6 — Filter

```bash
python3 $PIPELINE filter /tmp/blog_all_kw.json \
  --min-vol 100 \
  --max-kd {kd_ceiling} \
  --exclude-file /tmp/blog_excluded.json \
  --output /tmp/blog_filtered.json
```

The script prints filter stats. Show them to the user.

---

## STEP 7 — Intent + Funnel Classification

Build payloads, fire API calls, parse responses. All via the pipeline script.

**Build payloads:**

```bash
python3 $PIPELINE build-funnel-payload /tmp/blog_filtered.json \
  --business-name "{business_name}" \
  --product-type "{product_type}" \
  --batch-size 50 \
  --output-dir /tmp/blog_funnel
```

**Fire all API calls in parallel** (the script tells you how many batches were created):

```bash
[ -f .env ] && source .env
for f in /tmp/blog_funnel/funnel_payload_*.json; do
  i=$(echo "$f" | grep -o '[0-9]*')
  (curl -s -X POST "https://api.anthropic.com/v1/messages" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" \
    -d @"$f" > "/tmp/blog_funnel/funnel_resp_$i.json") &
done
wait
```

**Parse responses:**

```bash
python3 $PIPELINE parse-funnel /tmp/blog_filtered.json \
  --response-dir /tmp/blog_funnel \
  --output /tmp/blog_classified.json
```

Tell the user: `"Step 7 complete: keywords classified by funnel stage"`

---

## STEP 8 — Cluster Grouping

**Build payload:**

```bash
python3 $PIPELINE build-cluster-payload /tmp/blog_classified.json \
  --business-name "{business_name}" \
  --product-type "{product_type}" \
  --integrations "{integrations}" \
  --output /tmp/blog_cluster_payload.json
```

**Fire API call:**

```bash
[ -f .env ] && source .env
curl -s -X POST "https://api.anthropic.com/v1/messages" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d @/tmp/blog_cluster_payload.json > /tmp/blog_cluster_response.json
```

**Parse response + assign clusters:**

```bash
python3 $PIPELINE parse-clusters /tmp/blog_classified.json /tmp/blog_cluster_response.json \
  --idmap /tmp/blog_cluster_payload.json.idmap.json \
  --output-keywords /tmp/blog_clustered.json \
  --output-clusters /tmp/blog_clusters.json
```

Tell the user: `"Step 8 complete: {count} clusters created"`

---

## STEP 9 — Opportunity Scoring

```bash
python3 $PIPELINE score /tmp/blog_clustered.json \
  --output /tmp/blog_scored.json
```

The scoring formula is simplified (no gap score — it adds false precision for new domains):
```
opportunity_score = volume_score × intent_multiplier × difficulty_score
```

Volume uses 95th percentile cap to prevent outlier keywords from crushing all other scores.

Tell the user: `"Step 9 complete: opportunity scores calculated"`

---

## STEP 10 — Week 1 Topic Selection

```bash
python3 $PIPELINE select-topics /tmp/blog_scored.json \
  --count 10 \
  --output /tmp/blog_week1.json
```

The script picks one topic per cluster (breadth first), then fills remaining from global pool. Max 3 refresh candidates. Balanced funnel mix.

---

## STEP 10.5 — Generate Article Titles

Generate one SEO article title per selected topic. This runs one Claude Haiku call for all 10 topics together.

```bash
python3 $PIPELINE generate-titles /tmp/blog_week1.json \
  --business-name "{business_name}" \
  --product-type "{product_type}"
```

This updates `/tmp/blog_week1.json` in place, adding a `title` field to each topic. If this step fails for any reason, continue — the keyword is used as a fallback title.

---

## STEP 11 — Save Results

```bash
python3 $PIPELINE save \
  --keywords /tmp/blog_scored.json \
  --clusters /tmp/blog_clusters.json \
  --topics /tmp/blog_week1.json \
  --config .claude/blog-config.json \
  --export-dir .claude/exports \
  --content-plan CONTENT-PLAN.md
```

---

## STEP 12 — Output to User

Read `/tmp/blog_week1.json` and show the output in two parts.

**Part 1 — Week 1 Content Plan:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WEEK 1 CONTENT PLAN — {business_name}
  {current_date} · {location_label} · {filtered_count} keywords researched
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  10 topics selected across {cluster_count} clusters
  Estimated reach: {sum_of_week1_volumes} monthly searches
```

Then list each of the 10 topics in a numbered, formatted block:

```
  ┌─ #1  [{funnel}]  Score: {opportunity_score}
  │  Title:    {title}
  │  Keyword:  {keyword}
  │  Cluster:  {cluster_name}
  │  Volume:   {volume}/mo   KD: {kd}   CPC: ${cpc}
  │  Action:   {action}
  │  Also target: {related_keyword_1}, {related_keyword_2}, {related_keyword_3}
  │  Why:      {why}
  └──────────────────────────────────────────────────
```

After all 10:

```
  Funnel breakdown:  {tofu_count} TOFU  ·  {mofu_count} MOFU  ·  {bofu_count} BOFU
  Refresh articles:  {refresh_count}   (update existing)
  New articles:      {new_count}       (write from scratch)
```

**Part 2 — Files & Next Steps:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FILES SAVED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  CONTENT-PLAN.md                        ← open this to track your content
  .claude/exports/keywords-{DATE}.csv    ← open in Excel / Google Sheets
  .claude/blog-keywords.json             (engine file — {filtered_count} keywords)
  .claude/blog-clusters.json             (engine file — {cluster_count} clusters)
  .claude/blog-config.json               (engine file — 10 topics queued)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Write your first post (picks #1 from pipeline automatically):
    /user:blog-write

  Write a specific topic by number:
    /user:blog-write 1
    /user:blog-write 3

  Write a specific topic by keyword:
    /user:blog-write "{top_topic_keyword}"

  Run research again next week (this week's topics auto-excluded):
    /user:blog-topics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
