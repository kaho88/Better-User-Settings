"""Constants for Better User Settings."""

DOMAIN = "better_user_settings"
OLD_DOMAIN = "better_dashboard_roles"

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN
OLD_STORAGE_KEY = OLD_DOMAIN

CONF_USERS = "users"
CONF_GROUPS = "groups"
CONF_DASHBOARDS = "dashboards"
CONF_SIDEBAR_ITEMS = "sidebar_items"
CONF_DEFAULT_DASHBOARD = "default_dashboard"
CONF_OPTIONS = "options"

CONF_GROUP = "group"
CONF_ROLE = "role"
CONF_GROUPS_LIST = "groups"
CONF_ROLES = "roles"

CONF_USERS_YAML = "users_yaml"
CONF_GROUPS_YAML = "groups_yaml"
CONF_DASHBOARDS_YAML = "dashboards_yaml"
CONF_DEFAULT_DASHBOARD_YAML = "default_dashboard_yaml"

OPT_HIDE_SIDEBAR_ITEMS = "hide_sidebar_items"
OPT_REDIRECT_BLOCKED_DASHBOARDS = "redirect_blocked_dashboards"
OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN = "hide_admin_menu_for_non_admin"
OPT_DEBUG = "debug"

DEFAULT_ROLE = "guest"

STATIC_URL = f"/{DOMAIN}_static"
SIDEBAR_SCRIPT_URL = f"{STATIC_URL}/better-user-settings.js"
ADMIN_PANEL_URL = f"{STATIC_URL}/admin-panel.js"
ADMIN_PANEL_PATH = "better-user-settings"
ADMIN_PANEL_ELEMENT = "better-user-settings-panel"

DEFAULT_OPTIONS = {
    OPT_HIDE_SIDEBAR_ITEMS: True,
    OPT_REDIRECT_BLOCKED_DASHBOARDS: True,
    OPT_HIDE_ADMIN_MENU_FOR_NON_ADMIN: True,
    OPT_DEBUG: False,
}

DEFAULT_USERS_YAML = "{}\n"

DEFAULT_GROUPS_YAML = """garten:
  users:
    - schwiegervater
    - schwiegermutter
admins:
  users:
    - daniel
"""

DEFAULT_DASHBOARDS_YAML = """lovelace-garten:
  groups:
    - garten
    - admins
lovelace-wohnung:
  groups:
    - admins
    - wohnung
"""

DEFAULT_DASHBOARD_YAML = """garten: lovelace-garten
admins: lovelace-wohnung
wohnung: lovelace-wohnung
"""
