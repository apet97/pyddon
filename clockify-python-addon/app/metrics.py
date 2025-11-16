"""Lightweight in-process metrics registry exposed via /metrics."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from typing import Dict


class MetricsRegistry:
    """Thread-safe counter collection rendered in Prometheus text format."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        """Reset all counters (primarily used by tests)."""
        with self._lock:
            self.api_calls_total = 0
            self.api_calls_failed = 0
            self.rate_limit_events = 0
            self.rate_limit_wait_seconds = 0.0
            self.webhook_events_total = 0
            self.webhook_events_by_type: Dict[str, int] = defaultdict(int)
            self.lifecycle_events_total: Dict[str, int] = defaultdict(int)
            self.lifecycle_events_failed: Dict[str, int] = defaultdict(int)
            self.bootstrap_jobs_total = 0
            self.bootstrap_jobs_failed = 0

    def record_api_call(self, success: bool) -> None:
        """Record an API Studio call result."""
        with self._lock:
            self.api_calls_total += 1
            if not success:
                self.api_calls_failed += 1

    def record_webhook_event(self, event_type: str) -> None:
        """Record a processed Clockify webhook event."""
        normalized = self._normalize_label(event_type)
        with self._lock:
            self.webhook_events_total += 1
            self.webhook_events_by_type[normalized] += 1

    def record_rate_limit_wait(self, wait_time: float) -> None:
        """Record that a request waited due to rate limiting."""
        with self._lock:
            self.rate_limit_events += 1
            self.rate_limit_wait_seconds += max(wait_time, 0.0)

    def record_lifecycle_event(self, event: str, success: bool = True) -> None:
        """Record lifecycle callbacks such as install/uninstall."""
        normalized = self._normalize_label(event)
        with self._lock:
            self.lifecycle_events_total[normalized] += 1
            if not success:
                self.lifecycle_events_failed[normalized] += 1

    def record_bootstrap_job(self, success: bool) -> None:
        """Record bootstrap job completions."""
        with self._lock:
            self.bootstrap_jobs_total += 1
            if not success:
                self.bootstrap_jobs_failed += 1

    def render(self) -> str:
        """Render metrics in Prometheus text exposition format."""
        with self._lock:
            lines = [
                "# HELP clockify_api_calls_total Total Clockify API calls executed via API Studio",
                "# TYPE clockify_api_calls_total counter",
                f"clockify_api_calls_total {self.api_calls_total}",
                "# HELP clockify_api_calls_failed_total Clockify API calls that returned an error",
                "# TYPE clockify_api_calls_failed_total counter",
                f"clockify_api_calls_failed_total {self.api_calls_failed}",
                "# HELP clockify_rate_limit_events_total Requests delayed by the addon rate limiter",
                "# TYPE clockify_rate_limit_events_total counter",
                f"clockify_rate_limit_events_total {self.rate_limit_events}",
                "# HELP clockify_rate_limit_wait_seconds_total Total seconds spent waiting for rate limiter tokens",
                "# TYPE clockify_rate_limit_wait_seconds_total counter",
                f"clockify_rate_limit_wait_seconds_total {self.rate_limit_wait_seconds}",
                "# HELP clockify_webhook_events_total Clockify webhook events accepted by the addon",
                "# TYPE clockify_webhook_events_total counter",
                f"clockify_webhook_events_total {self.webhook_events_total}",
            ]

            for event_type, count in sorted(self.webhook_events_by_type.items()):
                lines.append(
                    f'clockify_webhook_events_total{{event_type="{event_type}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP clockify_lifecycle_events_total Lifecycle callbacks received",
                    "# TYPE clockify_lifecycle_events_total counter",
                ]
            )

            for event, count in sorted(self.lifecycle_events_total.items()):
                lines.append(
                    f'clockify_lifecycle_events_total{{event="{event}"}} {count}'
                )

            if self.lifecycle_events_failed:
                lines.extend(
                    [
                        "# HELP clockify_lifecycle_events_failed_total Failed lifecycle callbacks",
                        "# TYPE clockify_lifecycle_events_failed_total counter",
                    ]
                )
                for event, count in sorted(self.lifecycle_events_failed.items()):
                    lines.append(
                        f'clockify_lifecycle_events_failed_total{{event="{event}"}} {count}'
                    )

            lines.extend(
                [
                    "# HELP clockify_bootstrap_jobs_total Bootstrap jobs executed",
                    "# TYPE clockify_bootstrap_jobs_total counter",
                    f"clockify_bootstrap_jobs_total {self.bootstrap_jobs_total}",
                    "# HELP clockify_bootstrap_jobs_failed_total Bootstrap jobs that failed",
                    "# TYPE clockify_bootstrap_jobs_failed_total counter",
                    f"clockify_bootstrap_jobs_failed_total {self.bootstrap_jobs_failed}",
                ]
            )

            return "\n".join(lines) + "\n"

    @staticmethod
    def _normalize_label(value: str | None) -> str:
        """Normalize arbitrary strings into Prometheus-safe label values."""
        if not value:
            return "unknown"
        normalized = "".join(ch if ch.isalnum() else "_" for ch in value.lower())
        normalized = normalized.strip("_") or "unknown"
        return normalized


metrics_registry = MetricsRegistry()
