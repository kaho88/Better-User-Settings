/* Better User Settings global sidebar filter. */

(() => {
  if (window.__betterUserSettingsLoaded) {
    return;
  }
  window.__betterUserSettingsLoaded = true;

  const API_URL = "/api/better_user_settings/permissions";
  const RETRY_DELAY_MS = 1000;
  const MAX_BOOT_RETRIES = 30;

  const state = {
    permissions: null,
    observer: null,
    retryCount: 0,
  };

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

  function closestSidebarItem(anchor) {
    return (
      anchor.closest("ha-sidebar-item") ||
      anchor.closest("paper-icon-item") ||
      anchor.closest("a") ||
      anchor
    );
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
      if (!node.querySelectorAll) {
        return;
      }
      for (const element of node.querySelectorAll("*")) {
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

  function filterSidebar() {
    if (!state.permissions || state.permissions.options?.hide_sidebar_items === false) {
      return;
    }

    let checked = 0;
    for (const root of findRoots()) {
      for (const anchor of collectAnchors(root)) {
        const href = anchor.getAttribute("href") || anchor.href;
        const dashboardPath = dashboardRoot(href);
        const shouldCheck = dashboardPath || isHiddenSidebarPath(href);
        if (!shouldCheck) {
          continue;
        }
        checked += 1;
        const item = closestSidebarItem(anchor);
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

  function startObserver() {
    if (state.observer) {
      return;
    }
    state.observer = new MutationObserver(() => requestAnimationFrame(applyRules));
    state.observer.observe(document.documentElement, { childList: true, subtree: true });
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

  async function fetchPermissions() {
    const response = await fetch(API_URL, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }
    return response.json();
  }

  async function boot() {
    try {
      state.permissions = await fetchPermissions();
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
