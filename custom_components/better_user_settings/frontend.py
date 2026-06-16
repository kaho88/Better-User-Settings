"""Frontend registration for Better User Settings."""

from __future__ import annotations

import logging
from pathlib import Path
from inspect import isawaitable

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    ADMIN_PANEL_ELEMENT,
    ADMIN_PANEL_PATH,
    ADMIN_PANEL_URL,
    DOMAIN,
    SIDEBAR_SCRIPT_URL,
    STATIC_URL,
)

_LOGGER = logging.getLogger(__name__)
_REGISTERED_KEY = f"{DOMAIN}_frontend_registered"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve frontend files, register admin panel and load global script."""
    if hass.data.get(_REGISTERED_KEY):
        return

    static_path = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(static_path), cache_headers=False)]
    )

    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=ADMIN_PANEL_PATH,
        webcomponent_name=ADMIN_PANEL_ELEMENT,
        sidebar_title="User Settings",
        sidebar_icon="mdi:view-dashboard-edit",
        module_url=ADMIN_PANEL_URL,
        embed_iframe=False,
        require_admin=True,
        config_panel_domain=DOMAIN,
    )

    await _async_register_global_sidebar_script(hass)
    hass.data[_REGISTERED_KEY] = True


async def _async_register_global_sidebar_script(hass: HomeAssistant) -> None:
    """Register the sidebar script as a global Home Assistant frontend asset."""
    try:
        from homeassistant.components.frontend import async_register_extra_module_url

        result = async_register_extra_module_url(hass, SIDEBAR_SCRIPT_URL)
        if isawaitable(result):
            await result
        _LOGGER.debug("Registered Better User Settings as frontend module")
        return
    except (ImportError, AttributeError):
        pass

    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, SIDEBAR_SCRIPT_URL)
        _LOGGER.debug("Registered Better User Settings as frontend JS URL")
        return
    except (ImportError, AttributeError):
        _LOGGER.warning(
            "Could not globally register frontend script. Add this fallback to "
            "configuration.yaml: frontend: extra_module_url: [%s]",
            SIDEBAR_SCRIPT_URL,
        )
