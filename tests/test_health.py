"""Tests for the health monitoring system."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from content_machine.health import HeartbeatEntry, SchedulerHealthMonitor


class TestHeartbeatEntry:
    """Test the HeartbeatEntry dataclass."""
    
    def test_basic_creation(self):
        entry = HeartbeatEntry(
            timestamp="2024-01-01T12:00:00+00:00",
            scheduled_time="2024-01-01T12:00:00+00:00",
            function_name="test_func",
            status="completed",
        )
        assert entry.function_name == "test_func"
        assert entry.status == "completed"
        assert entry.error_message is None


class TestSchedulerHealthMonitor:
    """Test the SchedulerHealthMonitor class."""
    
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)
    
    @pytest.fixture
    def monitor(self, temp_dir):
        return SchedulerHealthMonitor(temp_dir)
    
    def test_record_heartbeat(self, monitor, temp_dir):
        """Test recording a heartbeat entry."""
        monitor.record_heartbeat("test_func", "started", run_id="run_123")
        
        # Check file was created
        assert monitor.heartbeat_file.exists()
        
        # Read and verify
        with open(monitor.heartbeat_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        
        data = json.loads(lines[0])
        assert data["function_name"] == "test_func"
        assert data["status"] == "started"
        assert data["run_id"] == "run_123"
    
    def test_multiple_heartbeats(self, monitor):
        """Test recording multiple heartbeats."""
        monitor.record_heartbeat("func1", "started")
        monitor.record_heartbeat("func2", "completed")
        monitor.record_heartbeat("func1", "failed", error_message="Error!")
        
        with open(monitor.heartbeat_file) as f:
            lines = f.readlines()
        assert len(lines) == 3
    
    def test_get_recent_heartbeats(self, monitor):
        """Test retrieving recent heartbeats."""
        # Record some entries
        monitor.record_heartbeat("func1", "started")
        monitor.record_heartbeat("func1", "completed")
        monitor.record_heartbeat("func2", "started")
        
        # Get all
        recent = monitor.get_recent_heartbeats(hours=1)
        assert len(recent) == 3
        
        # Filter by function
        func1_only = monitor.get_recent_heartbeats(function_name="func1", hours=1)
        assert len(func1_only) == 2
    
    def test_check_health_healthy(self, monitor):
        """Test health check when function is healthy."""
        # Record a recent success
        monitor.record_heartbeat("test_func", "completed", run_id="run_1")
        
        health = monitor.check_health("test_func", expected_schedule_minutes=60)
        
        assert health["status"] == "healthy"
        assert health["function"] == "test_func"
        assert health["missed_runs"] == 0
    
    def test_check_health_critical_no_recent(self, monitor):
        """Test health check when no recent runs."""
        # Create old entry manually
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        entry = HeartbeatEntry(
            timestamp=old_time,
            scheduled_time=old_time,
            function_name="test_func",
            status="completed",
            run_id="old_run",
        )
        with open(monitor.heartbeat_file, "a") as f:
            f.write(json.dumps(entry.__dict__) + "\n")
        
        health = monitor.check_health("test_func", expected_schedule_minutes=60)
        
        assert health["status"] == "critical"
        assert health["function"] == "test_func"
    
    def test_check_health_with_failures(self, monitor):
        """Test health check with failed runs."""
        monitor.record_heartbeat("test_func", "failed", error_message="Error!")
        monitor.record_heartbeat("test_func", "completed")
        
        health = monitor.check_health("test_func")
        
        assert health["status"] == "healthy"  # Last was success
        assert health["last_failure"] is not None
    
    def test_check_health_unknown_no_history(self, monitor):
        """Test health check when no history exists."""
        health = monitor.check_health("unknown_func")
        
        assert health["status"] == "unknown"
        assert health["function"] == "unknown_func"
    
    def test_get_all_health_status(self, monitor):
        """Test getting health status for all functions."""
        monitor.record_heartbeat("func1", "completed")
        monitor.record_heartbeat("func2", "failed")
        
        all_health = monitor.get_all_health_status()
        
        assert "func1" in all_health
        assert "func2" in all_health
        assert "_system" in all_health
    
    def test_heartbeat_with_duration(self, monitor):
        """Test recording heartbeat with duration."""
        monitor.record_heartbeat(
            "test_func",
            "completed",
            run_id="run_1",
            duration_ms=5000,
        )
        
        with open(monitor.heartbeat_file) as f:
            data = json.loads(f.readline())
        
        assert data["duration_ms"] == 5000
    
    def test_heartbeat_with_error(self, monitor):
        """Test recording failed heartbeat with error message."""
        monitor.record_heartbeat(
            "test_func",
            "failed",
            error_message="Connection timeout",
            run_id="run_1",
        )
        
        with open(monitor.heartbeat_file) as f:
            data = json.loads(f.readline())
        
        assert data["status"] == "failed"
        assert data["error_message"] == "Connection timeout"
