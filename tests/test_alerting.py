"""Tests for the alerting system."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from content_machine.alerting import Alert, AlertManager, alert, get_alert_manager

# Check if aiohttp is available
try:
    from aiohttp import ClientSession
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class TestAlert:
    """Test the Alert dataclass."""
    
    def test_alert_creation(self):
        alert = Alert(
            level="error",
            title="Test Alert",
            message="Test message",
            timestamp="2024-01-01T12:00:00+00:00",
            run_id="run_123",
        )
        assert alert.level == "error"
        assert alert.title == "Test Alert"
        assert alert.run_id == "run_123"


class TestAlertManager:
    """Test the AlertManager class."""
    
    @pytest.fixture
    def manager(self):
        # Clear any existing webhook env vars
        for key in ["ALERT_SLACK_WEBHOOK", "ALERT_DISCORD_WEBHOOK", "ALERT_EMAIL_WEBHOOK", "ALERT_CUSTOM_WEBHOOK"]:
            os.environ.pop(key, None)
        return AlertManager()
    
    def test_initialization_no_webhooks(self, manager):
        """Test manager initializes with no webhooks."""
        assert manager.slack_webhook is None
        assert manager.discord_webhook is None
        assert manager.email_webhook is None
        assert manager.custom_webhook is None
    
    def test_initialization_with_webhooks(self):
        """Test manager reads webhooks from env."""
        os.environ["ALERT_SLACK_WEBHOOK"] = "https://slack.test/webhook"
        os.environ["ALERT_DISCORD_WEBHOOK"] = "https://discord.test/webhook"
        
        manager = AlertManager()
        
        assert manager.slack_webhook == "https://slack.test/webhook"
        assert manager.discord_webhook == "https://discord.test/webhook"
    
    def test_should_alert_level_check(self, manager):
        """Test alert level filtering."""
        manager.min_level = "warning"
        
        assert manager._should_alert("error") is True
        assert manager._should_alert("warning") is True
        assert manager._should_alert("info") is False
    
    @pytest.mark.asyncio
    async def test_send_alert_no_webhooks(self, manager, caplog):
        """Test alert when no webhooks configured (logs only)."""
        result = await manager.send_alert(
            level="warning",
            title="Test",
            message="Test message",
        )
        
        assert result is True
        assert "ALERT (warning): Test - Test message" in caplog.text
    
    @pytest.mark.asyncio
    async def test_send_alert_skips_low_level(self, manager):
        """Test that low level alerts are skipped."""
        manager.min_level = "error"
        
        result = await manager.send_alert("info", "Test", "Message")
        
        assert result is True  # Returns true because it was filtered, not failed
    
    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_send_slack_alert(self, mock_session_class, manager):
        """Test sending Slack alert."""
        # Skip if aiohttp not available
        
        manager.slack_webhook = "https://slack.test/webhook"
        
        # Mock the session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = AsyncMock(return_value=mock_response)
        
        mock_session_class.return_value = mock_session
        
        result = await manager.send_alert(
            level="error",
            title="Error Alert",
            message="Something failed",
            run_id="run_123",
        )
        
        assert result is True
    
    @pytest.mark.skipif(not AIOHTTP_AVAILABLE, reason="aiohttp not installed")
    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_send_discord_alert(self, mock_session_class, manager):
        """Test sending Discord alert."""
        # Skip if aiohttp not available
        
        manager.discord_webhook = "https://discord.test/webhook"
        
        mock_response = AsyncMock()
        mock_response.status = 204
        
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = AsyncMock(return_value=mock_response)
        
        mock_session_class.return_value = mock_session
        
        result = await manager.send_alert("error", "Discord Test", "Message")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_convenience_methods(self, manager, caplog):
        """Test convenience methods (info, warning, error, critical)."""
        # Set min_level to info so all alerts are logged
        manager.min_level = "info"
        
        await manager.info("Info Title", "Info message")
        assert "ALERT (info): Info Title - Info message" in caplog.text
        
        await manager.warning("Warning Title", "Warning message")
        assert "ALERT (warning): Warning Title - Warning message" in caplog.text
        
        await manager.error("Error Title", "Error message")
        assert "ALERT (error): Error Title - Error message" in caplog.text
        
        await manager.critical("Critical Title", "Critical message")
        assert "ALERT (critical): Critical Title - Critical message" in caplog.text


class TestAlertManagerSingleton:
    """Test the alert manager singleton."""
    
    def test_get_alert_manager_singleton(self):
        """Test that get_alert_manager returns singleton."""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()
        
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    async def test_global_alert_function(self):
        """Test the global alert() function."""
        with patch.object(AlertManager, "send_alert", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await alert("error", "Test", "Message")
            
            assert result is True
            mock_send.assert_called_once()
