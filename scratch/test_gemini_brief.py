import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
from content_machine.config import load_settings
from content_machine.models import Opportunity, WorkItemType
from content_machine.anthropic_writer import ContentWriter

load_dotenv()

async def main():
    settings = load_settings()
    writer = ContentWriter(settings)
    
    opp = Opportunity(
        kind=WorkItemType.NEW_ARTICLE,
        keyword="ai content automation",
        title="AI Content Automation: From Tools to Autonomous Systems (2026)",
        score=8.4,
        metadata={
            "volume": 1200,
            "kd": 0,
            "intent": "commercial",
            "cluster_name": "Cluster 1: Ai Marketing Agent",
            "role": "spoke",
            "parent_pillar": "ai marketing agent",
            "anchor_text": "ai marketing agent"
        }
    )
    
    # Mock research structure
    research = {
        "competitor_headlines": ["AI content tools", "Autonomous content workflows"],
        "questions": ["How do I automate content?", "What is autonomous content?"],
        "keyphrases": ["ai content automation", "automate content writing"],
        "internal_links": [
            {"anchor": "AI marketing agent", "url": "https://blog.meetlyra.app/what-is-an-ai-marketing-agent/"}
        ],
        "authority_links": [
            {"anchor": "Google Search Central", "url": "https://developers.google.com/search/docs"}
        ],
        "target_internal_link": {
            "url": "https://blog.meetlyra.app/what-is-an-ai-marketing-agent/",
            "anchor_text": "ai marketing agent",
            "keyword": "ai marketing agent"
        }
    }
    
    sys_prompt = writer._system_prompt(opp, research)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Generate the content now. Return ONLY valid JSON."}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": sys_prompt}]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "slug": {"type": "STRING"},
                    "markdown": {"type": "STRING"},
                    "meta_title": {"type": "STRING"},
                    "meta_description": {"type": "STRING"},
                    "focus_keyphrase": {"type": "STRING"},
                    "excerpt": {"type": "STRING"},
                    "tags": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "categories": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "schema_json": {
                        "type": "OBJECT"
                    },
                    "image_prompt": {"type": "STRING"},
                    "image_alt_text": {"type": "STRING"},
                    "rich_blocks": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": [
                    "title", "slug", "markdown", "meta_title", "meta_description",
                    "focus_keyphrase", "excerpt", "tags", "categories", "schema_json",
                    "image_prompt", "image_alt_text"
                ]
            },
            "temperature": 0.2
        }
    }
    
    print("Calling Gemini API...")
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(url, headers={"content-type": "application/json"}, json=payload)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            print("\nRAW TEXT RESPONSE FROM GEMINI:")
            print(text)
            
            # Try to parse
            try:
                parsed = json.loads(text)
                print("\nParsed successfully!")
                print("Keys:", list(parsed.keys()))
                print("Markdown length:", len(parsed.get("markdown", "")))
                print("Markdown is empty?", not parsed.get("markdown"))
            except Exception as e:
                print("\nParsing error:", e)
        else:
            print("Response:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())
