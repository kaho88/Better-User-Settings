"""Storage helpers for Better User Settings."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_DASHBOARDS,
    CONF_GROUPS,
    CONF_OPTIONS,
    CONF_SIDEBAR_ITEMS,
    CONF_USERS,
    DEFAULT_OPTIONS,
    DOMAIN,
    OLD_STORAGE_KEY,
    STORAGE_KEY,
    STORAGE_VERSION,
)


def empty_storage_data() -> dict[str, Any]:
    """Return the canonical empty storage shape."""
    return {
        CONF_GROUPS: {},
        CONF_DASHBOARDS: {},
        CONF_SIDEBAR_ITEMS: {},
        CONF_OPTIONS: dict(DEFAULT_OPTIONS),
    }


def normalize_storage_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize persisted data into the canonical storage shape."""
    result = empty_storage_data()
    if not data:
        return result

    options = dict(DEFAULT_OPTIONS)
    options.update(data.get(CONF_OPTIONS, {}) or {})
    result[CONF_OPTIONS] = options

    for group_id, group_config in (data.get(CONF_GROUPS, {}) or {}).items():
        if not isinstance(group_config, dict):
            continue
        normalized_id = str(group_id).strip()
        if not normalized_id:
            continue
        result[CONF_GROUPS][normalized_id] = {
            "name": str(group_config.get("name") or normalized_id),
            CONF_USERS: sorted(
                {
                    str(user_id)
                    for user_id in group_config.get(CONF_USERS, [])
                    if str(user_id).strip()
                }
            ),
        }

    for dashboard_path, dashboard_config in (
        data.get(CONF_DASHBOARDS, {}) or {}
    ).items():
        if not isinstance(dashboard_config, dict):
            continue
        normalized_path = normalize_dashboard_path(str(dashboard_path))
        if not normalized_path:
            continue
        result[CONF_DASHBOARDS][normalized_path] = {
            "allowed_groups": sorted(
                {
                    str(group_id)
                    for group_id in dashboard_config.get(
                        "allowed_groups", dashboard_config.get(CONF_GROUPS, [])
                    )
                    if str(group_id).strip()
                }
            )
        }

    for sidebar_path, sidebar_config in (data.get(CONF_SIDEBAR_ITEMS, {}) or {}).items():
        if not isinstance(sidebar_config, dict):
            continue
        normalized_path = normalize_dashboard_path(str(sidebar_path))
        if not normalized_path:
            continue
        result[CONF_SIDEBAR_ITEMS][normalized_path] = {
            "allowed_groups": sorted(
                {
                    str(group_id)
                    for group_id in sidebar_config.get(
                        "allowed_groups", sidebar_config.get(CONF_GROUPS, [])
                    )
                    if str(group_id).strip()
                }
            )
        }

    return result


def normalize_dashboard_path(value: str) -> str:
    """Normalize dashboard paths to leading-slash URL paths."""
    path = value.strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        parts = path.split("/", 3)
        path = f"/{parts[3]}" if len(parts) > 3 else "/"
    path = path.split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/"


class BetterUserSettingsStore:
    """Home Assistant Store wrapper for the integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store wrapper."""
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._old_store = Store(hass, STORAGE_VERSION, OLD_STORAGE_KEY)
        self.data = empty_storage_data()

    async def async_load(self, seed_data: dict[str, Any] | None = None) -> None:
        """Load storage, optionally seeding it on first run."""
        stored = await self._store.async_load()
        if stored is None:
            stored = await self._old_store.async_load()
        if stored is None and seed_data:
            self.data = normalize_storage_data(seed_data)
            await self.async_save()
            return
        self.data = normalize_storage_data(stored)
        if stored is not None:
            await self.async_save()

    async def async_save(self) -> None:
        """Persist current data."""
        self.data = normalize_storage_data(self.data)
        await self._store.async_save(self.data)

    async def async_save_group_users(
        self, group_id: str, name: str, user_ids: list[str]
    ) -> dict[str, Any]:
        """Create/update a group and its user IDs."""
        normalized_id = group_id.strip()
        groups = self.data.setdefault(CONF_GROUPS, {})
        groups[normalized_id] = {
            "name": name.strip() or normalized_id,
            CONF_USERS: sorted({user_id for user_id in user_ids if user_id}),
        }
        await self.async_save()
        return groups[normalized_id]

    async def async_save_dashboard_groups(
        self, dashboard_path: str, allowed_groups: list[str]
    ) -> dict[str, Any]:
        """Create/update dashboard group permissions."""
        normalized_path = normalize_dashboard_path(dashboard_path)
        dashboards = self.data.setdefault(CONF_DASHBOARDS, {})
        dashboards[normalized_path] = {
            "allowed_groups": sorted({group_id for group_id in allowed_groups if group_id})
        }
        await self.async_save()
        return dashboards[normalized_path]

    async def async_save_sidebar_item_groups(
        self, sidebar_path: str, allowed_groups: list[str]
    ) -> dict[str, Any]:
        """Create/update sidebar item group permissions."""
        normalized_path = normalize_dashboard_path(sidebar_path)
        sidebar_items = self.data.setdefault(CONF_SIDEBAR_ITEMS, {})
        sidebar_items[normalized_path] = {
            "allowed_groups": sorted({group_id for group_id in allowed_groups if group_id})
        }
        await self.async_save()
        return sidebar_items[normalized_path]


def store_from_hass(hass: HomeAssistant) -> BetterUserSettingsStore:
    """Return the loaded integration store."""
    return hass.data[DOMAIN]["store"]
