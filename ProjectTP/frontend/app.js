(() => {
  const SLOT_START_HOUR = 7;
  const SLOT_COUNT = 11;

  const state = {
    me: null,
    isAdmin: false,
    isRootAdmin: false,
    canManageDuties: false,
    canManageReports: false,
    canManageNotifications: false,
    hasAdminAccess: false,
    employees: [],
    dutiesLoadedForDate: null,
    reportsLoadedKey: null,
    swapInboxTimerId: null,
    currentDutyTimerId: null,
    currentDuties: null,
    slotCount: SLOT_COUNT,
    slotStartHour: SLOT_START_HOUR,
    notificationSettingsReady: false,
    notificationSettingsSaving: false,
    notificationTemplatesReady: false,
    notificationTemplatesSaving: false,
    eeLastQrToken: null,
    dutyViewMode: "table",
    dutyDisplayFilter: "all",
    dutyCalendarRaw: null,
    adminSubtab: "analytics",
    adminUsersPage: 1,
    adminUsersPageSize: 10,
    dutyLeaveCalYear: new Date().getFullYear(),
    dutyLeaveCalMonth: new Date().getMonth(),
    dutyLeaveSelected: new Set(),
    reportsHistory: [],
    resourceCategory: "all",
    resourceGridFilter: "all",
  };

  const usefulResources = [
    {
      title: "Open WebUI",
      description: "Интерфейс LLM для работы команды",
      url: "https://i.hpdd.ru/",
      image: "./resource-images/open-webui.png",
      color: "#0f172a",
      category: "admin",
    },
    {
      title: "Админка Outlook",
      description: "Администрирование почты Outlook",
      url:
        "https://mail.hpdd.ru/owa/auth/logon.aspx?replaceCurrent=1&reason=3&url=https%3a%2f%2fmail.hpdd.ru%2fowa%2fauth%2flogon.aspx%3furl%3dhttps%253a%252f%252fmail.hpdd.ru%252fecp%252f%253fexsvurl%253d1%2526p%253dDistributionGroups%23replaceCurrent%3d1",
      image: "./resource-images/outlook-admin.png",
      color: "#0078d4",
      category: "communications",
    },
    {
      title: "YouTrack",
      description: "Трекер задач команды",
      url:
        "https://youtrack.hpdd.ru/hub/auth/login?response_type=token&client_id=386f73f9-b1a1-4a9a-8fa6-e9184a1471d0&redirect_uri=https:%2F%2Fyoutrack.hpdd.ru%2Foauth&scope=386f73f9-b1a1-4a9a-8fa6-e9184a1471d0%20Upsource%20TeamCity%20YouTrack%2520Slack%2520Integration%200-0-0-0-0&state=f59cee64-165b-4121-b407-b5b7889da362",
      image: "./resource-images/youtrack.png",
      color: "#e91e63",
      category: "services",
    },
    {
      title: "Graylog",
      description: "Мониторинг и логи",
      url: "https://new-graylog.corp.hpdd.ru/welcome",
      image: "./resource-images/graylog.png",
      color: "#0ea5e9",
      category: "monitoring",
    },
    {
      title: "КиберБэкап",
      description: "Портал резервного копирования",
      url: "https://hpdd-bcp-mng02.corp.hpdd.ru:9877/",
      image: "./resource-images/cyber-backup.png",
      color: "#1d4ed8",
      category: "services",
    },
    {
      title: "Админка Битрикс",
      description: "Администрирование портала Битрикс",
      url: "https://portal.hpdd.ru/bitrix/admin/user_edit.php?lang=ru&ID=3582&user_edit_active_tab=edit1#authorize",
      image: "./resource-images/bitrix-admin.png",
      color: "#38bdf8",
      category: "communications",
    },
    {
      title: "HRlink",
      description: "Личный кабинет сотрудника",
      url: "https://lk.hr-link.ru/employee",
      image: "./resource-images/hrlink.png",
      color: "#2563eb",
      category: "services",
    },
    {
      title: "Админка Zoom",
      description: "Панель управления Zoom",
      url: "https://hpdd-ru.zoom.us/myhome",
      image: "./resource-images/zoom-admin.png",
      color: "#2563eb",
      category: "communications",
    },
    {
      title: "ServiceDesk",
      description: "Система заявок и обращений",
      url: "https://esd.hpdd.ru/HomePage.do?view_type=my_view",
      image: "./resource-images/servicedesk.png",
      color: "#0f172a",
      category: "services",
    },
    {
      title: "Proxy admin",
      description: "Панель администрирования Proxy",
      url: "https://proxy-portal.hpdd.ru/",
      image: "./resource-images/proxy-admin.png",
      color: "#1f2937",
      category: "admin",
    },
  ];

  const resourceCategoryLabels = {
    all: "Все",
    communications: "Коммуникации",
    admin: "Администрирование",
    monitoring: "Мониторинг",
    services: "Сервисы",
  };

  const RESOURCE_RECENT_MAX = 5;
  const RESOURCE_RECENT_TTL_DAYS = 30;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function userCapabilities(user) {
    const p = user?.permissions || {};
    const isRootAdmin = user?.role === "admin";
    return {
      isRootAdmin,
      canManageDuties: isRootAdmin || Boolean(p.can_manage_duties),
      canManageReports: isRootAdmin || Boolean(p.can_manage_reports),
      canManageNotifications: isRootAdmin || Boolean(p.can_manage_notifications),
    };
  }

  function localISODate(d = new Date()) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function parseISODate(dateStr) {
    if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(String(dateStr))) return null;
    const [y, m, d] = String(dateStr).split("-").map(Number);
    const dt = new Date(y, m - 1, d);
    if (Number.isNaN(dt.getTime())) return null;
    dt.setHours(0, 0, 0, 0);
    return dt;
  }

  /** Первый и последний день календарного месяца для локальной даты (как localISODate). */
  function monthRangeISO(anchor = new Date()) {
    const y = anchor.getFullYear();
    const mo = anchor.getMonth();
    const first = new Date(y, mo, 1);
    const last = new Date(y, mo + 1, 0);
    return { start: localISODate(first), end: localISODate(last) };
  }

  /** Предыдущий календарный месяц относительно anchor. */
  function prevMonthRangeISO(anchor = new Date()) {
    const y = anchor.getFullYear();
    const mo = anchor.getMonth();
    const first = new Date(y, mo - 1, 1);
    const last = new Date(y, mo, 0);
    return { start: localISODate(first), end: localISODate(last) };
  }

  function shiftISODate(dateStr, deltaDays) {
    const dt = parseISODate(dateStr);
    if (!dt) return "";
    dt.setDate(dt.getDate() + Number(deltaDays || 0));
    return localISODate(dt);
  }

  function formatDutyCalendarDate(dateStr) {
    const dt = parseISODate(dateStr);
    if (!dt) return dateStr || "";
    return dt.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
  }

  function formatLongRuDate(dateStr) {
    const dt = parseISODate(dateStr);
    if (!dt) return dateStr || "";
    return dt.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
      weekday: "long",
    });
  }

  function initialsFromName(name) {
    const parts = String(name || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return "ТП";
    return parts.slice(0, 2).map((p) => p[0]).join("").toUpperCase();
  }

  function updateDashboardClock() {
    const now = new Date();
    const timeEl = $("#dashboardClockTime");
    const dateEl = $("#dashboardClockDate");
    if (timeEl) timeEl.textContent = now.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    if (dateEl) {
      dateEl.textContent = now.toLocaleDateString("ru-RU", {
        day: "numeric",
        month: "long",
        weekday: "long",
      });
    }
  }

  function updateScheduleTitle(dateStr) {
    const title = $("#scheduleTitle");
    if (title) title.textContent = `Расписание дежурств на ${formatLongRuDate(dateStr || localISODate())}`;
  }

  function slotRangeLabel(slot) {
    const start = state.slotStartHour + Number(slot);
    const base = `${String(start).padStart(2, "0")}:00`;
    return start <= 8 ? `${base} (утреннее дежурство)` : base;
  }

  function slotStartLabel(slot) {
    const start = state.slotStartHour + Number(slot);
    const base = `${String(start).padStart(2, "0")}:00`;
    return start <= 8 ? `${base} (утреннее дежурство)` : base;
  }

  function getDutyCalendarRange(dateStr, mode) {
    const selected = parseISODate(dateStr) || parseISODate(localISODate());
    if (!selected) return { dates: [], title: "" };
    const dates = [];
    const start = new Date(selected);
    if (mode === "month") {
      start.setDate(1);
      const month = start.getMonth();
      while (start.getMonth() === month) {
        dates.push(localISODate(start));
        start.setDate(start.getDate() + 1);
      }
      return { dates, title: `График за ${selected.toLocaleDateString("ru-RU", { month: "long", year: "numeric" })}` };
    }
    const day = selected.getDay();
    const offsetToMonday = day === 0 ? -6 : 1 - day;
    start.setDate(start.getDate() + offsetToMonday);
    for (let i = 0; i < 7; i += 1) {
      dates.push(localISODate(start));
      start.setDate(start.getDate() + 1);
    }
    return { dates, title: `График за неделю (${formatDutyCalendarDate(dates[0])} - ${formatDutyCalendarDate(dates[6])})` };
  }

  function formatApiDetail(detail) {
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (!d || typeof d !== "object") return String(d);
          const path = Array.isArray(d.loc) ? d.loc.join(".") : "";
          const msg = d.msg || d.message || JSON.stringify(d);
          return path ? `${path}: ${msg}` : String(msg);
        })
        .join("; ");
    }
    if (detail && typeof detail === "object") {
      return detail.message || JSON.stringify(detail);
    }
    return detail ? String(detail) : "";
  }

  function showMsg(el, text, type = "info") {
    if (!el) return;
    el.textContent = text || "";
    el.classList.remove("info", "error", "success");
    if (type) el.classList.add(type);
    el.hidden = !text;
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function resourceImageDataUri(title, color) {
    const initial = String(title || "?").trim().slice(0, 1).toUpperCase() || "?";
    const safeColor = color || "#2563eb";
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270" viewBox="0 0 480 270" role="img" aria-label="${initial}"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${safeColor}" offset="0"/><stop stop-color="#0f172a" offset="1"/></linearGradient></defs><rect width="480" height="270" fill="url(#g)"/><text x="240" y="156" text-anchor="middle" font-family="Arial, sans-serif" font-size="112" font-weight="700" fill="#ffffff">${initial}</text></svg>`;
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
  }

  function resourceByTitle(title) {
    return usefulResources.find((resource) => resource.title === title);
  }

  function resourcesStorageUserId() {
    const id = Number(state.me?.id);
    return Number.isFinite(id) && id > 0 ? id : null;
  }

  function resourcesFavoritesKey(userId) {
    return `tpp.resources.favorites.${userId}`;
  }

  function resourcesRecentKey(userId) {
    return `tpp.resources.recent.${userId}`;
  }

  function readJsonStorage(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch {
      return fallback;
    }
  }

  function writeJsonStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch {
      return false;
    }
  }

  function loadResourceFavorites() {
    const uid = resourcesStorageUserId();
    if (!uid) return [];
    const key = resourcesFavoritesKey(uid);
    let titles = readJsonStorage(key, null);
    if (titles === null) {
      writeJsonStorage(key, []);
      return [];
    }
    if (!Array.isArray(titles)) titles = [];
    return titles.filter((t) => typeof t === "string" && resourceByTitle(t));
  }

  function saveResourceFavorites(titles) {
    const uid = resourcesStorageUserId();
    if (!uid) return;
    writeJsonStorage(resourcesFavoritesKey(uid), titles);
  }

  function isResourceFavorite(title) {
    return loadResourceFavorites().includes(title);
  }

  function toggleResourceFavorite(title) {
    if (!resourceByTitle(title)) return;
    const list = loadResourceFavorites();
    const idx = list.indexOf(title);
    if (idx >= 0) list.splice(idx, 1);
    else list.push(title);
    saveResourceFavorites(list);
  }

  function loadResourceRecent() {
    const uid = resourcesStorageUserId();
    if (!uid) return [];
    const key = resourcesRecentKey(uid);
    let items = readJsonStorage(key, []);
    if (!Array.isArray(items)) items = [];
    const cutoff = Date.now() - RESOURCE_RECENT_TTL_DAYS * 24 * 60 * 60 * 1000;
    const cleaned = items
      .filter((it) => it && typeof it.title === "string" && resourceByTitle(it.title))
      .filter((it) => {
        const ts = Date.parse(it.openedAt || "");
        return Number.isFinite(ts) && ts >= cutoff;
      })
      .slice(0, RESOURCE_RECENT_MAX);
    if (JSON.stringify(cleaned) !== JSON.stringify(items)) {
      writeJsonStorage(key, cleaned);
    }
    return cleaned;
  }

  function recordResourceRecent(title) {
    const uid = resourcesStorageUserId();
    if (!uid || !resourceByTitle(title)) return;
    let items = loadResourceRecent().filter((it) => it.title !== title);
    items.unshift({ title, openedAt: new Date().toISOString() });
    items = items.slice(0, RESOURCE_RECENT_MAX);
    writeJsonStorage(resourcesRecentKey(uid), items);
    renderResourceAside();
  }

  function formatResourceRecentMeta(iso) {
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return "";
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const itemDay = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
    const diffDays = Math.round((todayStart - itemDay) / 86400000);
    const time = dt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    if (diffDays === 0) return time;
    if (diffDays === 1) return `Вчера, ${time}`;
    return dt.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  function renderResourceAside() {
    const favorites = loadResourceFavorites();
    const recent = loadResourceRecent().map((it) => ({
      title: it.title,
      meta: formatResourceRecentMeta(it.openedAt),
    }));
    renderResourceSideList($("#resourcesFavoritesList"), favorites);
    renderResourceSideList($("#resourcesRecentList"), recent);
  }

  function scrollResourcesGridIntoView() {
    $("#resourcesGrid")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function initResourcesPageHandlers() {
    const panel = $("#tab-resources");
    if (!panel || panel.dataset.resourcesBound === "1") return;
    panel.dataset.resourcesBound = "1";

    panel.addEventListener("click", (ev) => {
      const favBtn = ev.target.closest(".resource-favorite-btn");
      if (favBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        const title = favBtn.dataset.resourceTitle;
        if (title) {
          toggleResourceFavorite(title);
          renderUsefulResources();
        }
        return;
      }

      const link = ev.target.closest("a.resource-card, a.resources-side-item");
      if (!link) return;
      if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
      const title = link.dataset.resourceTitle;
      if (title) recordResourceRecent(title);
    });

    $("#resourcesFavoritesShowAllBtn")?.addEventListener("click", () => {
      state.resourceCategory = "all";
      state.resourceGridFilter = "favorites";
      const search = $("#resourcesSearchInput");
      if (search) search.value = "";
      $$(".resource-category-btn").forEach((btn) => {
        const active = btn.dataset.resourceCategory === "all";
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });
      renderUsefulResources();
      scrollResourcesGridIntoView();
    });

    $("#resourcesRecentShowAllBtn")?.addEventListener("click", () => {
      state.resourceCategory = "all";
      state.resourceGridFilter = "recent";
      const search = $("#resourcesSearchInput");
      if (search) search.value = "";
      $$(".resource-category-btn").forEach((btn) => {
        const active = btn.dataset.resourceCategory === "all";
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });
      renderUsefulResources();
      scrollResourcesGridIntoView();
    });
  }

  function renderResourceSideList(root, items) {
    if (!root) return;
    root.innerHTML = "";
    for (const item of items) {
      const title = typeof item === "string" ? item : item.title;
      const meta = typeof item === "string" ? "" : item.meta;
      const resource = resourceByTitle(title);
      if (!resource) continue;
      const category = resourceCategoryLabels[resource.category] || "Сервисы";
      const link = document.createElement("a");
      link.className = "resources-side-item";
      link.href = resource.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.dataset.resourceTitle = title;
      link.innerHTML = `
        <img class="resources-side-icon" src="${escapeHtml(resource.image || resourceImageDataUri(resource.title, resource.color))}" alt="" loading="lazy" />
        <span class="resources-side-text">
          <strong>${escapeHtml(resource.title)}</strong>
          <span>${escapeHtml(category)}</span>
        </span>
        ${meta ? `<span class="resources-side-meta">${escapeHtml(meta)}</span>` : ""}
        <span class="resources-side-open" aria-hidden="true">↗</span>
      `;
      const img = link.querySelector(".resources-side-icon");
      if (img) {
        img.addEventListener("error", () => {
          img.src = resourceImageDataUri(resource.title, resource.color);
        }, { once: true });
      }
      root.appendChild(link);
    }
    if (!root.children.length) {
      const empty = document.createElement("div");
      empty.className = "resources-side-empty muted";
      empty.textContent = "Пока нет данных.";
      root.appendChild(empty);
    }
  }

  function renderUsefulResources() {
    const grid = $("#resourcesGrid");
    if (!grid) return;
    const query = ($("#resourcesSearchInput")?.value || "").trim().toLowerCase();
    const activeCategory = state.resourceCategory || "all";
    const gridFilter = state.resourceGridFilter || "all";
    const favoriteTitles = new Set(loadResourceFavorites());
    const recentTitles = new Set(loadResourceRecent().map((it) => it.title));
    grid.innerHTML = "";
    for (const resource of usefulResources) {
      const title = String(resource.title || "");
      const description = String(resource.description || "");
      const category = resourceCategoryLabels[resource.category] || "Сервисы";
      const haystack = `${title} ${description} ${category}`.toLowerCase();
      if (query && !haystack.includes(query)) continue;
      if (activeCategory !== "all" && resource.category !== activeCategory) continue;
      if (gridFilter === "favorites" && !favoriteTitles.has(title)) continue;
      if (gridFilter === "recent" && !recentTitles.has(title)) continue;
      const isFavorite = favoriteTitles.has(title);
      const card = document.createElement("a");
      card.className = "resource-card";
      card.href = resource.url;
      card.target = "_blank";
      card.rel = "noopener noreferrer";
      card.dataset.resourceTitle = title;
      card.title = `${title} — открыть в новой вкладке`;
      const imageSrc = resource.image || resourceImageDataUri(title, resource.color);
      card.innerHTML = `
        <button type="button" class="resource-favorite-btn${isFavorite ? " is-active" : ""}" data-resource-title="${escapeHtml(title)}" aria-label="${isFavorite ? "Убрать из избранного" : "Добавить в избранное"}" aria-pressed="${isFavorite ? "true" : "false"}">★</button>
        <span class="resource-open-icon" aria-hidden="true">↗</span>
        <span class="resource-image-wrap">
          <img class="resource-image" src="${escapeHtml(imageSrc)}" alt="${escapeHtml(title)}" loading="lazy" />
        </span>
        <div class="resource-body">
          <div class="resource-title">${escapeHtml(title)}</div>
          <div class="resource-description">${escapeHtml(description)}</div>
          <span class="resource-badge">${escapeHtml(category)}</span>
        </div>
      `;
      const img = card.querySelector(".resource-image");
      if (img) {
        img.addEventListener("error", () => {
          img.src = resourceImageDataUri(title, resource.color);
        }, { once: true });
      }
      grid.appendChild(card);
    }
    if (!grid.children.length) {
      const empty = document.createElement("div");
      empty.className = "resources-empty muted";
      if (gridFilter === "favorites") {
        empty.textContent = "В избранном пока нет ресурсов. Нажмите ★ на карточке, чтобы добавить.";
      } else if (gridFilter === "recent") {
        empty.textContent = "Недавно открытых ресурсов пока нет. Откройте любую карточку или ссылку справа.";
      } else {
        empty.textContent = "По вашему запросу ресурсы не найдены.";
      }
      grid.appendChild(empty);
    }
    $$(".resource-category-btn").forEach((btn) => {
      const active = btn.dataset.resourceCategory === activeCategory;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    renderResourceAside();
  }

  /** Префикс перед /api (если приложение задеплоено в подпапку): meta name="api-base" content="/myapp" */
  function apiUrl(path) {
    if (typeof path !== "string" || !path.startsWith("/api")) return path;
    const raw = document.querySelector('meta[name="api-base"]')?.getAttribute("content") ?? "";
    if (raw.trim() === "") return path;
    const prefix = raw.trim().replace(/\/$/, "");
    if (!prefix) return path;
    return `${prefix}${path}`;
  }

  /** Тот же префикс, что у api-base, для путей вне /api (например /exports/... при деплое в подпапку). */
  function appRootPath(path) {
    if (typeof path !== "string" || !path.startsWith("/")) return path;
    const raw = document.querySelector('meta[name="api-base"]')?.getAttribute("content") ?? "";
    const prefix = raw.trim().replace(/\/$/, "");
    if (!prefix) return path;
    return `${prefix}${path}`;
  }

  async function apiFetchJson(url, { method = "GET", body, headers } = {}) {
    const resolved = apiUrl(url);
    const res = await fetch(resolved, {
      method,
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        ...(headers || {}),
        ...(body !== undefined ? { "Content-Type": "application/json" } : null),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      if (!res.ok) {
        const snippet = (text || "").replace(/\s+/g, " ").trim().slice(0, 240);
        throw new Error(snippet || `HTTP ${res.status}`);
      }
      throw new Error("Некорректный ответ сервера (не JSON).");
    }
    if (!res.ok) {
      const detail = formatApiDetail(data?.detail || data?.message);
      throw new Error(detail || `HTTP ${res.status}`);
    }
    return data;
  }

  async function apiGetMe() {
    return apiFetchJson("/api/me");
  }

  async function apiLogin({ username, password }) {
    return apiFetchJson("/api/login", {
      method: "POST",
      body: { username, password },
    });
  }

  async function apiLogout() {
    return apiFetchJson("/api/logout", { method: "POST" });
  }

  async function apiAdminChangeUserPassword(userId, newPassword) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}/password`, {
      method: "POST",
      body: { new_password: newPassword },
    });
  }

  async function apiAdminDeleteUserReports(userId) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}/reports`, {
      method: "DELETE",
    });
  }

  async function apiAdminDeleteUser(userId) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    });
  }

  async function apiAdminUpdateDutyStatus(userId, isActive) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}/duty-status`, {
      method: "PATCH",
      body: { is_active_for_duties: Boolean(isActive) },
    });
  }

  async function apiAdminUpdateUserProfile(userId, username, fullName) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      body: { username, full_name: fullName },
    });
  }

  async function apiAdminUpdateBitrixUserId(userId, bitrixUserId) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}/bitrix-user`, {
      method: "PATCH",
      body: { bitrix_user_id: bitrixUserId },
    });
  }

  async function apiAdminUpdateUserPermissions(userId, permissions) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}/permissions`, {
      method: "PATCH",
      body: {
        can_manage_duties: Boolean(permissions?.can_manage_duties),
        can_manage_reports: Boolean(permissions?.can_manage_reports),
        can_manage_notifications: Boolean(permissions?.can_manage_notifications),
      },
    });
  }

  async function apiAdminGrantAdmin(userId) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}/grant-admin`, {
      method: "POST",
      body: {},
    });
  }

  async function apiAdminRevokeAdmin(userId) {
    return apiFetchJson(`/api/admin/users/${encodeURIComponent(userId)}/revoke-admin`, {
      method: "POST",
      body: {},
    });
  }

  async function apiAdminRoleAudit(limit = 50) {
    return apiFetchJson(`/api/admin/role-audit?limit=${encodeURIComponent(String(limit))}`);
  }

  async function apiGetNotificationSettings() {
    return apiFetchJson("/api/admin/notifications/settings");
  }

  async function apiUpdateNotificationSettings(payload) {
    return apiFetchJson("/api/admin/notifications/settings", {
      method: "PATCH",
      body: payload,
    });
  }

  async function apiGetNotificationTemplates() {
    return apiFetchJson("/api/admin/notifications/templates");
  }

  async function apiUpdateNotificationTemplates(payload) {
    return apiFetchJson("/api/admin/notifications/templates", {
      method: "PATCH",
      body: payload,
    });
  }

  async function apiTestDutyNotification(userId) {
    return apiFetchJson(`/api/admin/notifications/duty-test?user_id=${encodeURIComponent(String(userId))}`, {
      method: "POST",
    });
  }

  async function apiGetDutiesSwapsAnalytics(startDate, endDate) {
    const query = new URLSearchParams();
    query.set("start_date", String(startDate || ""));
    query.set("end_date", String(endDate || ""));
    return apiFetchJson(`/api/admin/analytics/duties-swaps?${query.toString()}`);
  }

  async function apiMeNotifyDutyReplacementBitrix() {
    return apiFetchJson("/api/me/duty-replacement-request/bitrix", { method: "POST" });
  }

  async function apiGetMeDutyLeaveDates() {
    return apiFetchJson("/api/me/duty-leave-dates");
  }

  async function apiPutMeDutyLeaveDates(dates) {
    return apiFetchJson("/api/me/duty-leave-dates", { method: "PUT", body: { dates } });
  }

  async function apiDeleteMeDutyLeaveDates() {
    return apiFetchJson("/api/me/duty-leave-dates", { method: "DELETE" });
  }

  async function apiPostMeDutyLeaveResumeToday() {
    return apiFetchJson("/api/me/duty-leave-dates/resume-today", { method: "POST" });
  }

  async function apiChangeOwnPassword(oldPassword, newPassword) {
    return apiFetchJson("/api/me/password", {
      method: "POST",
      body: { old_password: oldPassword, new_password: newPassword },
    });
  }

  async function apiUpdateMeProfile(fullName) {
    return apiFetchJson("/api/me/profile", {
      method: "PATCH",
      body: { full_name: fullName },
    });
  }

  async function apiEmployeeExitInstruction({ fio, login, password, domain, blocks }) {
    return apiFetchJson("/api/ee_instruction", {
      method: "POST",
      body: { fio, login, password, domain, blocks },
    });
  }

  async function apiEmployeeExitInstructionDocx({ fio, login, password, domain, blocks }) {
    const res = await fetch(apiUrl("/api/ee_instruction/docx"), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fio, login, password, domain, blocks }),
    });
    if (!res.ok) {
      const errText = await res.text();
      let data = null;
      try {
        data = errText ? JSON.parse(errText) : null;
      } catch {
        // not JSON
      }
      const detail = formatApiDetail(data?.detail || data?.message);
      throw new Error(detail || errText || `HTTP ${res.status}`);
    }
    return res.blob();
  }

  function appPublicBaseUrl() {
    const raw = document.querySelector('meta[name="api-base"]')?.getAttribute("content") ?? "";
    const prefix = raw.trim().replace(/\/$/, "");
    return `${window.location.origin}${prefix}`;
  }

  async function apiEmployeeExitShare({ fio, login, password, domain, blocks }) {
    return apiFetchJson("/api/ee_instruction/share", {
      method: "POST",
      body: {
        fio,
        login,
        password,
        domain,
        blocks,
        public_base_url: appPublicBaseUrl(),
      },
    });
  }

  async function apiCreateDutySwapRequest({ date, fromSlot, toSlot }) {
    return apiFetchJson("/api/duty-swaps", {
      method: "POST",
      body: { date, from_slot: Number(fromSlot), to_slot: Number(toSlot) },
    });
  }

  async function apiGetDutySwapInbox(dateStr) {
    const query = new URLSearchParams();
    if (dateStr) query.set("date", dateStr);
    return apiFetchJson(`/api/duty-swaps/inbox${query.toString() ? `?${query.toString()}` : ""}`);
  }

  async function apiDecideDutySwapRequest(swapId, action) {
    return apiFetchJson(`/api/duty-swaps/${encodeURIComponent(swapId)}/decision`, {
      method: "POST",
      body: { action },
    });
  }

  /** Сотрудники для дежурств и отчётов: support и админы (админка не исключает из графика). */
  function supportEmployees() {
    return state.employees.filter((e) => e.role === "support" || e.role === "admin");
  }

  /** Сотрудники для селектов графика: только активные к дежурствам, плюс уже назначенный в слоте (если он неактивен). */
  function supportEmployeesForDutySlotSelect(assignedUser) {
    const all = supportEmployees();
    const active = all.filter((e) => e.is_active_for_duties !== false);
    const activeIds = new Set(active.map((e) => Number(e.id)));
    const assignedId = assignedUser ? Number(assignedUser.id) : null;
    const chosen = new Map(active.map((e) => [Number(e.id), e]));
    if (assignedId != null && !Number.isNaN(assignedId) && !activeIds.has(assignedId)) {
      const a = all.find((e) => Number(e.id) === assignedId);
      if (a) chosen.set(assignedId, a);
    }
    return [...chosen.keys()]
      .sort((x, y) => x - y)
      .map((id) => chosen.get(id))
      .filter(Boolean);
  }

  function adminEmployees() {
    return state.employees.filter((e) => e.role === "admin");
  }

  function fillNotifTestUserSelect() {
    const sel = $("#notifTestUserId");
    if (!sel) return;
    sel.innerHTML = "";
    const list = [...state.employees].sort((a, b) => Number(a.id) - Number(b.id));
    for (const emp of list) {
      const opt = document.createElement("option");
      opt.value = String(emp.id);
      opt.textContent = `${emp.full_name || emp.username} (id ${emp.id})`;
      sel.appendChild(opt);
    }
    if (list.length) sel.value = String(list[0].id);
  }

  async function loadEmployees() {
    const users = await apiFetchJson("/api/admin/users");
    state.employees = Array.isArray(users) ? users : [];
    state.adminUsersPage = 1;
    renderAdminUsersEditor();
    fillNotifTestUserSelect();
    return state.employees;
  }

  /** last_login_at в БД — UTC без суффикса; показываем как локальное время браузера. */
  function formatLastLoginAt(iso) {
    if (!iso) return "—";
    const s = String(iso).trim();
    const d = /Z|[+-]\d{2}:?\d{2}$/.test(s) ? new Date(s) : new Date(`${s.replace(" ", "T")}Z`);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
  }

  function formatReportStatusRu(status) {
    return status === "final" ? "Экспортирован" : "Черновик";
  }

  function formatShortEmployeeName(fullName) {
    const parts = String(fullName || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return "—";
    if (parts.length === 1) return parts[0];
    const initials = parts
      .slice(1)
      .map((p) => (p.length ? `${p.slice(0, 1).toUpperCase()}.` : ""))
      .join(" ")
      .trim();
    return `${parts[0]} ${initials}`.trim();
  }

  /** Одна строка таблицы «Сотрудники»; `adminCount` — число пользователей с ролью admin (для блокировки чекбокса «Админ»). */
  function buildAdminUserEditorRow(emp, adminCount) {
    const isAdmin = emp.role === "admin";
    const tr = document.createElement("tr");
    tr.dataset.userId = String(emp.id);
    const isDutyInactive = emp.role === "support" && emp.is_active_for_duties === false;
    tr.classList.toggle("admin-user-duty-inactive", isDutyInactive);

    const tdId = document.createElement("td");
    tdId.className = "admin-users-col-id";
    tdId.textContent = String(emp.id);

    const tdLogin = document.createElement("td");
    tdLogin.className = "admin-users-col-login";
    const tdName = document.createElement("td");
    tdName.className = "admin-users-col-name";
    if (emp.role === "support") {
      const inpL = document.createElement("input");
      inpL.type = "text";
      inpL.className = "admin-edit-username";
      inpL.value = emp.username || "";
      const inpN = document.createElement("input");
      inpN.type = "text";
      inpN.className = "admin-edit-fullname";
      inpN.value = emp.full_name || "";
      tdLogin.appendChild(inpL);
      tdName.appendChild(inpN);
    } else {
      tdLogin.textContent = emp.username || "";
      tdName.textContent = emp.full_name || "";
    }

    const tdLast = document.createElement("td");
    tdLast.className = "admin-users-col-lastlogin";
    tdLast.textContent = formatLastLoginAt(emp.last_login_at);

    const tdBitrix = document.createElement("td");
    tdBitrix.className = "admin-users-col-bitrix";
    const inpB = document.createElement("input");
    inpB.type = "text";
    inpB.inputMode = "numeric";
    inpB.className = "admin-edit-bitrix-id admin-bitrix-input";
    inpB.placeholder = "—";
    inpB.title =
      "ID пользователя Битрикс24 (число); для упоминания в чате при рассылке графика. У администратора — кнопка «Сохранить».";
    inpB.value = emp.bitrix_user_id != null && emp.bitrix_user_id !== undefined ? String(emp.bitrix_user_id) : "";
    tdBitrix.appendChild(inpB);

    const tdRole = document.createElement("td");
    tdRole.className = "admin-users-col-role";
    const roleStack = document.createElement("div");
    roleStack.className = "admin-role-stack";
    const badge = document.createElement("span");
    badge.className = isAdmin ? "role-badge role-badge--admin" : "role-badge role-badge--support";
    badge.textContent = isAdmin ? "Админ" : "Сотрудник";
    roleStack.appendChild(badge);
    const lbl = document.createElement("label");
    lbl.className = "checkbox-label admin-role-grant";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "admin-rights-checkbox";
    cb.dataset.userId = String(emp.id);
    if (isAdmin) cb.checked = true;
    const isBootstrap = Boolean(emp.is_bootstrap_admin);
    if (isAdmin && (adminCount <= 1 || isBootstrap)) {
      cb.disabled = true;
      cb.title = isBootstrap
        ? "Нельзя снять права у изначального администратора (учётная запись из BOOTSTRAP_ADMIN_* на сервере)"
        : "Нельзя снять права у последнего администратора";
    } else {
      cb.title = "Права администратора: вкладка «Админ» в интерфейсе";
    }
    const span = document.createElement("span");
    span.className = "admin-role-grant-label";
    span.textContent = "Права адм.";
    lbl.appendChild(cb);
    lbl.appendChild(span);
    roleStack.appendChild(lbl);
    tdRole.appendChild(roleStack);

    const tdPerms = document.createElement("td");
    tdPerms.className = "admin-users-col-perms";
    if (emp.role === "support") {
      const p = emp.permissions || {};
      const wrap = document.createElement("div");
      wrap.className = "admin-perm-badges";
      const mkPerm = (field, labelText) => {
        const label = document.createElement("label");
        label.className = "admin-perm-chip";
        const cbPerm = document.createElement("input");
        cbPerm.type = "checkbox";
        cbPerm.className = "admin-permission-checkbox";
        cbPerm.dataset.permission = field;
        cbPerm.checked = Boolean(p[field]);
        const spanPerm = document.createElement("span");
        spanPerm.className = "admin-perm-chip-text";
        spanPerm.textContent = labelText;
        label.appendChild(cbPerm);
        label.appendChild(spanPerm);
        wrap.appendChild(label);
      };
      mkPerm("can_manage_duties", "График");
      mkPerm("can_manage_reports", "Отчёты");
      mkPerm("can_manage_notifications", "Уведомления");
      tdPerms.appendChild(wrap);
    } else {
      const wrap = document.createElement("div");
      wrap.className = "admin-perm-badges admin-perm-badges--static";
      for (const t of ["График", "Отчёты", "Уведомления"]) {
        const s = document.createElement("span");
        s.className = "perm-badge perm-badge--all";
        s.textContent = t;
        wrap.appendChild(s);
      }
      tdPerms.appendChild(wrap);
    }

    const tdAct = document.createElement("td");
    tdAct.className = "admin-users-col-actions";
    if (emp.role === "support") {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-compact";
      btn.dataset.action = "saveUserProfile";
      btn.textContent = "Сохранить";
      tdAct.appendChild(btn);
    } else {
      const btnBx = document.createElement("button");
      btnBx.type = "button";
      btnBx.className = "btn btn-compact";
      btnBx.dataset.action = "saveBitrixId";
      btnBx.textContent = "Сохранить";
      btnBx.title = "Сохранить ID Битрикс (логин/ФИО админа в таблице не редактируются)";
      tdAct.appendChild(btnBx);
    }

    tr.appendChild(tdId);
    tr.appendChild(tdLogin);
    tr.appendChild(tdName);
    tr.appendChild(tdLast);
    tr.appendChild(tdBitrix);
    tr.appendChild(tdRole);
    tr.appendChild(tdPerms);
    tr.appendChild(tdAct);
    return tr;
  }

  /** После сохранения одного сотрудника — обновить только его строку, не сбрасывая черновики в других строках. */
  function replaceAdminUserEditorRow(emp) {
    const tbody = $("#adminUsersEditorBody");
    if (!tbody) return;
    const old = tbody.querySelector(`tr[data-user-id="${emp.id}"]`);
    if (!old) {
      renderAdminUsersEditor();
      return;
    }
    const adminCount = adminEmployees().length;
    old.replaceWith(buildAdminUserEditorRow(emp, adminCount));
  }

  function renderAdminUsersPagination(total, page, pageSize) {
    const el = $("#adminUsersPagination");
    if (!el) return;
    if (total === 0 || total <= pageSize) {
      el.innerHTML = "";
      el.hidden = true;
      return;
    }
    el.hidden = false;
    const totalPages = Math.ceil(total / pageSize);
    const start = (page - 1) * pageSize + 1;
    const end = Math.min(total, page * pageSize);
    const parts = [];
    if (page > 1) {
      parts.push(
        `<button type="button" class="btn btn-compact admin-users-page-btn" data-admin-users-page="${page - 1}" aria-label="Предыдущая страница">‹</button>`,
      );
    }
    for (let p = 1; p <= totalPages; p++) {
      const cur = p === page;
      parts.push(
        `<button type="button" class="btn btn-compact admin-users-page-btn${cur ? " primary" : ""}" data-admin-users-page="${p}"${cur ? ' aria-current="page"' : ""}>${p}</button>`,
      );
    }
    if (page < totalPages) {
      parts.push(
        `<button type="button" class="btn btn-compact admin-users-page-btn" data-admin-users-page="${page + 1}" aria-label="Следующая страница">›</button>`,
      );
    }
    el.innerHTML = `<div class="admin-users-pag-inner"><span class="muted admin-users-pag-meta">Показано ${start}–${end} из ${total}</span><div class="admin-users-pag-btns">${parts.join("")}</div></div>`;
  }

  function renderAdminUsersEditor() {
    const tbody = $("#adminUsersEditorBody");
    if (!tbody) return;
    tbody.innerHTML = "";
    const adminCount = adminEmployees().length;
    const list = [...state.employees].sort((a, b) => Number(a.id) - Number(b.id));
    const pageSize = Number(state.adminUsersPageSize) || 10;

    if (!list.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 8;
      td.className = "muted";
      td.textContent =
        "Список пользователей пуст или ещё не загружен. Нажмите «Обновить список». Если таблица не появляется — обновите страницу с полным сбросом кэша (Ctrl+F5).";
      tr.appendChild(td);
      tbody.appendChild(tr);
      renderAdminUsersPagination(0, 1, pageSize);
      return;
    }

    let page = Math.max(1, Number(state.adminUsersPage) || 1);
    const totalPages = Math.max(1, Math.ceil(list.length / pageSize));
    if (page > totalPages) page = totalPages;
    state.adminUsersPage = page;
    const slice = list.slice((page - 1) * pageSize, page * pageSize);
    for (const emp of slice) {
      tbody.appendChild(buildAdminUserEditorRow(emp, adminCount));
    }
    renderAdminUsersPagination(list.length, page, pageSize);
  }

  function fillEmployeesSelect(selectEl, { includeBlank = true, saveKey = null } = {}) {
    if (!selectEl) return;
    selectEl.innerHTML = "";

    if (includeBlank) {
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "—";
      selectEl.appendChild(placeholder);
    }

    const saved = saveKey ? localStorage.getItem(saveKey) : null;
    let selectedFound = false;
    const list = supportEmployees();
    for (const emp of list) {
      const opt = document.createElement("option");
      opt.value = String(emp.id);
      const title = emp.full_name || emp.username;
      if (selectEl.id === "adminUserSelect") {
        const roleRu = emp.role === "admin" ? "admin" : "сотрудник";
        opt.textContent =
          emp.is_active_for_duties === false ? `${title} (${roleRu}, не в графике дежурств)` : `${title} (${roleRu})`;
      } else {
        opt.textContent = emp.is_active_for_duties === false ? `${title} (не в графике дежурств)` : title;
      }
      if (saved && String(emp.id) === saved) {
        opt.selected = true;
        selectedFound = true;
      }
      selectEl.appendChild(opt);
    }

    if (!selectedFound && list.length) {
      selectEl.value = String(list[0].id);
      if (saveKey) localStorage.setItem(saveKey, String(list[0].id));
    }
  }

  function refreshPrivilegedSelectors() {
    if (state.canManageReports) {
      fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
    }
    if (state.isRootAdmin) {
      fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
    }
  }

  function activateAdminSubtab(tabName) {
    const btns = $$(".admin-subtab-btn");
    btns.forEach((b) => {
      const isActive = b.dataset.adminTab === tabName;
      b.classList.toggle("active", isActive);
      b.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    const map = {
      analytics: "#adminAnalyticsCard",
      generation: "#adminGenerateCard",
      notifications: "#adminNotificationsCard",
      users: "#adminUsersCard",
    };
    for (const [name, selector] of Object.entries(map)) {
      const card = $(selector);
      if (!card) continue;
      const canShow = !card.dataset.hiddenByCapability;
      card.hidden = !canShow || name !== tabName;
    }
    state.adminSubtab = tabName;
  }

  function syncAdminSubtabs() {
    const availability = {
      analytics: state.canManageReports,
      generation: state.canManageDuties,
      notifications: state.canManageNotifications,
      users: state.isRootAdmin,
    };
    const btns = $$(".admin-subtab-btn");
    for (const btn of btns) {
      const tab = btn.dataset.adminTab;
      btn.hidden = !availability[tab];
    }
    const availableTabs = Object.keys(availability).filter((name) => availability[name]);
    if (!availableTabs.length) return;
    const current = availableTabs.includes(state.adminSubtab) ? state.adminSubtab : availableTabs[0];
    activateAdminSubtab(current);
  }

  function setAdminMode(hasAdminAccess) {
    state.hasAdminAccess = Boolean(hasAdminAccess);

    document.body.classList.toggle("admin-user", state.canManageDuties || state.canManageReports || state.isRootAdmin);

    const adminTabBtn = $("#adminTabBtn");
    if (adminTabBtn) adminTabBtn.hidden = !state.isRootAdmin;

    for (const el of $$(".admin-only")) {
      // Elements in HTML can have "hidden" attribute; JS must control it.
      el.hidden = !state.hasAdminAccess;
    }

    for (const el of $$(".support-only")) {
      el.hidden = state.hasAdminAccess;
    }

    for (const el of $$(".duties-manage-only")) {
      el.hidden = !state.canManageDuties;
    }

    const swapCard = $("#swapCard");
    if (swapCard) {
      swapCard.hidden = false;
    }
    const genCard = $("#adminGenerateCard");
    if (genCard) genCard.dataset.hiddenByCapability = state.canManageDuties ? "" : "1";
    const notifCard = $("#adminNotificationsCard");
    if (notifCard) notifCard.dataset.hiddenByCapability = state.canManageNotifications ? "" : "1";
    const analyticsCard = $("#adminAnalyticsCard");
    if (analyticsCard) analyticsCard.dataset.hiddenByCapability = state.canManageReports ? "" : "1";
    const usersCard = $("#adminUsersCard");
    if (usersCard) usersCard.dataset.hiddenByCapability = state.isRootAdmin ? "" : "1";
    syncAdminSubtabs();
  }

  function applyNotificationSettingsToUi(settings) {
    if (!settings) return;
    const sch = $("#notifSchedulerEnabled");
    if (sch) sch.checked = Boolean(settings.scheduler_enabled);
    $("#notif5m").checked = Boolean(settings.enabled_upcoming_5m);
    $("#notifStart").checked = Boolean(settings.enabled_start);
    $("#notifChatStart").checked = Boolean(settings.enabled_chat_on_start);
  }

  function gatherNotificationSettingsFromUi() {
    return {
      scheduler_enabled: Boolean($("#notifSchedulerEnabled")?.checked),
      enabled_upcoming_5m: Boolean($("#notif5m")?.checked),
      enabled_start: Boolean($("#notifStart")?.checked),
      enabled_chat_on_start: Boolean($("#notifChatStart")?.checked),
    };
  }

  async function saveNotificationSettingsAuto() {
    if (!state.notificationSettingsReady) return;
    if (state.notificationSettingsSaving) return;
    const msg = $("#notificationSettingsMsg");
    try {
      state.notificationSettingsSaving = true;
      showMsg(msg, "Сохраняем настройки уведомлений…", "info");
      const payload = gatherNotificationSettingsFromUi();
      const out = await apiUpdateNotificationSettings(payload);
      applyNotificationSettingsToUi(out);
      showMsg(msg, "Настройки уведомлений сохранены.", "success");
    } catch (e) {
      showMsg(msg, e.message || String(e), "error");
    } finally {
      state.notificationSettingsSaving = false;
    }
  }

  function applyNotificationTemplatesToUi(templates) {
    if (!templates) return;
    $("#notifTpl5m").value = String(templates.upcoming_5m_template || "");
    $("#notifTplStartPersonal").value = String(templates.start_personal_template || "");
    $("#notifTplStartChat").value = String(templates.start_chat_template || "");
    $("#notifTplTestWithSlot").value = String(templates.test_with_slot_template || "");
    $("#notifTplTestNoSlot").value = String(templates.test_without_slot_template || "");
  }

  function gatherNotificationTemplatesFromUi() {
    return {
      upcoming_5m_template: ($("#notifTpl5m")?.value || "").trim(),
      start_personal_template: ($("#notifTplStartPersonal")?.value || "").trim(),
      start_chat_template: ($("#notifTplStartChat")?.value || "").trim(),
      test_with_slot_template: ($("#notifTplTestWithSlot")?.value || "").trim(),
      test_without_slot_template: ($("#notifTplTestNoSlot")?.value || "").trim(),
    };
  }

  async function saveNotificationTemplates() {
    if (!state.notificationTemplatesReady) return;
    if (state.notificationTemplatesSaving) return;
    const msg = $("#notificationSettingsMsg");
    try {
      state.notificationTemplatesSaving = true;
      showMsg(msg, "Сохраняем шаблоны уведомлений…", "info");
      const out = await apiUpdateNotificationTemplates(gatherNotificationTemplatesFromUi());
      applyNotificationTemplatesToUi(out);
      showMsg(msg, "Шаблоны уведомлений сохранены.", "success");
    } catch (e) {
      showMsg(msg, e.message || String(e), "error");
    } finally {
      state.notificationTemplatesSaving = false;
    }
  }

  function ymLongRu(ym) {
    if (!ym || !/^\d{4}-\d{2}$/.test(String(ym))) return String(ym || "");
    const [y, m] = String(ym)
      .split("-")
      .map((x) => Number(x));
    const d = new Date(y, m - 1, 1);
    if (Number.isNaN(d.getTime())) return String(ym);
    return d.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  }

  function slotsRuLabel(n) {
    const v = Math.abs(Number(n)) % 100;
    const v1 = v % 10;
    if (v >= 11 && v <= 14) return "слотов";
    if (v1 === 1) return "слот";
    if (v1 >= 2 && v1 <= 4) return "слота";
    return "слотов";
  }

  function setAnalyticsKpiText(id, text) {
    const el = $(`#${id}`);
    if (el) el.textContent = text;
  }

  function renderAnalyticsRiskSection(title, rows, assigned, warnings) {
    const empN = rows.length;
    const warns = Array.isArray(warnings) ? warnings : [];

    if (empN < 2 || assigned < 12) {
      return `<section class="analytics-risk-section"><h4>${escapeHtml(title)}</h4><p class="analytics-risk-placeholder muted">Для оценки перегруза нужно не менее <strong>12</strong> назначенных слотов в периоде и минимум <strong>2</strong> сотрудника с назначениями.</p></section>`;
    }
    const mean = assigned / empN;
    const meanStr = mean.toFixed(1).replace(".", ",");

    if (!warns.length) {
      return `<section class="analytics-risk-section"><h4>${escapeHtml(title)}</h4><p class="analytics-risk-ok">Риск перегруза отсутствует.</p><p class="muted" style="margin-top:0.5rem">Среднее число назначений на сотрудника: <strong>${meanStr}</strong>.</p></section>`;
    }

    const count = warns.length;
    let noun = "сотрудников";
    if (count === 1) noun = "сотрудник";
    else if (count >= 2 && count <= 4) noun = "сотрудника";
    const banner = `<div class="analytics-risk-banner">Обнаружено <strong>${count}</strong> ${noun} с риском перегруза. Доля назначений выше среднего.</div>`;
    const details = `<div class="analytics-risk-meta muted"><p>Среднее число назначений на сотрудника: <strong>${meanStr}</strong>.</p><p>Порог перегруза (эвристика): при ≥12 назначениях и ≥2 сотрудниках — выше max(1,35×среднее; ⌈среднее⌉+2) назначений у сотрудника.</p></div>`;
    const listItems = warns
      .map(
        (w) =>
          `<li><span class="analytics-risk-dot" aria-hidden="true"></span><strong>${escapeHtml(w.full_name || `ID ${w.user_id}`)}</strong> — ${escapeHtml(String(w.slot_count))} ${slotsRuLabel(w.slot_count)} (${escapeHtml(String(w.share_percent))}% от назначенных в периоде). ${escapeHtml(w.note || "")}</li>`,
      )
      .join("");
    const list = `<ul class="analytics-risk-ul">${listItems}</ul>`;
    return `<section class="analytics-risk-section"><h4>${escapeHtml(title)}</h4>${banner}${details}${list}</section>`;
  }

  function renderAnalyticsRiskPanel(out) {
    const el = $("#analyticsRiskBody");
    if (!el) return;
    if (!out) {
      el.className = "analytics-risk-body muted";
      el.innerHTML = "Загрузите данные кнопкой «Показать».";
      return;
    }
    const regularRows = Array.isArray(out.employee_slots) ? out.employee_slots : [];
    const morningRows = Array.isArray(out.morning_employee_slots) ? out.morning_employee_slots : [];
    el.className = "analytics-risk-body";
    el.innerHTML =
      renderAnalyticsRiskSection(
        "Обычные дежурства",
        regularRows,
        Number(out.regular_assigned_slots ?? out.assigned_slots ?? 0),
        out.overload_warnings,
      ) +
      renderAnalyticsRiskSection(
        "Утренние дежурства",
        morningRows,
        Number(out.morning_assigned_slots || 0),
        out.morning_overload_warnings,
      );
  }

  function renderAnalyticsEmployeeList(root, rows) {
    if (!root) return;
    const safeRows = Array.isArray(rows) ? rows : [];
    if (!safeRows.length) {
      root.innerHTML = '<div class="analytics-employee-card muted">Нет назначенных дежурств за выбранный период.</div>';
      return;
    }
    const maxSlots = safeRows.reduce((m, r) => Math.max(m, Number(r.slot_count || 0)), 0) || 1;
    root.innerHTML = safeRows
      .map((row) => {
        const n = Number(row.slot_count || 0);
        const pct = Math.min(100, Math.round((100 * n) / maxSlots));
        const name = escapeHtml(row.full_name || `ID ${row.user_id}`);
        return `<div class="analytics-employee-card"><div class="analytics-employee-row"><span class="analytics-employee-name"><strong>${name}</strong></span><div class="analytics-bar-track" role="presentation" aria-hidden="true"><div class="analytics-bar-fill" style="width:${pct}%"></div></div><span class="analytics-employee-count">${escapeHtml(String(n))} ${escapeHtml(slotsRuLabel(n))}</span></div></div>`;
      })
      .join("");
  }

  function renderAnalytics(out) {
    const listRoot = $("#analyticsEmployees");
    const morningListRoot = $("#analyticsMorningEmployees");
    const monthlyBlock = $("#analyticsMonthlyBlock");
    if (!listRoot) return;
    if (monthlyBlock) {
      monthlyBlock.innerHTML = "";
      monthlyBlock.hidden = true;
    }
    if (!out) {
      setAnalyticsKpiText("analyticsKpiSlots", "—");
      setAnalyticsKpiText("analyticsKpiUnassigned", "—");
      setAnalyticsKpiText("analyticsKpiSwaps", "—");
      setAnalyticsKpiText("analyticsKpiOverload", "—");
      setAnalyticsKpiText("analyticsKpiMorningSlots", "—");
      setAnalyticsKpiText("analyticsKpiMorningUnassigned", "—");
      setAnalyticsKpiText("analyticsKpiMorningOverload", "—");
      listRoot.innerHTML = "";
      if (morningListRoot) morningListRoot.innerHTML = "";
      renderAnalyticsRiskPanel(null);
      return;
    }
    const assigned = Number(out.regular_assigned_slots ?? out.assigned_slots ?? 0);
    const capacity = Number(out.regular_slot_capacity ?? out.slot_capacity ?? 0);
    const unassigned = Number(out.regular_unassigned_slots ?? out.unassigned_slots ?? 0);
    const morningAssigned = Number(out.morning_assigned_slots || 0);
    const morningCapacity = Number(out.morning_slot_capacity || 0);
    const morningUnassigned = Number(out.morning_unassigned_slots || 0);
    const swaps = out.swaps || {};
    setAnalyticsKpiText("analyticsKpiSlots", `${assigned}/${capacity}`);
    setAnalyticsKpiText("analyticsKpiUnassigned", String(unassigned));
    setAnalyticsKpiText("analyticsKpiSwaps", String(Number(swaps.total || 0)));
    const warns = Array.isArray(out.overload_warnings) ? out.overload_warnings : [];
    setAnalyticsKpiText("analyticsKpiOverload", String(warns.length));
    const morningWarns = Array.isArray(out.morning_overload_warnings) ? out.morning_overload_warnings : [];
    setAnalyticsKpiText("analyticsKpiMorningSlots", `${morningAssigned}/${morningCapacity}`);
    setAnalyticsKpiText("analyticsKpiMorningUnassigned", String(morningUnassigned));
    setAnalyticsKpiText("analyticsKpiMorningOverload", String(morningWarns.length));

    const monthly = Array.isArray(out.monthly) ? out.monthly : [];
    if (monthlyBlock && monthly.length) {
      const rows = monthly
        .map(
          (b) =>
            `<tr><td>${escapeHtml(ymLongRu(b.year_month))}</td><td class="num">${escapeHtml(String(b.regular_assigned_slots ?? b.assigned_slots ?? 0))}</td><td class="num">${escapeHtml(String(b.morning_assigned_slots ?? 0))}</td><td class="num">${escapeHtml(String(b.swap_requests_total ?? 0))}</td></tr>`,
        )
        .join("");
      monthlyBlock.innerHTML = `<div class="analytics-table-card"><h3 class="analytics-section-title">По месяцам</h3><p class="muted analytics-section-hint">Назначенные слоты и заявки обмена по месяцам выбранного периода.</p><div class="table-wrap"><table class="table analytics-monthly-table"><thead><tr><th>Месяц</th><th>Обычные слоты</th><th>Утренние слоты</th><th>Обмены</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
      monthlyBlock.hidden = false;
    }

    renderAnalyticsRiskPanel(out);
    renderAnalyticsEmployeeList(listRoot, out.employee_slots);
    renderAnalyticsEmployeeList(morningListRoot, out.morning_employee_slots);
  }

  async function loadAnalytics() {
    const msg = $("#analyticsMsg");
    const start = $("#analyticsStartDate")?.value;
    const end = $("#analyticsEndDate")?.value;
    if (!start || !end) {
      showMsg(msg, "Выберите период.", "error");
      return;
    }
    try {
      showMsg(msg, "Загрузка аналитики…", "info");
      const out = await apiGetDutiesSwapsAnalytics(start, end);
      renderAnalytics(out);
      showMsg(msg, "Аналитика обновлена", "success");
    } catch (e) {
      showMsg(msg, e.message || String(e), "error");
    }
  }

  function activateTab(tabName) {
    if (tabName === "admin" && !state.isRootAdmin) {
      tabName = "graph";
    }
    const btns = $$(".tab-btn[data-tab]");
    btns.forEach((b) => {
      const isActive = b.dataset.tab === tabName;
      b.classList.toggle("active", isActive);
      b.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    const panels = $$(".tab-panel");
    panels.forEach((p) => {
      const isActive = p.id === `tab-${tabName}`;
      p.classList.toggle("active", isActive);
    });
    if (tabName === "settings") {
      refreshDutyLeaveSettingsSummary();
    }
    if (tabName === "reports") {
      void loadReportsHistory();
    }
  }

  function dutyLeaveTodayIso() {
    return localISODate();
  }

  function dutyLeaveIncludesToday(emp) {
    if (!emp || !Array.isArray(emp.duty_leave_dates)) return false;
    const t = dutyLeaveTodayIso();
    return emp.duty_leave_dates.some((d) => String(d).slice(0, 10) === t);
  }

  function openDutyLeaveModal() {
    const m = $("#dutyLeaveModal");
    if (m) {
      m.hidden = false;
      document.body.style.overflow = "hidden";
    }
  }

  function closeDutyLeaveModal() {
    const m = $("#dutyLeaveModal");
    if (m) {
      m.hidden = true;
      document.body.style.overflow = "";
    }
  }

  function syncDutyLeaveEarlyReturnRow() {
    const row = $("#dutyLeaveEarlyRow");
    const btn = $("#dutyLeaveResumeTodayBtn");
    if (!row || !btn) return;
    row.hidden = !dutyLeaveIncludesToday(state.me);
    btn.disabled = false;
  }

  function refreshDutyLeaveSettingsSummary() {
    const el = $("#dutyLeaveSettingsSummary");
    if (!el) return;
    const me = state.me;
    const arr = Array.isArray(me?.duty_leave_dates) ? me.duty_leave_dates : [];
    if (!arr.length) {
      el.textContent = "Запланированных дней нет.";
      syncDutyLeaveEarlyReturnRow();
      return;
    }
    const formatted = arr
      .map((d) => String(d).slice(0, 10))
      .sort()
      .map((iso) => formatDutyCalendarDate(iso));
    el.textContent = formatted.join(", ");
    syncDutyLeaveEarlyReturnRow();
  }

  async function loadDutyLeaveModalFromServer() {
    const out = await apiGetMeDutyLeaveDates();
    state.dutyLeaveSelected = new Set((out.dates || []).map((d) => String(d).slice(0, 10)));
    const first = [...state.dutyLeaveSelected].sort()[0];
    if (first && /^\d{4}-\d{2}-\d{2}$/.test(first)) {
      const [yy, mm] = first.split("-").map(Number);
      state.dutyLeaveCalYear = yy;
      state.dutyLeaveCalMonth = mm - 1;
    } else {
      const now = new Date();
      state.dutyLeaveCalYear = now.getFullYear();
      state.dutyLeaveCalMonth = now.getMonth();
    }
    renderDutyLeaveCalendar();
  }

  function renderDutyLeaveCalendar() {
    const grid = $("#dutyLeaveCalGrid");
    const title = $("#dutyLeaveCalTitle");
    if (!grid || !title) return;
    const y = state.dutyLeaveCalYear;
    const m = state.dutyLeaveCalMonth;
    title.textContent = new Date(y, m, 1).toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
    grid.innerHTML = "";
    const wd = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];
    for (const h of wd) {
      const el = document.createElement("div");
      el.className = "cal-head";
      el.textContent = h;
      grid.appendChild(el);
    }
    const firstDow = (new Date(y, m, 1).getDay() + 6) % 7;
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const prevDays = new Date(y, m, 0).getDate();
    const todayIso = dutyLeaveTodayIso();
    for (let i = 0; i < firstDow; i++) {
      const dayNum = prevDays - firstDow + i + 1;
      const cell = document.createElement("div");
      cell.className = "cal-cell muted";
      cell.textContent = String(dayNum);
      grid.appendChild(cell);
    }
    for (let d = 1; d <= daysInMonth; d++) {
      const iso = localISODate(new Date(y, m, d));
      const cell = document.createElement("div");
      cell.className = "cal-cell";
      cell.textContent = String(d);
      if (iso === todayIso) cell.classList.add("today");
      if (iso < todayIso) {
        cell.classList.add("past");
      } else {
        cell.addEventListener("click", () => {
          if (state.dutyLeaveSelected.has(iso)) state.dutyLeaveSelected.delete(iso);
          else state.dutyLeaveSelected.add(iso);
          renderDutyLeaveCalendar();
        });
      }
      if (state.dutyLeaveSelected.has(iso)) cell.classList.add("selected");
      grid.appendChild(cell);
    }
    const totalCells = 42;
    const used = firstDow + daysInMonth;
    let n = 1;
    for (let i = used; i < totalCells; i++) {
      const cell = document.createElement("div");
      cell.className = "cal-cell muted";
      cell.textContent = String(n++);
      grid.appendChild(cell);
    }
  }

  function resetEmployeeExitShareUi() {
    const block = $("#employeeExitShareBlock");
    const img = $("#eeQrImg");
    const dl = $("#employeeExitQrDownloadBtn");
    const link = $("#eePublicLink");
    if (block) block.hidden = true;
    if (img) {
      img.hidden = true;
      img.removeAttribute("src");
    }
    if (dl) dl.hidden = true;
    if (link) {
      link.textContent = "";
      link.href = "#";
    }
    state.eeLastQrToken = null;
  }

  function resetEeBlocksToDefault() {
    for (const cb of $$('input[name="eeBlock"]')) {
      cb.checked = true;
    }
  }

  function gatherEeInstructionBlocks() {
    const cbs = $$('input[name="eeBlock"]:checked');
    if (!cbs.length) throw new Error("Отметьте хотя бы один блок текста.");
    return cbs.map((cb) => cb.value);
  }

  function openEmployeeExitModal() {
    resetEmployeeExitShareUi();
    resetEeBlocksToDefault();
    const m = $("#employeeExitModal");
    if (m) {
      m.hidden = false;
      document.body.style.overflow = "hidden";
    }
  }

  function closeEmployeeExitModal() {
    const m = $("#employeeExitModal");
    if (m) {
      m.hidden = true;
      document.body.style.overflow = "";
    }
  }

  async function loadDuties(dateStr) {
    if (!dateStr) return;

    const duties = await apiFetchJson(`/api/duties?date=${encodeURIComponent(dateStr)}`);
    const slots = Array.isArray(duties?.slots) ? duties.slots : [];
    if (slots.length > 0) {
      state.slotCount = slots.length;
      const firstTime = slots[0]?.start_time;
      if (typeof firstTime === "string" && /^\d{2}:\d{2}$/.test(firstTime)) {
        const parsedHour = Number(firstTime.slice(0, 2));
        if (Number.isInteger(parsedHour) && parsedHour >= 0 && parsedHour <= 23) {
          state.slotStartHour = parsedHour;
        }
      }
    }
    state.dutiesLoadedForDate = dateStr;
    state.currentDuties = duties;

    updateScheduleTitle(dateStr);
    renderDutiesTable(duties);
    updateCurrentDutyNow();
    showMsg($("#dutiesMsg"), "График загружен.", "success");
    const swapD = $("#swapDate")?.value;
    if (swapD === dateStr) {
      try {
        await refreshSwapSlotSelects();
      } catch {
        /* ignore: обмен подтянется при смене даты */
      }
    }
  }

  function updateCurrentDutyNow() {
    const nameEl = $("#currentDutyName");
    const timeEl = $("#currentDutyTime");
    const tbody = $("#dutiesTable tbody");
    if (!nameEl || !timeEl || !tbody) return;

    for (const tr of $$("tr", tbody)) tr.classList.remove("current-slot");

    const duties = state.currentDuties;
    const selectedDate = state.dutiesLoadedForDate || $("#dutiesDate")?.value || "";
    const today = localISODate();
    if (!duties || !selectedDate || selectedDate !== today) {
      nameEl.textContent = "—";
      timeEl.textContent = "—";
      const avatar = $(".avatar-circle");
      if (avatar) avatar.textContent = "—";
      return;
    }

    const slot = new Date().getHours() - state.slotStartHour;
    if (!Number.isInteger(slot) || slot < 0 || slot >= state.slotCount) {
      nameEl.textContent = "—";
      timeEl.textContent = "—";
      const avatar = $(".avatar-circle");
      if (avatar) avatar.textContent = "—";
      return;
    }

    const slotOut = (Array.isArray(duties.slots) ? duties.slots : []).find((s) => Number(s.slot) === slot);
    const user = slotOut?.user || null;
    const name = user ? (user.full_name || user.username) : "не назначен";
    nameEl.textContent = name;
    timeEl.textContent = slotStartLabel(slot);
    const avatar = $(".avatar-circle");
    if (avatar) avatar.textContent = user ? initialsFromName(name) : "—";

    const row = tbody.querySelector(`tr[data-slot="${slot}"]`);
    if (row && !row.hidden) row.classList.add("current-slot");
  }

  function renderDutiesTable(dutiesOut) {
    const tbody = $("#dutiesTable tbody");
    tbody.innerHTML = "";

    const isAdmin = state.canManageDuties;
    const slots = dutiesOut?.slots || [];
    const filter = state.dutyDisplayFilter || "all";
    const myId = state.me?.id != null ? Number(state.me.id) : null;

    const slotCount = Array.isArray(slots) && slots.length ? slots.length : state.slotCount;
    for (let slot = 0; slot < slotCount; slot++) {
      const slotOut = slots.find((s) => Number(s.slot) === slot) || slots[slot];
      const user = slotOut?.user || null;

      let hideRow = false;
      if (filter === "mine") {
        hideRow = !user || myId == null || Number(user.id) !== myId;
      } else if (filter === "unassigned") {
        hideRow = !!user;
      }

      const tr = document.createElement("tr");
      tr.dataset.slot = String(slot);
      tr.hidden = hideRow;

      const tdTime = document.createElement("td");
      tdTime.textContent = slotRangeLabel(slot);

      const tdUser = document.createElement("td");
      if (isAdmin) {
        const select = document.createElement("select");
        select.className = "duty-user-select";
        select.dataset.slot = String(slot);

        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = "—";
        select.appendChild(blank);

        for (const emp of supportEmployeesForDutySlotSelect(user)) {
          const opt = document.createElement("option");
          opt.value = String(emp.id);
          const title = emp.full_name || emp.username;
          opt.textContent = emp.is_active_for_duties === false ? `${title} (не в графике дежурств)` : title;
          if (user && Number(user.id) === Number(emp.id)) opt.selected = true;
          select.appendChild(opt);
        }

        tdUser.appendChild(select);
      } else {
        if (user) {
          const base = user.full_name || user.username;
          tdUser.textContent =
            user.is_active_for_duties === false ? `${base} (не в графике дежурств)` : base;
        } else {
          tdUser.textContent = "—";
        }
      }

      if (myId != null && user && Number(user.id) === myId) {
        tr.classList.add("duty-row-self");
        tr.title = "Ваш слот дежурства на выбранную дату";
      }

      tr.appendChild(tdTime);
      tr.appendChild(tdUser);
      tbody.appendChild(tr);
    }
  }

  function setDutyViewMode(mode) {
    const normalized = mode === "week" || mode === "month" ? mode : "table";
    state.dutyViewMode = normalized;
    const tableWrap = $("#dutiesTable")?.closest(".table-wrap");
    const calendarWrap = $("#dutiesCalendarWrap");
    if (tableWrap) tableWrap.hidden = normalized !== "table";
    if (calendarWrap) calendarWrap.hidden = normalized === "table";
    if (normalized === "table") state.dutyCalendarRaw = null;
  }

  function syncDutyFilterOptions() {
    const sel = $("#dutiesDisplayFilter");
    if (!sel) return;
    let optUn = sel.querySelector('option[value="unassigned"]');
    if (state.canManageDuties) {
      if (!optUn) {
        optUn = document.createElement("option");
        optUn.value = "unassigned";
        optUn.textContent = "Только пустые слоты";
        sel.appendChild(optUn);
      }
    } else if (optUn) {
      optUn.remove();
    }
    if (sel.value === "unassigned" && !state.canManageDuties) sel.value = "all";
  }

  function normalizeDutyCalendarDay(date, duties) {
    const slots = Array.isArray(duties?.slots) ? duties.slots : [];
    const slotCount = slots.length || state.slotCount;
    const bySlot = [];
    for (let slot = 0; slot < slotCount; slot += 1) {
      const slotOut = slots.find((s) => Number(s?.slot) === slot);
      const user = slotOut?.user || null;
      bySlot.push({ slot, user });
    }
    return { date, slots: bySlot, slotCount };
  }

  function projectCalendarDayForFilter(day) {
    const filter = state.dutyDisplayFilter || "all";
    const myId = state.me?.id != null ? Number(state.me.id) : null;

    if (filter === "mine") {
      const rows = [];
      for (const { slot, user } of day.slots) {
        if (user && myId != null && Number(user.id) === myId) {
          rows.push({ slot, name: user.full_name || user.username || "—", isSelf: true });
        }
      }
      rows.sort((a, b) => a.slot - b.slot);
      const n = rows.length;
      return {
        date: day.date,
        rows,
        assignedCount: n,
        slotCount: day.slotCount,
        countLabel: `${n} ваших · ${day.slotCount} слотов`,
        emptyText: "Нет ваших дежурств в этот день.",
      };
    }

    if (filter === "unassigned") {
      const rows = [];
      for (const { slot, user } of day.slots) {
        if (!user) {
          rows.push({ slot, name: "", isSelf: false, isEmpty: true });
        }
      }
      rows.sort((a, b) => a.slot - b.slot);
      const n = rows.length;
      return {
        date: day.date,
        rows,
        assignedCount: n,
        slotCount: day.slotCount,
        countLabel: `${n} пустых · ${day.slotCount} слотов`,
        emptyText: "Все слоты заполнены.",
      };
    }

    const rows = [];
    let assignedCount = 0;
    for (const { slot, user } of day.slots) {
      if (user) {
        rows.push({
          slot,
          name: user.full_name || user.username || "—",
          isSelf: myId != null && Number(user.id) === myId,
        });
        assignedCount += 1;
      }
    }
    rows.sort((a, b) => a.slot - b.slot);
    return {
      date: day.date,
      rows,
      assignedCount,
      slotCount: day.slotCount,
      countLabel: `${assignedCount} из ${day.slotCount}`,
      emptyText: "Назначений нет.",
    };
  }

  function renderDutiesCalendarFromCache() {
    const pack = state.dutyCalendarRaw;
    if (!pack) return;
    const projected = pack.days.map(projectCalendarDayForFilter);
    renderDutiesCalendarDays(projected, pack.title, pack.anchorDate);
  }

  function refreshDutyFilterViews() {
    if (state.currentDuties) renderDutiesTable(state.currentDuties);
    updateCurrentDutyNow();
    if (state.dutyViewMode === "week" || state.dutyViewMode === "month") {
      renderDutiesCalendarFromCache();
    }
  }

  function renderDutiesCalendarDays(days, title, selectedDate) {
    const titleEl = $("#dutiesCalendarTitle");
    const grid = $("#dutiesCalendarGrid");
    if (!titleEl || !grid) return;
    titleEl.textContent = title || "Календарный график";
    grid.innerHTML = "";
    for (const item of days) {
      const card = document.createElement("div");
      card.className = "duty-day-card";
      if (item.date === selectedDate) card.classList.add("is-selected");
      const header = document.createElement("div");
      header.className = "duty-day-header";
      const dateEl = document.createElement("div");
      dateEl.className = "duty-day-date";
      dateEl.textContent = formatDutyCalendarDate(item.date);
      const countEl = document.createElement("div");
      countEl.className = "muted";
      countEl.textContent =
        item.countLabel != null && item.countLabel !== ""
          ? item.countLabel
          : `${item.assignedCount} из ${item.slotCount}`;
      header.appendChild(dateEl);
      header.appendChild(countEl);
      card.appendChild(header);
      if (!item.rows.length) {
        const empty = document.createElement("div");
        empty.className = "duty-day-empty";
        empty.textContent = item.emptyText || "Назначений нет.";
        card.appendChild(empty);
      } else {
        const ul = document.createElement("ul");
        ul.className = "duty-day-list";
        for (const row of item.rows) {
          const li = document.createElement("li");
          if (row.isSelf) {
            li.classList.add("duty-day-list-self");
            li.title = "Ваше дежурство";
          }
          if (row.isEmpty) {
            li.classList.add("duty-day-list-unassigned");
            li.textContent = `${slotStartLabel(row.slot)} — не назначено`;
          } else {
            li.textContent = `${slotStartLabel(row.slot)} - ${row.name}`;
          }
          ul.appendChild(li);
        }
        card.appendChild(ul);
      }
      grid.appendChild(card);
    }
  }

  async function loadDutiesCalendar(dateStr) {
    const mode = state.dutyViewMode;
    if (mode !== "week" && mode !== "month") return;
    const { dates, title } = getDutyCalendarRange(dateStr, mode);
    const normalizedDays = await Promise.all(
      dates.map(async (date) => {
        const duties = await apiFetchJson(`/api/duties?date=${encodeURIComponent(date)}`);
        return normalizeDutyCalendarDay(date, duties);
      })
    );
    state.dutyCalendarRaw = { mode, anchorDate: dateStr, title, days: normalizedDays };
    renderDutiesCalendarFromCache();
  }

  async function saveDuties(dateStr) {
    const isAdmin = state.canManageDuties;
    if (!isAdmin) return;

    const assignments = [];
    const selects = $$(".duty-user-select");
    const seenSlots = new Set();

    for (const sel of selects) {
      const slot = Number(sel.dataset.slot);
      seenSlots.add(slot);
      const userId = sel.value ? Number(sel.value) : null;
      assignments.push({ slot, user_id: userId });
    }

    // Ensure all rendered slots are present (defensive).
    if (seenSlots.size !== state.slotCount) {
      throw new Error("Не удалось собрать все слоты графика.");
    }

    await apiFetchJson("/api/duties/batch", {
      method: "POST",
      body: { date: dateStr, assignments },
    });

    await loadDuties(dateStr);
    await loadDutiesCalendar(dateStr);
  }

  function sumEntryMinutesFromCard(card) {
    if (!card) return 0;
    let sum = 0;
    for (const inp of card.querySelectorAll(".entry-minutes")) {
      const n = Number(inp.value);
      sum += Number.isFinite(n) ? Math.max(0, n) : 0;
    }
    return sum;
  }

  function formatKpiHoursMinutes(totalMinutes) {
    const t = Math.max(0, Math.floor(Number(totalMinutes) || 0));
    const h = Math.floor(t / 60);
    const m = t % 60;
    return `${h} ч ${String(m).padStart(2, "0")} м`;
  }

  function refreshReportsKpi() {
    const strip = $("#reportsKpiStrip");
    if (!strip) return;
    const cards = document.querySelectorAll("#reportsList .report-card");
    if (!cards.length) {
      strip.hidden = true;
      return;
    }
    strip.hidden = false;
    let totalRows = 0;
    let totalMinutes = 0;
    for (const card of cards) {
      totalRows += card.querySelectorAll(".entries-table tbody tr").length;
      totalMinutes += sumEntryMinutesFromCard(card);
    }

    const first = cards[0];
    const status = first.dataset.reportStatus || "draft";
    const empName = first.dataset.employeeName || "";
    const finalizedAt = first.dataset.finalizedAt || "";

    const elEntries = $("#reportsKpiEntries");
    const elHours = $("#reportsKpiHours");
    const elStatus = $("#reportsKpiStatus");
    const elUpdated = $("#reportsKpiUpdated");
    if (elEntries) elEntries.textContent = String(totalRows);
    if (elHours) elHours.textContent = formatKpiHoursMinutes(totalMinutes);
    if (elStatus) {
      elStatus.textContent = formatReportStatusRu(status);
      elStatus.className =
        "reports-kpi-value reports-kpi-status " + (status === "final" ? "is-final" : "is-draft");
    }
    if (elUpdated) {
      let text = "—";
      if (status === "final" && finalizedAt) {
        text = `${formatLastLoginAt(finalizedAt)} · ${formatShortEmployeeName(empName)}`;
      } else {
        text = `Черновик · ${formatShortEmployeeName(empName)}`;
      }
      elUpdated.textContent = text;
    }
  }

  async function loadReportsHistory() {
    if (!$("#reportsHistoryList")) return;
    try {
      const list = await apiFetchJson("/api/reports/recent?limit=15");
      state.reportsHistory = Array.isArray(list) ? list : [];
    } catch {
      state.reportsHistory = [];
    }
    renderReportsHistoryList();
  }

  function renderReportsHistoryList() {
    const host = $("#reportsHistoryList");
    const badge = $("#reportsHistoryCount");
    if (!host) return;
    const list = state.reportsHistory || [];
    if (badge) {
      badge.hidden = !list.length;
      badge.textContent = String(list.length);
    }
    if (!list.length) {
      host.innerHTML = '<p class="muted">Пока нет отчётов с сохранёнными изменениями.</p>';
      return;
    }
    host.innerHTML = list
      .map((rec) => {
        const stClass = rec.status === "final" ? "exported" : "draft";
        const statusText = formatReportStatusRu(rec.status);
        const dateStr = String(rec.date ?? "").trim();
        const employeeName =
          rec.employee?.full_name || rec.employee?.username || `ID ${rec.employee_id ?? "?"}`;
        let timeLine = "—";
        if (rec.status === "final" && rec.finalized_at) {
          timeLine = `Экспорт: ${formatLastLoginAt(rec.finalized_at)}`;
        } else if (rec.updated_at) {
          timeLine = `Изменено: ${formatLastLoginAt(rec.updated_at)}`;
        }
        return `<div class="reports-history-item">
          <div class="reports-history-date">${escapeHtml(dateStr)}</div>
          <div class="reports-history-name">${escapeHtml(employeeName)}</div>
          <span class="reports-history-status reports-history-status--${stClass}">${escapeHtml(statusText)}</span>
          <div class="muted reports-history-time">${escapeHtml(timeLine)}</div>
        </div>`;
      })
      .join("");
  }

  function updateReportMinutesTotal(card) {
    void card;
    refreshReportsKpi();
  }

  function renderEntriesTable(reportId, report, editable) {
    const entriesTbody = document.querySelector(
      `.report-card[data-report-id="${reportId}"] .entries-table tbody`
    );

    entriesTbody.innerHTML = "";

    const entries = Array.isArray(report.entries) ? report.entries : [];
    const rows = entries.length ? entries : [{ task: "", minutes: 0, description: "" }];

    rows.forEach((entry, idx) => {
      const tr = document.createElement("tr");
      tr.dataset.entryIndex = String(idx);

      const tdTask = document.createElement("td");
      const taskInput = document.createElement("input");
      taskInput.type = "text";
      taskInput.maxLength = 500;
      taskInput.value = entry.task ?? "";
      taskInput.className = "entry-task";
      taskInput.disabled = !editable;
      tdTask.appendChild(taskInput);

      const tdDesc = document.createElement("td");
      const descInput = document.createElement("textarea");
      descInput.value = entry.description ?? "";
      descInput.className = "entry-description";
      descInput.disabled = !editable;
      tdDesc.appendChild(descInput);

      const tdMinutes = document.createElement("td");
      const minutesInput = document.createElement("input");
      minutesInput.type = "number";
      minutesInput.min = "0";
      minutesInput.max = "1440";
      minutesInput.step = "1";
      minutesInput.value = String(entry.minutes ?? 0);
      minutesInput.className = "entry-minutes";
      minutesInput.disabled = !editable;
      tdMinutes.appendChild(minutesInput);

      const tdActions = document.createElement("td");
      if (editable) {
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "btn danger";
        delBtn.title = "Удалить строку";
        delBtn.setAttribute("aria-label", "Удалить");
        delBtn.textContent = "🗑";
        delBtn.dataset.action = "removeEntry";
        delBtn.dataset.reportId = String(reportId);
        delBtn.addEventListener("click", () => {
          tr.remove();
          updateReportMinutesTotal(getReportCard(reportId));
        });
        tdActions.appendChild(delBtn);
      }

      tr.appendChild(tdTask);
      tr.appendChild(tdDesc);
      tr.appendChild(tdMinutes);
      tr.appendChild(tdActions);
      entriesTbody.appendChild(tr);
    });

    updateReportMinutesTotal(getReportCard(reportId));
  }

  function getReportCard(reportId) {
    return document.querySelector(`.report-card[data-report-id="${reportId}"]`);
  }

  function gatherReportEntries(reportId) {
    const card = getReportCard(reportId);
    if (!card) return [];

    const minutesInputs = $$(".entry-minutes", card);
    const descInputs = $$(".entry-description", card);
    const rows = card.querySelectorAll(".entries-table tbody tr");

    const entries = [];
    let idx = 0;
    for (const tr of rows) {
      const taskEl = tr.querySelector(".entry-task");
      const minutesEl = tr.querySelector(".entry-minutes");
      const descEl = tr.querySelector(".entry-description");
      const minutes = Number(minutesEl.value);
      const description = (descEl.value || "").trim();
      const task = (taskEl?.value || "").trim();
      entries.push({ task, minutes, description });
      idx += 1;
    }
    return entries;
  }

  async function finalizeReportExcel(reportId) {
    const card = getReportCard(reportId);
    if (!card) return;

    const btn = card.querySelector(`button[data-action="finalizeExcel"]`);
    if (btn) btn.disabled = true;
    try {
      const entries = gatherReportEntries(reportId);
      if (!entries.length) throw new Error("Добавьте хотя бы одну запись.");
      for (const [i, e] of entries.entries()) {
        if (!Number.isFinite(e.minutes)) throw new Error(`Минуты в записи ${i + 1} должны быть числом.`);
        if (e.minutes < 0 || e.minutes > 1440)
          throw new Error(`Минуты в записи ${i + 1} должны быть в диапазоне 0..1440.`);
        if (!e.description) throw new Error(`Результат в записи ${i + 1} не должен быть пустым.`);
        if (e.description.length > 2000) throw new Error(`Результат в записи ${i + 1} слишком длинный.`);
        if ((e.task || "").length > 500) throw new Error(`Задача в записи ${i + 1} слишком длинная.`);
      }
      await apiFetchJson(`/api/reports/${reportId}`, {
        method: "PUT",
        body: { entries },
      });

      const out = await apiFetchJson(`/api/reports/${reportId}/finalize`, { method: "POST" });
      // Backend returns excel_url even if already finalized.
      const excelUrl = out?.excel_url || "";
      if (!excelUrl) throw new Error("Не удалось получить ссылку на Excel.");

      // Refresh from backend so status and entries remain consistent.
      const date = $("#reportsDate")?.value;
      const selectedEmployeeId = state.canManageReports ? $("#reportsEmployeeSelect")?.value : null;
      await loadReports(date, selectedEmployeeId);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function downloadAllExcelsForDate(dateStr) {
    if (!dateStr) throw new Error("Выберите дату.");
    const res = await fetch(
      apiUrl(`/api/admin/reports/export-all?date=${encodeURIComponent(dateStr)}`),
      {
      method: "GET",
      credentials: "same-origin",
    });
    if (!res.ok) {
      const text = await res.text();
      let detail = "";
      try {
        const json = text ? JSON.parse(text) : null;
        detail = formatApiDetail(json?.detail || json?.message);
      } catch {
        detail = text || "";
      }
      throw new Error(detail || `HTTP ${res.status}`);
    }

    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const nameMatch = cd.match(/filename="([^"]+)"/i);
    const filename = nameMatch ? nameMatch[1] : `excel_reports_${dateStr}.zip`;
    const missingRaw = res.headers.get("X-Missing-Employees") || "";
    const missing = decodeURIComponent(missingRaw)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", filename);
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    return missing;
  }

  async function downloadDutiesPeriodExcel() {
    const start = $("#genStartDate")?.value;
    const end = $("#genEndDate")?.value;
    if (!start || !end) throw new Error("Укажите начало и конец периода.");
    const res = await fetch(
      apiUrl(
        `/api/duties/export-period?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`,
      ),
      { method: "GET", credentials: "same-origin" },
    );
    if (!res.ok) {
      const text = await res.text();
      let detail = "";
      try {
        const json = text ? JSON.parse(text) : null;
        detail = formatApiDetail(json?.detail || json?.message);
      } catch {
        detail = text || "";
      }
      throw new Error(detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const nameMatch = cd.match(/filename="([^"]+)"/i);
    const filename = nameMatch ? nameMatch[1] : `duties_${start}_${end}.xlsx`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", filename);
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function ensureReportExists(dateStr, employeeIdOrNull) {
    if (!dateStr) return;

    if (state.canManageReports) {
      const employeeId = Number(employeeIdOrNull);
      if (!employeeId) throw new Error("Выберите сотрудника для отчета.");
      await apiFetchJson("/api/reports", {
        method: "POST",
        body: { date: dateStr, employee_id: employeeId },
      });
    } else {
      await apiFetchJson("/api/reports", { method: "POST", body: { date: dateStr } });
    }
  }

  async function loadReports(dateStr, employeeIdOrNull) {
    if (!dateStr) return;

    const employeeId = state.canManageReports ? Number(employeeIdOrNull) : null;
    const reportsKey = `${dateStr}|${state.canManageReports ? employeeId : "me"}`;
    state.reportsLoadedKey = reportsKey;

    await ensureReportExists(dateStr, employeeId);

    const query = new URLSearchParams();
    query.set("date", dateStr);
    if (state.canManageReports && employeeId) query.set("employee_id", String(employeeId));

    const list = await apiFetchJson(`/api/reports?${query.toString()}`);
    const reports = Array.isArray(list) ? list : [];
    renderReportsList(reports);
    await loadReportsHistory();
    showMsg($("#reportsMsg"), "Отчеты загружены", "success");
  }

  function renderReportCard(report) {
    const reportsList = $("#reportsList");
    const reportId = report.report_id;
    const editable = true;

    const card = document.createElement("div");
    card.className = "report-card card";
    card.setAttribute("data-report-id", String(reportId));

    const employeeName = report.employee?.full_name || report.employee?.username || `ID ${report.employee_id}`;
    const status = report.status;
    const statusRu = formatReportStatusRu(status);
    const dateStr = String(report.date ?? "").trim();
    const isFinal = status === "final";

    let excelDownloadHtml = "";
    if (isFinal && dateStr) {
      const excelPath = appRootPath(`/exports/report_${reportId}_${dateStr}.xlsx`);
      const excelHref = escapeHtml(excelPath);
      excelDownloadHtml = `<a class="btn secondary" href="${excelHref}" target="_blank" rel="noopener">Скачать Excel</a>`;
    } else {
      excelDownloadHtml = '<button type="button" class="btn secondary" disabled>Скачать Excel</button>';
    }

    card.dataset.reportStatus = status;
    card.dataset.finalizedAt = report.finalized_at ? String(report.finalized_at) : "";
    card.dataset.employeeName = employeeName;

    card.innerHTML = `
      <div class="report-header">
        <div>
          <div class="report-title-line"><strong>${escapeHtml(employeeName)}</strong></div>
          <div class="muted">${escapeHtml(report.date)} · статус: ${escapeHtml(statusRu)}</div>
        </div>
        <div class="status-pill ${isFinal ? "status-pill-final" : ""}">${escapeHtml(statusRu)}</div>
      </div>

      <div class="entries">
        <table class="table entries-table">
          <thead>
            <tr>
              <th style="width: 22%;">Задача</th>
              <th>Результат</th>
              <th style="width: 120px;">Время работы</th>
              <th style="width: 96px;">Действия</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
        <div class="report-table-footer">
          <button class="btn btn-link" type="button" data-action="addEntry" data-report-id="${escapeHtml(String(reportId))}" ${
      editable ? "" : "disabled"
    }>+ Добавить запись</button>
          <div class="report-footer-actions">
            <button class="btn primary" type="button" data-action="finalizeExcel" data-report-id="${escapeHtml(String(reportId))}">Сформировать Excel</button>
            ${excelDownloadHtml}
          </div>
        </div>
      </div>
    `;

    reportsList.appendChild(card);

    renderEntriesTable(reportId, report, editable);
  }

  function renderReportsList(reports) {
    const reportsList = $("#reportsList");
    reportsList.innerHTML = "";

    if (!reports.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "Нет отчётов на выбранную дату (проверьте дату или выбранного сотрудника).";
      reportsList.appendChild(empty);
      refreshReportsKpi();
      return;
    }

    reports.forEach((r) => renderReportCard(r));
    refreshReportsKpi();
  }

  function setReportCardEditable(card, editable) {
    for (const input of card.querySelectorAll("input.entry-task, input.entry-minutes, textarea.entry-description")) {
      input.disabled = !editable;
    }
    for (const btn of card.querySelectorAll('button[data-action="addEntry"]')) {
      btn.disabled = !editable;
    }
  }

  async function refreshSwapSlotSelects() {
    const fromSel = $("#swapFromSlot");
    const toSel = $("#swapToSlot");
    if (!fromSel || !toSel) return;

    const dateStr = $("#swapDate")?.value || localISODate();
    let duties = null;
    if (state.dutiesLoadedForDate === dateStr && state.currentDuties) {
      duties = state.currentDuties;
    } else {
      try {
        duties = await apiFetchJson(`/api/duties?date=${encodeURIComponent(dateStr)}`);
      } catch {
        duties = null;
      }
    }

    if (!duties || !Array.isArray(duties.slots)) {
      fromSel.innerHTML = "";
      toSel.innerHTML = "";
      const o = document.createElement("option");
      o.value = "";
      o.disabled = true;
      o.textContent = "Не удалось загрузить график на эту дату";
      fromSel.appendChild(o);
      toSel.appendChild(o.cloneNode(true));
      return;
    }

    const slots = duties.slots;
    if (slots.length > 0) {
      state.slotCount = slots.length;
      const firstTime = slots[0]?.start_time;
      if (typeof firstTime === "string" && /^\d{2}:\d{2}$/.test(firstTime)) {
        const parsedHour = Number(firstTime.slice(0, 2));
        if (Number.isInteger(parsedHour) && parsedHour >= 0 && parsedHour <= 23) {
          state.slotStartHour = parsedHour;
        }
      }
    }

    const myId = state.me?.id != null ? Number(state.me.id) : NaN;
    const prevFrom = fromSel.value;
    const prevTo = toSel.value;

    fromSel.innerHTML = "";
    const mySlots = [];
    for (const s of slots) {
      const slot = Number(s.slot);
      const u = s.user || null;
      if (u && Number.isFinite(myId) && Number(u.id) === myId) {
        mySlots.push(slot);
        const opt = document.createElement("option");
        opt.value = String(slot);
        opt.textContent = slotRangeLabel(slot);
        fromSel.appendChild(opt);
      }
    }
    if (!mySlots.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.disabled = true;
      opt.textContent = "Нет вашего слота в графике на эту дату";
      fromSel.appendChild(opt);
      toSel.innerHTML = "";
      const toPlaceholder = document.createElement("option");
      toPlaceholder.value = "";
      toPlaceholder.disabled = true;
      toPlaceholder.textContent = "—";
      toSel.appendChild(toPlaceholder);
      fromSel.onchange = null;
      return;
    }
    if (mySlots.includes(Number(prevFrom))) {
      fromSel.value = String(prevFrom);
    } else {
      fromSel.value = String(mySlots[0]);
    }

    const rebuildTo = () => {
      const fromVal = Number(fromSel.value);
      const fromOk = Number.isInteger(fromVal) && fromVal >= 0;
      toSel.innerHTML = "";
      for (const s of slots) {
        const slot = Number(s.slot);
        const u = s.user || null;
        const timeStr = slotRangeLabel(slot);
        const nameStr = u ? (u.full_name || u.username || "—") : "не назначено";
        const opt = document.createElement("option");
        opt.value = String(slot);
        opt.textContent = `${timeStr} — ${nameStr}`;
        const canTarget = Boolean(
          u &&
            Number.isFinite(myId) &&
            Number(u.id) !== myId &&
            fromOk &&
            slot !== fromVal,
        );
        opt.disabled = !canTarget;
        toSel.appendChild(opt);
      }
      const tryPrev = [...toSel.options].find((o) => o.value === prevTo && !o.disabled);
      if (tryPrev) toSel.value = prevTo;
      else {
        const firstOk = [...toSel.options].find((o) => !o.disabled);
        if (firstOk) toSel.value = firstOk.value;
      }
    };

    rebuildTo();
    fromSel.onchange = rebuildTo;
  }

  function renderSwapInbox(items) {
    const root = $("#swapInboxList");
    if (!root) return;
    root.innerHTML = "";
    const rows = Array.isArray(items) ? items : [];
    const badge = $("#swapInboxBadge");
    if (badge) badge.textContent = String(rows.filter((r) => (r.status || "pending") === "pending").length);
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "Входящих запросов нет.";
      root.appendChild(empty);
      return;
    }
    for (const item of rows) {
      const el = document.createElement("div");
      el.className = "report-card swap-request-card";
      const statusLabel = item.status || "pending";
      const controls =
        statusLabel === "pending"
          ? `
        <div class="actions swap-request-actions">
          <button type="button" class="btn" data-action="swapAccept" data-swap-id="${escapeHtml(String(item.id || ""))}">Принять</button>
          <button type="button" class="btn danger" data-action="swapReject" data-swap-id="${escapeHtml(String(item.id || ""))}">Отклонить</button>
        </div>`
          : "";
      el.innerHTML = `
        <div><strong>${escapeHtml(item.message || "")}</strong></div>
        <div class="muted">${escapeHtml(item.date || "")} · ${escapeHtml(item.created_at || "")} · статус: ${escapeHtml(statusLabel)}</div>
        ${controls}
      `;
      root.appendChild(el);
    }
  }

  async function refreshSwapInbox() {
    const dateStr = $("#swapDate")?.value || $("#dutiesDate")?.value || localISODate();
    const list = await apiGetDutySwapInbox(dateStr);
    renderSwapInbox(list);
  }

  async function onIndexInit() {
    // Role & auth
    let me;
    try {
      me = await apiGetMe();
    } catch (e) {
      // If session is missing, go to login.
      window.location.href = "/login.html";
      return;
    }

    state.me = me;
    const caps = userCapabilities(me);
    state.isRootAdmin = caps.isRootAdmin;
    state.canManageDuties = caps.canManageDuties;
    state.canManageReports = caps.canManageReports;
    state.canManageNotifications = caps.canManageNotifications;
    state.isAdmin = state.canManageDuties;
    state.hasAdminAccess =
      state.isRootAdmin || state.canManageDuties || state.canManageReports || state.canManageNotifications;

    const meText = $("#meText");
    if (meText) {
      meText.innerHTML = `<span>${escapeHtml(me.full_name || me.username || "")}</span><span class="user-role-badge">${escapeHtml(me.role || "")}</span>`;
    }
    const selfFullName = $("#selfFullName");
    if (selfFullName) selfFullName.value = me.full_name || "";
    renderUsefulResources();
    initResourcesPageHandlers();
    $("#resourcesSearchInput")?.addEventListener("input", () => {
      state.resourceGridFilter = "all";
      renderUsefulResources();
    });
    $$(".resource-category-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.resourceCategory = btn.dataset.resourceCategory || "all";
        state.resourceGridFilter = "all";
        renderUsefulResources();
      });
    });

    const syncAdminDutyToggle = () => {
      const select = $("#adminUserSelect");
      const toggle = $("#adminDutyActiveToggle");
      const hint = $("#adminDutyLeaveHint");
      if (!select || !toggle) return;
      const userId = Number(select.value);
      const target = state.employees.find((u) => Number(u.id) === userId);
      const leaveToday = dutyLeaveIncludesToday(target);
      if (hint) {
        const arr = Array.isArray(target?.duty_leave_dates) ? target.duty_leave_dates : [];
        if (arr.length) {
          hint.hidden = false;
          hint.textContent = `Без участия в генерации: ${arr
            .map((d) => String(d).slice(0, 10))
            .sort()
            .map((iso) => formatDutyCalendarDate(iso))
            .join(", ")}`;
        } else {
          hint.hidden = true;
          hint.textContent = "";
        }
      }
      toggle.checked = target ? target.is_active_for_duties !== false && !leaveToday : true;
      toggle.disabled = Boolean(target && leaveToday);
    };

    setAdminMode(state.hasAdminAccess);
    syncDutyFilterOptions();

    // Logout
    const logoutBtn = $("#logoutBtn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", async () => {
        try {
          await apiLogout();
        } finally {
          window.location.href = "/login.html";
        }
      });
    }

    // Tab switching
    for (const tabBtn of $$(".tab-btn")) {
      tabBtn.addEventListener("click", () => {
        const tab = tabBtn.dataset.tab;
        if (!tab) return;
        activateTab(tab);
      });
    }
    for (const tabBtn of $$(".admin-subtab-btn")) {
      tabBtn.addEventListener("click", () => {
        const tab = tabBtn.dataset.adminTab;
        if (!tab) return;
        activateAdminSubtab(tab);
      });
    }

    for (const openId of ["employeeExitOpenBtnHero"]) {
      $(`#${openId}`)?.addEventListener("click", () => {
        showMsg($("#employeeExitMsg"), "", "info");
        openEmployeeExitModal();
        setTimeout(() => $("#eeFio")?.focus(), 0);
      });
    }
    $("#employeeExitCloseBtn")?.addEventListener("click", () => closeEmployeeExitModal());
    $("#employeeExitModal")?.addEventListener("click", (ev) => {
      if (ev.target === $("#employeeExitModal")) closeEmployeeExitModal();
    });
    document.addEventListener("keydown", (ev) => {
      const m = $("#employeeExitModal");
      if (m && !m.hidden && ev.key === "Escape") closeEmployeeExitModal();
      const dl = $("#dutyLeaveModal");
      if (dl && !dl.hidden && ev.key === "Escape") closeDutyLeaveModal();
    });

    $("#dutyLeaveOpenBtn")?.addEventListener("click", async () => {
      const msg = $("#dutyLeaveModalMsg");
      try {
        showMsg(msg, "", "info");
        await loadDutyLeaveModalFromServer();
        openDutyLeaveModal();
      } catch (e) {
        showMsg($("#dutiesMsg"), e.message || String(e), "error");
      }
    });
    $("#dutyLeaveOpenFromSettingsBtn")?.addEventListener("click", async () => {
      const msg = $("#dutyLeaveSettingsMsg");
      try {
        showMsg(msg, "", "info");
        await loadDutyLeaveModalFromServer();
        openDutyLeaveModal();
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });
    $("#dutyLeaveCancelFutureBtn")?.addEventListener("click", async () => {
      const msg = $("#dutyLeaveSettingsMsg");
      try {
        showMsg(msg, "", "info");
        await apiDeleteMeDutyLeaveDates();
        state.me = await apiGetMe();
        refreshDutyLeaveSettingsSummary();
        if (state.isRootAdmin) await loadEmployees();
        syncAdminDutyToggle();
        showMsg(msg, "Запланированные дни отменены.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });
    $("#dutyLeaveResumeTodayBtn")?.addEventListener("click", async () => {
      const btn = $("#dutyLeaveResumeTodayBtn");
      const msg = $("#dutyLeaveSettingsMsg");
      try {
        if (btn) btn.disabled = true;
        showMsg(msg, "", "info");
        await apiPostMeDutyLeaveResumeToday();
        state.me = await apiGetMe();
        refreshDutyLeaveSettingsSummary();
        if (state.isRootAdmin) await loadEmployees();
        syncAdminDutyToggle();
        showMsg(
          msg,
          "С сегодняшнего дня вы снова участвуете в генерации; остальные отмеченные дни без изменений.",
          "success",
        );
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      } finally {
        if (btn) btn.disabled = false;
      }
    });
    $("#dutyLeaveCalPrev")?.addEventListener("click", () => {
      state.dutyLeaveCalMonth -= 1;
      if (state.dutyLeaveCalMonth < 0) {
        state.dutyLeaveCalMonth = 11;
        state.dutyLeaveCalYear -= 1;
      }
      renderDutyLeaveCalendar();
    });
    $("#dutyLeaveCalNext")?.addEventListener("click", () => {
      state.dutyLeaveCalMonth += 1;
      if (state.dutyLeaveCalMonth > 11) {
        state.dutyLeaveCalMonth = 0;
        state.dutyLeaveCalYear += 1;
      }
      renderDutyLeaveCalendar();
    });
    $("#dutyLeaveSaveBtn")?.addEventListener("click", async () => {
      const msg = $("#dutyLeaveModalMsg");
      try {
        showMsg(msg, "", "info");
        const dates = [...state.dutyLeaveSelected].sort();
        await apiPutMeDutyLeaveDates(dates);
        state.me = await apiGetMe();
        refreshDutyLeaveSettingsSummary();
        if (state.isRootAdmin) await loadEmployees();
        syncAdminDutyToggle();
        showMsg(msg, "Сохранено.", "success");
        closeDutyLeaveModal();
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });
    $("#dutyLeaveModalCloseBtn")?.addEventListener("click", () => closeDutyLeaveModal());
    $("#dutyLeaveModal")?.addEventListener("click", (ev) => {
      if (ev.target === $("#dutyLeaveModal")) closeDutyLeaveModal();
    });

    $("#employeeExitGenerateBtn")?.addEventListener("click", async () => {
      const msg = $("#employeeExitMsg");
      try {
        showMsg(msg, "", "info");
        const fio = $("#eeFio")?.value?.trim() || "";
        const login = $("#eeLogin")?.value?.trim() || "";
        const password = $("#eePassword")?.value || "";
        const domain = $("#eeDomain")?.value?.trim() || "";
        if (!fio) throw new Error("Укажите ФИО сотрудника.");
        if (!login) throw new Error("Укажите логин.");
        if (!password) throw new Error("Укажите пароль.");
        if (!domain) throw new Error("Укажите домен.");
        const blocks = gatherEeInstructionBlocks();
        const out = await apiEmployeeExitInstruction({ fio, login, password, domain, blocks });
        const ta = $("#eeOutput");
        if (ta) ta.value = out.text || "";
        showMsg(msg, "Инструкция сформирована.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#employeeExitShareQrBtn")?.addEventListener("click", async () => {
      const msg = $("#employeeExitMsg");
      const shareBlock = $("#employeeExitShareBlock");
      const linkEl = $("#eePublicLink");
      const imgEl = $("#eeQrImg");
      const dlBtn = $("#employeeExitQrDownloadBtn");
      try {
        showMsg(msg, "", "info");
        const fio = $("#eeFio")?.value?.trim() || "";
        const login = $("#eeLogin")?.value?.trim() || "";
        const password = $("#eePassword")?.value || "";
        const domain = $("#eeDomain")?.value?.trim() || "";
        if (!fio) throw new Error("Укажите ФИО сотрудника.");
        if (!login) throw new Error("Укажите логин.");
        if (!password) throw new Error("Укажите пароль.");
        if (!domain) throw new Error("Укажите домен.");
        const blocks = gatherEeInstructionBlocks();
        const out = await apiEmployeeExitShare({ fio, login, password, domain, blocks });
        const token = out?.token;
        const publicUrl = out?.public_url;
        if (!token || !publicUrl) throw new Error("Пустой ответ сервера.");
        state.eeLastQrToken = token;
        if (shareBlock) shareBlock.hidden = false;
        if (linkEl) {
          linkEl.href = publicUrl;
          linkEl.textContent = publicUrl;
        }
        if (imgEl) {
          imgEl.src = `${apiUrl(`/api/ee_instruction/qr/${encodeURIComponent(token)}`)}?t=${Date.now()}`;
          imgEl.hidden = false;
        }
        if (dlBtn) dlBtn.hidden = false;
        showMsg(msg, "Ссылка и QR готовы.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#employeeExitQrDownloadBtn")?.addEventListener("click", async () => {
      const msg = $("#employeeExitMsg");
      const token = state.eeLastQrToken;
      try {
        if (!token) throw new Error("Сначала создайте ссылку и QR.");
        const res = await fetch(apiUrl(`/api/ee_instruction/qr/${encodeURIComponent(token)}`), {
          method: "GET",
          credentials: "same-origin",
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || `HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "instruction-qr.png";
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showMsg(msg, "QR сохранён как PNG.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#employeeExitDownloadBtn")?.addEventListener("click", async () => {
      const msg = $("#employeeExitMsg");
      try {
        showMsg(msg, "", "info");
        const fio = $("#eeFio")?.value?.trim() || "";
        const login = $("#eeLogin")?.value?.trim() || "";
        const password = $("#eePassword")?.value || "";
        const domain = $("#eeDomain")?.value?.trim() || "";
        if (!fio) throw new Error("Укажите ФИО сотрудника.");
        if (!login) throw new Error("Укажите логин.");
        if (!password) throw new Error("Укажите пароль.");
        if (!domain) throw new Error("Укажите домен.");
        const blocks = gatherEeInstructionBlocks();
        const blob = await apiEmployeeExitInstructionDocx({ fio, login, password, domain, blocks });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `instrukciya_${fio.replace(/[\\/:*?"<>|]+/g, "_").slice(0, 120) || "employee"}.docx`;
        a.rel = "noopener";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showMsg(msg, "Файл Word скачан.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#employeeExitCopyBtn")?.addEventListener("click", async () => {
      const msg = $("#employeeExitMsg");
      const ta = $("#eeOutput");
      try {
        if (!ta?.value) throw new Error("Сначала сформируйте инструкцию.");
        await navigator.clipboard.writeText(ta.value);
        showMsg(msg, "Скопировано в буфер обмена.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    // Dates defaults
    const dutiesDateEl = $("#dutiesDate");
    const reportsDateEl = $("#reportsDate");
    if (dutiesDateEl) dutiesDateEl.value = localISODate();
    if (reportsDateEl) reportsDateEl.value = localISODate();
    void loadReportsHistory();
    if ($("#analyticsStartDate")) $("#analyticsStartDate").value = localISODate();
    if ($("#analyticsEndDate")) $("#analyticsEndDate").value = localISODate();
    if ($("#swapDate")) $("#swapDate").value = dutiesDateEl?.value || localISODate();
    const dutiesViewModeEl = $("#dutiesViewMode");
    setDutyViewMode(dutiesViewModeEl?.value || "table");
    dutiesViewModeEl?.addEventListener("change", async () => {
      setDutyViewMode(dutiesViewModeEl.value);
      try {
        const dateStr = $("#dutiesDate")?.value || localISODate();
        await loadDuties(dateStr);
        await loadDutiesCalendar(dateStr);
      } catch (e) {
        showMsg($("#dutiesMsg"), e.message || String(e), "error");
      }
    });

    $("#dutiesDisplayFilter")?.addEventListener("change", () => {
      const sel = $("#dutiesDisplayFilter");
      if (sel) state.dutyDisplayFilter = sel.value || "all";
      refreshDutyFilterViews();
    });

    $("#quickReplacementFocusBtn")?.addEventListener("click", async () => {
      const msg = $("#dutiesMsg");
      try {
        showMsg(msg, "Отправляем запрос в Битрикс…", "info");
        await apiMeNotifyDutyReplacementBitrix();
        showMsg(msg, "Уведомление отправлено администраторам в личку Битрикс.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    // Initialize privileged-user dependent dropdowns
    if (state.hasAdminAccess) {
      try {
        await loadEmployees();
      } catch (e) {
        showMsg($("#adminRoleMsg"), e.message || String(e), "error");
        renderAdminUsersEditor();
      }

      if (state.canManageNotifications) {
        try {
          const settings = await apiGetNotificationSettings();
          applyNotificationSettingsToUi(settings);
          state.notificationSettingsReady = true;
          const templates = await apiGetNotificationTemplates();
          applyNotificationTemplatesToUi(templates);
          state.notificationTemplatesReady = true;
        } catch (e) {
          showMsg($("#notificationSettingsMsg"), e.message || String(e), "error");
        }
      }

      const reportsEmployeeSelect = $("#reportsEmployeeSelect");
      if (state.canManageReports) {
        fillEmployeesSelect(reportsEmployeeSelect, { includeBlank: true, saveKey: "reportsEmployeeId" });
      }
      if (state.isRootAdmin) {
        fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
        syncAdminDutyToggle();
        $("#adminUserSelect")?.addEventListener("change", syncAdminDutyToggle);
      }

      const row = $("#reportsEmployeeRow");
      if (row) row.hidden = !state.canManageReports;
      if (state.canManageReports) {
        await loadAnalytics();
      }

      if (state.canManageDuties) {
        const prev = prevMonthRangeISO();
        const cur = monthRangeISO();
        const cs = $("#copySourceStart");
        const ce = $("#copySourceEnd");
        const ts = $("#copyTargetStart");
        const te = $("#copyTargetEnd");
        if (cs) cs.value = prev.start;
        if (ce) ce.value = prev.end;
        if (ts) ts.value = cur.start;
        if (te) te.value = cur.end;
        const gs = $("#genStartDate");
        const ge = $("#genEndDate");
        if (gs) gs.value = cur.start;
        if (ge) ge.value = cur.end;
      }
    }

    async function sendTodayDutyScheduleToBitrix(msgEl) {
      showMsg(msgEl, "Отправка графика в Битрикс…", "info");
      const today = localISODate();
      await apiFetchJson(
        `/api/admin/notifications/duty-schedule/bitrix?date=${encodeURIComponent(today)}`,
        { method: "POST" },
      );
      showMsg(msgEl, "График на сегодня отправлен в настроенный чат Битрикс.", "success");
    }

    // Graphik handlers
    const dutiesMsgEl = $("#dutiesMsg");
    const dutiesDate = dutiesDateEl?.value;
    $("#loadDutiesBtn")?.addEventListener("click", async () => {
      try {
        showMsg(dutiesMsgEl, "", "info");
        await loadDuties($("#dutiesDate").value);
        await loadDutiesCalendar($("#dutiesDate").value);
      } catch (e) {
        showMsg(dutiesMsgEl, e.message || String(e), "error");
      }
    });

    $("#notifyDutiesBitrixGraphBtn")?.addEventListener("click", async () => {
      try {
        await sendTodayDutyScheduleToBitrix(dutiesMsgEl);
      } catch (e) {
        showMsg(dutiesMsgEl, e.message || String(e), "error");
      }
    });

    $("#dutiesDate")?.addEventListener("change", async () => {
      try {
        showMsg(dutiesMsgEl, "", "info");
        await loadDuties($("#dutiesDate").value);
        await loadDutiesCalendar($("#dutiesDate").value);
      } catch (e) {
        showMsg(dutiesMsgEl, e.message || String(e), "error");
      }
    });

    $("#saveDutiesBtn")?.addEventListener("click", async () => {
      try {
        const dateStr = $("#dutiesDate").value;
        await saveDuties(dateStr);
        await loadDutiesCalendar(dateStr);
      } catch (e) {
        showMsg($("#dutiesMsg"), e.message || String(e), "error");
      }
    });

    $("#swapDate")?.addEventListener("change", async () => {
      try {
        await refreshSwapSlotSelects();
        await refreshSwapInbox();
      } catch (e) {
        showMsg($("#swapMsg"), e.message || String(e), "error");
      }
    });
    $("#sendSwapBtn")?.addEventListener("click", async () => {
      const msg = $("#swapMsg");
      try {
        showMsg(msg, "", "info");
        const dateStr = $("#swapDate").value;
        const fromOpt = $("#swapFromSlot")?.selectedOptions?.[0];
        const toOpt = $("#swapToSlot")?.selectedOptions?.[0];
        if (fromOpt?.disabled) throw new Error("Нет вашего слота в графике на эту дату.");
        if (toOpt?.disabled) throw new Error("Выберите слот другого дежурного (с ФИО в списке).");
        const fromSlot = Number($("#swapFromSlot").value);
        const toSlot = Number($("#swapToSlot").value);
        if (!dateStr) throw new Error("Выберите дату.");
        if (!Number.isInteger(fromSlot) || !Number.isInteger(toSlot)) throw new Error("Выберите слоты.");
        await apiCreateDutySwapRequest({ date: dateStr, fromSlot, toSlot });
        showMsg(msg, "Запрос отправлен.", "success");
        await refreshSwapInbox();
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });
    $("#swapInboxList")?.addEventListener("click", async (ev) => {
      const btn = ev.target?.closest?.("button");
      if (!btn) return;
      const action = btn.dataset.action;
      const swapId = Number(btn.dataset.swapId);
      if (!swapId || (action !== "swapAccept" && action !== "swapReject")) return;
      try {
        const decision = action === "swapAccept" ? "accept" : "reject";
        await apiDecideDutySwapRequest(swapId, decision);
        if (decision === "accept" && $("#dutiesDate")?.value) {
          await loadDuties($("#dutiesDate").value);
        }
        if (decision === "accept") {
          try {
            await refreshSwapSlotSelects();
          } catch {
            /* ignore */
          }
        }
        await refreshSwapInbox();
        showMsg($("#swapMsg"), decision === "accept" ? "Запрос принят." : "Запрос отклонен.", "success");
      } catch (e) {
        showMsg($("#swapMsg"), e.message || String(e), "error");
      }
    });

    // Reports handlers
    $("#loadReportsBtn")?.addEventListener("click", async () => {
      try {
        await loadReports($("#reportsDate").value, state.canManageReports ? $("#reportsEmployeeSelect").value : null);
      } catch (e) {
        showMsg($("#reportsMsg"), e.message || String(e), "error");
      }
    });

    $("#downloadAllExcelsBtn")?.addEventListener("click", async () => {
      try {
        const dateStr = $("#reportsDate").value;
        const missing = await downloadAllExcelsForDate(dateStr);
        if (missing.length) {
          showMsg($("#reportsMsg"), `Скачаны все сформированные Excel. Не сформировали: ${missing.join(", ")}.`, "info");
        } else {
          showMsg($("#reportsMsg"), "Скачаны все сформированные Excel.", "success");
        }
      } catch (e) {
        showMsg($("#reportsMsg"), e.message || String(e), "error");
      }
    });

    $("#reportsDate")?.addEventListener("change", async () => {
      try {
        await loadReports($("#reportsDate").value, state.canManageReports ? $("#reportsEmployeeSelect").value : null);
      } catch (e) {
        showMsg($("#reportsMsg"), e.message || String(e), "error");
      }
    });

    $("#reportsEmployeeSelect")?.addEventListener("change", async () => {
      const val = $("#reportsEmployeeSelect").value;
      if (val) localStorage.setItem("reportsEmployeeId", val);
      try {
        await loadReports($("#reportsDate").value, val);
      } catch (e) {
        showMsg($("#reportsMsg"), e.message || String(e), "error");
      }
    });

    // Admin handlers: generate duties
    $("#genDutiesBtn")?.addEventListener("click", async () => {
      const msg = $("#genDutiesMsg");
      try {
        msg.hidden = false;
        showMsg(msg, "Выполняется генерация...", "info");

        const body = {
          start_date: $("#genStartDate").value,
          end_date: $("#genEndDate").value,
          overwrite: $("#genOverwrite").checked,
        };
        await apiFetchJson("/api/duties/generate", { method: "POST", body });
        showMsg(msg, "График сгенерирован.", "success");

        // Обновить таблицу дня и (при виде «Неделя»/«Месяц») календарь — иначе кэш календаря остаётся старым.
        const dutiesDateVal = $("#dutiesDate")?.value;
        if (dutiesDateVal) {
          await loadDuties(dutiesDateVal);
          await loadDutiesCalendar(dutiesDateVal);
        }
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#exportDutiesExcelBtn")?.addEventListener("click", async () => {
      const msg = $("#exportDutiesMsg");
      try {
        msg.hidden = false;
        showMsg(msg, "Формируем Excel…", "info");
        await downloadDutiesPeriodExcel();
        showMsg(msg, "Файл скачан.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#copyDutiesRangeBtn")?.addEventListener("click", async () => {
      const msg = $("#copyDutiesMsg");
      try {
        msg.hidden = false;
        showMsg(msg, "Копирование…", "info");
        const body = {
          source_start_date: $("#copySourceStart").value,
          source_end_date: $("#copySourceEnd").value,
          target_start_date: $("#copyTargetStart").value,
          target_end_date: $("#copyTargetEnd").value,
          overwrite: $("#copyOverwrite").checked,
        };
        const out = await apiFetchJson("/api/duties/copy-range", { method: "POST", body });
        const parts = [`дней: ${out.days_copied}`, `созд.: ${out.created}`, `обновл.: ${out.updated}`, `удал.: ${out.deleted}`];
        showMsg(msg, `Скопировано (${parts.join(", ")}).`, "success");
        if ($("#dutiesDate").value) {
          await loadDuties($("#dutiesDate").value);
          await loadDutiesCalendar($("#dutiesDate").value);
        }
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    const notificationSettingsControls = [
      "#notifSchedulerEnabled",
      "#notif5m",
      "#notifStart",
      "#notifChatStart",
    ];
    for (const selector of notificationSettingsControls) {
      $(selector)?.addEventListener("change", () => {
        saveNotificationSettingsAuto();
      });
    }

    $("#notifTestBtn")?.addEventListener("click", async () => {
      const msg = $("#notifTestMsg");
      const uid = $("#notifTestUserId")?.value;
      if (!uid) {
        showMsg(msg, "Нет сотрудников в списке.", "error");
        return;
      }
      try {
        showMsg(msg, "Отправка тестового сообщения в Битрикс…", "info");
        const out = await apiTestDutyNotification(uid);
        if (out.sent) {
          showMsg(msg, out.message || "Отправлено.", "success");
        } else {
          showMsg(msg, out.reason || "Не удалось отправить.", "error");
        }
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#notifyDutiesBitrixBtn")?.addEventListener("click", async () => {
      const msg = $("#notifyDutiesBitrixMsg");
      try {
        await sendTodayDutyScheduleToBitrix(msg);
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#saveNotifTemplatesBtn")?.addEventListener("click", async () => {
      await saveNotificationTemplates();
    });
    $("#loadAnalyticsBtn")?.addEventListener("click", async () => {
      await loadAnalytics();
    });

    // Admin handlers: create support user
    $("#createUserBtn")?.addEventListener("click", async () => {
      const msg = $("#createUserMsg");
      try {
        showMsg(msg, "", "info");
        const payload = {
          username: $("#newUserUsername").value.trim(),
          full_name: $("#newUserFullName").value.trim(),
          password: $("#newUserPassword").value,
        };
        const bxNew = ($("#newUserBitrixId")?.value || "").trim();
        if (bxNew) {
          const n = Number(bxNew);
          if (!Number.isInteger(n) || n < 1) throw new Error("ID Битрикс: целое число ≥ 1 или оставьте поле пустым.");
          payload.bitrix_user_id = n;
        }
        await apiFetchJson("/api/admin/users", { method: "POST", body: payload });
        showMsg(msg, "Сотрудник добавлен.", "success");
        $("#newUserBitrixId").value = "";

        await loadEmployees();
        refreshPrivilegedSelectors();
        $("#adminDutyActiveToggle").checked = true;

        // Refresh duties table selections.
        if ($("#dutiesDate").value) {
          await loadDuties($("#dutiesDate").value);
        }

        // Refresh reports list for current selection.
        const dateStr = $("#reportsDate").value;
        const empId = $("#reportsEmployeeSelect").value;
        if (dateStr && empId) {
          await loadReports(dateStr, empId);
        }
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#refreshUsersEditorBtn")?.addEventListener("click", async () => {
      const msg = $("#adminOpsMsg");
      try {
        await loadEmployees();
        refreshPrivilegedSelectors();
        syncAdminDutyToggle();
        showMsg(msg, "Список сотрудников обновлен.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#adminUsersPagination")?.addEventListener("click", (ev) => {
      const btn = ev.target?.closest?.("[data-admin-users-page]");
      if (!btn) return;
      const p = Number(btn.dataset.adminUsersPage);
      if (!Number.isFinite(p) || p < 1) return;
      state.adminUsersPage = p;
      renderAdminUsersEditor();
    });

    $("#adminUsersEditorBody")?.addEventListener("click", async (ev) => {
      const row = ev.target?.closest?.("tr");
      const msg = $("#adminOpsMsg");

      const btnBx = ev.target?.closest?.("button[data-action='saveBitrixId']");
      if (btnBx && row) {
        const userId = Number(row.dataset.userId);
        const bitrixRaw = row.querySelector(".admin-edit-bitrix-id")?.value?.trim() || "";
        try {
          if (!userId) throw new Error("Некорректный пользователь.");
          let bitrixVal = null;
          if (bitrixRaw) {
            const n = Number(bitrixRaw);
            if (!Number.isInteger(n) || n < 1) throw new Error("ID Битрикс: целое число ≥ 1 или пусто.");
            bitrixVal = n;
          }
          const updated = await apiAdminUpdateBitrixUserId(userId, bitrixVal);
          const permissionsPayload = {
            can_manage_duties: Boolean(row.querySelector("input[data-permission='can_manage_duties']")?.checked),
            can_manage_reports: Boolean(row.querySelector("input[data-permission='can_manage_reports']")?.checked),
            can_manage_notifications: Boolean(row.querySelector("input[data-permission='can_manage_notifications']")?.checked),
          };
          const updatedFinal =
            updated.role === "support" ? await apiAdminUpdateUserPermissions(userId, permissionsPayload) : updated;
          const idx = state.employees.findIndex((u) => Number(u.id) === Number(updated.id));
          if (idx >= 0) state.employees[idx] = updatedFinal;
          replaceAdminUserEditorRow(updatedFinal);
          refreshPrivilegedSelectors();
          if (state.isRootAdmin) $("#adminUserSelect").value = String(updatedFinal.id);
          syncAdminDutyToggle();
          showMsg(msg, "ID Битрикс сохранён.", "success");
        } catch (e) {
          showMsg(msg, e.message || String(e), "error");
        }
        return;
      }

      const btn = ev.target?.closest?.("button[data-action='saveUserProfile']");
      if (!btn || !row) return;
      const userId = Number(row.dataset.userId);
      const username = row.querySelector(".admin-edit-username")?.value?.trim() || "";
      const fullName = row.querySelector(".admin-edit-fullname")?.value?.trim() || "";
      const bitrixRaw = row.querySelector(".admin-edit-bitrix-id")?.value?.trim() || "";
      try {
        if (!userId) throw new Error("Некорректный пользователь.");
        if (!username) throw new Error("Логин не может быть пустым.");
        if (!fullName) throw new Error("ФИО не может быть пустым.");
        let bitrixVal = null;
        if (bitrixRaw) {
          const n = Number(bitrixRaw);
          if (!Number.isInteger(n) || n < 1) throw new Error("ID Битрикс: целое число ≥ 1 или пусто.");
          bitrixVal = n;
        }
        const updated = await apiAdminUpdateUserProfile(userId, username, fullName);
        const updated2 = await apiAdminUpdateBitrixUserId(userId, bitrixVal);
        const permissionsPayload = {
          can_manage_duties: Boolean(row.querySelector("input[data-permission='can_manage_duties']")?.checked),
          can_manage_reports: Boolean(row.querySelector("input[data-permission='can_manage_reports']")?.checked),
          can_manage_notifications: Boolean(row.querySelector("input[data-permission='can_manage_notifications']")?.checked),
        };
        const updated3 = await apiAdminUpdateUserPermissions(userId, permissionsPayload);
        const idx = state.employees.findIndex((u) => Number(u.id) === Number(updated3.id));
        if (idx >= 0) state.employees[idx] = updated3;
        replaceAdminUserEditorRow(updated3);
        refreshPrivilegedSelectors();
        if (state.isRootAdmin) $("#adminUserSelect").value = String(updated3.id);
        syncAdminDutyToggle();
        showMsg(msg, "Данные сотрудника обновлены.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#adminChangePasswordBtn")?.addEventListener("click", async () => {
      const msg = $("#adminOpsMsg");
      try {
        showMsg(msg, "", "info");
        const userId = Number($("#adminUserSelect").value);
        const newPassword = $("#adminNewPassword").value;
        if (!userId) throw new Error("Выберите сотрудника.");
        if (!newPassword || newPassword.length < 8) throw new Error("Пароль должен быть не короче 8 символов.");
        await apiAdminChangeUserPassword(userId, newPassword);
        $("#adminNewPassword").value = "";
        showMsg(msg, "Пароль сотрудника обновлен.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#adminSaveDutyStatusBtn")?.addEventListener("click", async () => {
      const msg = $("#adminOpsMsg");
      try {
        showMsg(msg, "", "info");
        const userId = Number($("#adminUserSelect").value);
        const toggle = $("#adminDutyActiveToggle");
        if (toggle?.disabled) {
          throw new Error(
            "Сотрудник отмечен отсутствием в генерации на сегодня; снимите отгулы в его настройках или дождитесь завтра.",
          );
        }
        const isActive = Boolean(toggle?.checked);
        if (!userId) throw new Error("Выберите сотрудника.");
        const updated = await apiAdminUpdateDutyStatus(userId, isActive);
        const idx = state.employees.findIndex((u) => Number(u.id) === Number(updated.id));
        if (idx >= 0) state.employees[idx] = updated;
        replaceAdminUserEditorRow(updated);
        refreshPrivilegedSelectors();
        if (state.isRootAdmin) $("#adminUserSelect").value = String(updated.id);
        $("#adminDutyActiveToggle").checked = updated.is_active_for_duties !== false;
        syncAdminDutyToggle();
        showMsg(msg, "Статус дежурств обновлен.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#adminDeleteReportsBtn")?.addEventListener("click", async () => {
      const msg = $("#adminOpsMsg");
      try {
        showMsg(msg, "", "info");
        const userId = Number($("#adminUserSelect").value);
        if (!userId) throw new Error("Выберите сотрудника.");
        const targetUser = state.employees.find((u) => Number(u.id) === userId);
        if (!confirm(`Удалить всю историю отчетов сотрудника ${targetUser?.full_name || targetUser?.username || userId}?`)) return;
        const res = await apiAdminDeleteUserReports(userId);
        showMsg(msg, `История удалена: отчетов ${res.deleted_reports ?? 0}, файлов ${res.deleted_exports ?? 0}.`, "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#adminDeleteUserBtn")?.addEventListener("click", async () => {
      const msg = $("#adminOpsMsg");
      try {
        showMsg(msg, "", "info");
        const userId = Number($("#adminUserSelect").value);
        if (!userId) throw new Error("Выберите сотрудника.");
        const targetUser = state.employees.find((u) => Number(u.id) === userId);
        const targetLabel = targetUser?.username || String(userId);
        if (!confirm(`Удалить сотрудника ${targetLabel}?`)) return;
        const verify = prompt(`Для подтверждения введите логин сотрудника: ${targetLabel}`);
        if (verify !== targetLabel) throw new Error("Подтверждение не совпало.");
        await apiAdminDeleteUser(userId);
        await loadEmployees();
        refreshPrivilegedSelectors();
        syncAdminDutyToggle();
        showMsg(msg, `Сотрудник ${targetLabel} удален.`, "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#adminUsersEditorBody")?.addEventListener("change", async (ev) => {
      const cb = ev.target?.closest?.("input.admin-rights-checkbox");
      if (!cb || cb.disabled) return;
      const userId = Number(cb.dataset.userId);
      const wantAdmin = cb.checked;
      const msg = $("#adminRoleMsg");
      try {
        if (!wantAdmin) {
          const u = state.employees.find((x) => Number(x.id) === userId);
          const label = u?.username || String(userId);
          if (!confirm(`Снять права администратора у пользователя ${label}?`)) {
            cb.checked = true;
            return;
          }
          await apiAdminRevokeAdmin(userId);
        } else {
          await apiAdminGrantAdmin(userId);
        }
        await loadEmployees();
        refreshPrivilegedSelectors();
        syncAdminDutyToggle();
        if ($("#dutiesDate").value) await loadDuties($("#dutiesDate").value);
        showMsg(msg, wantAdmin ? "Права администратора выданы." : "Права администратора сняты.", "success");
      } catch (e) {
        cb.checked = !wantAdmin;
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#refreshRoleAuditBtn")?.addEventListener("click", async () => {
      const msg = $("#adminRoleMsg");
      const pre = $("#roleAuditPre");
      try {
        const rows = await apiAdminRoleAudit(30);
        if (!pre) return;
        if (!Array.isArray(rows) || !rows.length) {
          pre.textContent = "(записей пока нет)";
          pre.hidden = false;
          showMsg(msg, "Журнал пуст.", "success");
          return;
        }
        const lines = rows.map(
          (r) =>
            `${r.created_at} · кто: id=${r.actor_user_id} → кому: id=${r.target_user_id} · ${r.action}`
        );
        pre.textContent = lines.join("\n");
        pre.hidden = false;
        showMsg(msg, "Журнал обновлён.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#selfChangePasswordBtn")?.addEventListener("click", async () => {
      const msg = $("#selfChangePasswordMsg");
      try {
        showMsg(msg, "", "info");
        const oldPassword = $("#selfOldPassword").value;
        const newPassword = $("#selfNewPassword").value;
        const newPassword2 = $("#selfNewPassword2").value;
        if (!oldPassword || !newPassword || !newPassword2) throw new Error("Заполните все поля.");
        if (newPassword.length < 8) throw new Error("Новый пароль должен быть не короче 8 символов.");
        if (newPassword !== newPassword2) throw new Error("Подтверждение нового пароля не совпадает.");
        if (oldPassword === newPassword) throw new Error("Новый пароль должен отличаться от текущего.");
        await apiChangeOwnPassword(oldPassword, newPassword);
        $("#selfOldPassword").value = "";
        $("#selfNewPassword").value = "";
        $("#selfNewPassword2").value = "";
        showMsg(msg, "Пароль успешно изменен.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#selfSaveProfileBtn")?.addEventListener("click", async () => {
      const msg = $("#selfProfileMsg");
      try {
        showMsg(msg, "", "info");
        const fullName = $("#selfFullName").value.trim();
        if (!fullName) throw new Error("ФИО не может быть пустым.");
        const me = await apiUpdateMeProfile(fullName);
        state.me = me;
        const meText = $("#meText");
        if (meText) {
          meText.innerHTML = `<span>${escapeHtml(me.full_name || me.username || "")}</span><span class="user-role-badge">${escapeHtml(me.role || "")}</span>`;
        }
        showMsg(msg, "Профиль обновлен.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#reportsList")?.addEventListener("input", (ev) => {
      const t = ev.target;
      if (!t?.classList?.contains?.("entry-minutes")) return;
      refreshReportsKpi();
    });

    // Report cards event delegation
    $("#reportsList")?.addEventListener("click", async (ev) => {
      const target = ev.target;
      const actionBtn = target?.closest?.("button");
      if (!actionBtn) return;
      const action = actionBtn.dataset.action;
      const reportId = actionBtn.dataset.reportId;
      if (!action || !reportId) return;

      try {
        if (action === "addEntry") {
          const card = getReportCard(reportId);
          if (!card) return;
          const tbody = card.querySelector(".entries-table tbody");
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><input type="text" class="entry-task" maxlength="500" value="" /></td>
            <td><textarea class="entry-description"></textarea></td>
            <td><input type="number" min="0" max="1440" step="1" class="entry-minutes" value="0" /></td>
            <td><button type="button" class="btn danger" data-action="removeEntry" title="Удалить строку" aria-label="Удалить">🗑</button></td>
          `;
          tbody.appendChild(tr);
          const delBtn = tr.querySelector('button[data-action="removeEntry"]');
          if (delBtn)
            delBtn.addEventListener("click", () => {
              tr.remove();
              updateReportMinutesTotal(card);
            });
          updateReportMinutesTotal(card);
        } else if (action === "finalizeExcel") {
          await finalizeReportExcel(Number(reportId));
        }
      } catch (e) {
        showMsg($("#reportsMsg"), e.message || String(e), "error");
      }
    });

    // Initial loads
    try {
      const dutyDateStr = $("#dutiesDate").value;
      if (dutyDateStr) {
        await loadDuties(dutyDateStr);
        await loadDutiesCalendar(dutyDateStr);
      }

      const reportsDateStr = $("#reportsDate").value;
      const employeeId = state.canManageReports ? $("#reportsEmployeeSelect")?.value : null;
      if (reportsDateStr) await loadReports(reportsDateStr, employeeId);
      await refreshSwapSlotSelects();
      await refreshSwapInbox();
      refreshDutyLeaveSettingsSummary();
      updateCurrentDutyNow();
    } catch (e) {
      const msg = $("#reportsMsg");
      showMsg(msg, e.message || String(e), "error");
    }

    if (state.swapInboxTimerId) clearInterval(state.swapInboxTimerId);
    state.swapInboxTimerId = setInterval(() => {
      refreshSwapInbox().catch(() => {});
    }, 30_000);
    if (state.currentDutyTimerId) clearInterval(state.currentDutyTimerId);
    state.currentDutyTimerId = setInterval(() => {
      updateCurrentDutyNow();
      updateDashboardClock();
    }, 30_000);
    updateDashboardClock();
  }

  async function initLoginPage() {
    const loginForm = $("#loginForm");
    if (!loginForm) return;

    // Redirect if already logged in
    try {
      await apiGetMe();
      window.location.href = "/index.html";
      return;
    } catch {
      // ok: not logged in
    }

    const errorEl = $("#loginError");
    loginForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const username = $("#loginUsername").value.trim();
      const password = $("#loginPassword").value;
      try {
        showMsg(errorEl, "", "error");
        await apiLogin({ username, password });
        window.location.href = "/index.html";
      } catch (e) {
        showMsg(errorEl, e.message || String(e), "error");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    if ($("#loginForm")) {
      initLoginPage();
      return;
    }

    if ($("#dutiesTable") || $("#reportsList")) {
      onIndexInit();
      return;
    }
  });
})();

