from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from .config import load_settings
from .discovery import DiscoveryReporter
from .google_auth import GA4_SCOPE, GSC_SCOPE, run_installed_app_oauth
from .doctor import live_checks
from .indexnow import IndexNowClient
from .pipeline import ContentMachine
from .strategy import StrictStrategyReporter
from .worker import start_worker

# New capabilities
from .competitor_pages import CompetitorPagesGenerator
from .hreflang import HreflangAuditor
from .programmatic_seo import ProgrammaticSEOPlanner
from .indexing import GoogleIndexingClient


def main() -> None:
    parser = argparse.ArgumentParser(prog="content-machine")
    sub = parser.add_subparsers(dest="command", required=True)
    
    # Existing commands
    run_now = sub.add_parser("run-now", help="Force the pipeline to run immediately once without waiting for the schedule")
    run_now.add_argument("--dry-run", action="store_true", help="Run logic without publishing")
    run_now.add_argument("--publish", action="store_true", help="Allow WordPress publish/draft writes")
    
    worker = sub.add_parser("worker", help="Start the cloud worker scheduler")
    
    doctor = sub.add_parser("doctor", help="Check configuration")
    doctor.add_argument("--live", action="store_true", help="Also test provider authentication/connectivity")
    
    discover = sub.add_parser("discover", help="Run discovery/research report without writing WordPress content")
    discover.add_argument("--limit", type=int, default=5, help="Number of opportunities to research")
    discover.add_argument("--days", type=int, default=28, help="Lookback window for GSC/GA4 signals")
    discover.add_argument("--strict", action="store_true", help="Hard-fail if live data or parser output is unavailable")
    
    strategy = sub.add_parser("strategy", help="Run strict SEO strategy report without writing WordPress content")
    strategy.add_argument("--limit", type=int, default=25, help="Number of keyword opportunities to research")
    strategy.add_argument("--days", type=int, default=90, help="Lookback window for GSC/GA4 signals")
    strategy.add_argument("--strict", action="store_true", help="Required; hard-fail if live data or parser output is unavailable")
    # --offline removed: the system must never use simulated data
    
    sub.add_parser("google-auth", help="Authorize GSC/GA4 with a real Google user account via OAuth")
    
    indexnow = sub.add_parser("indexnow", help="Submit URLs to IndexNow or verify the key file")
    indexnow.add_argument("--url", action="append", default=[], help="URL to submit. Can be repeated.")
    indexnow.add_argument("--verify", action="store_true", help="Verify INDEXNOW_KEY_LOCATION serves INDEXNOW_KEY")
    indexnow.add_argument("--configure-wordpress", action="store_true", help="Send INDEXNOW_KEY to the SEO Machine WordPress bridge")

    # New commands matching claude-seo capabilities
    competitor = sub.add_parser("competitor-pages", help="Generate competitor comparison 'X vs Y' and alternatives pages")
    competitor.add_argument("competitor", help="Name of the competitor to compare against")
    competitor.add_argument("--generate", action="store_true", default=True, help="Write generated comparison page to output directory")
    competitor.add_argument("--output-dir", type=str, default=".", help="Directory to save the markdown file")

    hreflang = sub.add_parser("hreflang", help="Validate or generate hreflang tags for multi-language sites")
    hreflang.add_argument("url", nargs="?", help="URL to audit/validate hreflang tags")
    hreflang.add_argument("--generate", type=str, help="JSON string representing locale-to-URL map for tag generation")
    hreflang.add_argument("--default-url", type=str, help="Fallback default URL for x-default")

    p_seo = sub.add_parser("programmatic-seo", help="Analyze programmatic SEO templates and data records for thin content risk")
    p_seo.add_argument("--page-count", type=int, required=True, help="Total number of programmatic pages planned")
    p_seo.add_argument("--expected-word-count", type=int, default=450, help="Expected average word count per page")
    p_seo.add_argument("--uniqueness", type=type(45.0), default=45.0, help="Expected average unique content percentage")
    p_seo.add_argument("--location-pages", type=int, default=0, help="Number of planned location pages (triggers doorways warnings)")

    indexing = sub.add_parser("google-indexing", help="Notify Google of updated/removed URLs via Google Indexing API")
    indexing.add_argument("url", help="URL to notify Google about")
    indexing.add_argument("--action", choices=["URL_UPDATED", "URL_DELETED"], default="URL_UPDATED", help="Action type")
    indexing.add_argument("--dry-run", action="store_true", help="Perform a dry-run without contacting the Indexing API")

    seo_geo = sub.add_parser("seo-geo", help="Run Generative Engine Optimization (GEO) audit and visibility plan")
    seo_geo.add_argument("url", nargs="?", help="Target URL to audit for GEO")
    seo_geo.add_argument("--strict", action="store_true", help="Fail if ANTHROPIC_API_KEY is missing or if offline")

    # Firecrawl command
    firecrawl_parser = sub.add_parser("firecrawl", help="Interact with the Firecrawl crawler/scraper")
    firecrawl_sub = firecrawl_parser.add_subparsers(dest="firecrawl_action", required=True)
    
    fc_crawl = firecrawl_sub.add_parser("crawl", help="Crawl website starting from target URL")
    fc_crawl.add_argument("url", help="Target URL to start crawling")
    fc_crawl.add_argument("--limit", type=int, default=10, help="Maximum number of pages to crawl")
    
    fc_scrape = firecrawl_sub.add_parser("scrape", help="Scrape a single page")
    fc_scrape.add_argument("url", help="URL of the page to scrape")
    
    fc_map = firecrawl_sub.add_parser("map", help="Discover URLs map for a website")
    fc_map.add_argument("url", help="Website domain/URL to map")
    
    # Keyword research subcommand
    kw_research = sub.add_parser("keyword-research", help="Perform keyword expansion, clustering, scoring, and content brief generation")
    kw_research.add_argument("--seeds", nargs="+", help="Seed keywords to expand")
    kw_research.add_argument("--location", default="United States", help="Target location")
    kw_research.add_argument("--language", default="English", help="Target language")
    kw_research.add_argument("--brief-limit", type=int, default=3, help="Generate content briefs for the top N keywords")
    kw_research.add_argument("--output", default="data/seo/keyword_research/google_ads_raw.csv", help="Output path for raw metrics CSV")

    # Yoast topic cluster planner subcommands
    gen_plan = sub.add_parser("generate-plan", help="Generate a structured Yoast topic cluster map and queue it")
    gen_plan.add_argument("--seed", default="AI marketing agent", help="Primary seed keyword for the topic cluster")
    gen_plan.add_argument("--competitor-domain", help="Competitor domain to fetch keywords from")

    view_plan = sub.add_parser("view-plan", help="View the queued topic cluster content plan")

    weekly_review = sub.add_parser("weekly-review", help="Run the weekly performance and content drift review")

    args = parser.parse_args()

    if args.command == "worker":
        start_worker()
        return

    settings = load_settings()
    
    if args.command == "run-now":
        print("Starting immediate pipeline run...")
        result = asyncio.run(ContentMachine(settings).run_once(dry_run=args.dry_run))
        print(f"\nFinished! Opportunity: {result.opportunity.keyword}")
        print(f"Status: {result.wordpress_status}")
        print(f"URL: {result.wordpress_url}")
        print(f"Audit Decision: {result.audit.decision.value}")
        return

    if args.command == "doctor":
        missing = settings.missing_required()
        payload = {"ok": not missing, "missing": missing, "state_db": str(settings.state_db)}
        if args.live:
            payload["live"] = asyncio.run(live_checks(settings))
            payload["ok"] = payload["ok"] and payload["live"]["ok"]
        print(json.dumps(payload, indent=2))
        return

    if args.command == "discover":
        report = asyncio.run(DiscoveryReporter(settings).run(limit=args.limit, days=args.days, strict=args.strict))
        print(json.dumps(report, indent=2, default=str))
        return

    if args.command == "strategy":
        if not args.strict:
            raise SystemExit("strategy requires --strict so no fallback data can be used")
        report = asyncio.run(StrictStrategyReporter(settings).run(limit=args.limit, days=args.days))
        print(json.dumps(report, indent=2, default=str))
        return

    if args.command == "google-auth":
        from .indexing import INDEXING_SCOPE
        token_path = run_installed_app_oauth(
            settings,
            [GSC_SCOPE, GA4_SCOPE, INDEXING_SCOPE, "https://www.googleapis.com/auth/blogger"]
        )
        print(json.dumps({"ok": True, "token_path": str(token_path)}, indent=2))
        return

    if args.command == "indexnow":
        client = IndexNowClient(settings)
        if args.configure_wordpress:
            from .wordpress import WordPressClient

            try:
                response = asyncio.run(WordPressClient(settings).configure_indexnow_key(settings.indexnow_key))
            except Exception as exc:
                response = {
                    "ok": False,
                    "message": "Could not configure WordPress. Install the updated Yoast bridge first, then retry.",
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            print(json.dumps(response, indent=2, default=str))
            return
        if args.verify:
            print(json.dumps(asyncio.run(client.verify_key_location()), indent=2, default=str))
            return
        results = asyncio.run(client.submit(args.url))
        print(json.dumps([result.__dict__ for result in results], indent=2, default=str))
        return

    if args.command == "competitor-pages":
        gen = CompetitorPagesGenerator(settings)
        out_dir = Path(args.output_dir) if args.output_dir else None
        res = gen.generate_vs_page(args.competitor, output_dir=out_dir)
        print(json.dumps(res, indent=2, default=str))
        return

    if args.command == "hreflang":
        auditor = HreflangAuditor()
        if args.generate:
            try:
                mapping = json.loads(args.generate)
            except Exception as exc:
                print(json.dumps({"ok": False, "error": f"Failed to parse --generate JSON: {exc}"}, indent=2))
                return
            res = auditor.generate_tags(mapping, default_url=args.default_url)
            print(json.dumps(res, indent=2, default=str))
        elif args.url:
            res = asyncio.run(auditor.audit_url(args.url))
            print(json.dumps(res, indent=2, default=str))
        else:
            print(json.dumps({"ok": False, "error": "Either url positional argument or --generate is required."}, indent=2))
        return

    if args.command == "programmatic-seo":
        planner = ProgrammaticSEOPlanner()
        # Create some stub templates/records based on inputs for testing
        templates = [{
            "name": "Service Template",
            "expected_word_count": args.expected_word_count,
            "uniqueness_percentage": args.uniqueness
        }]
        if args.location_pages > 0:
            templates.append({
                "name": "Location Template",
                "pattern": "/[city]/service",
                "expected_word_count": args.expected_word_count,
                "uniqueness_percentage": args.uniqueness
            })
        records = [{"slug": f"page-{i}"} for i in range(args.page_count)]
        res = planner.analyze_planning(args.page_count, templates, records)
        print(json.dumps(res, indent=2, default=str))
        return

    if args.command == "google-indexing":
        client = GoogleIndexingClient(settings)
        res = asyncio.run(client.notify(args.url, action=args.action, dry_run=args.dry_run))
        print(json.dumps(res, indent=2, default=str))
        return

    if args.command == "seo-geo":
        from .seo_geo import SEOGEOAuditor
        auditor = SEOGEOAuditor(settings)
        res = asyncio.run(auditor.run_analysis(args.url, strict=args.strict))
        print(json.dumps({
            "ok": True,
            "url": res["url"],
            "readiness_score": res["readiness_score"],
            "platform_scores": res["platform_scores"]
        }, indent=2))
        return

    if args.command == "firecrawl":
        from .firecrawl import FirecrawlClient
        fc = FirecrawlClient(settings)
        if args.firecrawl_action == "scrape":
            res = asyncio.run(fc.scrape(args.url))
            print(json.dumps(res, indent=2, default=str))
        elif args.firecrawl_action == "map":
            res = asyncio.run(fc.map(args.url))
            print(json.dumps(res, indent=2, default=str))
        elif args.firecrawl_action == "crawl":
            res = asyncio.run(fc.crawl(args.url, limit=args.limit))
            print(json.dumps(res, indent=2, default=str))
        return

    if args.command == "keyword-research":
        from .keyword_research_google_ads_api import (
            fetch_keywords_raw,
            process_and_score_keywords,
            generate_content_brief,
            save_raw_keywords_to_csv
        )
        seeds = args.seeds or [
            "AI marketing agent",
            "autonomous marketing agent",
            "AI agent for marketing",
            "AI marketing automation",
            "AI campaign generator",
            "AI content automation",
            "AI marketing strategy generator",
            "AI marketing assistant",
            "AI tools for startups",
            "marketing automation for startups",
            "Jasper alternative",
            "Copy.ai alternative",
            "ChatGPT for marketing",
            "AI content planner",
            "AI go to market strategy"
        ]
        
        print(f"Starting keyword research for seeds: {seeds}")
        
        # 1. Fetch Raw
        raw_kws = asyncio.run(fetch_keywords_raw(
            settings=settings,
            seeds=seeds,
            location=args.location,
            language=args.language
        ))
        
        print(f"Retrieved {len(raw_kws)} raw keywords. Exporting raw metrics to {args.output}...")
        save_raw_keywords_to_csv(Path(args.output), raw_kws)
        
        # 2. Process, Cluster, Score
        print("Clustering, classifying, and scoring keywords via Gemini...")
        scored_kws = asyncio.run(process_and_score_keywords(settings, raw_kws))
        
        # Save scored keywords to a JSON report in reports/ directory
        reports_dir = settings.data_dir / "keyword_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "keyword_analysis_report.json"
        
        # 3. Generate Briefs for top keywords
        brief_limit = min(args.brief_limit, len(scored_kws))
        print(f"\nGenerating Content Briefs for Top {brief_limit} Keywords...")
        briefs = []
        for i, item in enumerate(scored_kws[:brief_limit]):
            print(f"Creating brief for: '{item['keyword']}' (Priority Score: {item['priority_score']})")
            brief = asyncio.run(generate_content_brief(settings, item))
            briefs.append(brief)
            
        full_report = {
            "parameters": {
                "seeds": seeds,
                "location": args.location,
                "language": args.language
            },
            "keywords": scored_kws,
            "briefs": briefs
        }
        
        report_path.write_text(json.dumps(full_report, indent=2, default=str), encoding="utf-8")
        print(f"\nSaved analysis and briefs to: {report_path}")
        
        print("\nTop 10 Scored Keywords:")
        for idx, kw in enumerate(scored_kws[:10]):
            print(
                f"{idx+1}. {kw['keyword']} (Priority Score: {kw['priority_score']}) | Cluster: {kw['cluster']} | "
                f"Page Type: {kw['recommended_page_type']} | Searches: {kw['avg_monthly_searches']}"
            )
        return

    if args.command == "generate-plan":
        from .planner import ClusterPlanner
        print(f"Starting Yoast Topic Cluster generation for seed keyword: '{args.seed}'" + (f" with competitor domain '{args.competitor_domain}'" if args.competitor_domain else ""))
        planner = ClusterPlanner(settings)
        plan = asyncio.run(planner.generate_plan([args.seed], competitor_domain=args.competitor_domain))
        print(f"\nSuccessfully generated and queued {len(plan)} plan items!")
        print("To view the full plan, run: python -m content_machine.cli view-plan")
        return

    if args.command == "view-plan":
        from .state import StateStore
        store = StateStore(settings.state_db, settings=settings)
        plan = store.get_content_plan()
        if not plan:
            print("No planned posts found in the topic cluster plan queue.")
            print("To generate a plan, run: python -m content_machine.cli generate-plan --seed <keyword>")
            return
            
        print("\n--- Current Topic Cluster Content Plan Queue ---")
        print(f"{'Keyword':<35} | {'Role':<6} | {'Status':<10} | {'Score':<5} | {'Parent Pillar':<25} | {'WP URL'}")
        print("-" * 120)
        for item in plan:
            parent = item.get("parent_pillar") or "None"
            wp_url = item.get("wordpress_url") or "None"
            print(f"{item['keyword']:<35} | {item['role']:<6} | {item['status']:<10} | {item['score']:<5.2f} | {parent:<25} | {wp_url}")
        return

    if args.command == "weekly-review":
        from .performance_analyst import PerformanceAnalyst
        print("Starting weekly performance and content drift review...")
        result = asyncio.run(PerformanceAnalyst(settings).run_weekly_review())
        print(json.dumps(result, indent=2, default=str))
        return

    dry_run = True
    if args.publish:
        dry_run = False
    elif args.dry_run:
        dry_run = True

    result = asyncio.run(ContentMachine(settings).run_once(dry_run=dry_run))
    print(json.dumps(asdict(result), indent=2, default=str))

if __name__ == "__main__":
    main()
