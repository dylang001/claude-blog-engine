import json
import logging
import re
from typing import Any
import httpx

from .config import Settings
from .wordpress import WordPressClient
from .data_sources import DataForSEOClient

logger = logging.getLogger("content_machine.outreach")


class OutreachAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.wordpress = WordPressClient(settings)

    async def generate_campaign_for_post(self, post_slug: str) -> dict[str, Any]:
        """Generate a personalized backlink outreach campaign for a WordPress post via Next.js API."""
        if not self.settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for outreach campaign generation.")

        logger.info("Fetching post content from WordPress for slug: %s...", post_slug)
        post = await self.wordpress.find_post_by_slug(post_slug)
        if not post:
            raise ValueError(f"Post with slug '{post_slug}' not found in WordPress.")

        post_title = post.get("title", {}).get("rendered", "")
        post_link = post.get("link", "")
        post_content = post.get("content", {}).get("rendered", "")

        # Extract a short excerpt or first part of content for LLM context
        clean_text = re.sub(r"<[^>]+>", " ", post_content)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        context_snippet = clean_text[:3000]

        # Step 1: Call Anthropic to generate 2 search queries
        query_prompt = f"""You are an SEO expert. We published an article:
Title: "{post_title}"
URL: {post_link}

Generate 2 Google search queries (without search operators like site: or file:) that will find relevant blog posts, resource lists, news articles, or guides where we could pitch a backlink or guest post.

Return ONLY a JSON list of strings:
[
  "query 1",
  "query 2"
]
"""
        logger.info("Generating search queries for post...")
        queries = [post_title]  # default fallback
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5",
                        "max_tokens": 500,
                        "messages": [{"role": "user", "content": query_prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            
            text = data["content"][0]["text"]
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                queries = json.loads(text[start:end+1])
        except Exception as e:
            logger.error("Failed to generate search queries from Anthropic: %s. Using title fallback.", e)

        # Step 2: Run search queries via DataForSEO serp API
        search_results = []
        dataforseo = DataForSEOClient(self.settings)
        for query in queries:
            logger.info("Searching Google for: %s", query)
            try:
                serp_res = await dataforseo.serp(query, limit=8)
                for task in serp_res.get("tasks", []):
                    for result in task.get("result") or []:
                        for item in result.get("items") or []:
                            if item.get("type") == "organic" and item.get("url"):
                                search_results.append({
                                    "title": item.get("title", ""),
                                    "url": item.get("url", ""),
                                    "domain": item.get("domain", ""),
                                    "description": item.get("description", "") or item.get("snippet", "")
                                })
            except Exception as e:
                logger.error("Failed to run SERP search for '%s': %s", query, e)

        # Step 3: Call Anthropic to select prospects and map strategies
        prospects_prompt = f"""You are an elite B2B PR Specialist, media relations expert, and SEO Link Builder for MeetLyra (https://meetlyra.app).

We just published a new article:
Title: "{post_title}"
URL: {post_link}
Content Snippet: {context_snippet}

We searched Google and found the following organic search result pages:
{json.dumps(search_results[:12], indent=2)}

Select 3-5 highly relevant prospects from these actual search results where we can build a backlink or collaborate. You MUST use real URLs from the search results to "confirm that there are links".
For each prospect, you must:
1. Identify a valid professional contact email for their domain (e.g. editor@domain.com, hello@domain.com, or a guess like firstName@domain.com).
2. Identify their name (first and last name, or 'Editor' if unknown).
3. The publication/company name.
4. Select the best backlink outreach method/strategy from the Instantly.ai list:
   - Skyscraper (Offering Better Content): Reaching out to resource lists or competitor backlinks to pitch our better/updated guide.
   - Updating Old Content: Reaching out to old posts (e.g. 2023/2024) to replace outdated stats/data.
   - Guest Posting: Proposing a free guest post in exchange for a link.
   - Journalism Sourcing: Pitching editorial/journalist beats as a quote/data resource.
   - Link Reclamation: Reclaiming unlinked brand mentions.
5. Identify the specific target page/article URL from the search results where we want the link or replacement.
6. Write a tailored beat context explaining the strategy and link fit.

Format your response as a valid JSON object matching this structure:
{{
  "prospects": [
    {{
      "email": "editor@prospectdomain.com",
      "firstName": "Firstname",
      "lastName": "Lastname",
      "companyName": "Publication Name",
      "context": "Strategy: [Selected Strategy Name]\\nTarget URL: [Target page URL]\\nContext: [Tailored pitch context explaining the fit with their page/beat]"
    }}
  ]
}}
"""
        logger.info("Calling Anthropic to brainstorm prospects and pitch contexts based on search results...")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prospects_prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["content"][0]["text"]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object returned from Anthropic")
        parsed = json.loads(text[start:end+1], strict=False)

        logger.info("Connecting to Next.js Outbound Email Agent at %s...", self.settings.outbound_email_agent_url)
        
        # Step 4: Define custom campaign system prompt for email generation in Next.js
        custom_outreach_prompt = """You are an expert SEO Link Builder and PR outreach agent for MeetLyra (https://meetlyra.app).

For the contact provided, write a highly tailored, personal B2B cold email sequence (initial email + 2 follow-ups) asking for a backlink or guest posting opportunity.

The email sequence is sent from Dylan, the founder of Lyra.
- In the first paragraph of the first email, you MUST introduce yourself: "This is Dylan, the founder of Lyra."

You must look at the specific "Context/Notes" provided for the contact, which includes:
1. The chosen Backlink Strategy (e.g. Skyscraper (Offering Better Content), Updating Old Content, Guest Posting, Journalism Sourcing, Link Reclamation).
2. The specific target URL on their site where we want a link from or want to replace.
3. The specific topic/angle of their article.

Tailor the email copies to fit the chosen strategy perfectly:
- If the strategy is Skyscraper (Offering Better Content): Compliment their article at the target URL, mention that they reference competitor/general concepts, introduce our more comprehensive guide (the new post), and ask in a helpful way if they can add a link to it.
- If the strategy is Updating Old Content: Reference their target URL, note that some statistics or data in their article are outdated, introduce our new post with updated findings, and suggest linking to it as a replacement/update.
- If the strategy is Guest Posting: Reference their publication, mention the fit between our topics, and propose writing a high-quality free guest post for their audience in exchange for a backlink.
- If the strategy is Journalism Sourcing: Address them as a journalist/editor covering this beat, share 2-3 key unique takeaways from our new article/study, and offer our data/quotes as a resource for their future stories.
- If the strategy is Link Reclamation: Thank them for mentioning our brand or category, note they didn't include a hyperlink, and politely ask to turn the mention into a link.

Call to Action (CTA) Rules:
- The sole objective of this outreach is to get a backlink to our site.
- The call-to-action (CTA) must align with this objective. Do not ask for a phone call, meeting, demo, or sales chat.
- Ask for the link in the kindest, most helpful, and polite way possible. Focus on do-follow backlinks where appropriate. E.g., ask if they would be open to adding a do-follow link to our guide so their readers get the complete step-by-step walkthrough, or if they would mind linking to it.

General Formatting Rules:
- Keep emails short, F-shaped, clear and punchy (under 80 words per email).
- Write ONLY the email body. Do not include greetings like "Hi [Name]" or sign-offs/signatures (these are added automatically).
- Use HTML <p> and <br> tags.
- Do not use passive voice or exclamation marks. Avoid marketing jargon.
- Never use long sentences (keep sentences short, simple, and direct).
- Never use em dashes (—) or en dashes (–) anywhere. Use standard periods or commas."""

        # 1. Create a campaign on the Next.js app
        campaign_data = {
            "name": f"Backlinks: {post_title}",
            "description": f"Outreach campaign for WordPress post: {post_title} ({post_link})",
            "outreachMode": "local",
            "researchEnabled": True,
            "peopleResearchEnabled": False,
            "numberOfFollowUps": 2,
            "systemPrompt": custom_outreach_prompt
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                camp_resp = await client.post(
                    f"{self.settings.outbound_email_agent_url}/api/campaigns",
                    json=campaign_data
                )
                camp_resp.raise_for_status()
                campaign_res = camp_resp.json()
                campaign_id = campaign_res["campaign"]["id"]
                logger.info("Created campaign in Next.js with ID: %s", campaign_id)
            except Exception as e:
                logger.error("Failed to create campaign in Next.js API: %s", e)
                raise RuntimeError(f"Could not connect to outbound Next.js app at {self.settings.outbound_email_agent_url}: {e}")

            # 2. Add prospects as contacts to trigger Next.js research/outreach workflow
            prospects_created = []
            for p in parsed.get("prospects", []):
                email_addr = p.get("email", "").strip()
                if not email_addr:
                    continue

                contact_payload = {
                    "campaignId": campaign_id,
                    "contact": {
                        "email": email_addr,
                        "firstName": p.get("firstName", "Editor"),
                        "lastName": p.get("lastName", ""),
                        "companyName": p.get("companyName", "Unknown"),
                        "context": p.get("context", "")
                    }
                }

                try:
                    contact_resp = await client.post(
                        f"{self.settings.outbound_email_agent_url}/api/contacts",
                        json=contact_payload
                    )
                    if contact_resp.status_code == 201:
                        prospects_created.append({
                            "email": email_addr,
                            "company": p.get("companyName", "Unknown")
                        })
                        logger.info("Successfully queued prospect: %s", email_addr)
                    else:
                        logger.error("Failed to add prospect %s: %s", email_addr, contact_resp.text)
                except Exception as e:
                    logger.error("Exception adding prospect %s: %s", email_addr, e)

        logger.info("Outreach setup complete. Campaign ID: %s. Prospects queued: %d.", campaign_id, len(prospects_created))
        return {
            "campaign_id": campaign_id,
            "prospects": prospects_created
        }

    async def trigger_cron_job(self) -> dict[str, Any]:
        """Trigger the Next.js API cron job to process pending emails and check inbox replies."""
        logger.info("Triggering outreach cron job in Next.js Outbound App...")
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                resp = await client.post(
                    f"{self.settings.outbound_email_agent_url}/api/cron/process-outreach"
                )
                resp.raise_for_status()
                result = resp.json()
                logger.info("Cron job completed. Sent: %d, Replies Logged: %d.", result.get("sentCount", 0), result.get("repliesCount", 0))
                return result
            except Exception as e:
                logger.error("Failed to trigger Next.js cron job: %s", e)
                return {"success": False, "error": str(e)}
