class BetterUserSettingsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._tab = "groups";
    this._groups = {};
    this._users = [];
    this._dashboards = [];
    this._sidebarItems = [];
    this._selectedGroup = "";
    this._selectedDashboard = "";
    this._selectedSidebarItem = "";
    this._message = "";
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      this._loadAll();
    }
  }

  async _callWS(message) {
    return this._hass.callWS(message);
  }

  async _loadAll() {
    const [groupsResult, dashboardsResult, sidebarResult] = await Promise.all([
      this._callWS({ type: "better_user_settings/get_groups" }),
      this._callWS({ type: "better_user_settings/get_dashboards" }),
      this._callWS({ type: "better_user_settings/get_sidebar_items" }),
    ]);
    this._groups = groupsResult.groups || {};
    this._users = groupsResult.users || [];
    this._dashboards = dashboardsResult.dashboards || [];
    this._sidebarItems = sidebarResult.sidebar_items || [];
    this._selectedGroup = this._selectedGroup || Object.keys(this._groups)[0] || "";
    this._selectedDashboard =
      this._selectedDashboard || this._dashboards[0]?.path || "";
    this._selectedSidebarItem =
      this._selectedSidebarItem || this._sidebarItems[0]?.path || "";
    this._render();
  }

  _hasGroup(groupId) {
    return Object.prototype.hasOwnProperty.call(this._groups, groupId);
  }

  _groupOptions() {
    return Object.entries(this._groups)
      .sort((a, b) => (a[1].name || a[0]).localeCompare(b[1].name || b[0]))
      .map(
        ([id, group]) =>
          `<option value="${this._escape(id)}" ${id === this._selectedGroup ? "selected" : ""}>${this._escape(group.name || id)}</option>`
      )
      .join("");
  }

  _selectedGroupUsers() {
    return new Set(this._groups[this._selectedGroup]?.users || []);
  }

  _selectedDashboardGroups() {
    const dashboard = this._dashboards.find((item) => item.path === this._selectedDashboard);
    return new Set(dashboard?.allowed_groups || []);
  }

  _selectedSidebarGroups() {
    const item = this._sidebarItems.find((entry) => entry.path === this._selectedSidebarItem);
    return new Set(item?.allowed_groups || []);
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          color: var(--primary-text-color);
          background: var(--primary-background-color);
          min-height: 100vh;
        }
        .wrap {
          max-width: 1120px;
          margin: 0 auto;
          padding: 24px;
        }
        h1 {
          font-size: 24px;
          font-weight: 500;
          margin: 0 0 20px;
        }
        .tabs {
          display: flex;
          gap: 8px;
          border-bottom: 1px solid var(--divider-color);
          margin-bottom: 20px;
        }
        button {
          border: 0;
          border-radius: 4px;
          padding: 10px 14px;
          cursor: pointer;
          color: var(--primary-text-color);
          background: var(--secondary-background-color);
        }
        button.primary {
          color: var(--text-primary-color);
          background: var(--primary-color);
        }
        button.tab {
          border-bottom: 3px solid transparent;
          background: transparent;
          border-radius: 0;
        }
        button.tab.active {
          border-color: var(--primary-color);
          color: var(--primary-color);
        }
        .panel {
          display: grid;
          grid-template-columns: minmax(260px, 360px) 1fr;
          gap: 24px;
          align-items: start;
        }
        .box {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
          padding: 16px;
        }
        label {
          display: block;
          font-size: 13px;
          color: var(--secondary-text-color);
          margin: 0 0 6px;
        }
        input, select {
          box-sizing: border-box;
          width: 100%;
          min-height: 40px;
          color: var(--primary-text-color);
          background: var(--secondary-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          padding: 8px;
        }
        select[multiple] {
          min-height: 280px;
        }
        .field {
          margin-bottom: 14px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
        }
        th, td {
          padding: 10px 8px;
          border-bottom: 1px solid var(--divider-color);
          text-align: left;
          vertical-align: top;
        }
        th {
          color: var(--secondary-text-color);
          font-weight: 500;
        }
        .message {
          min-height: 22px;
          color: var(--primary-color);
          margin-top: 12px;
        }
        @media (max-width: 760px) {
          .wrap { padding: 16px; }
          .panel { grid-template-columns: 1fr; }
        }
      </style>
      <div class="wrap">
        <h1>Better User Settings</h1>
        <div class="tabs">
          <button class="tab ${this._tab === "groups" ? "active" : ""}" data-tab="groups">Gruppen</button>
          <button class="tab ${this._tab === "dashboards" ? "active" : ""}" data-tab="dashboards">Dashboards</button>
          <button class="tab ${this._tab === "sidebar" ? "active" : ""}" data-tab="sidebar">Sidebar</button>
        </div>
        ${this._renderActiveTab()}
        <div class="message">${this._escape(this._message)}</div>
      </div>
    `;
    this._syncSelectValues();
    this._bindEvents();
  }

  _syncSelectValues() {
    const groupSelect = this.shadowRoot.querySelector("#group-select");
    if (groupSelect && this._selectedGroup) {
      groupSelect.value = this._selectedGroup;
    }
    const dashboardSelect = this.shadowRoot.querySelector("#dashboard-select");
    if (dashboardSelect && this._selectedDashboard) {
      dashboardSelect.value = this._selectedDashboard;
    }
    const sidebarSelect = this.shadowRoot.querySelector("#sidebar-select");
    if (sidebarSelect && this._selectedSidebarItem) {
      sidebarSelect.value = this._selectedSidebarItem;
    }
  }

  _renderActiveTab() {
    if (this._tab === "groups") {
      return this._renderGroups();
    }
    if (this._tab === "sidebar") {
      return this._renderSidebar();
    }
    return this._renderDashboards();
  }

  _renderGroups() {
    const selectedUsers = this._selectedGroupUsers();
    const selectedGroupId = this._hasGroup(this._selectedGroup)
      ? this._selectedGroup
      : Object.keys(this._groups)[0] || "";
    this._selectedGroup = selectedGroupId;
    const group = this._groups[selectedGroupId] || { name: "", users: [] };
    return `
      <div class="panel">
        <div class="box">
          <div class="field">
            <label>Gruppe</label>
            <select id="group-select">
              ${this._groupOptions()}
            </select>
          </div>
          <div class="field">
            <label>Neue Gruppen-ID</label>
            <input id="new-group-id" placeholder="garten">
          </div>
          <div class="field">
            <label>Name</label>
            <input id="group-name" value="${this._escape(group.name || selectedGroupId)}">
          </div>
          <button class="primary" id="save-group">Speichern</button>
        </div>
        <div class="box">
          <div class="field">
            <label>Benutzer</label>
            <select id="group-users" multiple>
              ${this._users
                .map(
                  (user) =>
                    `<option value="${user.id}" ${selectedUsers.has(user.id) ? "selected" : ""}>${this._escape(user.name)} (${this._escape(user.id)})</option>`
                )
                .join("")}
            </select>
          </div>
        </div>
      </div>
    `;
  }

  _renderDashboards() {
    const selectedGroups = this._selectedDashboardGroups();
    return `
      <div class="panel">
        <div class="box">
          <div class="field">
            <label>Dashboard</label>
            <select id="dashboard-select">
              ${this._dashboards
                .map(
                  (dashboard) =>
                    `<option value="${dashboard.path}" ${dashboard.path === this._selectedDashboard ? "selected" : ""}>${this._escape(dashboard.title)} (${this._escape(dashboard.path)})</option>`
                )
                .join("")}
            </select>
          </div>
          <div class="field">
            <label>Erlaubte Gruppen</label>
            <select id="dashboard-groups" multiple>
              ${Object.entries(this._groups)
                .map(
                  ([id, group]) =>
                    `<option value="${id}" ${selectedGroups.has(id) ? "selected" : ""}>${this._escape(group.name || id)}</option>`
                )
                .join("")}
            </select>
          </div>
          <button class="primary" id="save-dashboard">Speichern</button>
        </div>
        <div class="box">
          <table>
            <thead><tr><th>Name</th><th>Pfad</th><th>Gruppen</th></tr></thead>
            <tbody>
              ${this._dashboards
                .map((dashboard) => {
                  const names = (dashboard.allowed_groups || [])
                    .map((id) => this._groups[id]?.name || id)
                    .join(", ");
                  return `<tr><td>${this._escape(dashboard.title)}</td><td>${this._escape(dashboard.path)}</td><td>${this._escape(names || "Offen")}</td></tr>`;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  _renderSidebar() {
    const selectedGroups = this._selectedSidebarGroups();
    return `
      <div class="panel">
        <div class="box">
          <div class="field">
            <label>Sidebar-Eintrag</label>
            <select id="sidebar-select">
              ${this._sidebarItems
                .map(
                  (item) =>
                    `<option value="${item.path}" ${item.path === this._selectedSidebarItem ? "selected" : ""}>${this._escape(item.title)} (${this._escape(item.path)})</option>`
                )
                .join("")}
            </select>
          </div>
          <div class="field">
            <label>Eigener Pfad</label>
            <input id="custom-sidebar-path" placeholder="/map">
          </div>
          <div class="field">
            <label>Erlaubte Gruppen</label>
            <select id="sidebar-groups" multiple>
              ${Object.entries(this._groups)
                .map(
                  ([id, group]) =>
                    `<option value="${id}" ${selectedGroups.has(id) ? "selected" : ""}>${this._escape(group.name || id)}</option>`
                )
                .join("")}
            </select>
          </div>
          <button class="primary" id="save-sidebar">Speichern</button>
        </div>
        <div class="box">
          <table>
            <thead><tr><th>Name</th><th>Pfad</th><th>Gruppen</th></tr></thead>
            <tbody>
              ${this._sidebarItems
                .map((item) => {
                  const names = (item.allowed_groups || [])
                    .map((id) => this._groups[id]?.name || id)
                    .join(", ");
                  return `<tr><td>${this._escape(item.title)}</td><td>${this._escape(item.path)}</td><td>${this._escape(names || "Offen")}</td></tr>`;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  _bindEvents() {
    for (const button of this.shadowRoot.querySelectorAll("button.tab")) {
      button.addEventListener("click", () => {
        this._tab = button.dataset.tab;
        this._render();
      });
    }
    this.shadowRoot.querySelector("#group-select")?.addEventListener("change", (event) => {
      this._selectedGroup = event.target.value;
      this._render();
    });
    this.shadowRoot.querySelector("#dashboard-select")?.addEventListener("change", (event) => {
      this._selectedDashboard = event.target.value;
      this._render();
    });
    this.shadowRoot.querySelector("#sidebar-select")?.addEventListener("change", (event) => {
      this._selectedSidebarItem = event.target.value;
      this._render();
    });
    this.shadowRoot.querySelector("#save-group")?.addEventListener("click", () => this._saveGroup());
    this.shadowRoot
      .querySelector("#save-dashboard")
      ?.addEventListener("click", () => this._saveDashboard());
    this.shadowRoot
      .querySelector("#save-sidebar")
      ?.addEventListener("click", () => this._saveSidebar());
  }

  async _saveGroup() {
    const newId = this.shadowRoot.querySelector("#new-group-id")?.value.trim();
    const groupId = newId || this._selectedGroup;
    const name = this.shadowRoot.querySelector("#group-name")?.value.trim() || groupId;
    const userIds = this._selectedOptions("#group-users");
    await this._callWS({
      type: "better_user_settings/save_group_users",
      group_id: groupId,
      name,
      user_ids: userIds,
    });
    this._selectedGroup = groupId;
    this._message = "Gespeichert";
    await this._loadAll();
  }

  async _saveDashboard() {
    const allowedGroups = this._selectedOptions("#dashboard-groups");
    await this._callWS({
      type: "better_user_settings/save_dashboard_allowed_groups",
      dashboard_path: this._selectedDashboard,
      allowed_groups: allowedGroups,
    });
    this._message = "Gespeichert";
    await this._loadAll();
  }

  async _saveSidebar() {
    const customPath = this.shadowRoot.querySelector("#custom-sidebar-path")?.value.trim();
    const sidebarPath = customPath || this._selectedSidebarItem;
    const allowedGroups = this._selectedOptions("#sidebar-groups");
    await this._callWS({
      type: "better_user_settings/save_sidebar_item_allowed_groups",
      sidebar_path: sidebarPath,
      allowed_groups: allowedGroups,
    });
    this._selectedSidebarItem = sidebarPath.startsWith("/") ? sidebarPath : `/${sidebarPath}`;
    this._message = "Gespeichert";
    await this._loadAll();
  }

  _selectedOptions(selector) {
    return Array.from(this.shadowRoot.querySelector(selector)?.selectedOptions || []).map(
      (option) => option.value
    );
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
}

customElements.define("better-user-settings-panel", BetterUserSettingsPanel);
