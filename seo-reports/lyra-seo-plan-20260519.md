# MeetLyra SEO Audit and Keyword Plan

Generated: 2026-05-19

## Executive Summary

The SEO content machine is active and wired into the intended source systems: WordPress, Yoast Premium REST bridge, DataForSEO, Banana/Gemini images, IndexNow, GA4, PageSpeed, and the vendored `dylang001/claude-seo` reference layer. The current foundation is strong technically, but the publishing gate is correctly holding the latest dry-run as draft because readability and proof quality are not yet publish-safe.

The main SEO opportunity is to build a focused product-led topic cluster around autonomous marketing execution, rather than chasing broad marketing terms. Search demand exists around AI marketing tools, AI SEO agents, SEO automation, content automation, and marketing automation platforms. MeetLyra should own the practical "agentic marketing operator" angle: how lean teams use an AI marketing agent to research, create, optimize, publish, and improve content across channels.

## System Status

| Area | Status | Evidence |
|---|---:|---|
| Anthropic writer | Pass | `doctor --live` returned `ok: true`; writer JSON now parses after output token budget fix. |
| WordPress REST | Pass | WordPress REST reachable. |
| Yoast bridge | Pass | Yoast 27.3 and Premium active; custom `yoast_seo` REST field detected. |
| IndexNow | Pass | Key file returns 200 and matches local key. |
| DataForSEO | Pass | Keyword research and SERP research returned live results. |
| Banana/Gemini images | Pass | Gemini image model reachable and dry-run generated a featured image path. |
| PageSpeed / claude-seo | Pass | PageSpeed API returned scores and CWV data. |
| GA4 | Pass | `properties/493361388` works through OAuth. |
| GSC | Blocked | Cached OAuth token lacks `webmasters.readonly`; re-run `google-auth`. |

## Claude SEO Activation

Confirmed active through the discovery report:

- Source: `dylang001/claude-seo`
- Active source files:
  - `vendor/claude-seo/gsc_query.py`
  - `vendor/claude-seo/ga4_report.py`
  - `vendor/claude-seo/pagespeed_check.py`
  - `vendor/claude-seo/schema-templates.json`
- Active checks:
  - Technical checks: home, robots, sitemap
  - PageSpeed and Core Web Vitals
  - GA4 organic landing page report
  - GSC query path, currently blocked by OAuth scope
  - Yoast schema improvement recommendations

## Latest Technical SEO Snapshot

From `.content-machine/reports/discovery-20260519-070824.json`:

| Check | Result |
|---|---:|
| Home page reachable | Pass |
| Robots.txt reachable | Pass |
| Sitemap reachable | Pass |
| PageSpeed performance | 71 |
| Accessibility | 87 |
| Best practices | 100 |
| SEO | 100 |
| LCP | 5.0s |
| FCP | 3.6s |
| TBT | 90ms |
| CLS | 0.002 |

Priority technical fix: reduce LCP/FCP on mobile. The SEO score is strong, but performance is the current technical ceiling.

## Dry-Run Content Audit

Run ID: `3042a0db-e9ba-43b3-a830-270003e1aac7`

| Metric | Result |
|---|---:|
| Decision | Draft |
| Score | 84 |
| Word count | 3,158 |
| H1 count | 0 |
| H2 count | 18 |
| Focus keyphrase | `AI marketing agent` |
| Keyword mentions | 19 |
| Outbound links | 8 |
| Internal links | 1 |
| Rich blocks | 12 |
| Yoast copywriting score | 94 |
| Human quality score | 80 |
| Flesch reading ease | 23.5 |
| Transition ratio | 14% |

Required fixes before this article can publish:

1. Add at least two relevant MeetLyra internal links.
2. Rewrite for simpler reading. Target Flesch above 50.
3. Increase transition sentence ratio above 30%.
4. Remove unsupported case studies and invented performance claims.
5. Replace generic related article URLs with real existing or planned URLs.
6. Keep the generated image, rich blocks, table, FAQ, TOC, and schema structure.

## Keyword Research

Data source: DataForSEO keyword ideas from product-relevant seeds.

Raw report: `.content-machine/reports/keyword-research-lyra-20260519.json`

The raw export includes some broad or irrelevant terms, so the plan below filters for MeetLyra relevance and product-led SEO fit.

### Priority Keyword Opportunities

| Priority | Keyword | Volume | KD | Intent | Recommended Page |
|---:|---|---:|---:|---|---|
| 1 | AI marketing tools | 5,400 | 19 | Commercial | Comparison/list article |
| 2 | AI tool for SEO | 1,000 | 8 | Commercial | Product-led guide |
| 3 | AI tools for SEO | 1,000 | 23 | Commercial | Cluster article |
| 4 | SEO AI agent | 320 | 4 | Commercial | Pillar/BOFU article |
| 5 | Best AI tools for SEO | 480 | 8 | Commercial | Comparison page |
| 6 | Best AI marketing tools | 480 | 24 | Commercial | Comparison page |
| 7 | Marketing automation tools | 1,300 | 26 | Commercial | Cluster article |
| 8 | Marketing automation software | 2,400 | 34 | Commercial | Comparison/alternative page |
| 9 | Marketing automation platforms | 1,300 | 32 | Commercial | Comparison/decision page |
| 10 | Content machines | 4,400 | 3 | Informational | Thought-leadership/pillar support |
| 11 | Content marketing automation | Seed topic | TBD | Commercial | Product-led cluster article |
| 12 | AI content generator | 1,600 | 33 | Commercial | Comparison/positioning article |
| 13 | AI automation agency | 2,900 | 6 | Mixed | Contrarian article: agent vs agency |
| 14 | Digital marketing platforms | 6,600 | 18 | Commercial | Broader category comparison |
| 15 | Small business marketing | 1,600 | 26 | Commercial | Use later, once topical authority improves |

Avoid or deprioritize:

- `vector marketing`, `cardenas marketing network`, `plannet marketing`, `lyfe marketing`: brand/navigational noise.
- `social media marketing jobs`, `digital marketing jobs`: hiring intent, poor fit.
- `affiliate marketing`, influencer/celebrity social topics: too broad or off-position.
- `seo agency`, `performance marketing agency`: competitive and agency-intent, useful only for comparison/alternative content later.

## Topic Cluster Strategy

### Pillar 1: AI Marketing Agent

Goal: Own the category language around an autonomous marketing system.

Primary pillar:

- `AI marketing agent`
- Current working URL: `/ai-marketing-agent-seo-content/`

Cluster articles:

1. `SEO AI agent`: what it is, workflows, use cases, guardrails.
2. `AI marketing tools`: best tools and where autonomous agents differ.
3. `Best AI marketing tools`: comparison article with MeetLyra angle.
4. `AI automation agency`: AI agent vs agency vs internal marketing hire.
5. `AI content generator`: why generators are not enough for execution.
6. `Marketing automation tools`: where classic automation stops and agents begin.

Internal linking:

- Every cluster links back to the AI marketing agent pillar.
- Pillar links to all clusters with descriptive anchors.
- Avoid exact-match anchor spam like repeated `AI marketing agent`.

### Pillar 2: AI SEO and GEO Content Engine

Goal: Win SEO/GEO/AEO searches with a more technical content cluster.

Primary pillar:

- `AI SEO agent`
- Secondary angle: `AI tool for SEO`

Cluster articles:

1. `AI tool for SEO`: how to choose one.
2. `AI tools for SEO`: comparison and workflow map.
3. `Best AI tools for SEO`: listicle with strong product-led criteria.
4. `Generative engine optimization`: practical GEO guide for SaaS teams.
5. `Answer engine optimization`: how to structure content for AI answers.
6. `SEO content automation`: end-to-end workflow with WordPress and Yoast.

### Pillar 3: Autonomous Content Operations

Goal: Build authority around continuous publishing, refreshes, and optimization.

Cluster articles:

1. `Content machines`: what they are and how they work.
2. `Content marketing automation`: how to automate research, briefs, writing, and publishing.
3. `AI blog generator for WordPress`: WordPress-specific BOFU article.
4. `Automated internal linking for SEO`: practical workflow.
5. `Content refresh automation`: how to use GSC/GA4 to update old posts.
6. `SEO content calendar automation`: how to move from plan to schedule.

## 30-Day Publishing Plan

Week 1:

1. Repair and publish `AI marketing agent for SEO content`.
2. Publish `SEO AI agent: how autonomous SEO workflows work`.
3. Publish `AI tool for SEO: what to look for before choosing one`.

Week 2:

4. Publish `AI marketing tools: the practical stack for lean teams`.
5. Publish `Best AI tools for SEO: comparison by workflow, not features`.
6. Publish `Content machines: how always-on content systems work`.

Week 3:

7. Publish `Marketing automation tools vs AI marketing agents`.
8. Publish `AI content generator vs AI content engine`.
9. Publish `Generative engine optimization for SaaS teams`.

Week 4:

10. Publish `Answer engine optimization: structure content for AI answers`.
11. Publish `AI blog generator for WordPress: what matters for SEO`.
12. Refresh both existing AI marketing agent posts to remove duplication and strengthen internal links.

## Implementation Priorities

### This Week

1. Re-run Google OAuth so GSC works:
   ```bash
   rm .content-machine/google-oauth-token.json
   .venv/bin/python -m content_machine google-auth
   ```
2. Add stricter factuality gate:
   - Block invented case studies.
   - Block unsupported numbers.
   - Require source-backed proof blocks.
3. Add internal link minimum as a hard publish blocker, not only a warning.
4. Improve readability repair prompt:
   - Shorter sentence rewrites.
   - More transition words.
   - Lower jargon density.
5. Repair the current article until score is at least 85 with no factuality blockers.

### Next Two Weeks

1. Build the AI SEO agent cluster.
2. Add GSC refresh candidate adapter after OAuth is fixed.
3. Add competitor-specific scoring for Frase, Writesonic, Wix, Nightwatch, Marketer Milk, and Search Engine Land SERP patterns.
4. Add PageSpeed actions to the technical backlog, especially LCP/FCP.

### This Quarter

1. Build 3 pillars and 18 cluster articles.
2. Add quarterly drift monitoring for every published post.
3. Use GA4 + GSC data to choose refreshes over net-new posts when refresh impact is higher.
4. Add schema extensions through Yoast filters only where visible content supports them.

## Bottom Line

The system is active and close, but not ready for unsupervised publishing today. The right next move is to fix GSC OAuth, add a factuality blocker for invented case studies, and repair the current AI marketing agent article. Once those pass, the first topic cluster should focus on AI marketing agents and AI SEO agents because those terms are commercially relevant, lower difficulty, and aligned with MeetLyra's actual product wedge.
