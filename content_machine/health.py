"""Health check and heartbeat system for scheduled runs.

This module provides visibility into whether scheduled jobs are firing correctly
by maintaining a heartbeat log and providing health check endpoints.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatEntry:
    """Record of a scheduled run attempt."""
    timestamp: str
    scheduled_time: str
    function_name: str
    status: str  # "started", "completed", "failed", "missed"
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    run_id: Optional[str] = None


class SchedulerHealthMonitor:
    """Monitors scheduled function health and detects missed runs."""
    
    def __init__(self, data_dir: Path, max_history_days: int = 30):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_file = self.data_dir / "scheduler_heartbeat.jsonl"
        self.max_history_days = max_history_days
        
    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def record_heartbeat(
        self,
        function_name: str,
        status: str,
        scheduled_time: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """Record a heartbeat entry."""
        entry = HeartbeatEntry(
            timestamp=self._now_iso(),
            scheduled_time=scheduled_time or self._now_iso(),
            function_name=function_name,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            run_id=run_id,
        )
        
        # Append to log file
        with open(self.heartbeat_file, "a") as f:
            f.write(json.dumps(asdict(entry), default=str) + "\n")
        
        logger.info(f"Heartbeat recorded: {function_name} - {status}")
    
    def get_recent_heartbeats(
        self,
        function_name: Optional[str] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> list[HeartbeatEntry]:
        """Get recent heartbeat entries."""
        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        entries = []
        
        if not self.heartbeat_file.exists():
            return entries
        
        with open(self.heartbeat_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = HeartbeatEntry(**data)
                    # Filter by time
                    entry_time = datetime.fromisoformat(entry.timestamp).timestamp()
                    if entry_time < cutoff:
                        continue
                    # Filter by function name
                    if function_name and entry.function_name != function_name:
                        continue
                    entries.append(entry)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        
        # Sort by timestamp descending and limit
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        return entries[:limit]
    
    def check_health(
        self,
        function_name: str,
        expected_schedule_minutes: int = 360,  # 6 hours default
    ) -> dict:
        """Check if a scheduled function is healthy.
        
        Returns health status with details about missed runs.
        """
        recent = self.get_recent_heartbeats(function_name, hours=48)
        
        if not recent:
            return {
                "status": "unknown",
                "function": function_name,
                "last_seen": None,
                "message": f"No heartbeat records found for {function_name}",
                "missed_runs": 0,
            }
        
        # Find last successful run
        last_success = None
        last_failure = None
        missed_count = 0
        
        for entry in recent:
            if entry.status == "completed" and not last_success:
                last_success = entry
            if entry.status == "failed" and not last_failure:
                last_failure = entry
            if entry.status == "missed":
                missed_count += 1
        
        if not last_success:
            return {
                "status": "critical",
                "function": function_name,
                "last_seen": recent[0].timestamp if recent else None,
                "message": f"No successful runs found in last 48 hours",
                "missed_runs": missed_count,
            }
        
        # Check if we're within expected schedule
        last_run_time = datetime.fromisoformat(last_success.timestamp)
        minutes_since_last = (datetime.now(timezone.utc) - last_run_time).total_seconds() / 60
        
        if minutes_since_last > expected_schedule_minutes * 2:
            status = "critical"
            message = f"Last successful run was {minutes_since_last:.0f} minutes ago (expected every {expected_schedule_minutes} min)"
        elif minutes_since_last > expected_schedule_minutes * 1.5:
            status = "warning"
            message = f"Last successful run was {minutes_since_last:.0f} minutes ago"
        else:
            status = "healthy"
            message = f"Last run {minutes_since_last:.0f} minutes ago"
        
        return {
            "status": status,
            "function": function_name,
            "last_success": last_success.timestamp,
            "last_run_id": last_success.run_id,
            "message": message,
            "missed_runs": missed_count,
            "last_failure": last_failure.timestamp if last_failure else None,
        }
    
    def get_all_health_status(self) -> dict:
        """Get health status for all monitored functions."""
        functions = set()
        
        # Collect all function names from recent history
        if self.heartbeat_file.exists():
            with open(self.heartbeat_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        functions.add(data.get("function_name"))
                    except (json.JSONDecodeError, TypeError):
                        continue
        
        # Default functions to check if no history
        if not functions:
            functions = {
                "content_machine_worker",
                "daily_email_report",
                "weekly_performance_review",
                "run_now",
            }
        
        results = {}
        for func in functions:
            if func:
                results[func] = self.check_health(func)
        
        # Overall system status
        critical = sum(1 for r in results.values() if r.get("status") == "critical")
        warning = sum(1 for r in results.values() if r.get("status") == "warning")
        
        results["_system"] = {
            "status": "critical" if critical > 0 else "warning" if warning > 0 else "healthy",
            "critical_count": critical,
            "warning_count": warning,
            "checked_at": self._now_iso(),
        }
        
        return results


# Singleton instance for easy access
_health_monitor: Optional[SchedulerHealthMonitor] = None


def get_health_monitor(data_dir: Optional[Path] = None) -> SchedulerHealthMonitor:
    """Get or create the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        if data_dir is None:
            from .config import load_settings
            settings = load_settings()
            data_dir = Path(settings.state_db).parent
        _health_monitor = SchedulerHealthMonitor(data_dir)
    return _health_monitor
