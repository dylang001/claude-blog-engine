"""Health Dashboard for Content Machine.

Simple Flask app displaying system health, recent runs, and circuit breaker status.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template_string

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from content_machine.health import get_health_monitor
from content_machine.circuit_breaker import get_all_circuit_status

app = Flask(__name__)

# Dashboard HTML template
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Content Machine - Health Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            border: 1px solid #475569;
        }
        h1 { font-size: 2rem; margin-bottom: 10px; color: #f8fafc; }
        .subtitle { color: #94a3b8; }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            border: 1px solid #334155;
        }
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }
        .card-title { font-size: 1.1rem; font-weight: 600; color: #f8fafc; }
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-healthy { background: #22c55e; color: #052e16; }
        .status-warning { background: #f59e0b; color: #451a03; }
        .status-critical { background: #ef4444; color: #450a0a; }
        .status-unknown { background: #6b7280; color: #f3f4f6; }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #334155;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #94a3b8; }
        .metric-value { font-weight: 600; color: #f8fafc; }
        .circuit-closed { color: #22c55e; }
        .circuit-open { color: #ef4444; }
        .circuit-half { color: #f59e0b; }
        .refresh-bar {
            background: #0f172a;
            padding: 10px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .refresh-btn {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .refresh-btn:hover { background: #2563eb; }
        .timestamp { color: #64748b; font-size: 0.9rem; }
        .recent-runs {
            max-height: 400px;
            overflow-y: auto;
        }
        .run-item {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            background: #0f172a;
            border-left: 4px solid;
        }
        .run-success { border-left-color: #22c55e; }
        .run-failed { border-left-color: #ef4444; }
        .run-started { border-left-color: #3b82f6; }
        .run-time { font-size: 0.8rem; color: #64748b; }
        .run-status { font-weight: 600; }
        @media (max-width: 768px) {
            .status-grid { grid-template-columns: 1fr; }
            h1 { font-size: 1.5rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Content Machine</h1>
            <p class="subtitle">Real-time health monitoring dashboard</p>
        </header>
        
        <div class="refresh-bar">
            <span class="timestamp">Last updated: {{ timestamp }}</span>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        </div>
        
        <div class="status-grid">
            <!-- System Status -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">System Status</span>
                    <span class="status-badge status-{{ system.status }}">{{ system.status.upper() }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Healthy Functions</span>
                    <span class="metric-value">{{ system.healthy_count }}/{{ system.total_count }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Runs (24h)</span>
                    <span class="metric-value">{{ system.total_runs }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Failed Runs (24h)</span>
                    <span class="metric-value">{{ system.failed_runs }}</span>
                </div>
            </div>
            
            <!-- Circuit Breakers -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Circuit Breakers</span>
                </div>
                {% for name, cb in circuits.items() %}
                <div class="metric">
                    <span class="metric-label">{{ name }}</span>
                    <span class="metric-value circuit-{{ cb.state }}">{{ cb.state.upper() }}</span>
                </div>
                {% endfor %}
            </div>
            
            <!-- Function Status -->
            {% for func_name, func in functions.items() %}
            <div class="card">
                <div class="card-header">
                    <span class="card-title">{{ func_name.replace('_', ' ').title() }}</span>
                    <span class="status-badge status-{{ func.status }}">{{ func.status.upper() }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Success</span>
                    <span class="metric-value">{{ func.last_success or 'Never' }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Run</span>
                    <span class="metric-value">{{ func.last_run or 'Never' }}</span>
                </div>
                {% if func.missed_runs %}
                <div class="metric">
                    <span class="metric-label">Missed Runs</span>
                    <span class="metric-value" style="color: #ef4444;">{{ func.missed_runs }}</span>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="card">
            <div class="card-header">
                <span class="card-title">Recent Runs (Last 24h)</span>
            </div>
            <div class="recent-runs">
                {% for run in recent_runs %}
                <div class="run-item run-{{ run.status }}">
                    <div class="run-time">{{ run.time }}</div>
                    <div><strong>{{ run.function }}</strong> - <span class="run-status">{{ run.status }}</span></div>
                    {% if run.error %}
                    <div style="color: #ef4444; font-size: 0.85rem; margin-top: 4px;">{{ run.error }}</div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
"""


def get_recent_runs_from_health(health_monitor, hours: int = 24) -> list:
    """Get recent runs from health monitor for display."""
    runs = []
    
    try:
        # Get heartbeat file if it exists
        heartbeat_file = health_monitor.heartbeat_file
        if heartbeat_file.exists():
            with open(heartbeat_file) as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        # Parse timestamp
                        ts_str = data.get("timestamp", "")
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            time_ago = (datetime.now(timezone.utc) - ts).total_seconds()
                            if time_ago > hours * 3600:
                                continue
                            
                            time_display = ts.strftime("%Y-%m-%d %H:%M")
                        except:
                            time_display = ts_str
                        
                        runs.append({
                            "time": time_display,
                            "function": data.get("function_name", "unknown"),
                            "status": data.get("status", "unknown"),
                            "error": data.get("error_message", "")[:100] if data.get("error_message") else "",
                        })
                    except:
                        continue
            
            # Sort by time (most recent first)
            runs.reverse()
    except Exception:
        pass
    
    return runs[:50]  # Limit to 50 recent runs


@app.route("/")
def dashboard():
    """Main dashboard page."""
    health = get_health_monitor()
    status = health.get_all_health_status()
    circuits = get_all_circuit_status()
    
    # Format system status
    system = status.get("_system", {})
    total_funcs = system.get("total_functions", 0)
    healthy_funcs = system.get("healthy_functions", 0)
    
    # Count runs
    recent_runs = get_recent_runs_from_health(health, hours=24)
    failed_count = sum(1 for r in recent_runs if r["status"] == "failed")
    
    system_data = {
        "status": system.get("status", "unknown"),
        "healthy_count": healthy_funcs,
        "total_count": total_funcs,
        "total_runs": len(recent_runs),
        "failed_runs": failed_count,
    }
    
    # Format function status (exclude system key)
    functions = {k: v for k, v in status.items() if not k.startswith("_")}
    
    # Format timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    return render_template_string(
        DASHBOARD_TEMPLATE,
        system=system_data,
        functions=functions,
        circuits=circuits,
        recent_runs=recent_runs,
        timestamp=timestamp,
    )


@app.route("/api/health")
def api_health():
    """JSON API endpoint for health status."""
    health = get_health_monitor()
    status = health.get_all_health_status()
    circuits = get_all_circuit_status()
    
    return jsonify({
        "system": status.get("_system", {}),
        "functions": {k: v for k, v in status.items() if not k.startswith("_")},
        "circuit_breakers": circuits,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/runs")
def api_runs():
    """JSON API endpoint for recent runs."""
    health = get_health_monitor()
    runs = get_recent_runs_from_health(health, hours=24)
    
    return jsonify({
        "runs": runs,
        "count": len(runs),
    })


def create_app():
    """Factory function for creating the Flask app."""
    return app


if __name__ == "__main__":
    # Run locally for development
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
