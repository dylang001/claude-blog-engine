import base64

from content_machine.config import Settings, SiteConfig
from content_machine.dataforseo_auth import dataforseo_headers


def test_dataforseo_headers_prefer_base64(tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(),
        dataforseo_login="ignored",
        dataforseo_password="ignored",
        dataforseo_auth_base64="already-encoded",
    )

    assert dataforseo_headers(settings)["Authorization"] == "Basic already-encoded"


def test_dataforseo_headers_encode_login_password(tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(),
        dataforseo_login="user",
        dataforseo_password="pass",
    )

    expected = base64.b64encode(b"user:pass").decode()
    assert dataforseo_headers(settings)["Authorization"] == f"Basic {expected}"
