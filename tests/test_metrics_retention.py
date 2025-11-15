"""Tests for metrics and retention utilities."""
import pytest
from datetime import datetime, timedelta, timezone

from clockify_core.metrics import MetricsCollector, get_metrics_collector, increment_counter, set_gauge
from clockify_core.retention import cleanup_old_records


def test_metrics_collector_counters():
    """Test counter increments."""
    collector = MetricsCollector()
    
    collector.increment("test.counter")
    collector.increment("test.counter")
    collector.increment("test.counter", 5)
    
    metrics = collector.get_metrics()
    assert metrics["counters"]["test.counter"] == 7


def test_metrics_collector_gauges():
    """Test gauge values."""
    collector = MetricsCollector()
    
    collector.set_gauge("test.gauge", 42.5)
    collector.set_gauge("test.gauge", 100.0)  # Overwrite
    
    metrics = collector.get_metrics()
    assert metrics["gauges"]["test.gauge"] == 100.0


def test_metrics_collector_prometheus_format():
    """Test Prometheus format output."""
    collector = MetricsCollector()
    
    collector.increment("webhooks_received_total", 5)
    collector.set_gauge("active_connections", 3.0)
    
    output = collector.get_prometheus_format()
    
    assert "webhooks_received_total 5" in output
    assert "active_connections 3" in output
    assert "# HELP" in output
    assert "# TYPE" in output


def test_global_metrics_functions():
    """Test global metrics functions."""
    # Note: This uses the global singleton, so it might interfere with other tests
    # In production, you'd want to reset the collector between tests
    
    increment_counter("test.global.counter")
    set_gauge("test.global.gauge", 42.0)
    
    collector = get_metrics_collector()
    metrics = collector.get_metrics()
    
    # Check that values were set (might include values from other tests)
    assert "test.global.counter" in metrics["counters"]
    assert "test.global.gauge" in metrics["gauges"]


def test_metrics_collector_uptime():
    """Test uptime metric."""
    collector = MetricsCollector()
    
    metrics = collector.get_metrics()
    
    assert "uptime_seconds" in metrics
    assert metrics["uptime_seconds"] >= 0


def test_metrics_collector_thread_safety():
    """Test that metrics collector is thread-safe."""
    import threading
    
    collector = MetricsCollector()
    
    def increment_many():
        for _ in range(100):
            collector.increment("thread.test")
    
    threads = [threading.Thread(target=increment_many) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    metrics = collector.get_metrics()
    # Should be exactly 1000 if thread-safe
    assert metrics["counters"]["thread.test"] == 1000
