import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.indexnow import IndexNowClient


def _settings(tmp_path):
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(site_url="https://blog.example.com"),
        indexnow_key="abc12345abc12345abc12345abc12345",
        indexnow_key_location="https://blog.example.com/indexnow-key.txt",
        indexnow_engines=["bing"],
    )


@pytest.mark.asyncio
async def test_indexnow_submit_posts_expected_payload(monkeypatch, tmp_path):
    captured = {}

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, endpoint, json=None, headers=None):
            captured["endpoint"] = endpoint
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("content_machine.indexnow.httpx.AsyncClient", FakeClient)

    results = await IndexNowClient(_settings(tmp_path)).submit(["https://blog.example.com/post"])

    assert results[0].success is True
    assert captured["json"]["host"] == "blog.example.com"
    assert captured["json"]["urlList"] == ["https://blog.example.com/post"]
    assert captured["json"]["keyLocation"] == "https://blog.example.com/indexnow-key.txt"


@pytest.mark.asyncio
async def test_indexnow_verify_key_location(monkeypatch, tmp_path):
    class FakeResponse:
        status_code = 200
        text = "abc12345abc12345abc12345abc12345"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("content_machine.indexnow.httpx.AsyncClient", FakeClient)

    result = await IndexNowClient(_settings(tmp_path)).verify_key_location()

    assert result["ok"] is True
    assert result["matches_key"] is True
