#!/usr/bin/env python3
"""
Blog Engine — Topics Pipeline

Deterministic keyword processing for blog-topics. Every data transformation
step is a subcommand here so the LLM only orchestrates API calls, not logic.

Usage from blog-topics skill:
    PIPELINE="$HOME/.claude/blog-scripts/topics_pipeline.py"
    python3 $PIPELINE <subcommand> <args>

Subcommands:
    parse-ranked        Parse DataForSEO ranked_keywords response
    parse-seeds         Parse keywords_for_keywords responses
    write-kd            Write bulk KD data back onto keyword records
    merge               Merge + deduplicate keyword sources
    filter              Apply volume/KD/ranking filters
    build-funnel-payload  Build Claude API payloads for funnel classification
    parse-funnel        Parse funnel classification responses
    build-cluster-payload Build Claude API payload for clustering
    parse-clusters      Parse cluster response, assign cluster IDs
    score               Calculate opportunity scores (0–100 scale, 70+ = good)
    select-topics       Pick Week 1 topics
    generate-titles     Generate SEO article titles for each selected topic
    save                Write all output files (config, CSV, CONTENT-PLAN.md)
"""

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# parse-ranked: Parse DataForSEO ranked_keywords/live response
# ---------------------------------------------------------------------------
def cmd_parse_ranked(args):
    with open(args.input) as f:
        data = json.load(f)

    task = data.get("tasks", [{}])[0]
    result = task.get("result", [{}])
    items = result[0].get("items") or [] if result else []
    records = []

    for item in items:
        kd = item.get("keyword_data", {})
        keyword = kd.get("keyword", "")
        if not keyword:
            continue

        serp = item.get("ranked_serp_element", {}).get("serp_item", {})
        position = serp.get("rank_group")
        url = serp.get("url")

        record = {
            "keyword": keyword,
            "volume": kd.get("keyword_info", {}).get("search_volume"),
            "kd": kd.get("keyword_properties", {}).get("keyword_difficulty"),
            "cpc": kd.get("keyword_info", {}).get("cpc"),
            "intent": kd.get("search_intent_info", {}).get("main_intent"),
            "source": args.source,
            "funnel": None,
            "cluster": None,
            "cluster_name": None,
            "opportunity_score": None,
            "status": None,
            "user_ranking_position": position if args.source == "user_existing" else None,
            "user_ranking_url": url if args.source == "user_existing" else None,
            "competitor_rankings": (
                {args.domain: position} if args.source == "competitor" else {}
            ),
        }
        records.append(record)

    with open(args.output, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Parsed {len(records)} keywords from {args.input} (source={args.source})")


# ---------------------------------------------------------------------------
# parse-seeds: Parse keywords_for_keywords/live responses
#
# NOTE: This endpoint returns keyword objects directly in the `result` array,
# NOT nested under `result[0].items`. Each result element has `keyword`,
# `search_volume`, `cpc` at the top level.
# ---------------------------------------------------------------------------
def cmd_parse_seeds(args):
    records = []

    for i in range(args.count):
        filepath = os.path.join(args.dir, f"seed_{i}.json")
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath) as f:
                data = json.load(f)

            task = data.get("tasks", [{}])[0]
            if task.get("status_code") != 20000:
                continue

            # result IS the keyword array (not result[0].items)
            results = task.get("result") or []
            for item in results:
                keyword = item.get("keyword", "")
                if keyword:
                    records.append(
                        {
                            "keyword": keyword,
                            "volume": item.get("search_volume"),
                            "kd": None,
                            "cpc": item.get("cpc"),
                            "intent": None,
                            "source": "seed_expansion",
                            "funnel": None,
                            "cluster": None,
                            "cluster_name": None,
                            "opportunity_score": None,
                            "status": None,
                            "user_ranking_position": None,
                            "user_ranking_url": None,
                            "competitor_rankings": {},
                        }
                    )
        except Exception:
            continue

    # Deduplicate on lowercase keyword
    seen = {}
    for r in records:
        key = r["keyword"].lower().strip()
        if key not in seen:
            seen[key] = r
    deduped = list(seen.values())

    with open(args.output, "w") as f:
        json.dump(deduped, f, indent=2)

    print(f"Parsed {len(deduped)} unique seed-expanded keywords from {args.count} files")


# ---------------------------------------------------------------------------
# write-kd: Write bulk_keyword_difficulty results back onto keyword records
# ---------------------------------------------------------------------------
def cmd_write_kd(args):
    with open(args.keywords) as f:
        keywords = json.load(f)
    with open(args.kd_response) as f:
        kd_data = json.load(f)

    kd_map = {}
    result = kd_data.get("tasks", [{}])[0].get("result") or []
    if result:
        items = result[0].get("items") or []
        for item in items:
            kw = item.get("keyword", "").lower().strip()
            kd_map[kw] = item.get("keyword_difficulty")

    updated = 0
    for k in keywords:
        val = kd_map.get(k["keyword"].lower().strip())
        if val is not None:
            k["kd"] = val
            updated += 1

    with open(args.output, "w") as f:
        json.dump(keywords, f, indent=2)

    print(f"KD populated for {updated}/{len(keywords)} keywords")


# ---------------------------------------------------------------------------
# merge: Merge multiple keyword source files, deduplicate
# ---------------------------------------------------------------------------
def cmd_merge(args):
    all_records = []
    for filepath in args.files:
        if os.path.exists(filepath):
            with open(filepath) as f:
                data = json.load(f)
                if data:
                    all_records.extend(data)

    src_priority = {"user_existing": 3, "competitor": 2, "seed_expansion": 1}

    merged = {}
    for k in all_records:
        key = k["keyword"].lower().strip()
        if key not in merged:
            merged[key] = k.copy()
            merged[key]["competitor_rankings"] = dict(
                k.get("competitor_rankings") or {}
            )
        else:
            existing = merged[key]
            ep = src_priority.get(existing.get("source", ""), 0)
            np = src_priority.get(k.get("source", ""), 0)

            # Higher priority source overwrites non-null fields
            if np >= ep:
                for field in ("volume", "kd", "cpc", "intent"):
                    if k.get(field) is not None:
                        existing[field] = k[field]
                if np > ep:
                    existing["source"] = k["source"]
            else:
                for field in ("volume", "kd", "cpc", "intent"):
                    if existing.get(field) is None and k.get(field) is not None:
                        existing[field] = k[field]

            # Always merge user ranking info
            if k.get("user_ranking_position") is not None:
                existing["user_ranking_position"] = k["user_ranking_position"]
                existing["user_ranking_url"] = k.get("user_ranking_url")

            # Always merge competitor rankings
            if k.get("competitor_rankings"):
                for domain, pos in k["competitor_rankings"].items():
                    if pos is not None:
                        existing["competitor_rankings"][domain] = pos

    result = list(merged.values())
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Merged {len(all_records)} records -> {len(result)} unique keywords")


# ---------------------------------------------------------------------------
# filter: Apply volume floor, KD ceiling, ranking filters
# ---------------------------------------------------------------------------
def cmd_filter(args):
    with open(args.input) as f:
        keywords = json.load(f)

    excluded = set()
    if args.exclude_file and os.path.exists(args.exclude_file):
        with open(args.exclude_file) as f:
            excluded = {kw.lower().strip() for kw in json.load(f)}

    removed_vol = removed_kd = removed_ranking = removed_excluded = refresh = 0
    filtered = []

    for k in keywords:
        vol = k.get("volume") or 0
        kd = k.get("kd")
        pos = k.get("user_ranking_position")
        kw_lower = k["keyword"].lower().strip()

        if vol < args.min_vol:
            removed_vol += 1
            continue
        if kd is not None and kd > args.max_kd:
            removed_kd += 1
            continue
        if pos is not None and pos <= 5:
            removed_ranking += 1
            continue
        if kw_lower in excluded:
            removed_excluded += 1
            continue

        if pos is not None and 8 <= pos <= 20:
            k["status"] = "refresh_candidate"
            refresh += 1
        else:
            k["status"] = "new_content"

        filtered.append(k)

    with open(args.output, "w") as f:
        json.dump(filtered, f, indent=2)

    print(f"Filtered: {len(filtered)} remaining")
    print(f"  Removed by volume floor (<{args.min_vol}):  {removed_vol}")
    print(f"  Removed by KD ceiling (>{args.max_kd}):     {removed_kd}")
    print(f"  Removed as already ranking (<=5):            {removed_ranking}")
    print(f"  Removed as excluded (pipeline/used):         {removed_excluded}")
    print(f"  Refresh candidates flagged:                  {refresh}")


# ---------------------------------------------------------------------------
# score: Calculate opportunity scores (0–100 scale, 70+ = good opportunity)
#
# Formula: weighted additive (not multiplicative — avoids score compression)
#   score = (0.40 × volume_score + 0.40 × difficulty_score + 0.20 × funnel_score) × 100
#
# Volume: log-normalized against fixed anchor of 100,000.
#   - Handles outliers naturally without percentile tricks
#   - 1,000 vol → 60%, 10,000 vol → 80%, 100,000+ → 100%
#
# Difficulty: linear inverse of KD. Null KD → 0.5 (neutral, not penalized).
#
# Funnel: BOFU=1.0, MOFU=0.85, TOFU=0.70, unknown=0.75
# ---------------------------------------------------------------------------
_VOLUME_ANCHOR = 100_000  # fixed log normalization anchor


def _volume_score(volume):
    v = max(volume or 0, 1)
    return min(1.0, math.log10(v) / math.log10(_VOLUME_ANCHOR))


def _difficulty_score(kd):
    if kd is None:
        return 0.5
    return max(0.0, (100 - kd) / 100)


def _funnel_score(funnel):
    return {"BOFU": 1.0, "MOFU": 0.85, "TOFU": 0.70}.get(funnel, 0.75)


def cmd_score(args):
    with open(args.input) as f:
        keywords = json.load(f)

    for k in keywords:
        vs = _volume_score(k.get("volume"))
        ds = _difficulty_score(k.get("kd"))
        fs = _funnel_score(k.get("funnel"))
        k["opportunity_score"] = round((0.40 * vs + 0.40 * ds + 0.20 * fs) * 100, 1)

    keywords.sort(key=lambda x: -(x.get("opportunity_score") or 0))

    with open(args.output, "w") as f:
        json.dump(keywords, f, indent=2)

    print(f"Scored {len(keywords)} keywords (scale 0–100, 70+ = good opportunity)")
    for k in keywords[:5]:
        print(
            f"  {k['opportunity_score']:5.1f} | vol={k.get('volume')} "
            f"kd={k.get('kd')} [{k.get('funnel')}] {k['keyword']}"
        )


# ---------------------------------------------------------------------------
# build-funnel-payload: Build Claude API payloads for funnel classification
# ---------------------------------------------------------------------------
def cmd_build_funnel_payload(args):
    with open(args.input) as f:
        keywords = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    batch_size = args.batch_size
    batches = []
    for i in range(0, len(keywords), batch_size):
        batch = [
            {"keyword": k["keyword"], "intent": k.get("intent")}
            for k in keywords[i : i + batch_size]
        ]
        batches.append(batch)

    prompt_template = (
        "You are an SEO strategist classifying keywords by funnel stage.\n\n"
        "Business context:\n"
        "- Business: {business_name}\n"
        "- Product: {product_type}\n\n"
        "Classify each keyword by funnel stage.\n\n"
        "Options: TOFU (broad problem-aware), MOFU (solution-aware/evaluating), "
        "BOFU (product-aware/ready to act), null (navigational)\n\n"
        "Signals:\n"
        "- navigational intent -> null\n"
        "- informational + broad concept -> TOFU\n"
        "- informational + specific use case/workflow/integration -> MOFU\n"
        "- commercial + alternatives/vs/best/compare -> MOFU\n"
        "- commercial + specific brand/integration -> BOFU\n"
        "- transactional + connect/sync/integrate/export/setup -> BOFU\n"
        "- transactional + pricing/free/trial/demo -> BOFU\n\n"
        "Keywords:\n{keywords}\n\n"
        'Return ONLY a valid JSON array. No explanation. No markdown.\n'
        '[{{"keyword": "string", "funnel": "TOFU | MOFU | BOFU | null"}}]'
    )

    for i, batch in enumerate(batches):
        prompt = prompt_template.format(
            business_name=args.business_name,
            product_type=args.product_type,
            keywords=json.dumps(batch, indent=2),
        )
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        }
        filepath = os.path.join(args.output_dir, f"funnel_payload_{i}.json")
        with open(filepath, "w") as f:
            json.dump(payload, f)

    print(f"Built {len(batches)} funnel payloads in {args.output_dir}")


# ---------------------------------------------------------------------------
# parse-funnel: Parse funnel classification responses
# ---------------------------------------------------------------------------
def cmd_parse_funnel(args):
    with open(args.input) as f:
        keywords = json.load(f)

    kw_map = {k["keyword"].lower().strip(): k for k in keywords}
    classified = 0

    for filename in sorted(os.listdir(args.response_dir)):
        if not filename.startswith("funnel_resp_") or not filename.endswith(".json"):
            continue
        filepath = os.path.join(args.response_dir, filename)
        try:
            with open(filepath) as f:
                resp = json.load(f)
            if "error" in resp:
                continue
            text = resp["content"][0]["text"]
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if not match:
                continue
            results = json.loads(match.group())
            for item in results:
                key = item["keyword"].lower().strip()
                if key in kw_map:
                    kw_map[key]["funnel"] = item.get("funnel")
                    classified += 1
        except Exception:
            continue

    with open(args.output, "w") as f:
        json.dump(keywords, f, indent=2)

    dist = defaultdict(int)
    for k in keywords:
        dist[k.get("funnel") or "null"] += 1

    print(f"Classified {classified} keywords")
    print(f"Distribution: {dict(dist)}")


# ---------------------------------------------------------------------------
# build-cluster-payload: Build Claude API payload for keyword clustering
#
# Uses SEQUENTIAL IDs (1..N) assigned only to the keywords sent to Claude.
# Saves an ID map file (id -> keyword string) so parse-clusters can resolve
# IDs back to keywords reliably.
# ---------------------------------------------------------------------------
def cmd_build_cluster_payload(args):
    with open(args.input) as f:
        keywords = json.load(f)

    # Only cluster non-null funnel keywords
    cluster_kw = []
    id_counter = 1
    id_map = {}
    for k in keywords:
        if k.get("funnel") in ("TOFU", "MOFU", "BOFU"):
            cluster_kw.append(
                {
                    "id": id_counter,
                    "keyword": k["keyword"],
                    "volume": k.get("volume"),
                    "intent": k.get("intent"),
                    "funnel": k.get("funnel"),
                }
            )
            id_map[id_counter] = k["keyword"]
            id_counter += 1

    # Save ID map alongside the payload
    idmap_path = args.output + ".idmap.json"
    with open(idmap_path, "w") as f:
        json.dump(id_map, f)

    prompt = (
        "You are a senior SEO content strategist building a topical authority map.\n\n"
        "Business context:\n"
        "- Business: {business_name}\n"
        "- Product: {product_type}\n"
        "- Key integrations: {integrations}\n\n"
        "Group the keywords below into 6-10 topic clusters.\n\n"
        "Rules:\n"
        "- Each cluster has exactly one pillar keyword (broadest/highest volume, prefer TOFU/MOFU)\n"
        "- All other keywords are supporting\n"
        "- BOFU keywords go into the most relevant cluster (no BOFU-only clusters)\n"
        "- Each cluster = distinct topic area, no overlap\n"
        "- Every keyword must be in exactly one cluster\n"
        "- Do not invent keywords\n\n"
        "Keywords:\n{keywords}\n\n"
        "Return ONLY valid JSON. No explanation. No markdown. Start with {{ end with }}.\n"
        '{{"clusters": [{{"cluster_id": "string", "cluster_name": "string", '
        '"pillar_keyword": "string", "pillar_intent": "string", '
        '"pillar_funnel": "string", "supporting_keyword_ids": [1, 2, 3]}}]}}'
    ).format(
        business_name=args.business_name,
        product_type=args.product_type,
        integrations=args.integrations,
        keywords=json.dumps(cluster_kw, indent=2),
    )

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }

    with open(args.output, "w") as f:
        json.dump(payload, f)

    print(f"Built cluster payload ({len(cluster_kw)} keywords, idmap at {idmap_path})")


# ---------------------------------------------------------------------------
# parse-clusters: Parse cluster response + assign cluster IDs to keywords
#
# Uses keyword STRING matching (via the saved ID map) instead of relying on
# numeric IDs surviving across bash calls. This is the fix for the cluster
# assignment bug from the test run.
# ---------------------------------------------------------------------------
def cmd_parse_clusters(args):
    with open(args.input) as f:
        keywords = json.load(f)
    with open(args.response) as f:
        resp = json.load(f)
    with open(args.idmap) as f:
        id_map = {int(k): v for k, v in json.load(f).items()}

    # Extract clusters JSON from Claude response
    text = resp["content"][0]["text"]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    clusters_data = json.loads(match.group())

    # Build keyword lookup by lowercase string
    kw_map = {}
    for k in keywords:
        kw_map[k["keyword"].lower().strip()] = k

    assigned = 0
    for cluster in clusters_data["clusters"]:
        cid = cluster["cluster_id"]
        cname = cluster["cluster_name"]
        pillar = cluster["pillar_keyword"]

        # Assign pillar by keyword string match
        pk = kw_map.get(pillar.lower().strip())
        if pk:
            pk["cluster"] = cid
            pk["cluster_name"] = cname
            pk["is_pillar"] = True
            assigned += 1

        # Assign supporting: resolve ID -> keyword string -> keyword record
        for sid in cluster.get("supporting_keyword_ids", []):
            kw_string = id_map.get(sid)
            if kw_string:
                kr = kw_map.get(kw_string.lower().strip())
                if kr:
                    kr["cluster"] = cid
                    kr["cluster_name"] = cname
                    kr["is_pillar"] = False
                    assigned += 1

    no_cluster = sum(1 for k in keywords if not k.get("cluster"))

    with open(args.output_keywords, "w") as f:
        json.dump(keywords, f, indent=2)
    with open(args.output_clusters, "w") as f:
        json.dump(clusters_data, f, indent=2)

    print(f"Assigned {assigned} keywords to clusters ({no_cluster} unassigned)")
    for c in clusters_data["clusters"]:
        print(f"  [{c['cluster_id']}] {c['cluster_name']}")


# ---------------------------------------------------------------------------
# select-topics: Pick Week 1 topics
# ---------------------------------------------------------------------------
def cmd_select_topics(args):
    with open(args.input) as f:
        keywords = json.load(f)

    count = args.count

    candidates = [
        k
        for k in keywords
        if k.get("cluster")
        and k.get("funnel") in ("TOFU", "MOFU", "BOFU")
        and k.get("status") in ("new_content", "refresh_candidate")
    ]

    # Step 1: Best keyword per cluster (breadth first)
    cluster_best = {}
    cluster_all = defaultdict(list)

    for k in candidates:
        cid = k["cluster"]
        cluster_all[cid].append(k)
        score = k.get("opportunity_score") or 0
        if cid not in cluster_best or score > (
            cluster_best[cid].get("opportunity_score") or 0
        ):
            cluster_best[cid] = k

    sorted_clusters = sorted(
        cluster_best.keys(),
        key=lambda c: -(cluster_best[c].get("opportunity_score") or 0),
    )

    selected = []
    selected_kws = set()

    # One per cluster
    for cid in sorted_clusters:
        if len(selected) >= count:
            break
        best = cluster_best[cid]
        selected.append(best)
        selected_kws.add(best["keyword"].lower().strip())

    # Fill remaining from global pool
    if len(selected) < count:
        remaining = sorted(
            candidates, key=lambda x: -(x.get("opportunity_score") or 0)
        )
        for k in remaining:
            if len(selected) >= count:
                break
            if k["keyword"].lower().strip() not in selected_kws:
                selected.append(k)
                selected_kws.add(k["keyword"].lower().strip())

    # Cap refresh candidates at 3
    rc = 0
    final = []
    for s in selected:
        if s.get("status") == "refresh_candidate":
            rc += 1
            if rc > 3:
                continue
        final.append(s)
    selected = final[:count]

    # Build output
    week1 = []
    for i, s in enumerate(selected):
        cid = s.get("cluster")
        # Top 3 supporting keywords from same cluster
        peers = cluster_all.get(cid, [])
        supporting = sorted(
            [p for p in peers if p["keyword"].lower().strip() != s["keyword"].lower().strip()],
            key=lambda x: -(x.get("opportunity_score") or 0),
        )
        related = [p["keyword"] for p in supporting[:3]]

        action = "Write new article"
        if s.get("status") == "refresh_candidate":
            pos = s.get("user_ranking_position", "?")
            action = f"Update existing article (position {pos})"

        kd = s.get("kd")
        vol = s.get("volume")
        kd_str = f"KD {kd}" if kd is not None else "KD unknown"
        why = f"{kd_str}, {vol}/mo searches — strong opportunity for the domain"

        week1.append(
            {
                "rank": i + 1,
                "keyword": s["keyword"],
                "cluster_id": cid,
                "cluster_name": s.get("cluster_name", ""),
                "funnel": s.get("funnel"),
                "volume": s.get("volume"),
                "kd": s.get("kd"),
                "cpc": s.get("cpc"),
                "opportunity_score": s.get("opportunity_score"),
                "status": s.get("status", "new_content"),
                "action": action,
                "related_keywords": related,
                "why": why,
            }
        )

    with open(args.output, "w") as f:
        json.dump(week1, f, indent=2)

    print(f"Selected {len(week1)} topics:")
    for t in week1:
        print(
            f"  #{t['rank']} [{t['funnel']}] score={t['opportunity_score']} "
            f"vol={t['volume']} kd={t['kd']} | {t['keyword']}"
        )


# ---------------------------------------------------------------------------
# generate-titles: Generate SEO article titles for selected topics via Claude
#
# Reads week1 topics JSON, calls Claude Haiku once with all keywords,
# writes title back onto each topic record. Updates the file in place.
# ---------------------------------------------------------------------------
def cmd_generate_titles(args):
    import subprocess

    with open(args.input) as f:
        topics = json.load(f)

    keywords_list = [{"rank": t["rank"], "keyword": t["keyword"], "funnel": t.get("funnel"), "cluster": t.get("cluster_name", "")} for t in topics]

    prompt = (
        "You are an SEO content strategist. Generate a compelling, click-worthy article title "
        "for each keyword below. The title should:\n"
        "- Be 50–65 characters\n"
        "- Include the keyword naturally (not stuffed)\n"
        "- Match the funnel stage: TOFU = educational/broad, MOFU = comparison/how-to, BOFU = specific/action\n"
        "- Be written for a human reader, not just search engines\n"
        "- Not use clickbait or vague superlatives like 'The Ultimate Guide'\n\n"
        f"Business context: {args.business_name} — {args.product_type}\n\n"
        "Keywords:\n"
        + json.dumps(keywords_list, indent=2)
        + "\n\nReturn only valid JSON. No explanation. No markdown.\n"
        '[{"rank": 1, "title": "string"}, ...]'
    )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}],
    }

    with open("/tmp/titles_payload.json", "w") as f:
        json.dump(payload, f)

    result = subprocess.run(
        [
            "bash", "-c",
            '[ -f .env ] && source .env; '
            'curl -s -X POST "https://api.anthropic.com/v1/messages" '
            '-H "x-api-key: $ANTHROPIC_API_KEY" '
            '-H "anthropic-version: 2023-06-01" '
            '-H "Content-Type: application/json" '
            '-d @/tmp/titles_payload.json',
        ],
        capture_output=True,
        text=True,
    )

    try:
        resp = json.loads(result.stdout)
        raw = resp["content"][0]["text"].strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        titles_data = json.loads(raw)
        title_map = {item["rank"]: item["title"] for item in titles_data}
    except Exception as e:
        print(f"Warning: Could not parse titles response — {e}. Using keywords as titles.")
        title_map = {}

    for t in topics:
        t["title"] = title_map.get(t["rank"], t["keyword"].title())
        print(f"  #{t['rank']} {t['title']}")

    with open(args.input, "w") as f:
        json.dump(topics, f, indent=2)

    print(f"Titles written to {args.input}")


# ---------------------------------------------------------------------------
# save: Write blog-config.json, CSV, CONTENT-PLAN.md, keyword/cluster JSONs
# ---------------------------------------------------------------------------
def cmd_save(args):
    with open(args.keywords) as f:
        keywords = json.load(f)
    with open(args.clusters) as f:
        clusters_data = json.load(f)
    with open(args.topics) as f:
        week1 = json.load(f)
    with open(args.config) as f:
        config = json.load(f)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = datetime.now().strftime("%Y-%m-%d")
    biz = config["business"]["business_name"]

    # --- 1. Update blog-config.json ---
    pipeline_items = []
    for t in week1:
        pipeline_items.append(
            {
                "keyword": t["keyword"],
                "title": t.get("title", t["keyword"].title()),
                "cluster_id": t["cluster_id"],
                "cluster_name": t["cluster_name"],
                "funnel": t["funnel"],
                "volume": t["volume"],
                "kd": t["kd"],
                "opportunity_score": t["opportunity_score"],
                "action": t["action"],
                "related_keywords": t["related_keywords"],
                "status": "queued",
                "queued_at": ts,
                "written_at": None,
                "article_url": None,
            }
        )

    config["topics"]["last_research_run"] = ts
    config["topics"]["total_keywords"] = len(keywords)
    config["topics"]["cluster_count"] = len(clusters_data.get("clusters", []))
    config["topics"]["pipeline"] = (
        config["topics"].get("pipeline", []) + pipeline_items
    )

    with open(args.config, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Updated {args.config} (+{len(pipeline_items)} topics)")

    # --- 2. CSV export ---
    os.makedirs(args.export_dir, exist_ok=True)
    csv_path = os.path.join(args.export_dir, f"keywords-{today}.csv")
    week1_kws = {t["keyword"].lower().strip() for t in week1}

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "keyword", "volume", "kd", "cpc", "funnel", "cluster_name",
                "opportunity_score", "status", "user_position", "week1_pick",
            ]
        )
        for k in sorted(keywords, key=lambda x: -(x.get("opportunity_score") or 0)):
            writer.writerow(
                [
                    k["keyword"],
                    k.get("volume", ""),
                    k.get("kd", ""),
                    k.get("cpc", ""),
                    k.get("funnel", ""),
                    k.get("cluster_name", ""),
                    k.get("opportunity_score", ""),
                    k.get("status", ""),
                    k.get("user_ranking_position", ""),
                    "YES" if k["keyword"].lower().strip() in week1_kws else "",
                ]
            )
    print(f"Wrote {csv_path}")

    # --- 3. blog-keywords.json and blog-clusters.json ---
    claude_dir = os.path.dirname(args.config)
    with open(os.path.join(claude_dir, "blog-keywords.json"), "w") as f:
        json.dump(keywords, f, indent=2)
    with open(os.path.join(claude_dir, "blog-clusters.json"), "w") as f:
        json.dump(clusters_data, f, indent=2)
    print("Saved blog-keywords.json and blog-clusters.json")

    # --- 4. CONTENT-PLAN.md ---
    week1_by_cluster = {t["cluster_id"]: t for t in week1}
    cluster_kws = defaultdict(list)
    for k in keywords:
        if k.get("cluster"):
            cluster_kws[k["cluster"]].append(k)

    # Pipeline table
    pipeline_rows = ""
    for t in week1:
        vol_str = "{:,}".format(t["volume"]) if t["volume"] else "—"
        title = t.get("title", t["keyword"].title())
        pipeline_rows += "| {} | {} | {} | {} | {} | {} | {} | {} | {} | queued |\n".format(
            t["rank"], title, t["keyword"], t["cluster_name"], t["funnel"],
            vol_str, t["kd"] if t["kd"] is not None else "—",
            t["opportunity_score"], t["action"],
        )

    support_note = ""
    for t in week1:
        if t["related_keywords"]:
            support_note += "> **#{}** — {}\n".format(
                t["rank"], " · ".join(t["related_keywords"])
            )

    # Cluster sections
    cluster_sections = ""
    for c in clusters_data.get("clusters", []):
        cid = c["cluster_id"]
        cname = c["cluster_name"]
        pillar = c["pillar_keyword"]
        kws = cluster_kws.get(cid, [])
        pillar_kw = next((k for k in kws if k.get("is_pillar")), None)
        supporting = [k for k in kws if not k.get("is_pillar")]
        w1 = week1_by_cluster.get(cid)

        p_vol = pillar_kw.get("volume", "—") if pillar_kw else "—"
        p_kd = pillar_kw.get("kd", "—") if pillar_kw else "—"
        p_fn = pillar_kw.get("funnel", "—") if pillar_kw else "—"

        kw_rows = ""
        if pillar_kw:
            kw_rows += "| {} *(pillar)* | {} | {} | {} | {} | {} |\n".format(
                pillar_kw["keyword"], p_vol, p_kd, p_fn,
                pillar_kw.get("opportunity_score", "—"),
                pillar_kw.get("status", "—"),
            )
        for k in sorted(supporting, key=lambda x: -(x.get("opportunity_score") or 0))[:10]:
            kw_rows += "| {} | {} | {} | {} | {} | {} |\n".format(
                k["keyword"], k.get("volume", "—"), k.get("kd", "—"),
                k.get("funnel", "—"), k.get("opportunity_score", "—"),
                k.get("status", "—"),
            )

        pick_str = '"{}"'.format(w1["keyword"]) if w1 else "— not selected this week"

        cluster_sections += (
            "\n### {cname}\n\n"
            "- **Pillar topic:** {pillar} ({fn}, {vol}/mo, KD {kd})\n"
            "- **Supporting topics:** {sup_count} keywords\n"
            "- **Week's pick:** {pick}\n\n"
            "<details>\n"
            "<summary>All keywords in this cluster ({total} total)</summary>\n\n"
            "| Keyword | Vol | KD | Funnel | Score | Status |\n"
            "|---------|-----|----|--------|-------|--------|\n"
            "{rows}"
            "</details>\n\n---\n"
        ).format(
            cname=cname, pillar=pillar, fn=p_fn, vol=p_vol, kd=p_kd,
            sup_count=len(supporting), pick=pick_str,
            total=len(kws), rows=kw_rows,
        )

    content = (
        "# Content Plan — {biz}\n\n"
        "> Generated by Blog Engine · Last updated: {today}\n"
        "> Keywords researched: {kw_count} · Clusters: {cl_count}\n"
        '> To write a post: `/blog-write` or `/blog-write "topic keyword"`\n\n'
        "---\n\n"
        "## Pipeline\n\n"
        "Topics queued for writing, ordered by opportunity score.\n"
        "Run `/blog-write` to start on the next one in the queue.\n\n"
        "| # | Title | Keyword | Cluster | Funnel | Vol/mo | KD | Score | Action | Status |\n"
        "|---|-------|---------|---------|--------|--------|----|-------|--------|--------|\n"
        "{pipeline}"
        "\n> Also target (supporting keywords per topic):\n"
        "{support}"
        "*(see full keyword list in `.claude/exports/keywords-{today}.csv`)*\n\n"
        "---\n\n"
        "## Written\n\n"
        "Articles completed via `/blog-write`. Updated automatically.\n\n"
        "| # | Topic | Cluster | Funnel | Written | Article URL |\n"
        "|---|-------|---------|--------|---------|-------------|\n"
        "| — | *(none yet)* | | | | |\n\n"
        "---\n\n"
        "## Keyword Clusters\n"
        "{clusters}\n"
        "## Files\n\n"
        "| File | What it contains |\n"
        "|------|------------------|\n"
        "| `CONTENT-PLAN.md` | This file — human-readable pipeline tracker |\n"
        "| `.claude/exports/keywords-{today}.csv` | Full keyword list — open in Excel or Google Sheets |\n"
        "| `.claude/blog-keywords.json` | Full keyword data (engine file) |\n"
        "| `.claude/blog-clusters.json` | Cluster map (engine file) |\n"
        "| `.claude/blog-config.json` | Pipeline state (do not edit manually) |\n"
    ).format(
        biz=biz, today=today, kw_count=len(keywords),
        cl_count=len(clusters_data.get("clusters", [])),
        pipeline=pipeline_rows, support=support_note,
        clusters=cluster_sections,
    )

    with open(args.content_plan, "w") as f:
        f.write(content)
    print(f"Wrote {args.content_plan}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Blog Engine Topics Pipeline")
    sub = parser.add_subparsers(dest="command")

    # parse-ranked
    p = sub.add_parser("parse-ranked")
    p.add_argument("input")
    p.add_argument("--domain", required=True)
    p.add_argument("--source", required=True, choices=["user_existing", "competitor"])
    p.add_argument("--output", required=True)

    # parse-seeds
    p = sub.add_parser("parse-seeds")
    p.add_argument("--dir", required=True)
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--output", required=True)

    # write-kd
    p = sub.add_parser("write-kd")
    p.add_argument("keywords")
    p.add_argument("kd_response")
    p.add_argument("--output", required=True)

    # merge
    p = sub.add_parser("merge")
    p.add_argument("files", nargs="+")
    p.add_argument("--output", required=True)

    # filter
    p = sub.add_parser("filter")
    p.add_argument("input")
    p.add_argument("--min-vol", type=int, default=100)
    p.add_argument("--max-kd", type=int, default=56)
    p.add_argument("--exclude-file")
    p.add_argument("--output", required=True)

    # score
    p = sub.add_parser("score")
    p.add_argument("input")
    p.add_argument("--output", required=True)

    # build-funnel-payload
    p = sub.add_parser("build-funnel-payload")
    p.add_argument("input")
    p.add_argument("--business-name", required=True)
    p.add_argument("--product-type", required=True)
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--output-dir", required=True)

    # parse-funnel
    p = sub.add_parser("parse-funnel")
    p.add_argument("input")
    p.add_argument("--response-dir", required=True)
    p.add_argument("--output", required=True)

    # build-cluster-payload
    p = sub.add_parser("build-cluster-payload")
    p.add_argument("input")
    p.add_argument("--business-name", required=True)
    p.add_argument("--product-type", required=True)
    p.add_argument("--integrations", required=True)
    p.add_argument("--output", required=True)

    # parse-clusters
    p = sub.add_parser("parse-clusters")
    p.add_argument("input")
    p.add_argument("response")
    p.add_argument("--idmap", required=True)
    p.add_argument("--output-keywords", required=True)
    p.add_argument("--output-clusters", required=True)

    # select-topics
    p = sub.add_parser("select-topics")
    p.add_argument("input")
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--output", required=True)

    # generate-titles
    p = sub.add_parser("generate-titles")
    p.add_argument("input", help="week1 topics JSON — updated in place")
    p.add_argument("--business-name", required=True)
    p.add_argument("--product-type", required=True)

    # save
    p = sub.add_parser("save")
    p.add_argument("--keywords", required=True)
    p.add_argument("--clusters", required=True)
    p.add_argument("--topics", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--export-dir", required=True)
    p.add_argument("--content-plan", required=True)

    args = parser.parse_args()

    commands = {
        "parse-ranked": cmd_parse_ranked,
        "parse-seeds": cmd_parse_seeds,
        "write-kd": cmd_write_kd,
        "merge": cmd_merge,
        "filter": cmd_filter,
        "score": cmd_score,
        "build-funnel-payload": cmd_build_funnel_payload,
        "parse-funnel": cmd_parse_funnel,
        "build-cluster-payload": cmd_build_cluster_payload,
        "parse-clusters": cmd_parse_clusters,
        "select-topics": cmd_select_topics,
        "generate-titles": cmd_generate_titles,
        "save": cmd_save,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
