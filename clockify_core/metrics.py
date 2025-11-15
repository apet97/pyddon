"""Metrics collection for Clockify add-ons."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict
import threading


class MetricsCollector:
    """Thread-safe metrics collector for add-on observability.
    
    Collects counters and gauges for:
    - Webhooks received (by type)
    - Flows executed (by status)
    - API calls made
    - Errors encountered
    """
    
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._start_time = datetime.now(timezone.utc)
    
    def increment(self, metric: str, value: int = 1) -> None:
        """Increment a counter metric."""
        with self._lock:
            self._counters[metric] += value
    
    def set_gauge(self, metric: str, value: float) -> None:
        """Set a gauge metric to a specific value."""
        with self._lock:
            self._gauges[metric] = value
    
    def get_metrics(self) -> Dict[str, any]:
        """Get all metrics as a dictionary.
        
        Returns:
            Dictionary with counters and gauges
        """
        with self._lock:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            return {
                "uptime_seconds": uptime,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges)
            }
    
    def get_prometheus_format(self) -> str:
        """Get metrics in Prometheus text format.
        
        Returns:
            Metrics formatted for Prometheus scraping
        """
        lines = []
        
        with self._lock:
            # Uptime
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            lines.append(f"# HELP addon_uptime_seconds Time since addon started")
            lines.append(f"# TYPE addon_uptime_seconds gauge")
            lines.append(f"addon_uptime_seconds {uptime}")
            lines.append("")
            
            # Counters
            for name, value in sorted(self._counters.items()):
                # Convert metric name to prometheus format
                prom_name = name.replace(".", "_").replace("-", "_")
                lines.append(f"# HELP {prom_name} Counter for {name}")
                lines.append(f"# TYPE {prom_name} counter")
                lines.append(f"{prom_name} {value}")
                lines.append("")
            
            # Gauges
            for name, value in sorted(self._gauges.items()):
                prom_name = name.replace(".", "_").replace("-", "_")
                lines.append(f"# HELP {prom_name} Gauge for {name}")
                lines.append(f"# TYPE {prom_name} gauge")
                lines.append(f"{prom_name} {value}")
                lines.append("")
        
        return "\n".join(lines)


# Global metrics instance
_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics


def increment_counter(metric: str, value: int = 1) -> None:
    """Increment a counter metric."""
    _metrics.increment(metric, value)


def set_gauge(metric: str, value: float) -> None:
    """Set a gauge metric."""
    _metrics.set_gauge(metric, value)
