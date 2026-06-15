/* Better Dashboard Roles
 *
 * Frontend-only dashboard filtering for Home Assistant. This is not access
 * control; it only hides sidebar entries and optionally redirects in the UI.
 */

(() => {
  if (window.__betterDashboardRolesLoaded) {
    return;
  }
  window.__betterDashboardRolesLoaded = true;

  const VERSION = "0.1.0";
  const API_URL = "/api/better_dashboard_roles/config";
  const RETRY_DELAY_MS = 1000;
  const MAX_BOOT_RETRIES = 30;
  const ADMIN_ROLE = "admin";
  const ADMIN_PATH_PREFIXES = [
    "/config",
    "/developer-tools",
    "/hassio",
    "/supervisor",
  ];

  const state = {
    config: null,
    observer: null,
    retryCount: 0,
    redirecting: false,
  };

  function debug(...args) {
    if (state.config?.options?.debug) {
      // eslint-disable-next-line no-console
      console.debug("[better-dashboard-roles]", ...args);
    }
  }

  function warn(...args) {
    // eslint-disable-next-line no-console
    console.warn("[better-dashboard-roles]", ...args);
  }

  function normalizePath(value) {
    if (!value || typeof value !== "string") {
      return "";
    }

    let path = value.trim();
    if (!path) {
      return "";
    }

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

  function dashboardIdToPath(dashboardId) {
    return normalizePath(dashboardId);
  }

  function pathToDashboardId(pathname) {
    const path = normalizePath(pathname);
    if (!path || path === "/") {
      return "";
    }

    const firstSegment = path.split("/").filter(Boolean)[0] || "";
    if (!firstSegment) {
      return "";
    }

    if (firstSegment === "lovelace") {
      return "lovelace";
    }

    return firstSegment;
  }

  function isDashboardPath(pathname) {
    const dashboardId = pathToDashboardId(pathname);
    return (
      dashboardId === "lovelace" ||
      dashboardId.startsWith("lovelace-") ||
      dashboardId.startsWith("dashboard-")
    );
  }

  function currentDashboardId() {
    return pathToDashboardId(window.location.pathname);
  }

  function allowedDashboardSet() {
    return new Set(state.config?.allowed_dashboards || []);
  }

  function isAllowedDashboard(dashboardId) {
    if (!dashboardId) {
      return true;
    }

    const allowed = allowedDashboardSet();
    return allowed.has(dashboardId);
  }

  function defaultDashboardPath() {
    const dashboardId = state.config?.default_dashboard;
    if (!dashboardId) {
      return "";
    }

    return dashboardIdToPath(dashboardId);
  }

  function hideElement(element) {
    if (!element || element.dataset.bdrHidden === "true") {
      return;
    }

    element.dataset.bdrHidden = "true";
    element.dataset.bdrPreviousDisplay = element.style.display || "";
    element.style.setProperty("display", "none", "important");
  }

  function showElement(element) {
    if (!element || element.dataset.bdrHidden !== "true") {
      return;
    }

    element.style.display = element.dataset.bdrPreviousDisplay || "";
    delete element.dataset.bdrHidden;
    delete element.dataset.bdrPreviousDisplay;
  }

  function closestSidebarItem(anchor) {
    return (
      anchor.closest("a") ||
      anchor.closest("paper-icon-item") ||
      anchor.closest("ha-sidebar-item") ||
      anchor
    );
  }

  function shouldHideHref(href) {
    const path = normalizePath(href);
    if (!path) {
      return false;
    }

    if (isDashboardPath(path)) {
      return !isAllowedDashboard(pathToDashboardId(path));
    }

    if (
      state.config?.options?.hide_admin_menu_for_non_admin &&
      !isAdminPrincipal()
    ) {
      return ADMIN_PATH_PREFIXES.some(
        (prefix) => path === prefix || path.startsWith(`${prefix}/`)
      );
    }

    return false;
  }

  function isAdminPrincipal() {
    const groups = state.config?.groups || [];
    return (
      state.config?.role === ADMIN_ROLE ||
      state.config?.primary_group === ADMIN_ROLE ||
      state.config?.primary_group === "admins" ||
      groups.includes(ADMIN_ROLE) ||
      groups.includes("admins")
    );
  }

  function findSidebarRoots() {
    const roots = [];
    const app = document.querySelector("home-assistant");
    const main = app?.shadowRoot?.querySelector("home-assistant-main");
    const mainRoot = main?.shadowRoot;
    const drawer =
      mainRoot?.querySelector("ha-drawer") ||
      mainRoot?.querySelector("app-drawer") ||
      mainRoot;

    for (const root of [document, app?.shadowRoot, mainRoot, drawer?.shadowRoot, drawer]) {
      if (root && !roots.includes(root)) {
        roots.push(root);
      }
    }

    return roots;
  }

  function filterSidebar() {
    if (!state.config?.options?.hide_sidebar_items) {
      return;
    }

    const roots = findSidebarRoots();
    let checked = 0;

    for (const root of roots) {
      for (const anchor of collectAnchors(root)) {
        checked += 1;
        const item = closestSidebarItem(anchor);
        if (shouldHideHref(anchor.getAttribute("href") || anchor.href)) {
          hideElement(item);
        } else {
          showElement(item);
        }
      }
    }

    debug("sidebar filtered", { checked });
  }

  function collectAnchors(root) {
    const anchors = [];
    const visited = new Set();

    function walk(node) {
      if (!node || visited.has(node)) {
        return;
      }
      visited.add(node);

      if (node.nodeType === Node.ELEMENT_NODE && node.matches?.("a[href]")) {
        anchors.push(node);
      }

      const queryRoot =
        node.nodeType === Node.DOCUMENT_NODE ||
        node.nodeType === Node.DOCUMENT_FRAGMENT_NODE ||
        node.nodeType === Node.ELEMENT_NODE
          ? node
          : null;

      if (!queryRoot?.querySelectorAll) {
        return;
      }

      for (const element of queryRoot.querySelectorAll("*")) {
        if (element.matches?.("a[href]")) {
          anchors.push(element);
        }
        if (element.shadowRoot) {
          walk(element.shadowRoot);
        }
      }
    }

    walk(root);
    return Array.from(new Set(anchors));
  }

  function redirectIfBlocked() {
    if (!state.config?.options?.redirect_blocked_dashboards || state.redirecting) {
      return;
    }

    const dashboardId = currentDashboardId();
    if (!dashboardId || !isDashboardPath(window.location.pathname)) {
      return;
    }

    if (isAllowedDashboard(dashboardId)) {
      return;
    }

    const target = defaultDashboardPath();
    if (!target || normalizePath(window.location.pathname) === target) {
      debug("blocked dashboard without redirect target", { dashboardId, target });
      return;
    }

    state.redirecting = true;
    debug("redirecting blocked dashboard", { dashboardId, target });
    history.replaceState(null, "", target);
    window.dispatchEvent(new Event("location-changed"));
    setTimeout(() => {
      state.redirecting = false;
      filterSidebar();
    }, 250);
  }

  function applyRules() {
    try {
      redirectIfBlocked();
      filterSidebar();
    } catch (err) {
      warn("failed to apply frontend rules", err);
    }
  }

  function startObserver() {
    if (state.observer) {
      return;
    }

    state.observer = new MutationObserver(() => {
      window.requestAnimationFrame(applyRules);
    });
    state.observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });

    window.addEventListener("location-changed", applyRules);
    window.addEventListener("popstate", applyRules);

    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    history.pushState = function patchedPushState(...args) {
      const result = originalPushState.apply(this, args);
      window.dispatchEvent(new Event("location-changed"));
      return result;
    };

    history.replaceState = function patchedReplaceState(...args) {
      const result = originalReplaceState.apply(this, args);
      window.dispatchEvent(new Event("location-changed"));
      return result;
    };
  }

  async function fetchConfig() {
    const response = await fetch(API_URL, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    return response.json();
  }

  function frontendUserName() {
    const app = document.querySelector("home-assistant");
    const hass = app?.hass;
    return hass?.user?.name || hass?.connection?.options?.auth?.data?.hassUrl || null;
  }

  async function boot() {
    try {
      state.config = await fetchConfig();
      debug("loaded", {
        version: VERSION,
        backendUser: state.config.username,
        frontendUser: frontendUserName(),
        role: state.config.role,
        allowedDashboards: state.config.allowed_dashboards,
      });

      startObserver();
      applyRules();
      window.setTimeout(applyRules, 500);
      window.setTimeout(applyRules, 2000);
      window.setInterval(applyRules, 3000);
    } catch (err) {
      state.retryCount += 1;
      if (state.retryCount <= MAX_BOOT_RETRIES) {
        window.setTimeout(boot, RETRY_DELAY_MS);
        return;
      }

      warn("could not load backend config", err);
    }
  }

  boot();
})();
