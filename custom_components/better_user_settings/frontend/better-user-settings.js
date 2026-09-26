/* Better User Settings global sidebar filter. */

(() => {
  if (window.__betterUserSettingsLoaded) {
    return;
  }
  window.__betterUserSettingsLoaded = true;

  const API_PATH = "better_user_settings/permissions";
  const RETRY_DELAY_MS = 1000;
  const MAX_BOOT_RETRIES = 30;

  const state = {
    permissions: null,
    observer: null,
    retryCount: 0,
  };

  function installStyles() {
    if (document.getElementById("better-user-settings-style")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "better-user-settings-style";
    style.textContent = `
      [data-bus-hidden="true"] {
        display: none !important;
      }
    `;
    document.head.appendChild(style);
  }

  function debug(...args) {
    if (state.permissions?.options?.debug) {
      console.debug("[better-user-settings]", ...args);
    }
  }

  function normalizePath(value) {
    if (!value || typeof value !== "string") {
      return "";
    }
    let path = value.trim();
    try {
      if (path.startsWith("http://") || path.startsWith("https://")) {
        path = new URL(path).pathname;
      }
    } catch (_err) {
      return "";
    }
    path = path.split("?")[0].split("#")[0];
    if (!path.startsWith("/")) {
      path = `/${path}`;
    }
    return path.replace(/\/+$/, "") || "/";
  }

  function dashboardRoot(pathname) {
    const path = normalizePath(pathname);
    const segment = path.split("/").filter(Boolean)[0] || "";
    if (
      segment === "lovelace" ||
      segment.startsWith("lovelace-") ||
      segment.startsWith("dashboard-")
    ) {
      return `/${segment}`;
    }
    return "";
  }

  function isAllowedDashboard(pathname) {
    if (state.permissions?.is_admin) {
      return true;
    }
    const root = dashboardRoot(pathname);
    if (!root) {
      return true;
    }
    return new Set(state.permissions?.allowed_dashboard_paths || []).has(root);
  }

  function isHiddenSidebarPath(pathname) {
    if (state.permissions?.is_admin) {
      return false;
    }
    const path = normalizePath(pathname);
    if (!path) {
      return false;
    }
    return (state.permissions?.hidden_sidebar_paths || []).some(
      (hiddenPath) => path === hiddenPath || path.startsWith(`${hiddenPath}/`)
    );
  }

  function hrefForElement(element) {
    return (
      element?.getAttribute?.("href") ||
      element?.getAttribute?.("path") ||
      element?.href ||
      element?.path ||
      element?.item?.href ||
      element?.item?.path ||
      element?.getAttribute?.("data-panel") ||
      ""
    );
  }

  function isNavigableSidebarElement(element) {
    if (!element?.matches) {
      return false;
    }
    if (element.matches("a[href]")) {
      return true;
    }
    if (
      element.matches(
        "ha-sidebar-item, ha-md-list-item, ha-list-item, paper-icon-item, mwc-list-item, sl-menu-item, ha-button-menu-item, [href], [path]"
      ) &&
      hrefForElement(element)
    ) {
      return true;
    }
    return false;
  }

  function closestSidebarItem(anchor) {
    return (
      anchor.closest("ha-sidebar-item") ||
      anchor.closest("ha-md-list-item") ||
      anchor.closest("ha-list-item") ||
      anchor.closest("paper-icon-item") ||
      anchor.closest("mwc-list-item") ||
      anchor.closest("sl-menu-item") ||
      anchor.closest("a") ||
      anchor
    );
  }

  function hideElement(element) {
    if (!element || element.dataset.bdrHidden === "true") {
      return;
    }
    element.dataset.bdrHidden = "true";
    element.dataset.busHidden = "true";
    element.dataset.bdrPreviousDisplay = element.style.display || "";
    element.style.setProperty("display", "none", "important");
  }

  function showElement(element) {
    if (!element || element.dataset.bdrHidden !== "true") {
      return;
    }
    element.style.display = element.dataset.bdrPreviousDisplay || "";
    delete element.dataset.bdrHidden;
    delete element.dataset.busHidden;
    delete element.dataset.bdrPreviousDisplay;
  }

  function findRoots() {
    const app = document.querySelector("home-assistant");
    const main = app?.shadowRoot?.querySelector("home-assistant-main");
    const mainRoot = main?.shadowRoot;
    const drawer =
      mainRoot?.querySelector("ha-drawer") ||
      mainRoot?.querySelector("app-drawer") ||
      mainRoot;
    return [document, app?.shadowRoot, mainRoot, drawer?.shadowRoot, drawer].filter(
      (root, index, roots) => root && roots.indexOf(root) === index
    );
  }

  function collectSidebarElements(root) {
    const elements = [];
    const visited = new Set();

    function walk(node) {
      if (!node || visited.has(node)) {
        return;
      }
      visited.add(node);
      if (node.nodeType === Node.ELEMENT_NODE && isNavigableSidebarElement(node)) {
        elements.push(node);
      }
      if (!node.querySelectorAll) {
        return;
      }
      for (const element of node.querySelectorAll("*")) {
        if (isNavigableSidebarElement(element)) {
          elements.push(element);
        }
        if (element.shadowRoot) {
          walk(element.shadowRoot);
        }
      }
    }

    walk(root);
    return Array.from(new Set(elements));
  }

  function filterSidebar() {
    if (!state.permissions || state.permissions.options?.hide_sidebar_items === false) {
      return;
    }

    let checked = 0;
    for (const root of findRoots()) {
      for (const element of collectSidebarElements(root)) {
        const href = hrefForElement(element);
        const dashboardPath = dashboardRoot(href);
        const shouldCheck = dashboardPath || isHiddenSidebarPath(href);
        if (!shouldCheck) {
          continue;
        }
        checked += 1;
        const item = closestSidebarItem(element);
        if (dashboardPath && !isAllowedDashboard(href)) {
          hideElement(item);
        } else if (isHiddenSidebarPath(href)) {
          hideElement(item);
        } else {
          showElement(item);
        }
      }
    }
    debug("sidebar filtered", { checked });
  }

  function redirectIfBlocked() {
    if (
      state.permissions?.options?.redirect_blocked_dashboards === false ||
      isAllowedDashboard(window.location.pathname)
    ) {
      return;
    }
    const target = state.permissions.allowed_dashboard_paths?.[0];
    if (!target || normalizePath(window.location.pathname) === target) {
      return;
    }
    history.replaceState(null, "", target);
    window.dispatchEvent(new Event("location-changed"));
  }

  function applyRules() {
    try {
      redirectIfBlocked();
      filterSidebar();
    } catch (err) {
      console.warn("[better-user-settings] failed to apply rules", err);
    }
  }

  function debugState() {
    const entries = [];
    for (const root of findRoots()) {
      for (const element of collectSidebarElements(root)) {
        entries.push({
          tag: element.localName,
          href: hrefForElement(element),
          text: (element.textContent || "").trim(),
          hidden: element.dataset?.busHidden === "true",
        });
      }
    }
    return {
      permissions: state.permissions,
      entries,
    };
  }

  function startObserver() {
    if (state.observer) {
      return;
    }
    state.observer = new MutationObserver(() => requestAnimationFrame(applyRules));
    state.observer.observe(document.documentElement, { childList: true, subtree: true });
    window.addEventListener("location-changed", applyRules);
    window.addEventListener("popstate", applyRules);
  }

  async function fetchPermissions() {
    const app = document.querySelector("home-assistant");
    const hass = app?.hass;
    if (hass?.callApi) {
      return hass.callApi("GET", API_PATH);
    }

    throw new Error("Home Assistant frontend API is not ready");
  }

  async function boot() {
    try {
      state.permissions = await fetchPermissions();
      installStyles();
      window.betterUserSettingsDebug = debugState;
      debug("permissions loaded", {
        userId: state.permissions.user_id,
        isAdmin: state.permissions.is_admin,
        groups: state.permissions.groups,
        allowedDashboards: state.permissions.allowed_dashboard_paths,
        hiddenDashboards: state.permissions.hidden_dashboard_paths,
        hiddenSidebar: state.permissions.hidden_sidebar_paths,
      });
      startObserver();
      applyRules();
      setTimeout(applyRules, 500);
      setTimeout(applyRules, 2000);
      setInterval(async () => {
        state.permissions = await fetchPermissions();
        applyRules();
      }, 10000);
    } catch (err) {
      state.retryCount += 1;
      if (state.retryCount <= MAX_BOOT_RETRIES) {
        setTimeout(boot, RETRY_DELAY_MS);
        return;
      }
      console.warn("[better-user-settings] could not load permissions", err);
    }
  }

  boot();
})();
