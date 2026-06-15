"""Better Dashboard Roles integration.

This integration exposes a small authenticated API endpoint for the companion
frontend resource. It intentionally does not enforce access control in Home
Assistant; it only provides role metadata for frontend filtering.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import yaml

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DASHBOARDS,
    CONF_DASHBOARDS_YAML,
    CONF_DEFAULT_DASHBOARD,
    CONF_DEFAULT_DASHBOARD_YAML,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_GROUPS_LIST,
    CONF_GROUPS_YAML,
    CONF_OPTIONS,
    CONF_ROLE,
    CONF_ROLES,
    CONF_USERS,
    CONF_USERS_YAML,
    DEFAULT_OPTIONS,
    DEFAULT_ROLE,
    DOMAIN,
    OPT_DEBUG,
    OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN,
    OPT_HIDE_SIDEBAR_ITEMS,
    OPT_REDIRECT_BLOCKED_DASHBOARDS,
)

_LOGGER = logging.getLogger(__name__)
_YAML_CONFIG_KEY = f"{DOMAIN}_yaml_config"
_VIEW_REGISTERED_KEY = f"{DOMAIN}_view_registered"

USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ROLE): cv.string,
        vol.Optional(CONF_GROUP): cv.string,
        vol.Optional(CONF_GROUPS_LIST): vol.All(cv.ensure_list, [cv.string]),
    }
)

GROUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERS): vol.All(cv.ensure_list, [cv.string]),
    }
)

DASHBOARD_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ROLES, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_GROUPS_LIST, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(key, default=value): cv.boolean
        for key, value in DEFAULT_OPTIONS.items()
    }
)

DOMAIN_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERS, default={}): {cv.string: USER_SCHEMA},
        vol.Optional(CONF_GROUPS, default={}): {cv.string: GROUP_SCHEMA},
        vol.Optional(CONF_DASHBOARDS, default={}): {cv.string: DASHBOARD_SCHEMA},
        vol.Optional(CONF_DEFAULT_DASHBOARD, default={}): {cv.string: cv.string},
        vol.Optional(CONF_OPTIONS, default=DEFAULT_OPTIONS): OPTIONS_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: DOMAIN_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Better Dashboard Roles from YAML."""
    yaml_config = _normalize_config(config.get(DOMAIN, {}))
    hass.data[_YAML_CONFIG_KEY] = yaml_config
    _store_config(hass, yaml_config)
    _register_api_view(hass)

    _LOGGER.info(
        "Better Dashboard Roles YAML base loaded with %s users and %s dashboards",
        len(yaml_config[CONF_USERS]),
        len(yaml_config[CONF_DASHBOARDS]),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Better Dashboard Roles from a config entry."""
    entry_config = _config_from_entry_options(entry.options)
    yaml_config = hass.data.get(_YAML_CONFIG_KEY, _empty_config())
    merged_config = _merge_configs(yaml_config, entry_config)

    _store_config(hass, merged_config)
    _register_api_view(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info(
        "Better Dashboard Roles UI config loaded with %s users and %s dashboards",
        len(merged_config[CONF_USERS]),
        len(merged_config[CONF_DASHBOARDS]),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and fall back to YAML config if present."""
    _store_config(hass, hass.data.get(_YAML_CONFIG_KEY, _empty_config()))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


class BetterDashboardRolesConfigView(HomeAssistantView):
    """Return the effective dashboard role configuration for the current user."""

    url = "/api/better_dashboard_roles/config"
    name = "api:better_dashboard_roles:config"
    requires_auth = True

    async def get(self, request):
        """Handle config requests from the Home Assistant frontend."""
        hass: HomeAssistant = request.app["hass"]
        config = hass.data.get(DOMAIN, {})

        user = request.get("hass_user") or request.get("user")
        username = _get_username(user)
        user_id = getattr(user, "id", None)
        user_groups = _find_groups_for_user(config, username, user_id)
        role = _find_role_for_user(config.get(CONF_USERS, {}), username, user_id)
        primary_group = user_groups[0] if user_groups else role

        dashboards = config.get(CONF_DASHBOARDS, {})
        allowed_dashboards = _allowed_dashboards_for_user(dashboards, role, user_groups)
        default_dashboards = config.get(CONF_DEFAULT_DASHBOARD, {})
        default_dashboard = _find_default_dashboard(default_dashboards, user_groups, role)

        response = {
            "username": username,
            "user_id": user_id,
            "role": role,
            "primary_group": primary_group,
            "groups": user_groups,
            "allowed_dashboards": allowed_dashboards,
            "default_dashboard": default_dashboard,
            "default_dashboards": default_dashboards,
            "options": config.get(CONF_OPTIONS, DEFAULT_OPTIONS),
        }

        if response["options"].get("debug"):
            _LOGGER.debug("Better Dashboard Roles response: %s", response)

        return self.json(response)


def _get_username(user: Any | None) -> str | None:
    """Extract the most stable display name Home Assistant exposes."""
    if user is None:
        return None

    name = getattr(user, CONF_NAME, None) or getattr(user, "name", None)
    if name:
        return str(name)

    return getattr(user, "id", None)


def _find_role_for_user(
    users_config: dict[str, dict[str, str]], username: str | None, user_id: str | None
) -> str:
    """Resolve the configured role for a HA user name or id."""
    candidates = [value for value in (username, user_id) if value]
    candidates.extend(value.lower() for value in candidates)

    for candidate in candidates:
        user_config = users_config.get(candidate)
        if user_config and user_config.get(CONF_ROLE):
            return user_config[CONF_ROLE]

    return DEFAULT_ROLE


def _find_groups_for_user(
    config: dict[str, Any], username: str | None, user_id: str | None
) -> list[str]:
    """Resolve all groups for a HA user from group membership and user config."""
    candidates = _user_candidates(username, user_id)
    groups: list[str] = []

    for group_name, group_config in config.get(CONF_GROUPS, {}).items():
        configured_users = group_config.get(CONF_USERS, [])
        configured_candidates = {
            value
            for configured_user in configured_users
            for value in (str(configured_user), str(configured_user).lower())
        }
        if any(candidate in configured_candidates for candidate in candidates):
            groups.append(group_name)

    for candidate in candidates:
        user_config = config.get(CONF_USERS, {}).get(candidate)
        if not user_config:
            continue
        if user_config.get(CONF_GROUP):
            groups.append(user_config[CONF_GROUP])
        for group_name in user_config.get(CONF_GROUPS_LIST, []):
            groups.append(group_name)

    return list(dict.fromkeys(groups))


def _user_candidates(username: str | None, user_id: str | None) -> list[str]:
    """Return normalized lookup candidates for a HA user."""
    candidates = [value for value in (username, user_id) if value]
    candidates.extend(value.lower() for value in candidates)
    return list(dict.fromkeys(candidates))


def _allowed_dashboards_for_user(
    dashboards: dict[str, dict[str, list[str]]], role: str, groups: list[str]
) -> list[str]:
    """Return dashboard ids that include the current role or any group."""
    principals = {role, *groups}
    return [
        dashboard_id
        for dashboard_id, dashboard_config in dashboards.items()
        if principals.intersection(dashboard_config.get(CONF_ROLES, []))
        or principals.intersection(dashboard_config.get(CONF_GROUPS_LIST, []))
    ]


def _find_default_dashboard(
    default_dashboards: dict[str, str], groups: list[str], role: str
) -> str | None:
    """Return the first matching default dashboard for groups, then role."""
    for group_name in groups:
        if group_name in default_dashboards:
            return default_dashboards[group_name]
    return default_dashboards.get(role)


def _register_api_view(hass: HomeAssistant) -> None:
    """Register the API view once."""
    if hass.data.get(_VIEW_REGISTERED_KEY):
        return
    hass.http.register_view(BetterDashboardRolesConfigView())
    hass.data[_VIEW_REGISTERED_KEY] = True


def _store_config(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Store the effective runtime config."""
    hass.data[DOMAIN] = _normalize_config(config)


def _empty_config() -> dict[str, Any]:
    """Return an empty normalized config."""
    return {
        CONF_USERS: {},
        CONF_GROUPS: {},
        CONF_DASHBOARDS: {},
        CONF_DEFAULT_DASHBOARD: {},
        CONF_OPTIONS: dict(DEFAULT_OPTIONS),
    }


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize config from YAML or UI options."""
    options = dict(DEFAULT_OPTIONS)
    options.update(config.get(CONF_OPTIONS, {}))

    return {
        CONF_USERS: config.get(CONF_USERS, {}) or {},
        CONF_GROUPS: config.get(CONF_GROUPS, {}) or {},
        CONF_DASHBOARDS: config.get(CONF_DASHBOARDS, {}) or {},
        CONF_DEFAULT_DASHBOARD: config.get(CONF_DEFAULT_DASHBOARD, {}) or {},
        CONF_OPTIONS: options,
    }


def _merge_configs(
    base_config: dict[str, Any], override_config: dict[str, Any]
) -> dict[str, Any]:
    """Merge YAML config with UI config. UI values win per section."""
    base = _normalize_config(base_config)
    override = _normalize_config(override_config)

    options = dict(base[CONF_OPTIONS])
    options.update(override[CONF_OPTIONS])

    return {
        CONF_USERS: override[CONF_USERS] or base[CONF_USERS],
        CONF_GROUPS: override[CONF_GROUPS] or base[CONF_GROUPS],
        CONF_DASHBOARDS: override[CONF_DASHBOARDS] or base[CONF_DASHBOARDS],
        CONF_DEFAULT_DASHBOARD: override[CONF_DEFAULT_DASHBOARD]
        or base[CONF_DEFAULT_DASHBOARD],
        CONF_OPTIONS: options,
    }


def _config_from_entry_options(options: dict[str, Any]) -> dict[str, Any]:
    """Convert config entry options into the runtime config shape."""
    return {
        CONF_USERS: _parse_yaml_mapping(options.get(CONF_USERS_YAML, "")),
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
        _LOGGER.warning("Ignoring Better Dashboard Roles UI value; expected mapping")
        return {}
    return parsed
