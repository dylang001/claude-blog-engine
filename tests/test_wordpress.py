from content_machine.config import Settings, SiteConfig
from content_machine.models import GeneratedContent, PublishDecision
from content_machine.wordpress import WordPressClient, _rest_route_url


def test_wordpress_client_builds_yoast_payload(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(),
        wp_base_url="https://example.com",
        wp_username="user",
        wp_app_password="pass",
    )
    client = WordPressClient(settings)
    captured = {}

    class FakeResponse:
        headers = {"content-type": "application/json"}

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": 7, "status": "publish", "link": "https://example.com/post"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, auth=None, json=None, **kwargs):
            captured["url"] = url
            captured["method"] = method
            captured["auth"] = auth
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("content_machine.wordpress.httpx.AsyncClient", FakeAsyncClient)

    content = GeneratedContent(
        title="SEO Automation",
        slug="seo-automation",
        markdown="# SEO Automation",
        html="<h1>SEO Automation</h1>",
        meta_title="SEO Automation Guide",
        meta_description="A practical guide to SEO automation.",
        focus_keyphrase="seo automation",
        excerpt="A practical guide.",
        tags=["seo"],
        categories=["SEO"],
        schema_json={"@context": "https://schema.org", "@type": "Article"},
    )

    import asyncio

    result = asyncio.run(client.upsert_post(content, PublishDecision.PUBLISH))

    assert result["id"] == 7
    assert captured["json"]["yoast_seo"]["focus_keyphrase"] == "seo automation"
    assert "application/ld+json" in captured["json"]["content"]
    assert "<h1>" not in captured["json"]["content"]


def test_rest_route_url_preserves_params():
    url = _rest_route_url("https://blog.meetlyra.app", "/posts", {"per_page": 1, "context": "edit"})

    assert "rest_route=%2Fwp%2Fv2%2Fposts" in url
    assert "per_page=1" in url
    assert "context=edit" in url


def test_wordpress_client_finds_existing_slug(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(),
        wp_base_url="https://example.com",
        wp_username="user",
        wp_app_password="pass",
    )
    client = WordPressClient(settings)
    captured = {}

    class FakeResponse:
        headers = {"content-type": "application/json"}

        def raise_for_status(self):
            return None

        def json(self):
            return [{"id": 11, "slug": "seo-automation"}]

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, auth=None, params=None, **kwargs):
            captured["method"] = method
            captured["params"] = params
            return FakeResponse()

    monkeypatch.setattr("content_machine.wordpress.httpx.AsyncClient", FakeAsyncClient)

    import asyncio

    result = asyncio.run(client.find_post_by_slug("seo-automation"))

    assert result["id"] == 11
    assert captured["params"]["slug"] == "seo-automation"


def test_upsert_post_uploads_inline_images(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(),
        wp_base_url="https://example.com",
        wp_username="user",
        wp_app_password="pass",
    )
    client = WordPressClient(settings)
    
    dummy_img = tmp_path / "inline-1.png"
    dummy_img.write_bytes(b"dummy image content")
    
    captured = {}
    uploads = []

    class FakeResponse:
        headers = {"content-type": "application/json"}
        def raise_for_status(self):
            return None
        def json(self):
            if "/media" in captured.get("url", ""):
                return {"id": 42, "source_url": "https://example.com/wp-content/uploads/inline-1.png"}
            return {"id": 7}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def request(self, method, url, auth=None, json=None, **kwargs):
            captured["url"] = url
            captured["json"] = json
            if "/media" in url and method == "POST":
                uploads.append(url)
            return FakeResponse()

    monkeypatch.setattr("content_machine.wordpress.httpx.AsyncClient", FakeAsyncClient)

    content = GeneratedContent(
        title="SEO Guide",
        slug="seo-guide",
        markdown="Text.",
        html=f"<p>Check out this chart:</p><p><img src=\"{dummy_img}\" alt=\"My inline chart\" /></p>",
        meta_title="SEO Guide Title",
        meta_description="SEO Guide description",
        focus_keyphrase="seo guide",
        excerpt="Excerpt",
        tags=[],
        categories=[],
        schema_json=None,
    )

    import asyncio
    result = asyncio.run(client.upsert_post(content, PublishDecision.DRAFT))

    assert len(uploads) > 0
    assert "https://example.com/wp-content/uploads/inline-1.png" in captured["json"]["content"]
    assert "alt=\"My inline chart\"" in captured["json"]["content"]
