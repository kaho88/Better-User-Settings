"""Permission calculation for Better User Settings."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_DASHBOARDS, CONF_GROUPS, CONF_OPTIONS, CONF_SIDEBAR_ITEMS
from .dashboards import async_get_dashboards
from .storage import normalize_dashboard_path


def user_display_name(user: Any | None) -> str | None:
    """Return a user display name for UI only."""
    if user is None:
        return None
    return getattr(user, "name", None) or getattr(user, "id", None)


def user_id(user: Any | None) -> str | None:
    """Return the Home Assistant user ID."""
    return getattr(user, "id", None) if user is not None else None


def is_admin(user: Any | None) -> bool:
    """Return whether the current HA user is an admin."""
    return bool(getattr(user, "is_admin", False))


def groups_for_user(data: dict[str, Any], current_user_id: str | None) -> list[str]:
    """Return group IDs containing the current Home Assistant user ID."""
    if not current_user_id:
        return []
    groups = []
    for group_id, group_config in data.get(CONF_GROUPS, {}).items():
        if current_user_id in group_config.get("users", []):
            groups.append(group_id)
    return groups


async def async_permissions_for_user(
    hass: HomeAssistant, data: dict[str, Any], user: Any | None
) -> dict[str, Any]:
    """Return sidebar permissions for a user."""
    current_user_id = user_id(user)
    admin = is_admin(user)
    user_groups = groups_for_user(data, current_user_id)
    dashboards = await async_get_dashboards(hass)
    configured_dashboards = data.get(CONF_DASHBOARDS, {})
    configured_sidebar_items = data.get(CONF_SIDEBAR_ITEMS, {})
    known_paths = {normalize_dashboard_path(dashboard["path"]) for dashboard in dashboards}
    for configured_path in configured_dashboards:
        path = normalize_dashboard_path(configured_path)
        if path not in known_paths:
            dashboards.append({"title": path, "path": path, "url": path})
            known_paths.add(path)

    if admin:
        allowed_paths = [dashboard["path"] for dashboard in dashboards]
        hidden_paths: list[str] = []
        allowed_sidebar_paths = list(configured_sidebar_items)
        hidden_sidebar_paths: list[str] = []
    else:
        allowed_paths = []
        hidden_paths = []
        for dashboard in dashboards:
            path = normalize_dashboard_path(dashboard["path"])
            allowed_groups = configured_dashboards.get(path, {}).get(
                "allowed_groups", []
            )
            if not allowed_groups or set(allowed_groups).intersection(user_groups):
                allowed_paths.append(path)
            else:
                hidden_paths.append(path)

        allowed_sidebar_paths = []
        hidden_sidebar_paths = []
        for sidebar_path, sidebar_config in configured_sidebar_items.items():
            path = normalize_dashboard_path(sidebar_path)
            allowed_groups = sidebar_config.get("allowed_groups", [])
            if not allowed_groups or set(allowed_groups).intersection(user_groups):
                allowed_sidebar_paths.append(path)
            else:
                hidden_sidebar_paths.append(path)

    return {
        "user_id": current_user_id,
        "username": user_display_name(user),
        "is_admin": admin,
        "groups": user_groups,
        "allowed_dashboard_paths": sorted(set(allowed_paths)),
        "hidden_dashboard_paths": sorted(set(hidden_paths)),
        "allowed_sidebar_paths": sorted(set(allowed_sidebar_paths)),
        "hidden_sidebar_paths": sorted(set(hidden_sidebar_paths)),
        "dashboards": dashboards,
        "options": data.get(CONF_OPTIONS, {}),
    }
