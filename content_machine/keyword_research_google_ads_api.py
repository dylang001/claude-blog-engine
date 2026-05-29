from __future__ import annotations
import os
import csv
import json
import logging
from pathlib import Path
from typing import Any
import httpx

from .config import Settings

logger = logging.getLogger(__name__)

# Try importing google ads client
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    HAS_GOOGLE_ADS = True
except ImportError:
    HAS_GOOGLE_ADS = False
    class GoogleAdsException(Exception): pass

# Import DataForSEO client as fallback
try:
    from .data_sources import DataForSEOClient
    HAS_DATAFORSEO = True
except ImportError:
    HAS_DATAFORSEO = False


async def fetch_keywords_raw(
    settings: Settings,
    seeds: list[str],
    location: str = "United States",
    language: str = "English"
) -> list[dict[str, Any]]:
    """
    Fetches raw keyword metrics using Google Ads API with fallback to DataForSEO or mock data.
    """
    results = []

    # 1. Try Google Ads API
    if HAS_GOOGLE_ADS:
        results = _fetch_from_google_ads(settings, seeds, location, language)
        if results:
            logger.info(f"Successfully retrieved {len(results)} keyword ideas from Google Ads API.")
            return results

    # 2. Fall back to DataForSEO
    if HAS_DATAFORSEO and settings.dataforseo_login:
        results = await _fetch_from_dataforseo(settings, seeds)
        if results:
            logger.info(f"Successfully retrieved {len(results)} keyword ideas from DataForSEO Labs.")
            return results

    # 3. Last fallback: Mock Data for development/testing
    results = _fetch_mock_fallback(seeds)
    return results


def _fetch_from_google_ads(settings: Settings, seeds: list[str], location: str, language: str) -> list[dict[str, Any]]:
    developer_token = settings.google_ads_developer_token
    customer_id = settings.google_ads_customer_id.replace("-", "").strip()
    client_id = settings.google_ads_client_id
    client_secret = settings.google_ads_client_secret
    refresh_token = settings.google_ads_refresh_token

    if not all([developer_token, customer_id, client_id, client_secret, refresh_token]):
        logger.info("Google Ads API credentials not fully configured. Skipping Google Ads client.")
        return []

    config = {
        "developer_token": developer_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }

    try:
        # Location mapping (simple matching)
        loc_map = {
            "united states": "2840",
            "united kingdom": "2826",
            "canada": "2124",
            "australia": "2036",
        }
        loc_id = loc_map.get(location.lower().strip(), "2840")

        # Language mapping
        lang_map = {
            "english": "1000",
            "spanish": "1003",
            "french": "1002",
        }
        lang_id = lang_map.get(language.lower().strip(), "1000")

        client = GoogleAdsClient.load_from_dict(config)
        keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
        google_ads_service = client.get_service("GoogleAdsService")

        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id
        request.language = google_ads_service.language_constant_path(lang_id)
        request.geo_target_constants.append(
            google_ads_service.geo_target_constant_path(loc_id)
        )
        request.keyword_seed.keywords.extend(seeds)

        logger.info(f"Querying Google Ads API for seeds: {seeds}")
        response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

        results = []
        for idea in response:
            metrics = idea.keyword_idea_metrics
            low_bid = metrics.low_top_of_page_bid_micros / 1000000.0 if metrics.low_top_of_page_bid_micros else 0.0
            high_bid = metrics.high_top_of_page_bid_micros / 1000000.0 if metrics.high_top_of_page_bid_micros else 0.0

            monthly_searches = []
            if metrics and hasattr(metrics, "monthly_search_volumes") and metrics.monthly_search_volumes:
                for vol in metrics.monthly_search_volumes:
                    m_val = vol.month
                    m_name = getattr(m_val, "name", str(m_val))
                    monthly_searches.append({
                        "year": vol.year,
                        "month": m_name,
                        "search_volume": vol.monthly_searches
                    })

            results.append({
                "keyword": idea.text,
                "avg_monthly_searches": metrics.avg_monthly_searches or 0,
                "competition": metrics.competition.name if metrics.competition else "UNSPECIFIED",
                "low_top_of_page_bid": low_bid,
                "high_top_of_page_bid": high_bid,
                "kd": 0,
                "monthly_searches": monthly_searches,
            })
        return results

    except GoogleAdsException as ex:
        logger.warning(f"Google Ads API Exception: {ex}")
        return []
    except Exception as ex:
        logger.warning(f"Error querying Google Ads API: {ex}")
        return []


async def _fetch_from_dataforseo(settings: Settings, seeds: list[str]) -> list[dict[str, Any]]:
    logger.info("Querying DataForSEO Labs for keyword ideas...")
    client = DataForSEOClient(settings)
    try:
        raw_items = await client.keyword_ideas(seeds, limit=50)
        results = []
        for item in raw_items:
            info = item.get("keyword_info") or {}
            props = item.get("keyword_properties") or {}
            keyword = item.get("keyword") or ""

            avg_searches = info.get("search_volume") or 0
            competition = info.get("competition_level") or "UNSPECIFIED"

            cpc = info.get("cpc") or 0.0
            low_bid = props.get("low_top_of_page_bid") or cpc * 0.5
            high_bid = props.get("high_top_of_page_bid") or cpc * 1.5
            kd = props.get("keyword_difficulty") or 0

            m_searches = info.get("monthly_searches") or []
            monthly_searches_list = []
            for ms in m_searches:
                monthly_searches_list.append({
                    "year": ms.get("year"),
                    "month": ms.get("month"),
                    "search_volume": ms.get("search_volume")
                })

            results.append({
                "keyword": keyword,
                "avg_monthly_searches": int(avg_searches),
                "competition": str(competition).upper(),
                "low_top_of_page_bid": float(low_bid),
                "high_top_of_page_bid": float(high_bid),
                "kd": int(kd),
                "monthly_searches": monthly_searches_list,
            })
        return results
    except Exception as e:
        logger.warning(f"DataForSEO query failed: {e}")
        return []


def _fetch_mock_fallback(seeds: list[str]) -> list[dict[str, Any]]:
    logger.info("Using mock/fallback data for keyword ideas...")
    results = []
    # Add seeds directly
    for s_idx, seed in enumerate(seeds):
        kw = seed.lower().strip()
        variants = [
            kw,
            f"best {kw}",
            f"how to use {kw}",
            "autonomous agent",
            "ai content automation",
            "seo keyword research",
            "topic clustering tips"
        ]
        for v_idx, variant in enumerate(variants):
            monthly_searches_list = []
            is_declining = ((s_idx + v_idx) % 3 == 0) # some decline
            base_sv = 1500 - (v_idx * 150)
            if base_sv < 50:
                base_sv = 50
                
            for month_offset in range(12):
                year = 2025 if month_offset < 7 else 2026
                month = ((month_offset + 5) % 12) + 1
                if is_declining:
                    vol = int(base_sv * (1.3 - (month_offset * 0.08)))
                else:
                    vol = int(base_sv * (0.95 + (month_offset * 0.01)))
                if vol < 10:
                    vol = 10
                monthly_searches_list.append({
                    "year": year,
                    "month": month,
                    "search_volume": vol
                })
                
            avg_sv = int(sum([x["search_volume"] for x in monthly_searches_list]) / 12)
            
            results.append({
                "keyword": variant,
                "avg_monthly_searches": avg_sv,
                "competition": "HIGH" if v_idx % 3 == 0 else ("MEDIUM" if v_idx % 3 == 1 else "LOW"),
                "low_top_of_page_bid": round(0.5 + v_idx * 0.4, 2),
                "high_top_of_page_bid": round(2.0 + v_idx * 1.2, 2),
                "kd": 15 + (v_idx * 12) % 75,
                "monthly_searches": monthly_searches_list
            })
    return results


def check_is_declining(monthly_searches: list[dict[str, Any]]) -> bool:
    """
    Checks if a keyword's search volume is declining.
    Compares the average of the last 3 months to the average of the preceding 9 months.
    Requires at least 6 months of historical data to evaluate.
    """
    if not monthly_searches or len(monthly_searches) < 6:
        return False
    
    month_map = {
        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
        "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
    }
    
    sorted_vols = []
    for item in monthly_searches:
        m = item.get("month")
        y = item.get("year")
        sv = item.get("search_volume")
        if sv is None:
            continue
        
        m_int = 1
        if isinstance(m, int):
            m_int = m
        elif isinstance(m, str):
            m_upper = m.upper().strip()
            if m_upper.isdigit():
                m_int = int(m_upper)
            else:
                m_int = month_map.get(m_upper, 1)
        elif hasattr(m, "name"):
            m_int = month_map.get(m.name, 1)
        
        sorted_vols.append((y or 0, m_int, sv))
    
    sorted_vols.sort(key=lambda x: (x[0], x[1]))
    
    recent_data = sorted_vols[-12:]
    n = len(recent_data)
    if n < 6:
        return False
    
    recent_3 = [x[2] for x in recent_data[-3:]]
    older_9 = [x[2] for x in recent_data[:-3]]
    
    avg_recent = sum(recent_3) / len(recent_3)
    avg_older = sum(older_9) / len(older_9)
    
    return avg_recent < avg_older


async def fetch_competitor_keywords_raw(
    settings: Settings,
    domain: str,
    limit: int = 50
) -> list[dict[str, Any]]:
    """
    Fetches keywords that the competitor domain ranks for, using DataForSEO Google Competitor Keywords API,
    with a fallback to a deterministic mock list if credentials/APIs are unavailable.
    """
    if not domain:
        return []
        
    if HAS_DATAFORSEO and settings.dataforseo_login:
        logger.info(f"Querying DataForSEO Labs for competitor keywords of domain '{domain}'...")
        client = DataForSEOClient(settings)
        try:
            raw_items = await client.competitor_keywords(domain, limit=limit)
            results = []
            for item in raw_items:
                info = item.get("keyword_info") or {}
                props = item.get("keyword_properties") or {}
                keyword = item.get("keyword") or ""

                avg_searches = info.get("search_volume") or 0
                competition = info.get("competition_level") or "UNSPECIFIED"

                cpc = info.get("cpc") or 0.0
                low_bid = props.get("low_top_of_page_bid") or cpc * 0.5
                high_bid = props.get("high_top_of_page_bid") or cpc * 1.5
                
                m_searches = info.get("monthly_searches") or []
                monthly_searches_list = []
                for ms in m_searches:
                    monthly_searches_list.append({
                        "year": ms.get("year"),
                        "month": ms.get("month"),
                        "search_volume": ms.get("search_volume")
                    })

                results.append({
                    "keyword": keyword,
                    "avg_monthly_searches": int(avg_searches),
                    "competition": str(competition).upper(),
                    "low_top_of_page_bid": float(low_bid),
                    "high_top_of_page_bid": float(high_bid),
                    "kd": int(props.get("keyword_difficulty") or 0),
                    "monthly_searches": monthly_searches_list
                })
            if results:
                logger.info(f"Successfully retrieved {len(results)} competitor keywords from DataForSEO Labs.")
                return results
        except Exception as e:
            logger.warning(f"DataForSEO competitor query failed: {e}")
            
    logger.info(f"Using mock/fallback data for competitor keywords of domain '{domain}'...")
    results = []
    domain_clean = domain.lower().replace("www.", "").split(".")[0]
    
    mock_keywords = [
        f"{domain_clean} review",
        f"{domain_clean} pricing",
        f"{domain_clean} alternatives",
        f"best {domain_clean} workflow",
        "marketing automation software",
        "ai campaign management",
        "autonomous marketing strategy",
        "ai copy assistant",
        "seo writing assistant",
        "growth marketing ai tools"
    ]
    
    for idx, kw in enumerate(mock_keywords):
        monthly_searches_list = []
        is_declining = (idx % 2 == 0)
        base_sv = 1200 - (idx * 100)
        if base_sv < 100:
            base_sv = 100
            
        for month_offset in range(12):
            year = 2025 if month_offset < 7 else 2026
            month = ((month_offset + 5) % 12) + 1
            if is_declining:
                vol = int(base_sv * (1.2 - (month_offset * 0.07)))
            else:
                vol = int(base_sv * (0.9 + (month_offset * 0.02)))
            if vol < 10:
                vol = 10
            monthly_searches_list.append({
                "year": year,
                "month": month,
                "search_volume": vol
            })
            
        avg_sv = int(sum([x["search_volume"] for x in monthly_searches_list]) / 12)
        
        results.append({
            "keyword": kw,
            "avg_monthly_searches": avg_sv,
            "competition": "HIGH" if idx % 3 == 0 else ("MEDIUM" if idx % 3 == 1 else "LOW"),
            "low_top_of_page_bid": round(1.0 + idx * 0.5, 2),
            "high_top_of_page_bid": round(3.0 + idx * 1.5, 2),
            "kd": 20 + (idx * 7) % 80,
            "monthly_searches": monthly_searches_list
        })
        
    return results


async def process_and_score_keywords(settings: Settings, raw_keywords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Groups keywords, scores them, and uses Gemini to classify intent, cluster, and recommended page types.
    """
    if not raw_keywords:
        return []

    # De-duplicate raw keyword items
    unique_kws = {}
    for item in raw_keywords:
        k = item["keyword"].strip().lower()
        if k not in unique_kws:
            unique_kws[k] = item

    items_list = list(unique_kws.values())

    # Process in batches of up to 40 keywords to prevent prompt size issues or LLM confusion
    batch_size = 40
    classified_results = []

    for i in range(0, len(items_list), batch_size):
        batch = items_list[i:i + batch_size]
        classified_batch = await _classify_batch_with_gemini(settings, batch)
        classified_results.extend(classified_batch)

    # Compute final score
    processed = []
    for item in classified_results:
        search_vol = item.get("avg_monthly_searches", 0)
        comp = item.get("competition", "UNSPECIFIED").upper()
        business_value = item.get("business_value", 2)
        comm_intent = item.get("commercial_intent_score", 5)

        # 1. Search volume score (0-10)
        if search_vol >= 10000:
            sv_score = 10
        elif search_vol >= 5000:
            sv_score = 8
        elif search_vol >= 1000:
            sv_score = 6
        elif search_vol >= 500:
            sv_score = 4
        elif search_vol >= 100:
            sv_score = 2
        else:
            sv_score = 1

        # 2. Low competition score (0-10)
        if comp == "LOW":
            comp_score = 10
        elif comp == "MEDIUM":
            comp_score = 5
        else:
            comp_score = 1

        # 3. Check decline
        monthly_searches = item.get("monthly_searches") or []
        is_declining = check_is_declining(monthly_searches)
        item["is_declining"] = is_declining

        # Scale business value from 0-3 to 0-10
        scaled_bv = business_value * 3.33

        # Formula: priority_score = (sv_score * 0.25) + (comm_intent * 0.2) + (business_value * 3.33 * 0.45) + (comp_score * 0.1)
        priority_score = (sv_score * 0.25) + (comm_intent * 0.2) + (scaled_bv * 0.45) + (comp_score * 0.1)

        # Apply declining trend penalty
        if is_declining:
            priority_score -= 3.0

        item["search_volume_score"] = sv_score
        item["low_competition_score"] = comp_score
        item["priority_score"] = round(priority_score, 2)
        processed.append(item)

    # Sort by priority score descending
    processed.sort(key=lambda x: x["priority_score"], reverse=True)
    return processed


async def _classify_batch_with_gemini(settings: Settings, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY missing. Skipping AI clustering/intent classification.")
        # Return fallback values
        return [
            {
                **item,
                "intent": "commercial",
                "cluster": "General AI",
                "recommended_page_type": "blog_guide",
                "business_value": 2,
                "product_fit_score": 6.66,
                "commercial_intent_score": 5,
            } for item in batch
        ]

    try:
        system_prompt = """You are an expert SEO Strategist. Analyze the provided list of keywords and for each keyword:
1. Assign it a cluster (e.g., 'AI Marketing Agent', 'AI automation', 'AI content', 'Startup marketing', 'Competitor alternatives', 'Templates/tools').
2. Classify the user's search intent ('commercial', 'transactional', 'informational', 'navigational').
3. Classify the recommended page type:
   - 'pillar_page' (broad topic guide/landing page)
   - 'comparison_page' (X vs Y or alternatives)
   - 'use_case_page' (specific use case like startups, real estate, etc.)
   - 'blog_guide' (how-to guides, educational posts)
   - 'product_page' (interactive tool or product feature page)
4. Score the 'business_value' (integer 0-3) on the Ahrefs scale indicating the business value/product fit for an autonomous AI marketing agent product (Lyra) that automatically plans, generates and optimizes marketing campaigns:
   - 3: Our product is an indispensable solution (the searcher is actively looking for exactly what our product does).
   - 2: Our product is helpful, but the searcher could solve their problem without it.
   - 1: Our product can only be mentioned in passing (problem is loosely related to marketing).
   - 0: Our product is irrelevant to the search query.
5. Score the 'commercial_intent_score' (integer 0-10) indicating the commercial value (higher bids, transactional or commercial intent words).

Return ONLY a valid JSON array of objects, containing the following keys:
- "keyword": exact keyword string (matches the input case-sensitively)
- "cluster": cluster name
- "intent": intent classification
- "recommended_page_type": page type classification
- "business_value": integer 0 to 3
- "commercial_intent_score": integer 0 to 10

Do not return any markdown code blocks, text, or explanations outside the JSON array."""

        # Format input list for LLM
        input_list = []
        for kw in batch:
            input_list.append({
                "keyword": kw["keyword"],
                "avg_monthly_searches": kw["avg_monthly_searches"],
                "competition": kw["competition"],
                "low_top_of_page_bid": kw["low_top_of_page_bid"],
                "high_top_of_page_bid": kw["high_top_of_page_bid"]
            })

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(input_list)}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers={"content-type": "application/json", "x-goog-api-key": settings.gemini_api_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Clean markdown wrappers if any
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        classifications = json.loads(text)
        
        # Map back to raw items by keyword
        class_map = {item["keyword"].lower().strip(): item for item in classifications if "keyword" in item}

        results = []
        for kw in batch:
            k_key = kw["keyword"].lower().strip()
            cls_info = class_map.get(k_key, {})
            bv = int(cls_info.get("business_value", 2))
            results.append({
                **kw,
                "intent": cls_info.get("intent", "commercial"),
                "cluster": cls_info.get("cluster", "General AI"),
                "recommended_page_type": cls_info.get("recommended_page_type", "blog_guide"),
                "business_value": bv,
                "product_fit_score": bv * 3.33,
                "commercial_intent_score": int(cls_info.get("commercial_intent_score", 5)),
            })
        return results

    except Exception as e:
        logger.exception("Gemini keyword classification failed")
        # Return fallback classification
        return [
            {
                **item,
                "intent": "commercial",
                "cluster": "General AI",
                "recommended_page_type": "blog_guide",
                "business_value": 2,
                "product_fit_score": 6.66,
                "commercial_intent_score": 5,
            } for item in batch
        ]


async def generate_content_brief(settings: Settings, keyword_data: dict[str, Any]) -> dict[str, Any]:
    """
    Generates an SEO Content Brief for a high-priority keyword.
    """
    if not settings.gemini_api_key:
        return {
            "url_slug": f"/{keyword_data['keyword'].lower().replace(' ', '-')}/",
            "primary_keyword": keyword_data["keyword"],
            "secondary_keywords": [],
            "intent": keyword_data["intent"],
            "page_type": keyword_data["recommended_page_type"],
            "cta": settings.site.cta or "Join the MeetLyra waitlist",
            "h1": f"Ultimate Guide to {keyword_data['keyword']}",
            "seo_title": f"Ultimate Guide to {keyword_data['keyword']} | {settings.site.brand_name}",
            "meta_description": f"Learn more about {keyword_data['keyword']} and how to leverage it to grow your business.",
            "outline": ["Introduction", f"What is {keyword_data['keyword']}?", "Best Practices", "Conclusion"]
        }

    try:
        system_prompt = f"""You are an expert SEO Content Planner. Generate a comprehensive content brief for the primary keyword provided.
The brand details:
Brand Name: {settings.site.brand_name}
Target Audience: {settings.site.audience}
Value Proposition/CTA: {settings.site.cta or 'Join the MeetLyra private beta waitlist'}

CRITICAL GUARDRAIL:
The product {settings.site.brand_name} is currently in PRIVATE BETA and NOT publicly available.
- Do NOT generate any headings, outlines, descriptions, or CTAs that instruct the reader to try, log in, sign up, or use the product directly.
- The content must be purely educational, conceptual, and informational.
- The Call-to-Action (CTA) must focus ONLY on joining the waitlist or subscribing to the newsletter for early access updates.

Return ONLY a valid JSON object matching this schema:
{{
  "url_slug": "relative url path like /ai-marketing-agent/",
  "primary_keyword": "exact keyword",
  "secondary_keywords": ["list of 3-5 relevant secondary search terms"],
  "intent": "intent string",
  "page_type": "pillar, comparison, use-case, or blog-guide",
  "cta": "the exact call to action phrase",
  "h1": "compelling H1 title",
  "seo_title": "SEO Title (under 60 chars)",
  "meta_description": "Compelling search snippet under 155 chars",
  "outline": ["heading 1", "heading 2", "heading 3", "..."],
  "internal_links": ["list of topic areas to link from or link to"]
}}
Do not return any markdown code blocks, explanations, or commentary outside the JSON object."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(keyword_data)}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.4
            }
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers={"content-type": "application/json", "x-goog-api-key": settings.gemini_api_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Clean markdown wrappers if any
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)

    except Exception as e:
        logger.exception("Failed to generate content brief")
        # Default brief fallback
        return {
            "url_slug": f"/{keyword_data['keyword'].lower().replace(' ', '-')}/",
            "primary_keyword": keyword_data["keyword"],
            "secondary_keywords": [],
            "intent": keyword_data["intent"],
            "page_type": keyword_data["recommended_page_type"],
            "cta": settings.site.cta or "Join the MeetLyra waitlist",
            "h1": f"Ultimate Guide to {keyword_data['keyword']}",
            "seo_title": f"Ultimate Guide to {keyword_data['keyword']} | {settings.site.brand_name}",
            "meta_description": f"Learn more about {keyword_data['keyword']} and how to leverage it to grow your business.",
            "outline": ["Introduction", f"What is {keyword_data['keyword']}?", "Best Practices", "Conclusion"]
        }


def save_raw_keywords_to_csv(filepath: Path, raw_keywords: list[dict[str, Any]]):
    """
    Saves raw keyword metric data into a CSV.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["keyword", "avg_monthly_searches", "competition", "low_top_of_page_bid", "high_top_of_page_bid"])
        for kw in raw_keywords:
            writer.writerow([
                kw["keyword"],
                kw["avg_monthly_searches"],
                kw["competition"],
                kw["low_top_of_page_bid"],
                kw["high_top_of_page_bid"]
            ])
