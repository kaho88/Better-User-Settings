"""Config flow for Better Dashboard Roles."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
import yaml

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_DASHBOARDS_YAML,
    CONF_DEFAULT_DASHBOARD_YAML,
    CONF_USERS_YAML,
    DEFAULT_DASHBOARD_YAML,
    DEFAULT_DASHBOARDS_YAML,
    DEFAULT_OPTIONS,
    DEFAULT_USERS_YAML,
    DOMAIN,
    OPT_DEBUG,
    OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN,
    OPT_HIDE_SIDEBAR_ITEMS,
    OPT_REDIRECT_BLOCKED_DASHBOARDS,
)

CONF_ASSIGNED_ROLE = "assigned_role"
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
            menu_options=["assign_user", "edit_all"],
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

    async def async_step_assign_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Assign a role to one Home Assistant user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            role = user_input.get(CONF_ASSIGNED_ROLE, "").strip()
            user_key = user_input.get(CONF_SELECTED_USER)

            if not role:
                errors[CONF_ASSIGNED_ROLE] = "missing_role"
            elif not user_key:
                errors[CONF_SELECTED_USER] = "missing_user"
            else:
                options = dict(self._config_entry.options)
                try:
                    users = _parse_yaml_mapping(options.get(CONF_USERS_YAML, ""))
                except (TypeError, yaml.YAMLError):
                    errors[CONF_SELECTED_USER] = "invalid_yaml"
                    users = {}

            if not errors and user_input is not None:
                users[user_key] = {"role": role}
                options[CONF_USERS_YAML] = yaml.safe_dump(
                    users,
                    allow_unicode=True,
                    sort_keys=False,
                )
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="assign_user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SELECTED_USER): vol.In(
                        await _async_user_choices(self.hass)
                    ),
                    vol.Required(CONF_ASSIGNED_ROLE): TEXT_SELECTOR,
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
                if not isinstance(user_config, dict) or not user_config.get("role"):
                    errors[field] = "invalid_users"
                    break

        if field == CONF_DASHBOARDS_YAML:
            for dashboard_config in value.values():
                roles = (
                    dashboard_config.get("roles")
                    if isinstance(dashboard_config, dict)
                    else None
                )
                if not isinstance(roles, list) or not all(
                    isinstance(role, str) for role in roles
                ):
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
