import csv
import json
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

# Define keywords and data structure
keywords_data = [
    # Cluster 1: AI Marketing Agents (Pillar: best ai marketing agent - Published)
    {
        "keyword": "best ai marketing agent",
        "cluster_name": "Cluster 1: AI Marketing Agents",
        "role": "pillar",
        "parent_pillar": None,
        "anchor_text": "best ai marketing agent",
        "volume": 1400,
        "kd": 28,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 9.50,
        "status": "published",
        "wordpress_url": "https://blog.meetlyra.app/best-ai-marketing-agent/",
        "published_at": "2026-05-21T12:05:58.520317+00:00",
        "title": "Ultimate Guide to Best AI Marketing Agent",
        "publish_month": 0,
        "is_declining": False
    },
    {
        "keyword": "autonomous ai marketing agent",
        "cluster_name": "Cluster 1: AI Marketing Agents",
        "role": "spoke",
        "parent_pillar": "best ai marketing agent",
        "anchor_text": "best ai marketing agent",
        "volume": 850,
        "kd": 24,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 8.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Autonomous AI Marketing Agent: Complete Strategy Guide",
        "publish_month": 1,
        "is_declining": False
    },
    {
        "keyword": "ai marketing agent for startups",
        "cluster_name": "Cluster 1: AI Marketing Agents",
        "role": "spoke",
        "parent_pillar": "best ai marketing agent",
        "anchor_text": "best ai marketing agent",
        "volume": 450,
        "kd": 18,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 7.20,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "AI Marketing Agents for Startups: Scale Without a Team",
        "publish_month": 1,
        "is_declining": False
    },
    {
        "keyword": "ai campaign management",
        "cluster_name": "Cluster 1: AI Marketing Agents",
        "role": "spoke",
        "parent_pillar": "best ai marketing agent",
        "anchor_text": "best ai marketing agent",
        "volume": 700,
        "kd": 35,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 9.00,
        "status": "published",
        "wordpress_url": "https://blog.meetlyra.app/ai-campaign-management/",
        "published_at": "2026-05-21T14:15:49.254101+00:00",
        "title": "AI Campaign Management: The Modern Marketer's Playbook",
        "publish_month": 0,
        "is_declining": False
    },
    {
        "keyword": "ai agent for marketing execution",
        "cluster_name": "Cluster 1: AI Marketing Agents",
        "role": "spoke",
        "parent_pillar": "best ai marketing agent",
        "anchor_text": "best ai marketing agent",
        "volume": 320,
        "kd": 15,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 8.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Choosing an AI Agent for Marketing Execution: A Practical Guide",
        "publish_month": 1,
        "is_declining": False
    },
    {
        "keyword": "autonomous marketing software",
        "cluster_name": "Cluster 1: AI Marketing Agents",
        "role": "spoke",
        "parent_pillar": "best ai marketing agent",
        "anchor_text": "best ai marketing agent",
        "volume": 600,
        "kd": 28,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 10.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Autonomous Marketing Software: The Future of Growth Execution",
        "publish_month": 1,
        "is_declining": False
    },
    
    # Cluster 2: AI Content & SEO Automation (Pillar: best ai content automation - Planned)
    {
        "keyword": "best ai content automation",
        "cluster_name": "Cluster 2: AI Content & SEO Automation",
        "role": "pillar",
        "parent_pillar": None,
        "anchor_text": "best ai content automation",
        "volume": 1200,
        "kd": 32,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 9.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Best AI Content Automation Tools and Strategies for 2026",
        "publish_month": 1,
        "is_declining": False
    },
    {
        "keyword": "ai content automation",
        "cluster_name": "Cluster 2: AI Content & SEO Automation",
        "role": "spoke",
        "parent_pillar": "best ai content automation",
        "anchor_text": "best ai content automation",
        "volume": 900,
        "kd": 40,
        "intent": "commercial",
        "business_value": 2,
        "cpc": 8.20,
        "status": "published",
        "wordpress_url": "https://blog.meetlyra.app/?p=3368",
        "published_at": "2026-05-21T19:19:12.065052+00:00",
        "title": "AI Content Automation: Scaling Organic Traffic Without Thin Content",
        "publish_month": 0,
        "is_declining": False
    },
    {
        "keyword": "ai blog generator for b2b",
        "cluster_name": "Cluster 2: AI Content & SEO Automation",
        "role": "spoke",
        "parent_pillar": "best ai content automation",
        "anchor_text": "best ai content automation",
        "volume": 500,
        "kd": 22,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 7.80,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "How to Build a High-Quality AI Blog Generator Workflow for B2B",
        "publish_month": 1,
        "is_declining": False
    },
    {
        "keyword": "autonomous seo content engine",
        "cluster_name": "Cluster 2: AI Content & SEO Automation",
        "role": "spoke",
        "parent_pillar": "best ai content automation",
        "anchor_text": "best ai content automation",
        "volume": 350,
        "kd": 15,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 9.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Building an Autonomous SEO Content Engine: Step-by-Step Blueprint",
        "publish_month": 1,
        "is_declining": False
    },
    {
        "keyword": "generative engine optimization tools",
        "cluster_name": "Cluster 2: AI Content & SEO Automation",
        "role": "spoke",
        "parent_pillar": "best ai content automation",
        "anchor_text": "best ai content automation",
        "volume": 280,
        "kd": 12,
        "intent": "informational",
        "business_value": 3,
        "cpc": 8.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Top Generative Engine Optimization Tools for Modern GEO Strategy",
        "publish_month": 1,
        "is_declining": False
    },
    {
        "keyword": "ai copywriting workflow automation",
        "cluster_name": "Cluster 2: AI Content & SEO Automation",
        "role": "spoke",
        "parent_pillar": "best ai content automation",
        "anchor_text": "best ai content automation",
        "volume": 180,
        "kd": 10,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 6.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "AI Copywriting Workflow Automation: Save Hours of Draft Tweaking",
        "publish_month": 1,
        "is_declining": False
    },
    
    # Cluster 3: AI Campaign Planning (Pillar: ai campaign planning - Planned)
    {
        "keyword": "ai campaign planning",
        "cluster_name": "Cluster 3: AI Campaign Planning",
        "role": "pillar",
        "parent_pillar": None,
        "anchor_text": "ai campaign planning",
        "volume": 1500,
        "kd": 26,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 11.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "AI Campaign Planning: The Ultimate Guide to Autonomous Strategies",
        "publish_month": 2,
        "is_declining": False
    },
    {
        "keyword": "how to use ai campaign planning",
        "cluster_name": "Cluster 3: AI Campaign Planning",
        "role": "spoke",
        "parent_pillar": "ai campaign planning",
        "anchor_text": "ai campaign planning",
        "volume": 1200,
        "kd": 20,
        "intent": "informational",
        "business_value": 3,
        "cpc": 5.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "How to Use AI Campaign Planning to Orchestrate Multi-Channel Growth",
        "publish_month": 2,
        "is_declining": False
    },
    {
        "keyword": "ai campaign planning software",
        "cluster_name": "Cluster 3: AI Campaign Planning",
        "role": "spoke",
        "parent_pillar": "ai campaign planning",
        "anchor_text": "ai campaign planning",
        "volume": 750,
        "kd": 30,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 12.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Comparing AI Campaign Planning Software: What B2B Teams Need",
        "publish_month": 2,
        "is_declining": False
    },
    {
        "keyword": "best ai campaign planning",
        "cluster_name": "Cluster 3: AI Campaign Planning",
        "role": "spoke",
        "parent_pillar": "ai campaign planning",
        "anchor_text": "ai campaign planning",
        "volume": 550,
        "kd": 25,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 11.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Best AI Campaign Planning Tools: Core Features and Integrations",
        "publish_month": 2,
        "is_declining": False
    },
    {
        "keyword": "autonomous campaign execution",
        "cluster_name": "Cluster 3: AI Campaign Planning",
        "role": "spoke",
        "parent_pillar": "ai campaign planning",
        "anchor_text": "ai campaign planning",
        "volume": 200,
        "kd": 14,
        "intent": "commercial",
        "business_value": 3,
        "cpc": 10.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Autonomous Campaign Execution: Bridging the Gap from Plan to Launch",
        "publish_month": 2,
        "is_declining": False
    },
    
    # Cluster 4: Competitor Alternatives (Pillar: jasper pricing alternatives - Planned)
    {
        "keyword": "jasper pricing alternatives",
        "cluster_name": "Cluster 4: Competitor Alternatives",
        "role": "pillar",
        "parent_pillar": None,
        "anchor_text": "jasper pricing alternatives",
        "volume": 1800,
        "kd": 38,
        "intent": "transactional",
        "business_value": 2,
        "cpc": 14.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Jasper Pricing Alternatives: Find More Value in AI Copywriting",
        "publish_month": 3,
        "is_declining": False
    },
    {
        "keyword": "jasper pricing",
        "cluster_name": "Cluster 4: Competitor Alternatives",
        "role": "spoke",
        "parent_pillar": "jasper pricing alternatives",
        "anchor_text": "jasper pricing alternatives",
        "volume": 1100,
        "kd": 32,
        "intent": "transactional",
        "business_value": 2,
        "cpc": 12.50,
        "status": "published",
        "wordpress_url": "https://blog.meetlyra.app/jasper-pricing/",
        "published_at": "2026-05-21T19:30:28.033228+00:00",
        "title": "Jasper Pricing Breakdowns: Is the Industry Standard Worth the Cost?",
        "publish_month": 0,
        "is_declining": False
    },
    {
        "keyword": "copy ai pricing alternatives",
        "cluster_name": "Cluster 4: Competitor Alternatives",
        "role": "spoke",
        "parent_pillar": "jasper pricing alternatives",
        "anchor_text": "jasper pricing alternatives",
        "volume": 950,
        "kd": 28,
        "intent": "transactional",
        "business_value": 2,
        "cpc": 11.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Copy AI Pricing and Alternatives: Finding the Best Content Engine",
        "publish_month": 3,
        "is_declining": False
    },
    {
        "keyword": "writesonic vs jasper",
        "cluster_name": "Cluster 4: Competitor Alternatives",
        "role": "spoke",
        "parent_pillar": "jasper pricing alternatives",
        "anchor_text": "jasper pricing alternatives",
        "volume": 1400,
        "kd": 35,
        "intent": "commercial",
        "business_value": 2,
        "cpc": 13.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Writesonic vs Jasper: Deep Dive Comparison for B2B Copywriting",
        "publish_month": 3,
        "is_declining": True
    },
    {
        "keyword": "best surferseo alternatives",
        "cluster_name": "Cluster 4: Competitor Alternatives",
        "role": "spoke",
        "parent_pillar": "jasper pricing alternatives",
        "anchor_text": "jasper pricing alternatives",
        "volume": 650,
        "kd": 25,
        "intent": "commercial",
        "business_value": 2,
        "cpc": 9.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Best SurferSEO Alternatives: Get Better SEO Content Results",
        "publish_month": 3,
        "is_declining": False
    },
    {
        "keyword": "hubspot marketing hub alternatives",
        "cluster_name": "Cluster 4: Competitor Alternatives",
        "role": "spoke",
        "parent_pillar": "jasper pricing alternatives",
        "anchor_text": "jasper pricing alternatives",
        "volume": 500,
        "kd": 42,
        "intent": "commercial",
        "business_value": 2,
        "cpc": 18.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "HubSpot Marketing Hub Alternatives for Modern Agile Startups",
        "publish_month": 3,
        "is_declining": False
    },
    
    # Cluster 5: Marketing Automation & AI Integration (Pillar: marketing automation for startups - Planned)
    {
        "keyword": "marketing automation for startups",
        "cluster_name": "Cluster 5: Marketing Automation & AI Integration",
        "role": "pillar",
        "parent_pillar": None,
        "anchor_text": "marketing automation for startups",
        "volume": 1600,
        "kd": 35,
        "intent": "commercial",
        "business_value": 2,
        "cpc": 12.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Marketing Automation for Startups: Practical Guide to Scale Fast",
        "publish_month": 3,
        "is_declining": False
    },
    {
        "keyword": "zapier marketing automation workflows",
        "cluster_name": "Cluster 5: Marketing Automation & AI Integration",
        "role": "spoke",
        "parent_pillar": "marketing automation for startups",
        "anchor_text": "marketing automation for startups",
        "volume": 800,
        "kd": 28,
        "intent": "commercial",
        "business_value": 2,
        "cpc": 10.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Essential Zapier Marketing Automation Workflows for High-Growth Teams",
        "publish_month": 3,
        "is_declining": False
    },
    {
        "keyword": "autonomous agent",
        "cluster_name": "Cluster 5: Marketing Automation & AI Integration",
        "role": "spoke",
        "parent_pillar": "marketing automation for startups",
        "anchor_text": "marketing automation for startups",
        "volume": 900,
        "kd": 45,
        "intent": "informational",
        "business_value": 1,
        "cpc": 4.50,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "What is an Autonomous Agent? Definition and Real-world Uses",
        "publish_month": 3,
        "is_declining": False
    },
    {
        "keyword": "topic clustering tips",
        "cluster_name": "Cluster 5: Marketing Automation & AI Integration",
        "role": "spoke",
        "parent_pillar": "marketing automation for startups",
        "anchor_text": "marketing automation for startups",
        "volume": 500,
        "kd": 20,
        "intent": "informational",
        "business_value": 1,
        "cpc": 3.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "Advanced Topic Clustering Tips: Structuring Your Site for SEO",
        "publish_month": 3,
        "is_declining": False
    },
    {
        "keyword": "seo keyword research",
        "cluster_name": "Cluster 5: Marketing Automation & AI Integration",
        "role": "spoke",
        "parent_pillar": "marketing automation for startups",
        "anchor_text": "marketing automation for startups",
        "volume": 750,
        "kd": 50,
        "intent": "informational",
        "business_value": 1,
        "cpc": 6.00,
        "status": "planned",
        "wordpress_url": None,
        "published_at": None,
        "title": "SEO Keyword Research: How to Find the Opportunities Competitors Miss",
        "publish_month": 3,
        "is_declining": False
    }
]

def calculate_metrics(kw):
    sv = kw["volume"]
    kd = kw["kd"]
    intent = kw["intent"]
    bp = kw["business_value"]
    cpc = kw["cpc"]
    status = kw["status"]
    is_declining = kw["is_declining"]
    
    # 1. Search volume score (0-10)
    if sv >= 10000:
        sv_score = 10
    elif sv >= 5000:
        sv_score = 8
    elif sv >= 1000:
        sv_score = 6
    elif sv >= 500:
        sv_score = 4
    elif sv >= 100:
        sv_score = 2
    else:
        sv_score = 1

    # 2. Low competition score (0-10)
    if kd <= 20:
        comp_score = 10
    elif kd <= 40:
        comp_score = 5
    else:
        comp_score = 1

    # 3. Commercial intent score (0-10)
    if intent == "transactional":
        comm_score = 10
    elif intent == "commercial":
        comm_score = 8
    elif intent == "informational":
        comm_score = 4
    else:
        comm_score = 2

    # Ahrefs business potential scaling (0-3 -> 0-10)
    scaled_bp = bp * 3.33

    # Priority Score Formula
    priority_score = (sv_score * 0.25) + (comm_score * 0.2) + (scaled_bp * 0.45) + (comp_score * 0.1)
    if is_declining:
        priority_score -= 3.0
    priority_score = max(0.0, round(priority_score, 2))

    # Backlink requirements: referring domains needed
    backlinks_needed = max(0, int(round(kd * 1.3)))

    # Estimated time to rank (months)
    if kd <= 20:
        ttr_str = "1-3 months"
        ttr_months = 2
    elif kd <= 40:
        ttr_str = "3-6 months"
        ttr_months = 4
    elif kd <= 60:
        ttr_str = "6-8 months"
        ttr_months = 7
    else:
        ttr_str = "9-12 months"
        ttr_months = 10

    # Click potential (CTR %) based on intent and KD
    if intent in ["transactional", "commercial"]:
        ctr = 0.25 # Ads and products take some clicks
    else:
        ctr = 0.35 # Organic informational gets high CTR if well written
        
    potential_monthly_traffic = int(round(sv * ctr))
    potential_monthly_seo_value = round(potential_monthly_traffic * cpc, 2)

    return {
        "priority_score": priority_score,
        "backlinks_needed": backlinks_needed,
        "ttr_str": ttr_str,
        "ttr_months": ttr_months,
        "ctr": ctr,
        "potential_monthly_traffic": potential_monthly_traffic,
        "potential_monthly_seo_value": potential_monthly_seo_value,
        "sv_score": sv_score,
        "comp_score": comp_score,
        "comm_score": comm_score
    }

def project_traffic_and_value(kw, metrics, month):
    # Calculations for run-rate traffic and value in Month `month`
    # and cumulative traffic/value up to Month `month`
    status = kw["status"]
    pub_m = kw["publish_month"]
    ttr_months = metrics["ttr_months"]
    pot_traffic = metrics["potential_monthly_traffic"]
    cpc = kw["cpc"]
    
    # We calculate the monthly traffic in each month from 1 to 12
    monthly_traffic = []
    for m in range(1, 13):
        if status == "published":
            # Already published before Month 1
            if m == 1:
                factor = 0.85
            elif m == 2:
                factor = 0.95
            else:
                factor = 1.0
            t = int(round(pot_traffic * factor))
        else:
            # Planned post
            if m < pub_m:
                t = 0
            else:
                months_since_pub = m - pub_m + 1
                if ttr_months <= 2: # low difficulty
                    if months_since_pub == 1:
                        factor = 0.25
                    elif months_since_pub == 2:
                        factor = 0.60
                    elif months_since_pub == 3:
                        factor = 0.90
                    else:
                        factor = 1.0
                elif ttr_months <= 4: # medium difficulty
                    if months_since_pub == 1:
                        factor = 0.05
                    elif months_since_pub == 2:
                        factor = 0.20
                    elif months_since_pub == 3:
                        factor = 0.50
                    elif months_since_pub == 4:
                        factor = 0.80
                    elif months_since_pub == 5:
                        factor = 0.95
                    else:
                        factor = 1.0
                else: # high difficulty
                    if months_since_pub <= 2:
                        factor = 0.0
                    elif months_since_pub == 3:
                        factor = 0.10
                    elif months_since_pub == 4:
                        factor = 0.25
                    elif months_since_pub == 5:
                        factor = 0.50
                    elif months_since_pub == 6:
                        factor = 0.75
                    elif months_since_pub == 7:
                        factor = 0.90
                    else:
                        factor = 1.0
                t = int(round(pot_traffic * factor))
        monthly_traffic.append(t)
        
    # Run rate in the target month (1-indexed, so index month-1)
    run_rate_traffic = monthly_traffic[month - 1]
    run_rate_value = round(run_rate_traffic * cpc, 2)
    
    # Cumulative up to the target month
    cumulative_traffic = sum(monthly_traffic[:month])
    cumulative_value = round(sum([t * cpc for t in monthly_traffic[:month]]), 2)
    
    return run_rate_traffic, run_rate_value, cumulative_traffic, cumulative_value

# Main processing
def main():
    processed_list = []
    
    # Group by cluster to calculate traffic potential (max SV in cluster)
    cluster_volumes = {}
    for kw in keywords_data:
        c = kw["cluster_name"]
        cluster_volumes[c] = max(cluster_volumes.get(c, 0), kw["volume"])
        
    for kw in keywords_data:
        m = calculate_metrics(kw)
        
        # Projections
        rr_t_3, rr_v_3, cum_t_3, cum_v_3 = project_traffic_and_value(kw, m, 3)
        rr_t_6, rr_v_6, cum_t_6, cum_v_6 = project_traffic_and_value(kw, m, 6)
        rr_t_12, rr_v_12, cum_t_12, cum_v_12 = project_traffic_and_value(kw, m, 12)
        
        processed = {
            "keyword": kw["keyword"],
            "topic_cluster": kw["cluster_name"],
            "search_volume": kw["volume"],
            "kd": kw["kd"],
            "intent": kw["intent"],
            "click_potential_ctr": m["ctr"],
            "business_potential": kw["business_value"],
            "priority_score": m["priority_score"],
            "backlink_requirements_rd": m["backlinks_needed"],
            "estimated_time_to_rank": m["ttr_str"],
            "cpc": kw["cpc"],
            "potential_monthly_traffic": m["potential_monthly_traffic"],
            "potential_monthly_seo_value": m["potential_monthly_seo_value"],
            
            "run_rate_traffic_3m": rr_t_3,
            "run_rate_seo_value_3m": rr_v_3,
            "run_rate_traffic_6m": rr_t_6,
            "run_rate_seo_value_6m": rr_v_6,
            "run_rate_traffic_12m": rr_t_12,
            "run_rate_seo_value_12m": rr_v_12,
            
            "cumulative_traffic_3m": cum_t_3,
            "cumulative_seo_value_3m": cum_v_3,
            "cumulative_traffic_6m": cum_t_6,
            "cumulative_seo_value_6m": cum_v_6,
            "cumulative_traffic_12m": cum_t_12,
            "cumulative_seo_value_12m": cum_v_12,
            
            "status": kw["status"],
            "wordpress_url": kw["wordpress_url"],
            "recommended_title": kw["title"],
            "role": kw["role"],
            "parent_pillar": kw["parent_pillar"],
            "anchor_text": kw["anchor_text"],
            "published_at": kw["published_at"],
            "publish_month": kw["publish_month"]
        }
        processed_list.append(processed)

    # 1. Save CSV
    csv_path = Path("/Users/dylanangloher/claude-blog-engine/data/seo/keyword_research/seo_keyword_plan.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    headers = [
        "keyword", "topic_cluster", "search_volume", "kd", "intent", 
        "click_potential_ctr", "business_potential", "priority_score", 
        "backlink_requirements_rd", "estimated_time_to_rank", "cpc", 
        "potential_monthly_traffic", "potential_monthly_seo_value",
        "run_rate_traffic_3m", "run_rate_seo_value_3m", 
        "run_rate_traffic_6m", "run_rate_seo_value_6m", 
        "run_rate_traffic_12m", "run_rate_seo_value_12m",
        "cumulative_traffic_3m", "cumulative_seo_value_3m", 
        "cumulative_traffic_6m", "cumulative_seo_value_6m", 
        "cumulative_traffic_12m", "cumulative_seo_value_12m",
        "status", "wordpress_url", "recommended_title"
    ]
    
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for item in processed_list:
            writer.writerow(item)
    print(f"Saved CSV to {csv_path}")

    # 2. Update SQLite database content_plan table
    db_path = Path("/Users/dylanangloher/claude-blog-engine/.content-machine/content_machine.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Let's clear the old content plan
    cursor.execute("DELETE FROM content_plan")
    
    # Insert new items
    for item in processed_list:
        tp = cluster_volumes[item["topic_cluster"]]
        cursor.execute(
            """
            INSERT INTO content_plan (
                keyword, title, intent, cluster_name, role, parent_pillar,
                anchor_text, score, volume, kd, status, created_at,
                published_at, wordpress_url, business_value, traffic_potential
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["keyword"],
                item["recommended_title"],
                item["intent"],
                item["topic_cluster"],
                item["role"],
                item["parent_pillar"],
                item["anchor_text"],
                item["priority_score"],
                item["search_volume"],
                item["kd"],
                item["status"],
                datetime.now(timezone.utc).isoformat(),
                item["published_at"],
                item["wordpress_url"],
                item["business_potential"],
                tp
            )
        )
    conn.commit()
    conn.close()
    print("Database content_plan table updated and synchronized!")

    # 3. Generate summary reports
    # Let's calculate total projections
    totals = {
        "sv": sum([x["search_volume"] for x in processed_list]),
        "potential_traffic": sum([x["potential_monthly_traffic"] for x in processed_list]),
        "potential_value": sum([x["potential_monthly_seo_value"] for x in processed_list]),
        
        "rr_t_3": sum([x["run_rate_traffic_3m"] for x in processed_list]),
        "rr_v_3": sum([x["run_rate_seo_value_3m"] for x in processed_list]),
        "rr_t_6": sum([x["run_rate_traffic_6m"] for x in processed_list]),
        "rr_v_6": sum([x["run_rate_seo_value_6m"] for x in processed_list]),
        "rr_t_12": sum([x["run_rate_traffic_12m"] for x in processed_list]),
        "rr_v_12": sum([x["run_rate_seo_value_12m"] for x in processed_list]),
        
        "cum_t_3": sum([x["cumulative_traffic_3m"] for x in processed_list]),
        "cum_v_3": sum([x["cumulative_seo_value_3m"] for x in processed_list]),
        "cum_t_6": sum([x["cumulative_traffic_6m"] for x in processed_list]),
        "cum_v_6": sum([x["cumulative_seo_value_6m"] for x in processed_list]),
        "cum_t_12": sum([x["cumulative_traffic_12m"] for x in processed_list]),
        "cum_v_12": sum([x["cumulative_seo_value_12m"] for x in processed_list])
    }
    
    # Save the markdown plan
    md = []
    md.append("# Master SEO Plan & Strategic Forecast for MeetLyra")
    md.append(f"Document Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC\n")
    md.append("This document outlines the Master SEO and Content Plan for MeetLyra, a B2B AI marketing agent and SEO engine. It provides detailed keyword research, prioritization, Yoast hub-and-spoke content architecture, and a 12-month traffic and SEO value forecast model.\n")
    
    md.append("## Executive Summary")
    md.append("Our SEO strategy focuses on capturing high-intent search queries for autonomous AI marketing agents, campaign planning systems, and content automation engines, while also targeting competitor terms (e.g. Jasper and Copy.ai).")
    md.append(f"We have identified **28 strategic target keywords** organized into **5 core topic clusters**.")
    md.append("All articles adhere to **Yoast's Pyramid structure** and use flat URL slugs under `/blog/` to ensure high crawlability and clean indexing. Supporting spoke articles link back contextually to their parent pillar pages.\n")
    
    md.append("### 12-Month SEO Forecast Totals")
    md.append(f"- **Total Search Volume of Target Keyword Universe**: {totals['sv']:,} monthly searches")
    md.append(f"- **Total Monthly Traffic Potential (At Maturity)**: {totals['potential_traffic']:,} visits/month")
    md.append(f"- **Total Monthly SEO Value (At Maturity)**: ${totals['potential_value']:,.2f}/month\n")
    
    md.append("#### Cumulative Traffic & SEO Value Growth Projections")
    md.append("| Period | Monthly Traffic Run-Rate | Monthly SEO Value Run-Rate | Cumulative Traffic Generated | Cumulative SEO Value Generated |")
    md.append("|---|---|---|---|---|")
    md.append(f"| **Month 3** | {totals['rr_t_3']:,} visits/mo | ${totals['rr_v_3']:,.2f}/mo | {totals['cum_t_3']:,} visits | ${totals['cum_v_3']:,.2f} |")
    md.append(f"| **Month 6** | {totals['rr_t_6']:,} visits/mo | ${totals['rr_v_6']:,.2f}/mo | {totals['cum_t_6']:,} visits | ${totals['cum_v_6']:,.2f} |")
    md.append(f"| **Month 12** | {totals['rr_t_12']:,} visits/mo | ${totals['rr_v_12']:,.2f}/mo | {totals['cum_t_12']:,} visits | ${totals['cum_v_12']:,.2f} |\n")
    
    md.append("---")
    md.append("## 1. Topical Map & Yoast Pyramid Architecture")
    md.append("The 28 keywords are organized into 5 thematic clusters. Spokes link back to their respective Pillar Page to establish topical authority.")
    
    # Group by cluster
    clusters = {}
    for item in processed_list:
        c = item["topic_cluster"]
        if c not in clusters:
            clusters[c] = []
        clusters[c].append(item)
        
    for c_name, members in clusters.items():
        md.append(f"\n### {c_name}")
        
        pillar = [m for m in members if m["role"] == "pillar"][0]
        spokes = [m for m in members if m["role"] == "spoke"]
        
        md.append(f"**Pillar Page:**")
        md.append(f"- **Keyword:** `{pillar['keyword']}`")
        md.append(f"- **Target Title:** *{pillar['recommended_title']}*")
        md.append(f"- **Status:** `{pillar['status'].upper()}`" + (f" ([Live URL]({pillar['wordpress_url']}))" if pillar['wordpress_url'] else ""))
        md.append(f"- **Volume:** {pillar['search_volume']:,} | **KD:** {pillar['kd']} | **Ahrefs Priority:** {pillar['priority_score']:.2f}")
        md.append(f"- **Time to Rank:** {pillar['estimated_time_to_rank']} | **Competitor Backlinks Needed (RD):** {pillar['backlink_requirements_rd']}")
        md.append("")
        
        md.append("**Supporting Spoke Articles:**")
        md.append("| Spoke Keyword | Recommended Title | Status | Ahrefs Score | Vol | KD | Backlinks (RD) | Time to Rank | Contextual Anchor to Pillar |")
        md.append("|---|---|---|---|---|---|---|---|---|")
        for spoke in spokes:
            status_str = spoke['status'].upper()
            if spoke['wordpress_url']:
                status_str = f"[{status_str}]({spoke['wordpress_url']})"
            md.append(
                f"| `{spoke['keyword']}` | {spoke['recommended_title']} | {status_str} | {spoke['priority_score']:.2f} | "
                f"{spoke['search_volume']:,} | {spoke['kd']} | {spoke['backlink_requirements_rd']} | "
                f"{spoke['estimated_time_to_rank']} | `{spoke['anchor_text']}` |"
            )
        md.append("")
        
    md.append("---")
    md.append("## 2. Traffic Projections & SEO Value Modeling")
    md.append("The projections are based on standard click-through rate (CTR) models adjusted for search intent (Informational: 35% CTR, Commercial/Transactional: 25% CTR) and a ranking velocity curve aligned with keyword difficulty (KD) and publish schedule.")
    
    md.append("\n### Detailed Projections Table")
    md.append("| Keyword | Cluster | Vol | KD | CPC | Monthly Traffic Potential | Monthly SEO Value Potential | M3 Run-Rate | M6 Run-Rate | M12 Run-Rate | Cumulative Traffic (12m) | Cumulative Value (12m) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for item in processed_list:
        md.append(
            f"| `{item['keyword']}` | {item['topic_cluster'].split(': ')[-1]} | {item['search_volume']:,} | {item['kd']} | "
            f"${item['cpc']:.2f} | {item['potential_monthly_traffic']:,} | ${item['potential_monthly_seo_value']:,.2f} | "
            f"{item['run_rate_traffic_3m']:,} | {item['run_rate_traffic_6m']:,} | {item['run_rate_traffic_12m']:,} | "
            f"{item['cumulative_traffic_12m']:,} | ${item['cumulative_seo_value_12m']:,.2f} |"
        )
        
    md.append("\n## 3. Implementation and Linking Guidelines")
    md.append("1. **First-Priority Publishing**: Always publish Pillar Pages before Spokes, or update them immediately as spokes go live. This allows you to construct internal links dynamically.")
    md.append("2. **Contextual Internal Linking**: For every Spoke article published, insert a link pointing to the Pillar page using the designated anchor text (shown in the table). This establishes hierarchical topical relevance.")
    md.append("3. **Flat URL Structure**: Ensure all WordPress slugs follow a flat pattern, for example, `/blog/best-ai-marketing-agent/` and `/blog/autonomous-ai-marketing-agent/`, rather than nested patterns.")
    md.append("4. **Waitlist Calls-To-Action (CTA)**: All articles must link exclusively to `https://waitlist.meetlyra.app` to drive waitlist signups. Never link to trial or product registration pages as the system is currently in private beta.")
    
    md_content = "\n".join(md)
    
    # Save markdown plan locally in workspace
    local_plan_path = Path("/Users/dylanangloher/claude-blog-engine/seo-reports/master_seo_plan.md")
    local_plan_path.write_text(md_content, encoding="utf-8")
    print(f"Saved Master SEO Plan markdown to {local_plan_path}")
    
    # Save markdown plan to brain artifacts
    brain_plan_path = Path("/Users/dylanangloher/.gemini/antigravity/brain/5cb25842-f1a4-4d2f-80dc-68e4801fd23e/master_seo_plan.md")
    brain_plan_path.write_text(md_content, encoding="utf-8")
    print(f"Saved Master SEO Plan to brain artifact: {brain_plan_path}")

    # Also update cluster-plan.md to match
    planner_report_path = Path("/Users/dylanangloher/claude-blog-engine/cluster-plan.md")
    # Make a simpler summary of clusters for the planner_report
    rep_md = []
    rep_md.append("# Unified Yoast Topic Cluster & Topical Map Plan")
    rep_md.append(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    rep_md.append("This document outlines the structured hub-and-spoke topic cluster plan following Yoast's site structure guidelines and Ahrefs' keyword prioritization rules.\n")
    
    for c_name, members in clusters.items():
        rep_md.append(f"## {c_name}")
        
        pillar = [m for m in members if m["role"] == "pillar"][0]
        spokes = [m for m in members if m["role"] == "spoke"]
        
        rep_md.append("### Pillar Page")
        rep_md.append(f"- **Keyword**: `{pillar['keyword']}`")
        rep_md.append(f"- **Target Title**: {pillar['recommended_title']}")
        rep_md.append(f"- **Status**: `{pillar['status'].upper()}`")
        if pillar.get("wordpress_url"):
            rep_md.append(f"- **Live URL**: {pillar['wordpress_url']}")
        rep_md.append(f"- **Search Intent**: {pillar['intent']}")
        rep_md.append(f"- **Volume**: {pillar['search_volume']} | **KD**: {pillar['kd']} | **Priority Score**: {pillar['priority_score']}")
        rep_md.append(f"- **Business Value (0-3)**: {pillar['business_potential']} | **Traffic Potential**: {cluster_volumes[c_name]}")
        rep_md.append("")
        
        rep_md.append("### Supporting Spoke Pages")
        rep_md.append("| Spoke Keyword | Target Title | Status | Score | Vol | KD | Biz Value | Traffic Potential | Parent Link Anchor | WordPress URL |")
        rep_md.append("|---|---|---|---|---|---|---|---|---|---|")
        for spoke in spokes:
            wp_url = spoke.get("wordpress_url") or "None"
            status_str = spoke.get("status", "planned").upper()
            rep_md.append(
                f"| `{spoke['keyword']}` | {spoke['recommended_title']} | `{status_str}` | {spoke['priority_score']} | {spoke['search_volume']} | "
                f"{spoke['kd']} | {spoke['business_potential']} | {cluster_volumes[c_name]} | `{spoke['anchor_text']}` | {wp_url} |"
            )
        rep_md.append("")
        rep_md.append("---")
        
    rep_content = "\n".join(rep_md)
    planner_report_path.write_text(rep_content, encoding="utf-8")
    
    brain_cluster_path = Path("/Users/dylanangloher/.gemini/antigravity/brain/5cb25842-f1a4-4d2f-80dc-68e4801fd23e/cluster_plan.md")
    brain_cluster_path.write_text(rep_content, encoding="utf-8")
    
    # Update cluster-plan.json
    local_json_path = Path("/Users/dylanangloher/claude-blog-engine/cluster-plan.json")
    with open(local_json_path, "w", encoding="utf-8") as json_f:
        json.dump(processed_list, json_f, indent=2, default=str)
        
if __name__ == "__main__":
    main()
