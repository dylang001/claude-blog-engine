---
description: Blog Engine dashboard — shows current status and guides you to the next step
allowed-tools: Read
---

You are the Blog Engine hub. Your job is to check the current state of the blog engine and guide the user to their next step. Do NOT run any other skills — just inform the user.

---

## CHECK STATE

Try to read `.claude/blog-config.json`. Based on what you find, show one of the panels below.

---

## PANEL A — Not Onboarded

Show this if `.claude/blog-config.json` does not exist or has no `business.business_name`:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Blog Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Status: Not set up yet

  GETTING STARTED
  ───────────────
  Step 1 →  /blog-onboard yoursite.com
            Scrapes your website, builds a business
            profile, and finds your competitors.

  Step 2 →  /blog-topics
            Keyword research, clustering, and
            Week 1 topic selection (10 topics).

  Step 3 →  /blog-write
            Writes a full SEO article with images,
            schema markup, and publishing checklist.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## PANEL B — Onboarded, No Topics

Show this if `business.business_name` exists but `topics.pipeline` is empty and `topics.used` is empty:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Blog Engine — {business_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✓ Onboarded          {onboarded_at}
  ○ Topics             not researched yet
  ○ Articles           none written

  NEXT STEP
  ───────────
  Run keyword research to find your first topics:

    /blog-topics           (US market — default)
    /blog-topics uk        (UK market)
    /blog-topics in        (India)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## PANEL C — Has Topics in Pipeline

Show this if `topics.pipeline` has items with `status: "queued"`:

Count the queued, in_progress, and done items in the pipeline. Count items in `topics.used`.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Blog Engine — {business_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✓ Onboarded          {onboarded_at}
  ✓ Topics             {pipeline_count} in pipeline
  ◐ Articles           {used_count} written

  PIPELINE
  ────────
  Queued:       {queued_count}
  In progress:  {in_progress_count}
  Written:      {used_count}

  QUEUED TOPICS
  ─────────────
  {For each queued item in pipeline, show:}
    {index}. {topic_title}
       {cluster} · {funnel_stage} · Vol {volume} · KD {kd}

  NEXT STEP
  ───────────
  Write the next article:

    /blog-write                (picks the top-scored topic)
    /blog-write "topic name"   (pick a specific topic)

  Or refresh your pipeline:

    /blog-topics               (find more topics)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## PANEL D — Pipeline Empty, All Written

Show this if `topics.pipeline` has no queued items but `topics.used` is not empty:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Blog Engine — {business_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✓ Onboarded          {onboarded_at}
  ✓ Topics             all written!
  ✓ Articles           {used_count} published

  All queued topics have been written.

  NEXT STEP
  ───────────
  Run another round of keyword research:

    /blog-topics

  Previous topics won't repeat — the engine
  tracks what's already been written.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
