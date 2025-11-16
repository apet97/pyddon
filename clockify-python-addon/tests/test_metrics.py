from app.metrics import MetricsRegistry


def test_metrics_registry_render_includes_counters():
    registry = MetricsRegistry()
    registry.record_api_call(True)
    registry.record_api_call(False)
    registry.record_webhook_event("NEW_TIME_ENTRY")
    registry.record_webhook_event("NEW_TIME_ENTRY")
    registry.record_lifecycle_event("installed", success=True)
    registry.record_lifecycle_event("installed", success=False)
    registry.record_bootstrap_job(success=True)
    registry.record_bootstrap_job(success=False)
    registry.record_rate_limit_wait(0.25)

    output = registry.render()

    assert "clockify_api_calls_total 2" in output
    assert 'clockify_webhook_events_total{event_type="new_time_entry"} 2' in output
    assert 'clockify_lifecycle_events_total{event="installed"} 2' in output
    assert 'clockify_lifecycle_events_failed_total{event="installed"} 1' in output
    assert "clockify_bootstrap_jobs_total 2" in output
    assert "clockify_bootstrap_jobs_failed_total 1" in output
    assert "clockify_rate_limit_events_total 1" in output
    assert "clockify_rate_limit_wait_seconds_total 0.25" in output
