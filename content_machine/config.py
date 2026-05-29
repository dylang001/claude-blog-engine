from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional for tests
    load_dotenv = None

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SiteConfig:
    brand_name: str = "Your Brand"
    site_url: str = ""
    audience: str = ""
    products: list[str] = field(default_factory=list)
    voice: str = ""
    competitors: list[str] = field(default_factory=list)
    forbidden_topics: list[str] = field(default_factory=list)
    cta: str = ""
    timezone: str = "Africa/Johannesburg"
    publishing_slots: list[str] = field(default_factory=lambda: ["09:00", "15:00"])
    min_publish_score: float = 85.0
    min_draft_score: float = 70.0
    seo_plugin: str = "yoast"
    enable_backlinks_api: bool = True
    enable_gmb_api: bool = False


_DEFAULT_BANANA_STYLE_PROMPT = (
    "Premium editorial tech photography: clean desk setup with a MacBook showing SaaS dashboards, "
    "realistic office or studio lighting, shallow depth of field, modern millennial workspace vibe, "
    "warm aesthetic tones, high-resolution, no logos, and no readable text."
)


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    data_dir: Path
    state_db: Path
    site: SiteConfig
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    writer_provider: str = "gemini"
    gemini_model: str = "gemini-2.5-pro"
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_auth_base64: str = ""
    wp_base_url: str = ""
    wp_username: str = ""
    wp_app_password: str = ""
    google_service_account_json: str = ""
    google_oauth_client_secrets_json: str = ""
    google_oauth_token_json: str = ""
    google_ads_developer_token: str = ""
    google_ads_customer_id: str = ""
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
    pagespeed_api_key: str = ""
    ga4_property_id: str = ""
    gsc_site_url: str = ""
    gemini_api_key: str = ""
    banana_model: str = "gemini-3.1-flash-image-preview"
    banana_aspect_ratio: str = "16:9"
    banana_resolution: str = "2K"
    banana_style_prompt: str = _DEFAULT_BANANA_STYLE_PROMPT
    indexnow_key: str = ""
    indexnow_key_location: str = ""
    indexnow_engines: list[str] = field(default_factory=lambda: ["bing", "yandex", "seznam", "indexnow"])
    dry_run_default: bool = True
    firecrawl_api_key: str = ""
    tavily_api_key: str = ""
    state_store_type: str = "sqlite"
    supermemory_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    open_seo_url: str = ""  # URL of self-hosted open-seo Cloud Run service
    blogger_blog_id: str = ""


    def missing_required(self) -> list[str]:
        required = {
            "WP_BASE_URL": self.wp_base_url,
            "WP_USERNAME": self.wp_username,
            "WP_APP_PASSWORD": self.wp_app_password,
            "GOOGLE_SERVICE_ACCOUNT_JSON": self.google_service_account_json,
            "GA4_PROPERTY_ID": self.ga4_property_id,
            "GSC_SITE_URL": self.gsc_site_url,
        }
        if self.writer_provider == "gemini":
            required["GEMINI_API_KEY"] = self.gemini_api_key
        else:
            required["ANTHROPIC_API_KEY"] = self.anthropic_api_key

        missing = [name for name, value in required.items() if not value]
        if not self.dataforseo_auth_base64 and not (self.dataforseo_login and self.dataforseo_password):
            missing.append("DATAFORSEO_AUTH_BASE64 or DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD")
        return missing


def _load_site_config(path: Path) -> SiteConfig:
    if not path.exists():
        return SiteConfig()

    raw: dict[str, Any]
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"} and yaml:
        raw = yaml.safe_load(text) or {}
    else:
        raw = json.loads(text)
    return SiteConfig(
        brand_name=raw.get("brand_name", "Your Brand"),
        site_url=raw.get("site_url", ""),
        audience=raw.get("audience", ""),
        products=list(raw.get("products", [])),
        voice=raw.get("voice", ""),
        competitors=list(raw.get("competitors", [])),
        forbidden_topics=list(raw.get("forbidden_topics", [])),
        cta=raw.get("cta", ""),
        timezone=raw.get("timezone", "Africa/Johannesburg"),
        publishing_slots=list(raw.get("publishing_slots", ["09:00", "15:00"])),
        min_publish_score=float(raw.get("min_publish_score", 85)),
        min_draft_score=float(raw.get("min_draft_score", 70)),
        seo_plugin=raw.get("seo_plugin", "yoast"),
    )


def load_settings(root_dir: Path | None = None, config_path: Path | None = None) -> Settings:
    root = root_dir or ROOT
    if load_dotenv:
        load_dotenv(root / ".env", override=True)

    data_dir = Path(os.getenv("CONTENT_MACHINE_DATA_DIR", root / ".content-machine"))
    site_path = config_path or Path(os.getenv("CONTENT_MACHINE_SITE_CONFIG", root / "config" / "site.yaml"))
    state_db = Path(os.getenv("CONTENT_MACHINE_DB", data_dir / "content_machine.db"))

    return Settings(
        root_dir=root,
        data_dir=data_dir,
        state_db=state_db,
        site=_load_site_config(site_path),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        writer_provider=os.getenv("WRITER_PROVIDER", "gemini"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        dataforseo_login=os.getenv("DATAFORSEO_LOGIN", ""),
        dataforseo_password=os.getenv("DATAFORSEO_PASSWORD", ""),
        dataforseo_auth_base64=os.getenv("DATAFORSEO_AUTH_BASE64", os.getenv("DATAFORSEO_BASE_64", "")),
        wp_base_url=os.getenv("WP_BASE_URL", os.getenv("WORDPRESS_URL", "")),
        wp_username=os.getenv("WP_USERNAME", os.getenv("WORDPRESS_USERNAME", "")),
        wp_app_password=os.getenv("WP_APP_PASSWORD", os.getenv("WORDPRESS_APP_PASSWORD", "")),
        google_service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        google_oauth_client_secrets_json=os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS_JSON", ""),
        google_oauth_token_json=os.getenv("GOOGLE_OAUTH_TOKEN_JSON", str(data_dir / "google-oauth-token.json")),
        google_ads_developer_token=os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
        google_ads_customer_id=os.getenv("GOOGLE_ADS_CUSTOMER_ID", ""),
        google_ads_client_id=os.getenv("GOOGLE_ADS_CLIENT_ID", ""),
        google_ads_client_secret=os.getenv("GOOGLE_ADS_CLIENT_SECRET", ""),
        google_ads_refresh_token=os.getenv("GOOGLE_ADS_REFRESH_TOKEN", ""),
        pagespeed_api_key=os.getenv("PAGESPEED_API_KEY", os.getenv("GOOGLE_PAGESPEED_API_KEY", "")),
        ga4_property_id=os.getenv("GA4_PROPERTY_ID", ""),
        gsc_site_url=os.getenv("GSC_SITE_URL", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_AI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))),
        banana_model=os.getenv("BANANA_MODEL", "gemini-3.1-flash-image-preview"),
        banana_aspect_ratio=os.getenv("BANANA_ASPECT_RATIO", "16:9"),
        banana_resolution=os.getenv("BANANA_RESOLUTION", "2K"),
        banana_style_prompt=os.getenv("BANANA_STYLE_PROMPT", _DEFAULT_BANANA_STYLE_PROMPT),
        indexnow_key=os.getenv("INDEXNOW_KEY", ""),
        indexnow_key_location=os.getenv("INDEXNOW_KEY_LOCATION", ""),
        indexnow_engines=[part.strip() for part in os.getenv("INDEXNOW_ENGINES", "bing,yandex,seznam,indexnow").split(",") if part.strip()],
        dry_run_default=os.getenv("CONTENT_MACHINE_DRY_RUN", "true").lower() != "false",
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        state_store_type=os.getenv("STATE_STORE_TYPE", "sqlite"),
        supermemory_api_key=os.getenv("SUPERMEMORY_API_KEY", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""),
        smtp_to=os.getenv("SMTP_TO", ""),
        open_seo_url=os.getenv("OPEN_SEO_URL", ""),
        blogger_blog_id=os.getenv("BLOGGER_BLOG_ID", ""),
    )
