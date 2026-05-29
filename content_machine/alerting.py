"""Alerting system for pipeline failures and health issues.

Supports Slack, email, and webhook notifications.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import asyncio

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Alert notification."""
    level: str  # "info", "warning", "error", "critical"
    title: str
    message: str
    timestamp: str
    run_id: Optional[str] = None
    function_name: Optional[str] = None
    details: Optional[dict] = None


class AlertManager:
    """Manages alert notifications across multiple channels."""
    
    def __init__(self):
        self.slack_webhook: Optional[str] = os.getenv("ALERT_SLACK_WEBHOOK")
        self.email_webhook: Optional[str] = os.getenv("ALERT_EMAIL_WEBHOOK")
        self.discord_webhook: Optional[str] = os.getenv("ALERT_DISCORD_WEBHOOK")
        self.custom_webhook: Optional[str] = os.getenv("ALERT_CUSTOM_WEBHOOK")
        self.min_level: str = os.getenv("ALERT_MIN_LEVEL", "warning")
        
        self._level_priority = {
            "info": 0,
            "warning": 1,
            "error": 2,
            "critical": 3,
        }
    
    def _should_alert(self, level: str) -> bool:
        """Check if alert level meets minimum threshold."""
        return self._level_priority.get(level, 0) >= self._level_priority.get(self.min_level, 1)
    
    async def send_alert(
        self,
        level: str,
        title: str,
        message: str,
        run_id: Optional[str] = None,
        function_name: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> bool:
        """Send alert to all configured channels."""
        if not self._should_alert(level):
            return True
        
        alert = Alert(
            level=level,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
            function_name=function_name,
            details=details,
        )
        
        tasks = []
        
        if self.slack_webhook:
            tasks.append(self._send_slack(alert))
        if self.email_webhook:
            tasks.append(self._send_email(alert))
        if self.discord_webhook:
            tasks.append(self._send_discord(alert))
        if self.custom_webhook:
            tasks.append(self._send_custom(alert))
        
        if not tasks:
            # No channels configured, just log
            logger.warning(f"ALERT ({level}): {title} - {message}")
            return True
        
        # Send to all channels
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = all(isinstance(r, bool) and r for r in results)
        
        if success:
            logger.info(f"Alert sent: {title}")
        else:
            logger.error(f"Failed to send some alerts: {results}")
        
        return success
    
    async def _send_slack(self, alert: Alert) -> bool:
        """Send alert to Slack webhook."""
        try:
            from aiohttp import ClientSession
            
            color_map = {
                "info": "#36a64f",
                "warning": "#ff9900",
                "error": "#ff0000",
                "critical": "#990000",
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.level, "#999999"),
                    "title": f"[{alert.level.upper()}] {alert.title}",
                    "text": alert.message,
                    "fields": [],
                    "footer": "Content Machine",
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }]
            }
            
            if alert.run_id:
                payload["attachments"][0]["fields"].append({
                    "title": "Run ID",
                    "value": alert.run_id,
                    "short": True,
                })
            
            if alert.function_name:
                payload["attachments"][0]["fields"].append({
                    "title": "Function",
                    "value": alert.function_name,
                    "short": True,
                })
            
            if alert.details:
                payload["attachments"][0]["fields"].append({
                    "title": "Details",
                    "value": json.dumps(alert.details, indent=2)[:1000],
                    "short": False,
                })
            
            async with ClientSession() as session:
                async with session.post(
                    self.slack_webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    async def _send_discord(self, alert: Alert) -> bool:
        """Send alert to Discord webhook."""
        try:
            from aiohttp import ClientSession
            
            color_map = {
                "info": 3066993,      # Green
                "warning": 16776960,  # Yellow
                "error": 16711680,    # Red
                "critical": 10038562, # Dark Red
            }
            
            embed = {
                "title": f"[{alert.level.upper()}] {alert.title}",
                "description": alert.message,
                "color": color_map.get(alert.level, 0),
                "timestamp": alert.timestamp,
                "fields": [],
            }
            
            if alert.run_id:
                embed["fields"].append({
                    "name": "Run ID",
                    "value": alert.run_id,
                    "inline": True,
                })
            
            if alert.function_name:
                embed["fields"].append({
                    "name": "Function",
                    "value": alert.function_name,
                    "inline": True,
                })
            
            payload = {"embeds": [embed]}
            
            async with ClientSession() as session:
                async with session.post(
                    self.discord_webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    return response.status == 204
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
    
    async def _send_email(self, alert: Alert) -> bool:
        """Send alert via email webhook (e.g., Zapier, Make)."""
        try:
            from aiohttp import ClientSession
            
            payload = {
                "subject": f"[Content Machine] [{alert.level.upper()}] {alert.title}",
                "body": f"""
{alert.message}

---
Timestamp: {alert.timestamp}
Level: {alert.level}
Run ID: {alert.run_id or "N/A"}
Function: {alert.function_name or "N/A"}
                """.strip(),
                "details": alert.details,
            }
            
            async with ClientSession() as session:
                async with session.post(
                    self.email_webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    return response.status in (200, 201, 202)
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    async def _send_custom(self, alert: Alert) -> bool:
        """Send alert to custom webhook."""
        try:
            from aiohttp import ClientSession
            
            payload = {
                "level": alert.level,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp,
                "run_id": alert.run_id,
                "function_name": alert.function_name,
                "details": alert.details,
                "source": "content_machine",
            }
            
            async with ClientSession() as session:
                async with session.post(
                    self.custom_webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    return response.status in (200, 201, 202)
        except Exception as e:
            logger.error(f"Failed to send custom alert: {e}")
            return False
    
    # Convenience methods
    async def info(self, title: str, message: str, **kwargs):
        return await self.send_alert("info", title, message, **kwargs)
    
    async def warning(self, title: str, message: str, **kwargs):
        return await self.send_alert("warning", title, message, **kwargs)
    
    async def error(self, title: str, message: str, **kwargs):
        return await self.send_alert("error", title, message, **kwargs)
    
    async def critical(self, title: str, message: str, **kwargs):
        return await self.send_alert("critical", title, message, **kwargs)


# Singleton
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# Convenience function for quick alerts
async def alert(level: str, title: str, message: str, **kwargs) -> bool:
    """Send an alert using the global alert manager."""
    return await get_alert_manager().send_alert(level, title, message, **kwargs)
