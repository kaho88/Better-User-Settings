"""Better User Settings integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import yaml

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DASHBOARDS,
    CONF_DASHBOARDS_YAML,
    CONF_DEFAULT_DASHBOARD,
    CONF_DEFAULT_DASHBOARD_YAML,
    CONF_GROUPS,
    CONF_GROUPS_LIST,
    CONF_GROUPS_YAML,
    CONF_OPTIONS,
    CONF_ROLES,
    CONF_SIDEBAR_ITEMS,
    CONF_USERS,
    DEFAULT_OPTIONS,
    DOMAIN,
    OLD_DOMAIN,
    OPT_DEBUG,
    OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN,
    OPT_HIDE_SIDEBAR_ITEMS,
    OPT_REDIRECT_BLOCKED_DASHBOARDS,
)
from .frontend import async_setup_frontend
from .permissions import async_permissions_for_user
from .storage import (
    BetterUserSettingsStore,
    empty_storage_data,
    normalize_dashboard_path,
)
from .websocket import async_setup as async_setup_websocket

_LOGGER = logging.getLogger(__name__)
_YAML_CONFIG_KEY = f"{DOMAIN}_yaml_config"
_HTTP_VIEW_REGISTERED_KEY = f"{DOMAIN}_http_view_registered"
_WEBSOCKET_REGISTERED_KEY = f"{DOMAIN}_websocket_registered"

GROUP_SCHEMA = vol.Schema({vol.Required(CONF_USERS): vol.All(cv.ensure_list, [cv.string])})
DASHBOARD_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ROLES, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_GROUPS_LIST, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)
OPTIONS_SCHEMA = vol.Schema(
    {vol.Optional(key, default=value): cv.boolean for key, value in DEFAULT_OPTIONS.items()}
)
DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_GROUPS, default={}): {cv.string: GROUP_SCHEMA},
        vol.Optional(CONF_DASHBOARDS, default={}): {cv.string: DASHBOARD_SCHEMA},
        vol.Optional(CONF_SIDEBAR_ITEMS, default={}): {cv.string: DASHBOARD_SCHEMA},
        vol.Optional(CONF_DEFAULT_DASHBOARD, default={}): {cv.string: cv.string},
        vol.Optional(CONF_OPTIONS, default=DEFAULT_OPTIONS): OPTIONS_SCHEMA,
    }
)
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN): DOMAIN_SCHEMA,
        vol.Optional(OLD_DOMAIN): DOMAIN_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Better User Settings from YAML."""
    yaml_config = _normalize_legacy_config(
        config.get(DOMAIN, config.get(OLD_DOMAIN, {}))
    )
    hass.data[_YAML_CONFIG_KEY] = yaml_config
    if DOMAIN in config or OLD_DOMAIN in config:
        await _async_setup_runtime(hass, yaml_config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Better User Settings from a config entry."""
    entry_config = _config_from_entry_options(entry.options)
    yaml_config = hass.data.get(_YAML_CONFIG_KEY, _empty_legacy_config())
    seed_config = _merge_legacy_configs(yaml_config, entry_config)
    await _async_setup_runtime(hass, seed_config)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_setup_runtime(
    hass: HomeAssistant, seed_config: dict[str, Any] | None
) -> None:
    """Load storage and register frontend/API pieces."""
    hass.data.setdefault(DOMAIN, {})

    if "store" not in hass.data[DOMAIN]:
        store = BetterUserSettingsStore(hass)
        seed_data = await _async_storage_seed_from_legacy(hass, seed_config or {})
        await store.async_load(seed_data)
        hass.data[DOMAIN]["store"] = store

    _register_http_views(hass)
    _register_websocket(hass)
    await async_setup_frontend(hass)


class BetterUserSettingsPermissionsView(HomeAssistantView):
    """Return dashboard permissions for the current user."""

    url = "/api/better_user_settings/permissions"
    name = "api:better_user_settings:permissions"
    requires_auth = True

    async def get(self, request):
        """Handle permission requests from the Home Assistant frontend."""
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user") or request.get("user")
        store = hass.data[DOMAIN]["store"]
        return self.json(await async_permissions_for_user(hass, store.data, user))


class BetterUserSettingsLegacyConfigView(HomeAssistantView):
    """Backward-compatible config endpoint for older frontend files."""

    url = "/api/better_user_settings/config"
    name = "api:better_user_settings:config"
    requires_auth = True

    async def get(self, request):
        """Handle legacy config requests."""
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user") or request.get("user")
        store = hass.data[DOMAIN]["store"]
        permissions = await async_permissions_for_user(hass, store.data, user)
        return self.json(
            {
                **permissions,
                "allowed_dashboards": [
                    path.strip("/") for path in permissions["allowed_dashboard_paths"]
                ],
                "role": "admin" if permissions["is_admin"] else "guest",
                "primary_group": permissions["groups"][0]
                if permissions["groups"]
                else None,
                "default_dashboard": (
                    permissions["allowed_dashboard_paths"][0].strip("/")
                    if permissions["allowed_dashboard_paths"]
                    else None
                ),
                "default_dashboards": {},
            }
        )


def _register_http_views(hass: HomeAssistant) -> None:
    """Register HTTP API views once."""
    if hass.data.get(_HTTP_VIEW_REGISTERED_KEY):
        return
    hass.http.register_view(BetterUserSettingsPermissionsView())
    hass.http.register_view(BetterUserSettingsLegacyConfigView())
    hass.data[_HTTP_VIEW_REGISTERED_KEY] = True


def _register_websocket(hass: HomeAssistant) -> None:
    """Register WebSocket API once."""
    if hass.data.get(_WEBSOCKET_REGISTERED_KEY):
        return
    async_setup_websocket(hass)
    hass.data[_WEBSOCKET_REGISTERED_KEY] = True


async def _async_storage_seed_from_legacy(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, Any]:
    """Convert legacy YAML/options data to the canonical storage structure."""
    seed = empty_storage_data()
    seed[CONF_OPTIONS].update(config.get(CONF_OPTIONS, {}) or {})

    users_by_name: dict[str, str] = {}
    users_by_id: set[str] = set()
    for user in await hass.auth.async_get_users():
        current_id = getattr(user, "id", None)
        if not current_id:
            continue
        users_by_id.add(current_id)
        name = getattr(user, "name", None)
        if name:
            users_by_name[str(name)] = current_id

    for group_id, group_config in (config.get(CONF_GROUPS, {}) or {}).items():
        if not isinstance(group_config, dict):
            continue
        user_ids = []
        for configured_user in group_config.get(CONF_USERS, []):
            value = str(configured_user)
            user_ids.append(value if value in users_by_id else users_by_name.get(value, value))
        seed[CONF_GROUPS][str(group_id)] = {
            "name": str(group_config.get("name") or group_id),
            CONF_USERS: sorted(set(user_ids)),
        }

    for dashboard_path, dashboard_config in (config.get(CONF_DASHBOARDS, {}) or {}).items():
        if not isinstance(dashboard_config, dict):
            continue
        path = normalize_dashboard_path(str(dashboard_path))
        seed[CONF_DASHBOARDS][path] = {
            "allowed_groups": sorted(
                {
                    str(group_id)
                    for group_id in dashboard_config.get(CONF_GROUPS_LIST, [])
                    if str(group_id).strip()
                }
            )
        }

    for sidebar_path, sidebar_config in (
        config.get(CONF_SIDEBAR_ITEMS, {}) or {}
    ).items():
        if not isinstance(sidebar_config, dict):
            continue
        path = normalize_dashboard_path(str(sidebar_path))
        seed[CONF_SIDEBAR_ITEMS][path] = {
            "allowed_groups": sorted(
                {
                    str(group_id)
                    for group_id in sidebar_config.get(
                        CONF_GROUPS_LIST, sidebar_config.get("allowed_groups", [])
                    )
                    if str(group_id).strip()
                }
            )
        }

    return seed


def _empty_legacy_config() -> dict[str, Any]:
    """Return empty legacy configuration."""
    return {
        CONF_GROUPS: {},
        CONF_DASHBOARDS: {},
        CONF_SIDEBAR_ITEMS: {},
        CONF_DEFAULT_DASHBOARD: {},
        CONF_OPTIONS: dict(DEFAULT_OPTIONS),
    }


def _normalize_legacy_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy YAML/options configuration."""
    options = dict(DEFAULT_OPTIONS)
    options.update(config.get(CONF_OPTIONS, {}) or {})
    return {
        CONF_GROUPS: config.get(CONF_GROUPS, {}) or {},
        CONF_DASHBOARDS: config.get(CONF_DASHBOARDS, {}) or {},
        CONF_SIDEBAR_ITEMS: config.get(CONF_SIDEBAR_ITEMS, {}) or {},
        CONF_DEFAULT_DASHBOARD: config.get(CONF_DEFAULT_DASHBOARD, {}) or {},
        CONF_OPTIONS: options,
    }


def _merge_legacy_configs(
    base_config: dict[str, Any], override_config: dict[str, Any]
) -> dict[str, Any]:
    """Merge YAML config with UI options. UI values win per section."""
    base = _normalize_legacy_config(base_config)
    override = _normalize_legacy_config(override_config)
    options = dict(base[CONF_OPTIONS])
    options.update(override[CONF_OPTIONS])
    return {
        CONF_GROUPS: override[CONF_GROUPS] or base[CONF_GROUPS],
        CONF_DASHBOARDS: override[CONF_DASHBOARDS] or base[CONF_DASHBOARDS],
        CONF_SIDEBAR_ITEMS: override[CONF_SIDEBAR_ITEMS] or base[CONF_SIDEBAR_ITEMS],
        CONF_DEFAULT_DASHBOARD: override[CONF_DEFAULT_DASHBOARD]
        or base[CONF_DEFAULT_DASHBOARD],
        CONF_OPTIONS: options,
    }


def _config_from_entry_options(options: dict[str, Any]) -> dict[str, Any]:
    """Convert config entry options into the legacy runtime config shape."""
    return {
        CONF_GROUPS: _parse_yaml_mapping(options.get(CONF_GROUPS_YAML, "")),
        CONF_DASHBOARDS: _parse_yaml_mapping(options.get(CONF_DASHBOARDS_YAML, "")),
        CONF_DEFAULT_DASHBOARD: _parse_yaml_mapping(
            options.get(CONF_DEFAULT_DASHBOARD_YAML, "")
        ),
        CONF_OPTIONS: {
            OPT_HIDE_SIDEBAR_ITEMS: options.get(
                OPT_HIDE_SIDEBAR_ITEMS, DEFAULT_OPTIONS[OPT_HIDE_SIDEBAR_ITEMS]
            ),
            OPT_REDIRECT_BLOCKED_DASHBOARDS: options.get(
                OPT_REDIRECT_BLOCKED_DASHBOARDS,
                DEFAULT_OPTIONS[OPT_REDIRECT_BLOCKED_DASHBOARDS],
            ),
            OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN: options.get(
                OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN,
                DEFAULT_OPTIONS[OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN],
            ),
            OPT_DEBUG: options.get(OPT_DEBUG, DEFAULT_OPTIONS[OPT_DEBUG]),
        },
    }


def _parse_yaml_mapping(value: str) -> dict[str, Any]:
    """Parse a YAML text field and return a mapping."""
    parsed = yaml.safe_load(value.strip() or "{}")
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        _LOGGER.warning("Ignoring Better User Settings UI value; expected mapping")
        return {}
    return parsed
