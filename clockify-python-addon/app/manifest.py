from copy import deepcopy
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

from app.config import get_settings
from app.constants import (
    CLOCKIFY_SCOPE_LIST,
    CLOCKIFY_WEBHOOK_ROUTE_MAP,
)

settings = get_settings()

router = APIRouter(tags=["manifest"])

MANIFEST_FILE = Path(__file__).parent.parent / "manifest.json"

def _load_manifest_from_file() -> Optional[dict]:
    if MANIFEST_FILE.exists():
        with MANIFEST_FILE.open() as handle:
            return json.load(handle)
    return None


def _apply_base_url(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return value
    placeholder = "http://localhost:8000"
    if value.startswith(placeholder):
        return value.replace(placeholder, settings.base_url, 1)
    return value


def _legacy_manifest() -> dict:
    """Fallback manifest used only if manifest.json is missing."""
    base_url = settings.base_url
    return {
        "schemaVersion": "1.3",
        "key": settings.addon_key,
        "name": settings.addon_name,
        "description": settings.addon_description,
        "baseUrl": base_url,
        "vendor": {
            "name": settings.addon_vendor_name,
            "url": settings.addon_vendor_url
        },
        "permissions": {
            "scopes": list(CLOCKIFY_SCOPE_LIST)
        },
        "lifecycle": {
            "installed": f"{base_url}/lifecycle/installed",
            "settingsUpdated": f"{base_url}/lifecycle/settings-updated",
            "statusChanged": f"{base_url}/lifecycle/status-changed",
            "deleted": f"{base_url}/lifecycle/deleted"
        },
        "webhooks": [
            {
                "event": event,
                "url": f"{base_url}{path}"
            }
            for event, path in CLOCKIFY_WEBHOOK_ROUTE_MAP.items()
        ],
        "components": [
            {
                "type": "SIDEBAR",
                "name": "API Studio",
                "url": f"{base_url}/ui",
                "icon": {
                    "light": f"{base_url}/static/icon.svg",
                    "dark": f"{base_url}/static/icon.svg"
                }
            }
        ],
        "settings": {
            "type": "STRUCTURED",
            "fields": []
        }
    }


def generate_manifest() -> dict:
    """Generate Clockify addon manifest using manifest.json as the source of truth."""
    manifest_template = _load_manifest_from_file()
    manifest = deepcopy(manifest_template) if manifest_template else _legacy_manifest()

    manifest["baseUrl"] = settings.base_url

    lifecycle = manifest.get("lifecycle", {})
    for key, value in lifecycle.items():
        lifecycle[key] = _apply_base_url(value)

    for webhook in manifest.get("webhooks", []):
        webhook["url"] = _apply_base_url(webhook.get("url"))

    for component in manifest.get("components", []):
        if "url" in component:
            component["url"] = _apply_base_url(component["url"])
        if "icon" in component:
            for theme, url in component["icon"].items():
                component["icon"][theme] = _apply_base_url(url)

    return manifest


@router.get("/manifest")
async def get_manifest():
    """Return addon manifest."""
    return generate_manifest()
