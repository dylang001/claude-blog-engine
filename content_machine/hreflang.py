from __future__ import annotations

import re
from typing import Any
import httpx


# ISO 639-1 language codes (sample list of standard codes)
VALID_LANGS = {
    "en", "es", "fr", "de", "it", "ja", "zh", "pt", "ru", "ar", "hi", "ko", "nl", "sv", "no", "fi", "da", "pl", "tr"
}

# ISO 3166-1 Alpha-2 country codes (sample list of standard region codes)
VALID_REGIONS = {
    "US", "GB", "CA", "AU", "DE", "FR", "JP", "CN", "BR", "ES", "IT", "IN", "KR", "MX", "NL", "SE", "NO", "DK"
}


class HreflangAuditor:
    def __init__(self):
        pass

    def validate_code(self, code: str) -> tuple[bool, str]:
        """Validates language/region code. Returns (is_valid, explanation)."""
        if not code:
            return False, "Empty code"
        if code.lower() == "x-default":
            return True, "Valid default fallback"

        parts = code.split("-")
        lang = parts[0].lower()
        
        # Check language
        if lang not in VALID_LANGS:
            return False, f"Invalid language code '{lang}'. Must be ISO 639-1 two-letter code (e.g., 'ja' instead of 'jp')."

        if len(parts) > 1:
            region = parts[1].upper()
            if region not in VALID_REGIONS:
                return False, f"Invalid region code '{region}'. Must be ISO 3166-1 Alpha-2 code (e.g., 'GB' instead of 'uk')."
            return True, f"Valid locale: language '{lang}', region '{region}'"

        return True, f"Valid language code '{lang}'"

    async def audit_url(self, url: str) -> dict[str, Any]:
        """Audits the hreflang tags found at a live URL."""
        report = {
            "url": url,
            "scanned_at": "",
            "tags_found": [],
            "issues": [],
            "warnings": [],
            "status": "ok",
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url)
            
            html = resp.text
            report["status_code"] = resp.status_code
            
            # Find all <link rel="alternate" ... /> tags
            pattern = re.compile(r'<link\s+[^>]*rel=["\']alternate["\'][^>]*>', re.IGNORECASE)
            tags = pattern.findall(html)
            
            parsed_tags = []
            for tag in tags:
                href_match = re.search(r'href=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                hreflang_match = re.search(r'hreflang=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if href_match and hreflang_match:
                    parsed_tags.append({
                        "tag": tag,
                        "href": href_match.group(1),
                        "hreflang": hreflang_match.group(1)
                    })

            report["tags_found"] = parsed_tags
            
            # 1. Check self-referencing tag
            self_ref_found = False
            for t in parsed_tags:
                # Basic matching (ignoring query parameters and trailing slash differences)
                t_href = t["href"].rstrip("/")
                u_url = url.rstrip("/")
                if t_href == u_url:
                    self_ref_found = True
                    break
            
            if parsed_tags and not self_ref_found:
                report["issues"].append("Missing self-referencing tag. Every page must contain a tag pointing to itself.")

            # 2. Check language/region code validity
            for t in parsed_tags:
                lang_ok, desc = self.validate_code(t["hreflang"])
                if not lang_ok:
                    report["issues"].append(f"Invalid hreflang attribute value '{t['hreflang']}': {desc}")

            # 3. Check for x-default
            has_x_default = any(t["hreflang"].lower() == "x-default" for t in parsed_tags)
            if parsed_tags and not has_x_default:
                report["warnings"].append("Missing x-default tag. A fallback page is highly recommended for unmatched locales.")

            # 4. Check HTTP/HTTPS protocol consistency
            protocols = {t["href"].split("://")[0].lower() for t in parsed_tags if "://" in t["href"]}
            if len(protocols) > 1:
                report["issues"].append(f"Protocol inconsistency detected: mixed {sorted(list(protocols))} protocols.")

            if report["issues"]:
                report["status"] = "error"
            elif report["warnings"]:
                report["status"] = "warning"

        except Exception as exc:
            report["status"] = "error"
            report["error"] = str(exc)
            report["issues"].append(f"Failed to scan URL: {exc}")

        return report

    def generate_tags(self, mapping: dict[str, str], default_url: str | None = None) -> dict[str, Any]:
        """
        Generates HTML link tags, HTTP Headers, and XML sitemap snippet for a mapping of locales to URLs.
        
        Args:
            mapping: e.g. {"en-US": "https://example.com/page", "fr": "https://example.com/fr/page"}
            default_url: Fallback URL for x-default
        """
        html_tags = []
        http_headers = []
        sitemap_urls = []

        # Add x-default if provided
        all_mappings = dict(mapping)
        if default_url:
            all_mappings["x-default"] = default_url

        # Check self-referencing logic and build representations
        for lang, href in all_mappings.items():
            html_tags.append(f'<link rel="alternate" hreflang="{lang}" href="{href}" />')
            http_headers.append(f'<{href}>; rel="alternate"; hreflang="{lang}"')

        # XML sitemap entry representation
        sitemap_urls.append("<url>")
        # Example for the first URL in sitemap
        first_url = next(iter(mapping.values())) if mapping else "https://example.com/"
        sitemap_urls.append(f"  <loc>{first_url}</loc>")
        for lang, href in all_mappings.items():
            sitemap_urls.append(f'  <xhtml:link rel="alternate" hreflang="{lang}" href="{href}" />')
        sitemap_urls.append("</url>")

        return {
            "html": "\n".join(html_tags),
            "http_header": "Link: " + ", ".join(http_headers),
            "sitemap_xml": "\n".join(sitemap_urls),
        }
