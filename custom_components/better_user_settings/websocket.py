"""WebSocket API for Better User Settings."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DASHBOARDS, CONF_GROUPS, CONF_SIDEBAR_ITEMS, DOMAIN
from .dashboards import async_get_dashboards
from .permissions import async_permissions_for_user
from .storage import normalize_dashboard_path, store_from_hass


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register WebSocket commands."""
    websocket_api.async_register_command(hass, websocket_get_groups)
    websocket_api.async_register_command(hass, websocket_save_group_users)
    websocket_api.async_register_command(hass, websocket_get_dashboards)
    websocket_api.async_register_command(hass, websocket_save_dashboard_groups)
    websocket_api.async_register_command(hass, websocket_get_sidebar_items)
    websocket_api.async_register_command(hass, websocket_save_sidebar_item_groups)
    websocket_api.async_register_command(hass, websocket_get_permissions)
    websocket_api.async_register_command(hass, websocket_get_allowed_paths)


COMMON_SIDEBAR_ITEMS = {
    "/map": "Karte",
    "/logbook": "Aktivitaet",
    "/history": "Verlauf",
    "/energy": "Energie",
    "/media-browser": "Medien",
    "/todo": "To-do-Listen",
    "/calendar": "Kalender",
}


def _require_admin(connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> bool:
    """Return False and send an error if the connection user is not admin."""
    if getattr(connection.user, "is_admin", False):
        return True
    connection.send_error(msg["id"], "unauthorized", "Admin permissions required")
    return False


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_groups"})
@websocket_api.async_response
async def websocket_get_groups(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return all groups and Home Assistant users."""
    if not _require_admin(connection, msg):
        return

    users = []
    for user in await hass.auth.async_get_users():
        current_user_id = getattr(user, "id", None)
        if not current_user_id:
            continue
        users.append(
            {
                "id": current_user_id,
                "name": getattr(user, "name", None) or current_user_id,
                "is_admin": bool(getattr(user, "is_admin", False)),
            }
        )

    connection.send_result(
        msg["id"],
        {
            "groups": store_from_hass(hass).data.get(CONF_GROUPS, {}),
            "users": sorted(users, key=lambda item: item["name"].lower()),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_group_users",
        vol.Required("group_id"): str,
        vol.Required("name"): str,
        vol.Required("user_ids"): [str],
    }
)
@websocket_api.async_response
async def websocket_save_group_users(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save one group's user IDs."""
    if not _require_admin(connection, msg):
        return

    group_id = msg["group_id"].strip()
    if not group_id:
        connection.send_error(msg["id"], "invalid_group", "Group ID is required")
        return

    group = await store_from_hass(hass).async_save_group_users(
        group_id, msg["name"], msg["user_ids"]
    )
    connection.send_result(msg["id"], {"group_id": group_id, "group": group})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_dashboards"})
@websocket_api.async_response
async def websocket_get_dashboards(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return all dashboards with configured group permissions."""
    if not _require_admin(connection, msg):
        return

    data = store_from_hass(hass).data
    dashboards = []
    discovered_paths = set()
    for dashboard in await async_get_dashboards(hass):
        path = normalize_dashboard_path(dashboard["path"])
        discovered_paths.add(path)
        dashboards.append(
            {
                **dashboard,
                "path": path,
                "allowed_groups": data.get(CONF_DASHBOARDS, {})
                .get(path, {})
                .get("allowed_groups", []),
            }
        )

    for path, dashboard_config in data.get(CONF_DASHBOARDS, {}).items():
        if path in discovered_paths:
            continue
        dashboards.append(
            {
                "title": f"{path} (configured)",
                "path": path,
                "url": path,
                "allowed_groups": dashboard_config.get("allowed_groups", []),
            }
        )

    connection.send_result(
        msg["id"],
        {
            "dashboards": dashboards,
            "groups": data.get(CONF_GROUPS, {}),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_dashboard_allowed_groups",
        vol.Required("dashboard_path"): str,
        vol.Required("allowed_groups"): [str],
    }
)
@websocket_api.async_response
async def websocket_save_dashboard_groups(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save one dashboard's allowed group IDs."""
    if not _require_admin(connection, msg):
        return

    path = normalize_dashboard_path(msg["dashboard_path"])
    if not path:
        connection.send_error(msg["id"], "invalid_dashboard", "Dashboard path required")
        return

    dashboard = await store_from_hass(hass).async_save_dashboard_groups(
        path, msg["allowed_groups"]
    )
    connection.send_result(msg["id"], {"dashboard_path": path, "dashboard": dashboard})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_sidebar_items"})
@websocket_api.async_response
async def websocket_get_sidebar_items(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return configured and common non-dashboard sidebar items."""
    if not _require_admin(connection, msg):
        return

    data = store_from_hass(hass).data
    configured_items = data.get(CONF_SIDEBAR_ITEMS, {})
    sidebar_items = []
    seen_paths = set()

    for path, title in COMMON_SIDEBAR_ITEMS.items():
        seen_paths.add(path)
        sidebar_items.append(
            {
                "title": title,
                "path": path,
                "allowed_groups": configured_items.get(path, {}).get(
                    "allowed_groups", []
                ),
            }
        )

    for path, item_config in configured_items.items():
        if path in seen_paths:
            continue
        sidebar_items.append(
            {
                "title": f"{path} (configured)",
                "path": path,
                "allowed_groups": item_config.get("allowed_groups", []),
            }
        )

    connection.send_result(
        msg["id"],
        {
            "sidebar_items": sidebar_items,
            "groups": data.get(CONF_GROUPS, {}),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_sidebar_item_allowed_groups",
        vol.Required("sidebar_path"): str,
        vol.Required("allowed_groups"): [str],
    }
)
@websocket_api.async_response
async def websocket_save_sidebar_item_groups(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Save one non-dashboard sidebar item's allowed group IDs."""
    if not _require_admin(connection, msg):
        return

    path = normalize_dashboard_path(msg["sidebar_path"])
    if not path:
        connection.send_error(msg["id"], "invalid_sidebar_item", "Sidebar path required")
        return

    item = await store_from_hass(hass).async_save_sidebar_item_groups(
        path, msg["allowed_groups"]
    )
    connection.send_result(msg["id"], {"sidebar_path": path, "sidebar_item": item})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_permissions"})
@websocket_api.async_response
async def websocket_get_permissions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return permissions for the current user."""
    result = await async_permissions_for_user(
        hass, store_from_hass(hass).data, connection.user
    )
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_allowed_paths"})
@websocket_api.async_response
async def websocket_get_allowed_paths(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return allowed dashboard paths for the current user."""
    result = await async_permissions_for_user(
        hass, store_from_hass(hass).data, connection.user
    )
    connection.send_result(
        msg["id"],
        {
            "allowed_dashboard_paths": result["allowed_dashboard_paths"],
            "hidden_dashboard_paths": result["hidden_dashboard_paths"],
            "allowed_sidebar_paths": result["allowed_sidebar_paths"],
            "hidden_sidebar_paths": result["hidden_sidebar_paths"],
        },
    )
