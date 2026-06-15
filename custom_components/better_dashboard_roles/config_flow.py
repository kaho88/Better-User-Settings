"""Config flow for Better Dashboard Roles."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
import yaml

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_DASHBOARDS_YAML,
    CONF_DEFAULT_DASHBOARD_YAML,
    CONF_GROUPS_YAML,
    CONF_USERS_YAML,
    DEFAULT_DASHBOARD_YAML,
    DEFAULT_DASHBOARDS_YAML,
    DEFAULT_GROUPS_YAML,
    DEFAULT_OPTIONS,
    DEFAULT_USERS_YAML,
    DOMAIN,
    OPT_DEBUG,
    OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN,
    OPT_HIDE_SIDEBAR_ITEMS,
    OPT_REDIRECT_BLOCKED_DASHBOARDS,
)

CONF_ASSIGNED_GROUP = "assigned_group"
CONF_SELECTED_DASHBOARD = "selected_dashboard"
CONF_SET_AS_DEFAULT = "set_as_default"
CONF_SELECTED_USER = "selected_user"

MULTILINE_TEXT_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(
        multiline=True,
        type=selector.TextSelectorType.TEXT,
    )
)

TEXT_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
)


class BetterDashboardRolesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Better Dashboard Roles."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return BetterDashboardRolesOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Create the integration from the Home Assistant UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_user_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title="Better Dashboard Roles",
                    data={},
                    options=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(user_input),
            errors=errors,
        )


class BetterDashboardRolesOptionsFlow(config_entries.OptionsFlow):
    """Handle Better Dashboard Roles options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["assign_user_group", "assign_dashboard_group", "edit_all"],
        )

    async def async_step_edit_all(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage integration options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_user_input(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="edit_all",
            data_schema=_data_schema(user_input or dict(self._config_entry.options)),
            errors=errors,
        )

    async def async_step_assign_user_group(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Assign one Home Assistant user to a group."""
        errors: dict[str, str] = {}

        if user_input is not None:
            group = user_input.get(CONF_ASSIGNED_GROUP, "").strip()
            user_key = user_input.get(CONF_SELECTED_USER)

            if not group:
                errors[CONF_ASSIGNED_GROUP] = "missing_group"
            elif not user_key:
                errors[CONF_SELECTED_USER] = "missing_user"
            else:
                options = dict(self._config_entry.options)
                try:
                    groups = _parse_yaml_mapping(options.get(CONF_GROUPS_YAML, ""))
                except (TypeError, yaml.YAMLError):
                    errors[CONF_SELECTED_USER] = "invalid_yaml"
                    groups = {}

            if not errors and user_input is not None:
                group_config = groups.setdefault(group, {})
                users = group_config.setdefault("users", [])
                if user_key not in users:
                    users.append(user_key)
                options[CONF_GROUPS_YAML] = yaml.safe_dump(
                    groups,
                    allow_unicode=True,
                    sort_keys=False,
                )
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="assign_user_group",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SELECTED_USER): vol.In(
                        await _async_user_choices(self.hass)
                    ),
                    vol.Required(CONF_ASSIGNED_GROUP): TEXT_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_assign_dashboard_group(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Allow one group to access one dashboard."""
        errors: dict[str, str] = {}

        if user_input is not None:
            dashboard_id = user_input.get(CONF_SELECTED_DASHBOARD)
            group = user_input.get(CONF_ASSIGNED_GROUP, "").strip()
            set_as_default = user_input.get(CONF_SET_AS_DEFAULT, False)

            if not dashboard_id:
                errors[CONF_SELECTED_DASHBOARD] = "missing_dashboard"
            elif not group:
                errors[CONF_ASSIGNED_GROUP] = "missing_group"
            else:
                options = dict(self._config_entry.options)
                try:
                    dashboards = _parse_yaml_mapping(
                        options.get(CONF_DASHBOARDS_YAML, "")
                    )
                    default_dashboards = _parse_yaml_mapping(
                        options.get(CONF_DEFAULT_DASHBOARD_YAML, "")
                    )
                except (TypeError, yaml.YAMLError):
                    errors[CONF_SELECTED_DASHBOARD] = "invalid_yaml"
                    dashboards = {}
                    default_dashboards = {}

            if not errors and user_input is not None:
                dashboard_config = dashboards.setdefault(dashboard_id, {})
                groups = dashboard_config.setdefault("groups", [])
                if group not in groups:
                    groups.append(group)

                options[CONF_DASHBOARDS_YAML] = yaml.safe_dump(
                    dashboards,
                    allow_unicode=True,
                    sort_keys=False,
                )

                if set_as_default:
                    default_dashboards[group] = dashboard_id
                    options[CONF_DEFAULT_DASHBOARD_YAML] = yaml.safe_dump(
                        default_dashboards,
                        allow_unicode=True,
                        sort_keys=False,
                    )

                return self.async_create_entry(title="", data=options)

        dashboard_choices = await _async_dashboard_choices(
            self.hass, self._config_entry.options
        )
        if not dashboard_choices:
            errors["base"] = "no_dashboards_found"

        return self.async_show_form(
            step_id="assign_dashboard_group",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SELECTED_DASHBOARD): vol.In(dashboard_choices),
                    vol.Required(CONF_ASSIGNED_GROUP): TEXT_SELECTOR,
                    vol.Optional(CONF_SET_AS_DEFAULT, default=False): bool,
                }
            ),
            errors=errors,
        )


def _data_schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Return the form schema with current values as defaults."""
    values = values or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_USERS_YAML,
                default=values.get(CONF_USERS_YAML, DEFAULT_USERS_YAML),
            ): MULTILINE_TEXT_SELECTOR,
            vol.Optional(
                CONF_GROUPS_YAML,
                default=values.get(CONF_GROUPS_YAML, DEFAULT_GROUPS_YAML),
            ): MULTILINE_TEXT_SELECTOR,
            vol.Optional(
                CONF_DASHBOARDS_YAML,
                default=values.get(CONF_DASHBOARDS_YAML, DEFAULT_DASHBOARDS_YAML),
            ): MULTILINE_TEXT_SELECTOR,
            vol.Optional(
                CONF_DEFAULT_DASHBOARD_YAML,
                default=values.get(
                    CONF_DEFAULT_DASHBOARD_YAML, DEFAULT_DASHBOARD_YAML
                ),
            ): MULTILINE_TEXT_SELECTOR,
            vol.Optional(
                OPT_HIDE_SIDEBAR_ITEMS,
                default=values.get(
                    OPT_HIDE_SIDEBAR_ITEMS, DEFAULT_OPTIONS[OPT_HIDE_SIDEBAR_ITEMS]
                ),
            ): bool,
            vol.Optional(
                OPT_REDIRECT_BLOCKED_DASHBOARDS,
                default=values.get(
                    OPT_REDIRECT_BLOCKED_DASHBOARDS,
                    DEFAULT_OPTIONS[OPT_REDIRECT_BLOCKED_DASHBOARDS],
                ),
            ): bool,
            vol.Optional(
                OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN,
                default=values.get(
                    OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN,
                    DEFAULT_OPTIONS[OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN],
                ),
            ): bool,
            vol.Optional(
                OPT_DEBUG,
                default=values.get(OPT_DEBUG, DEFAULT_OPTIONS[OPT_DEBUG]),
            ): bool,
        }
    )


def _validate_user_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate YAML snippets from the form."""
    errors: dict[str, str] = {}

    for field in (
        CONF_USERS_YAML,
        CONF_GROUPS_YAML,
        CONF_DASHBOARDS_YAML,
        CONF_DEFAULT_DASHBOARD_YAML,
    ):
        try:
            value = _parse_yaml_mapping(user_input.get(field, ""))
        except (TypeError, yaml.YAMLError):
            errors[field] = "invalid_yaml"
            continue

        if field == CONF_USERS_YAML:
            for user_config in value.values():
                if not isinstance(user_config, dict) or not (
                    user_config.get("role")
                    or user_config.get("group")
                    or user_config.get("groups")
                ):
                    errors[field] = "invalid_users"
                    break

        if field == CONF_GROUPS_YAML:
            for group_config in value.values():
                users = (
                    group_config.get("users")
                    if isinstance(group_config, dict)
                    else None
                )
                if not isinstance(users, list) or not all(
                    isinstance(user, str) for user in users
                ):
                    errors[field] = "invalid_groups"
                    break

        if field == CONF_DASHBOARDS_YAML:
            for dashboard_config in value.values():
                if not isinstance(dashboard_config, dict):
                    errors[field] = "invalid_dashboards"
                    break
                roles = dashboard_config.get("roles", [])
                groups = dashboard_config.get("groups", [])
                if not roles and not groups:
                    errors[field] = "invalid_dashboards"
                    break
                if not isinstance(roles, list) or not isinstance(groups, list):
                    errors[field] = "invalid_dashboards"
                    break
                if not all(isinstance(role, str) for role in roles):
                    errors[field] = "invalid_dashboards"
                    break
                if not all(isinstance(group, str) for group in groups):
                    errors[field] = "invalid_dashboards"
                    break

        if field == CONF_DEFAULT_DASHBOARD_YAML:
            if not all(isinstance(key, str) and isinstance(val, str) for key, val in value.items()):
                errors[field] = "invalid_defaults"

    return errors


def _parse_yaml_mapping(value: str) -> dict[str, Any]:
    """Parse a YAML text field and require a mapping."""
    parsed = yaml.safe_load(value.strip() or "{}")
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise TypeError("Expected a YAML mapping")
    return parsed


async def _async_user_choices(hass) -> dict[str, str]:
    """Return Home Assistant users as selector choices."""
    users = await hass.auth.async_get_users()
    choices: dict[str, str] = {}

    for user in users:
        user_id = getattr(user, "id", "")
        if not user_id:
            continue

        name = getattr(user, CONF_NAME, None) or getattr(user, "name", None) or user_id
        choices[user_id] = f"{name} ({user_id})"

    return choices


async def _async_dashboard_choices(hass, options: dict[str, Any]) -> dict[str, str]:
    """Return known Home Assistant dashboards as selector choices."""
    choices: dict[str, str] = {"lovelace": "Overview (/lovelace)"}

    _collect_dashboard_choices(hass.data.get("lovelace"), choices)
    _collect_dashboard_choices(hass.data.get("frontend_panels"), choices)

    try:
        configured_dashboards = _parse_yaml_mapping(
            options.get(CONF_DASHBOARDS_YAML, "")
        )
    except (TypeError, yaml.YAMLError):
        configured_dashboards = {}

    for dashboard_id in configured_dashboards:
        normalized = _normalize_dashboard_id(str(dashboard_id))
        if normalized:
            choices.setdefault(normalized, f"{normalized} (configured)")

    return dict(sorted(choices.items(), key=lambda item: item[1].lower()))


def _collect_dashboard_choices(
    source: Any, choices: dict[str, str], depth: int = 0
) -> None:
    """Collect dashboard-like url paths from HA internals without version locks."""
    if source is None or depth > 4:
        return

    if isinstance(source, dict):
        values = source.values()
        for key, value in source.items():
            if isinstance(key, str):
                _add_dashboard_choice(key, value, choices)
            if isinstance(value, (str, int, float, bool)) or value is None:
                continue
            _collect_dashboard_choices(value, choices, depth + 1)
        return

    if isinstance(source, (list, tuple, set)):
        for item in source:
            _collect_dashboard_choices(item, choices, depth + 1)
        return

    for attr in ("dashboards", "url_path", "urlPath", "path", "id", "title"):
        if hasattr(source, attr):
            value = getattr(source, attr)
            if attr == "dashboards":
                _collect_dashboard_choices(value, choices, depth + 1)
            else:
                _add_dashboard_choice(str(value), source, choices)


def _add_dashboard_choice(
    raw_dashboard_id: str, source: Any, choices: dict[str, str]
) -> None:
    """Add one dashboard id if it looks like a dashboard url path."""
    dashboard_id = _normalize_dashboard_id(raw_dashboard_id)
    if not dashboard_id:
        return

    title = _dashboard_title(source) or dashboard_id
    choices.setdefault(dashboard_id, f"{title} (/{dashboard_id})")


def _normalize_dashboard_id(value: str) -> str:
    """Normalize HA dashboard path/id to the first URL segment."""
    dashboard_id = value.strip().strip("/")
    if not dashboard_id:
        return ""

    dashboard_id = dashboard_id.split("/")[0]
    if dashboard_id == "lovelace" or dashboard_id.startswith(
        ("lovelace-", "dashboard-")
    ):
        return dashboard_id

    return ""


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
