"""Dashboard discovery for Better User Settings."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .storage import normalize_dashboard_path

LOVELACE_DASHBOARDS_STORAGE_KEY = "lovelace_dashboards"


async def async_get_dashboards(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return known Home Assistant dashboards with title and path."""
    dashboards: dict[str, dict[str, str]] = {
        "/lovelace": {
            "title": "Overview",
            "path": "/lovelace",
            "url": "/lovelace",
        }
    }

    _collect_dashboard_entries(hass.data.get("lovelace"), dashboards)
    _collect_dashboard_entries(hass.data.get("frontend_panels"), dashboards)
    await _collect_lovelace_storage_dashboards(hass, dashboards)

    return sorted(dashboards.values(), key=lambda item: item["title"].lower())


async def _collect_lovelace_storage_dashboards(
    hass: HomeAssistant, dashboards: dict[str, dict[str, str]]
) -> None:
    """Collect dashboards from Home Assistant's lovelace dashboard storage."""
    store = Store(hass, 1, LOVELACE_DASHBOARDS_STORAGE_KEY)
    data = await store.async_load()
    if not isinstance(data, dict):
        return

    for raw_config in data.get("items", []):
        if not isinstance(raw_config, dict):
            continue
        url_path = raw_config.get("url_path") or raw_config.get("urlPath")
        if not url_path:
            continue
        path = normalize_dashboard_path(str(url_path))
        title = str(raw_config.get("title") or raw_config.get("name") or path)
        dashboards[path] = {"title": title, "path": path, "url": path}


def _collect_dashboard_entries(
    source: Any, dashboards: dict[str, dict[str, str]], depth: int = 0
) -> None:
    """Collect dashboard-like URL paths from Home Assistant internals."""
    if source is None or depth > 4:
        return

    if isinstance(source, dict):
        for key, value in source.items():
            if isinstance(key, str):
                _add_dashboard_entry(key, value, dashboards)
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                _collect_dashboard_entries(value, dashboards, depth + 1)
        return

    if isinstance(source, (list, tuple, set)):
        for item in source:
            _collect_dashboard_entries(item, dashboards, depth + 1)
        return

    for attr in ("dashboards", "url_path", "urlPath", "path", "id", "title"):
        if not hasattr(source, attr):
            continue
        value = getattr(source, attr)
        if attr == "dashboards":
            _collect_dashboard_entries(value, dashboards, depth + 1)
        else:
            _add_dashboard_entry(str(value), source, dashboards)


def _add_dashboard_entry(
    raw_path: str, source: Any, dashboards: dict[str, dict[str, str]]
) -> None:
    """Add one dashboard if the path looks like a Lovelace dashboard."""
    path = normalize_dashboard_path(raw_path)
    if not _is_dashboard_path(path):
        return

    title = _dashboard_title(source) or path
    dashboards.setdefault(path, {"title": title, "path": path, "url": path})


def _is_dashboard_path(path: str) -> bool:
    """Return True for Home Assistant dashboard path shapes."""
    segment = path.strip("/").split("/", 1)[0]
    return segment == "lovelace" or segment.startswith(("lovelace-", "dashboard-"))


def _dashboard_title(source: Any) -> str | None:
    """Best-effort dashboard title extraction."""
    if isinstance(source, dict):
        for key in ("title", "name"):
            if source.get(key):
                return str(source[key])
        return None

    for attr in ("title", "name"):
        if hasattr(source, attr):
            value = getattr(source, attr)
            if value:
                return str(value)

    return None
