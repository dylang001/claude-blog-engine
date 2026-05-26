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
from .daily_report import compile_daily_report, send_daily_email_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="content-machine")
    sub = parser.add_subparsers(dest="command", required=True)
    
    # Existing commands
    run = sub.add_parser("run", help="Run one content machine slot")
    run.add_argument("--dry-run", action="store_true", help="Generate and audit without publishing")
    run.add_argument("--publish", action="store_true", help="Allow WordPress publish/draft writes")
    
    sub.add_parser("worker", help="Start the cloud worker scheduler")
    
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

    daily_report = sub.add_parser("daily-report", help="Generate and send daily execution & GA4 performance summary report")
    daily_report.add_argument("--send-email", action="store_true", help="Force email sending even if SMTP config is incomplete (will raise error if it fails)")

    outreach = sub.add_parser("outreach", help="Manage cold outreach link building campaigns")
    outreach_sub = outreach.add_subparsers(dest="outreach_action", required=True)
    outreach_create = outreach_sub.add_parser("create", help="Create outreach campaign for a blog post")
    outreach_create.add_argument("--slug", required=True, help="WordPress post slug")
    outreach_sub.add_parser("process", help="Trigger Next.js to process sequence emails and monitor replies")

    args = parser.parse_args()

    if args.command == "worker":
        start_worker()
        return

    settings = load_settings()
    
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
        token_path = run_installed_app_oauth(settings, [GSC_SCOPE, GA4_SCOPE])
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

    if args.command == "daily-report":
        report = asyncio.run(compile_daily_report(settings))
        print(json.dumps(report, indent=2, default=str))
        email_sent = send_daily_email_report(settings, report)
        if args.send_email and not email_sent:
            raise SystemExit("Failed to send daily report email. Check SMTP settings and logs.")
        return

    if args.command == "outreach":
        from .outreach_agent import OutreachAgent
        agent = OutreachAgent(settings)
        if args.outreach_action == "create":
            res = asyncio.run(agent.generate_campaign_for_post(args.slug))
            print(json.dumps(res, indent=2, default=str))
        elif args.outreach_action == "process":
            res = asyncio.run(agent.trigger_cron_job())
            print(json.dumps(res, indent=2, default=str))
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
