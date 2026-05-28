from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
from content_machine.config import Settings
from content_machine.blogger import BloggerClient

@pytest.fixture
def mock_settings():
    return Settings(
        root_dir=None,
        data_dir=None,
        state_db=None,
        site=None,
        blogger_blog_id="123456789"
    )

@pytest.mark.asyncio
@patch("content_machine.blogger.get_google_credentials")
@patch("content_machine.blogger.build")
async def test_blogger_client_publish_post(mock_build, mock_get_creds, mock_settings):
    # Setup mocks
    mock_credentials = MagicMock()
    mock_get_creds.return_value = (mock_credentials, "oauth_user")
    
    mock_service = MagicMock()
    mock_posts = MagicMock()
    mock_insert = MagicMock()
    mock_execute = MagicMock()
    
    mock_build.return_value = mock_service
    mock_service.posts.return_value = mock_posts
    mock_posts.insert.return_value = mock_insert
    mock_insert.execute.return_value = {"id": "post-abc", "url": "https://blogger.com/post-abc"}
    
    client = BloggerClient(mock_settings)
    result = await client.publish_post("Test Title", "<p>Test Content</p>", is_draft=True)
    
    # Assertions
    mock_get_creds.assert_called_once_with(mock_settings, ["https://www.googleapis.com/auth/blogger"])
    mock_build.assert_called_once_with("blogger", "v3", credentials=mock_credentials, cache_discovery=False)
    mock_service.posts.assert_called_once()
    mock_posts.insert.assert_called_once_with(
        blogId="123456789",
        body={"kind": "blogger#post", "title": "Test Title", "content": "<p>Test Content</p>"},
        isDraft=True
    )
    assert result["id"] == "post-abc"
    assert result["url"] == "https://blogger.com/post-abc"

@pytest.mark.asyncio
async def test_blogger_client_raises_if_missing_blog_id():
    empty_settings = Settings(
        root_dir=None,
        data_dir=None,
        state_db=None,
        site=None,
        blogger_blog_id=""
    )
    client = BloggerClient(empty_settings)
    with pytest.raises(RuntimeError, match="Blogger blog ID is not configured"):
        await client.publish_post("Test", "<p>Test</p>")
