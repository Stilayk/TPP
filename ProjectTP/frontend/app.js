(() => {
  const SLOT_START_HOUR = 7;
  const SLOT_COUNT = 11;

  const state = {
    me: null,
    isAdmin: false,
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
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function localISODate(d = new Date()) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
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

  async function apiEmployeeExitInstruction({ fio, login, password, domain }) {
    return apiFetchJson("/api/ee_instruction", {
      method: "POST",
      body: { fio, login, password, domain },
    });
  }

  async function apiEmployeeExitInstructionDocx({ fio, login, password, domain }) {
    const res = await fetch(apiUrl("/api/ee_instruction/docx"), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fio, login, password, domain }),
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

  async function loadEmployees() {
    const users = await apiFetchJson("/api/admin/users");
    state.employees = Array.isArray(users) ? users : [];
    renderAdminUsersEditor();
    return state.employees;
  }

  function renderAdminUsersEditor() {
    const tbody = $("#adminUsersEditorBody");
    if (!tbody) return;
    tbody.innerHTML = "";
    const adminCount = adminEmployees().length;
    const list = [...state.employees].sort((a, b) => Number(a.id) - Number(b.id));

    if (!list.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 6;
      td.className = "muted";
      td.textContent =
        "Список пользователей пуст или ещё не загружен. Нажмите «Обновить список». Если таблица не появляется — обновите страницу с полным сбросом кэша (Ctrl+F5).";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    for (const emp of list) {
      const isAdmin = emp.role === "admin";
      const isSupport = emp.role === "support";
      const tr = document.createElement("tr");
      tr.dataset.userId = String(emp.id);

      const tdId = document.createElement("td");
      tdId.textContent = String(emp.id);

      const tdLogin = document.createElement("td");
      const tdName = document.createElement("td");
      if (isSupport) {
        const inpL = document.createElement("input");
        inpL.type = "text";
        inpL.className = "admin-edit-username";
        inpL.value = emp.username || "";
        const inpN = document.createElement("input");
        inpN.type = "text";
        inpN.className = "admin-edit-fullname";
        inpN.value = emp.full_name || "";
        const dutyInactiveTag = document.createElement("span");
        dutyInactiveTag.className = "muted admin-duty-inactive-tag";
        dutyInactiveTag.textContent = "не в графике дежурств";
        dutyInactiveTag.hidden = emp.is_active_for_duties !== false;
        tdLogin.appendChild(inpL);
        tdName.appendChild(inpN);
        tdName.appendChild(document.createElement("br"));
        tdName.appendChild(dutyInactiveTag);
      } else {
        tdLogin.textContent = emp.username || "";
        tdName.textContent = emp.full_name || "";
      }

      const tdBitrix = document.createElement("td");
      const inpB = document.createElement("input");
      inpB.type = "text";
      inpB.inputMode = "numeric";
      inpB.className = "admin-edit-bitrix-id";
      inpB.placeholder = "—";
      inpB.title =
        "ID пользователя Битрикс24 (число); для упоминания в чате при рассылке графика. У администратора сохраняется кнопкой «Сохранить ID».";
      inpB.value = emp.bitrix_user_id != null && emp.bitrix_user_id !== undefined ? String(emp.bitrix_user_id) : "";
      tdBitrix.appendChild(inpB);

      const tdRights = document.createElement("td");
      const lbl = document.createElement("label");
      lbl.className = "checkbox-label";
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
      span.className = "muted";
      span.style.marginLeft = "6px";
      span.textContent = "Админ";
      lbl.appendChild(cb);
      lbl.appendChild(span);
      tdRights.appendChild(lbl);

      const tdAct = document.createElement("td");
      if (isSupport) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn";
        btn.dataset.action = "saveUserProfile";
        btn.textContent = "Сохранить";
        tdAct.appendChild(btn);
      } else {
        const btnBx = document.createElement("button");
        btnBx.type = "button";
        btnBx.className = "btn";
        btnBx.dataset.action = "saveBitrixId";
        btnBx.textContent = "Сохранить ID";
        btnBx.title = "Сохранить только ID Битрикс (логин/ФИО админа в таблице не редактируются)";
        tdAct.appendChild(btnBx);
      }

      tr.appendChild(tdId);
      tr.appendChild(tdLogin);
      tr.appendChild(tdName);
      tr.appendChild(tdBitrix);
      tr.appendChild(tdRights);
      tr.appendChild(tdAct);
      tbody.appendChild(tr);
    }
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
      opt.textContent = emp.is_active_for_duties === false ? `${title} (не в графике дежурств)` : title;
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

  function setAdminMode(isAdmin) {
    state.isAdmin = Boolean(isAdmin);

    document.body.classList.toggle("admin-user", state.isAdmin);

    const adminTabBtn = $("#adminTabBtn");
    if (adminTabBtn) adminTabBtn.hidden = !state.isAdmin;

    for (const el of $$(".admin-only")) {
      // Elements in HTML can have "hidden" attribute; JS must control it.
      el.hidden = !state.isAdmin;
    }

    for (const el of $$(".support-only")) {
      el.hidden = state.isAdmin;
    }

    if (!state.isAdmin) {
      // Remove dropdown selection controls that are admin-specific from state.
    }
  }

  function selectedNotificationMethod() {
    return $("#notifMethodN8n")?.checked ? "n8n" : "cron";
  }

  function updateNotificationSettingsVisibility() {
    const method = selectedNotificationMethod();
    const cronBlock = $("#notifCronSettingsBlock");
    const n8nBlock = $("#notifN8nSettingsBlock");
    if (cronBlock) cronBlock.hidden = method !== "cron";
    if (n8nBlock) n8nBlock.hidden = method !== "n8n";
  }

  function applyNotificationSettingsToUi(settings) {
    if (!settings) return;
    $("#notifMethodCron").checked = settings.selected_method === "cron";
    $("#notifMethodN8n").checked = settings.selected_method === "n8n";

    $("#notifCron5m").checked = Boolean(settings?.cron?.enabled_upcoming_5m);
    $("#notifCronStart").checked = Boolean(settings?.cron?.enabled_start);
    $("#notifCronChatStart").checked = Boolean(settings?.cron?.enabled_chat_on_start);

    $("#notifN8n5m").checked = Boolean(settings?.n8n?.enabled_upcoming_5m);
    $("#notifN8nStart").checked = Boolean(settings?.n8n?.enabled_start);
    $("#notifN8nChatStart").checked = Boolean(settings?.n8n?.enabled_chat_on_start);
    updateNotificationSettingsVisibility();
  }

  function gatherNotificationSettingsFromUi() {
    const cronSelected = Boolean($("#notifMethodCron")?.checked);
    const n8nSelected = Boolean($("#notifMethodN8n")?.checked);
    if ((cronSelected && n8nSelected) || (!cronSelected && !n8nSelected)) {
      throw new Error("Выберите только один способ запуска уведомлений: cron или n8n.");
    }
    return {
      selected_method: cronSelected ? "cron" : "n8n",
      cron: {
        enabled_upcoming_5m: Boolean($("#notifCron5m")?.checked),
        enabled_start: Boolean($("#notifCronStart")?.checked),
        enabled_chat_on_start: Boolean($("#notifCronChatStart")?.checked),
      },
      n8n: {
        enabled_upcoming_5m: Boolean($("#notifN8n5m")?.checked),
        enabled_start: Boolean($("#notifN8nStart")?.checked),
        enabled_chat_on_start: Boolean($("#notifN8nChatStart")?.checked),
      },
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

  function activateTab(tabName) {
    const btns = $$(".tab-btn");
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
  }

  function openEmployeeExitModal() {
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

    renderDutiesTable(duties);
    updateCurrentDutyNow();
    showMsg($("#dutiesMsg"), "График загружен.", "success");
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
      return;
    }

    const slot = new Date().getHours() - state.slotStartHour;
    if (!Number.isInteger(slot) || slot < 0 || slot >= state.slotCount) {
      nameEl.textContent = "—";
      timeEl.textContent = "—";
      return;
    }

    const slotOut = (Array.isArray(duties.slots) ? duties.slots : []).find((s) => Number(s.slot) === slot);
    const user = slotOut?.user || null;
    nameEl.textContent = user ? (user.full_name || user.username) : "не назначен";
    timeEl.textContent = slotStartLabel(slot);

    const row = tbody.querySelector(`tr[data-slot="${slot}"]`);
    if (row) row.classList.add("current-slot");
  }

  function renderDutiesTable(dutiesOut) {
    const tbody = $("#dutiesTable tbody");
    tbody.innerHTML = "";

    const isAdmin = state.isAdmin;
    const slots = dutiesOut?.slots || [];

    const slotCount = Array.isArray(slots) && slots.length ? slots.length : state.slotCount;
    for (let slot = 0; slot < slotCount; slot++) {
      const slotOut = slots.find((s) => Number(s.slot) === slot) || slots[slot];
      const user = slotOut?.user || null;

      const tr = document.createElement("tr");
      tr.dataset.slot = String(slot);

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

      const myId = state.me?.id != null ? Number(state.me.id) : null;
      if (myId != null && user && Number(user.id) === myId) {
        tr.classList.add("duty-row-self");
        tr.title = "Ваш слот дежурства на выбранную дату";
      }

      tr.appendChild(tdTime);
      tr.appendChild(tdUser);
      tbody.appendChild(tr);
    }
  }

  async function saveDuties(dateStr) {
    const isAdmin = state.isAdmin;
    if (!isAdmin) return;

    const assignments = [];
    const selects = $$(".duty-user-select");
    const seenSlots = new Set();

    for (const sel of selects) {
      const slot = Number(sel.dataset.slot);
      seenSlots.add(slot);
      const userId = sel.value ? Number(sel.value) : null;
      if (!userId) {
        throw new Error(`Выберите сотрудника для слота ${slotRangeLabel(slot)}.`);
      }
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
  }

  function formatWorkDurationTotalMinutes(totalMinutes) {
    const t = Math.max(0, Math.floor(Number(totalMinutes) || 0));
    if (t === 0) return "0 мин";
    const h = Math.floor(t / 60);
    const m = t % 60;
    const parts = [];
    if (h > 0) parts.push(`${h} ч`);
    if (m > 0) parts.push(`${m} мин`);
    return parts.length ? parts.join(" ") : "0 мин";
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

  function updateReportMinutesTotal(card) {
    if (!card) return;
    const el = card.querySelector(".report-minutes-total-value");
    if (!el) return;
    el.textContent = formatWorkDurationTotalMinutes(sumEntryMinutesFromCard(card));
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
        delBtn.textContent = "Удалить";
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

      const statusPill = card.querySelector(".status-pill");
      if (statusPill) statusPill.textContent = "final";

      const msg = $("#reportsMsg");
      showMsg(msg, "Excel сформирован.", "success");

      // Refresh from backend so status and entries remain consistent.
      const date = $("#reportsDate")?.value;
      const selectedEmployeeId = state.isAdmin ? $("#reportsEmployeeSelect")?.value : null;
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

  async function ensureReportExists(dateStr, employeeIdOrNull) {
    if (!dateStr) return;

    if (state.isAdmin) {
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

    const employeeId = state.isAdmin ? Number(employeeIdOrNull) : null;
    const reportsKey = `${dateStr}|${state.isAdmin ? employeeId : "me"}`;
    state.reportsLoadedKey = reportsKey;

    await ensureReportExists(dateStr, employeeId);

    const query = new URLSearchParams();
    query.set("date", dateStr);
    if (state.isAdmin && employeeId) query.set("employee_id", String(employeeId));

    const list = await apiFetchJson(`/api/reports?${query.toString()}`);
    const reports = Array.isArray(list) ? list : [];
    renderReportsList(reports);
    showMsg($("#reportsMsg"), "Отчеты загружены.", "success");
  }

  function renderReportCard(report) {
    const reportsList = $("#reportsList");
    const reportId = report.report_id;
    const editable = true;

    const card = document.createElement("div");
    card.className = "report-card";
    // Attribute used by query selectors in helper methods.
    card.setAttribute("data-report-id", String(reportId));

    const employeeName = report.employee?.full_name || report.employee?.username || `ID ${report.employee_id}`;
    const status = report.status;
    const statusLabel = status === "draft" ? "draft" : "final";
    const dateStr = String(report.date ?? "").trim();
    const isFinal = status === "final";
    let excelAreaHtml = "";
    if (state.isAdmin) {
      if (isFinal && dateStr) {
        const excelPath = appRootPath(`/exports/report_${reportId}_${dateStr}.xlsx`);
        const excelHref = escapeHtml(excelPath);
        excelAreaHtml = `<a class="excel-link" href="${excelHref}" target="_blank" rel="noopener">Скачать Excel</a>`;
      } else {
        excelAreaHtml = '<a class="excel-link" href="#" hidden>Скачать Excel</a>';
      }
    }

    card.innerHTML = `
      <div class="report-header">
        <div>
          <div><strong>${escapeHtml(employeeName)}</strong></div>
          <div class="muted">${escapeHtml(report.date)} · статус: ${escapeHtml(statusLabel)}</div>
        </div>
        <div class="status-pill">${escapeHtml(statusLabel)}</div>
      </div>

      <div class="entries">
        <table class="table entries-table">
          <thead>
            <tr>
              <th style="width: 22%;">Задача</th>
              <th>Результат</th>
              <th style="width: 120px;">Время работы</th>
              <th style="width: 120px;"></th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
        <div class="report-minutes-total muted" aria-live="polite">
          Всего: <span class="report-minutes-total-value">0 мин</span>
        </div>
        <div class="actions">
          <button class="btn" type="button" data-action="addEntry" data-report-id="${escapeHtml(String(reportId))}" ${
      editable ? "" : "disabled"
    }>Добавить запись</button>
        </div>
      </div>

      <div class="report-actions">
        <button class="btn primary" data-action="finalizeExcel" data-report-id="${escapeHtml(String(reportId))}">Сформировать Excel</button>
      </div>

      <div class="muted excel-area">
        ${excelAreaHtml}
      </div>
    `;

    reportsList.appendChild(card);

    // Render inputs.
    renderEntriesTable(reportId, report, editable);
  }

  function renderReportsList(reports) {
    const reportsList = $("#reportsList");
    reportsList.innerHTML = "";

    if (!reports.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "Нет отчетов на выбранную дату.";
      reportsList.appendChild(empty);
      return;
    }

    reports.forEach((r) => renderReportCard(r));
  }

  function setReportCardEditable(card, editable) {
    for (const input of card.querySelectorAll("input.entry-task, input.entry-minutes, textarea.entry-description")) {
      input.disabled = !editable;
    }
    for (const btn of card.querySelectorAll('button[data-action="addEntry"]')) {
      btn.disabled = !editable;
    }
  }

  function fillSwapSlotSelects() {
    const fromSel = $("#swapFromSlot");
    const toSel = $("#swapToSlot");
    if (!fromSel || !toSel) return;

    fromSel.innerHTML = "";
    toSel.innerHTML = "";
    for (let slot = 0; slot < state.slotCount; slot++) {
      const label = slotStartLabel(slot);
      const fromOpt = document.createElement("option");
      fromOpt.value = String(slot);
      fromOpt.textContent = label;
      fromSel.appendChild(fromOpt);

      const toOpt = document.createElement("option");
      toOpt.value = String(slot);
      toOpt.textContent = label;
      toSel.appendChild(toOpt);
    }
    toSel.value = "1";
  }

  function renderSwapInbox(items) {
    const root = $("#swapInboxList");
    if (!root) return;
    root.innerHTML = "";
    const rows = Array.isArray(items) ? items : [];
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "Входящих запросов нет.";
      root.appendChild(empty);
      return;
    }
    for (const item of rows) {
      const el = document.createElement("div");
      el.className = "report-card";
      const statusLabel = item.status || "pending";
      const controls =
        statusLabel === "pending"
          ? `
        <div class="actions">
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
    if (state.isAdmin) return;
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
    state.isAdmin = me?.role === "admin";

    const meText = $("#meText");
    if (meText) meText.textContent = `${me.full_name} (${me.role})`;
    const selfFullName = $("#selfFullName");
    if (selfFullName) selfFullName.value = me.full_name || "";

    const syncAdminDutyToggle = () => {
      const select = $("#adminUserSelect");
      const toggle = $("#adminDutyActiveToggle");
      if (!select || !toggle) return;
      const userId = Number(select.value);
      const target = state.employees.find((u) => Number(u.id) === userId);
      toggle.checked = target ? target.is_active_for_duties !== false : true;
    };

    setAdminMode(state.isAdmin);

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
        activateTab(tab);
      });
    }

    $("#employeeExitOpenBtn")?.addEventListener("click", () => {
      showMsg($("#employeeExitMsg"), "", "info");
      openEmployeeExitModal();
      setTimeout(() => $("#eeFio")?.focus(), 0);
    });
    $("#employeeExitCloseBtn")?.addEventListener("click", () => closeEmployeeExitModal());
    $("#employeeExitModal")?.addEventListener("click", (ev) => {
      if (ev.target === $("#employeeExitModal")) closeEmployeeExitModal();
    });
    document.addEventListener("keydown", (ev) => {
      const m = $("#employeeExitModal");
      if (m && !m.hidden && ev.key === "Escape") closeEmployeeExitModal();
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
        const out = await apiEmployeeExitInstruction({ fio, login, password, domain });
        const ta = $("#eeOutput");
        if (ta) ta.value = out.text || "";
        showMsg(msg, "Инструкция сформирована.", "success");
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
        const blob = await apiEmployeeExitInstructionDocx({ fio, login, password, domain });
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
    if ($("#swapDate")) $("#swapDate").value = dutiesDateEl?.value || localISODate();

    // Initialize admin-dependent dropdowns
    if (state.isAdmin) {
      try {
        await loadEmployees();
      } catch (e) {
        showMsg($("#adminRoleMsg"), e.message || String(e), "error");
        renderAdminUsersEditor();
      }

      try {
        const settings = await apiGetNotificationSettings();
        applyNotificationSettingsToUi(settings);
        state.notificationSettingsReady = true;
      } catch (e) {
        showMsg($("#notificationSettingsMsg"), e.message || String(e), "error");
      }

      const reportsEmployeeSelect = $("#reportsEmployeeSelect");
      fillEmployeesSelect(reportsEmployeeSelect, { includeBlank: true, saveKey: "reportsEmployeeId" });
      fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
      syncAdminDutyToggle();
      $("#adminUserSelect")?.addEventListener("change", syncAdminDutyToggle);

      const row = $("#reportsEmployeeRow");
      if (row) row.hidden = false;
    }

    // Graphik handlers
    const dutiesMsgEl = $("#dutiesMsg");
    const dutiesDate = dutiesDateEl?.value;
    $("#loadDutiesBtn")?.addEventListener("click", async () => {
      try {
        showMsg(dutiesMsgEl, "", "info");
        await loadDuties($("#dutiesDate").value);
      } catch (e) {
        showMsg(dutiesMsgEl, e.message || String(e), "error");
      }
    });

    $("#dutiesDate")?.addEventListener("change", async () => {
      try {
        showMsg(dutiesMsgEl, "", "info");
        await loadDuties($("#dutiesDate").value);
      } catch (e) {
        showMsg(dutiesMsgEl, e.message || String(e), "error");
      }
    });

    $("#saveDutiesBtn")?.addEventListener("click", async () => {
      try {
        const dateStr = $("#dutiesDate").value;
        await saveDuties(dateStr);
      } catch (e) {
        showMsg($("#dutiesMsg"), e.message || String(e), "error");
      }
    });

    fillSwapSlotSelects();
    $("#swapDate")?.addEventListener("change", async () => {
      try {
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
        await refreshSwapInbox();
        showMsg($("#swapMsg"), decision === "accept" ? "Запрос принят." : "Запрос отклонен.", "success");
      } catch (e) {
        showMsg($("#swapMsg"), e.message || String(e), "error");
      }
    });

    // Reports handlers
    $("#loadReportsBtn")?.addEventListener("click", async () => {
      try {
        await loadReports($("#reportsDate").value, state.isAdmin ? $("#reportsEmployeeSelect").value : null);
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
        await loadReports($("#reportsDate").value, state.isAdmin ? $("#reportsEmployeeSelect").value : null);
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

        // Refresh current Graphik date if it is visible.
        if ($("#dutiesDate").value) {
          await loadDuties($("#dutiesDate").value);
        }
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    const notificationSettingsControls = [
      "#notifMethodCron",
      "#notifMethodN8n",
      "#notifCron5m",
      "#notifCronStart",
      "#notifCronChatStart",
      "#notifN8n5m",
      "#notifN8nStart",
      "#notifN8nChatStart",
    ];
    for (const selector of notificationSettingsControls) {
      $(selector)?.addEventListener("change", () => {
        updateNotificationSettingsVisibility();
        saveNotificationSettingsAuto();
      });
    }

    $("#notifyDutiesBitrixBtn")?.addEventListener("click", async () => {
      const msg = $("#notifyDutiesBitrixMsg");
      try {
        showMsg(msg, "Отправка графика в Битрикс…", "info");
        const today = localISODate();
        await apiFetchJson(
          `/api/admin/notifications/duty-schedule/bitrix?date=${encodeURIComponent(today)}`,
          { method: "POST" },
        );
        showMsg(msg, "График на сегодня отправлен в настроенный чат Битрикс.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
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
        fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
        fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
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
        fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
        fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
        syncAdminDutyToggle();
        showMsg(msg, "Список сотрудников обновлен.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
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
          const idx = state.employees.findIndex((u) => Number(u.id) === Number(updated.id));
          if (idx >= 0) state.employees[idx] = updated;
          renderAdminUsersEditor();
          fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
          fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
          $("#adminUserSelect").value = String(updated.id);
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
        const idx = state.employees.findIndex((u) => Number(u.id) === Number(updated2.id));
        if (idx >= 0) state.employees[idx] = updated2;
        renderAdminUsersEditor();
        fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
        fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
        $("#adminUserSelect").value = String(updated2.id);
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
        const isActive = Boolean($("#adminDutyActiveToggle").checked);
        if (!userId) throw new Error("Выберите сотрудника.");
        const updated = await apiAdminUpdateDutyStatus(userId, isActive);
        const idx = state.employees.findIndex((u) => Number(u.id) === Number(updated.id));
        if (idx >= 0) state.employees[idx] = updated;
        renderAdminUsersEditor();
        fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
        fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
        $("#adminUserSelect").value = String(updated.id);
        $("#adminDutyActiveToggle").checked = updated.is_active_for_duties !== false;
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
        fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
        fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
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
        fillEmployeesSelect($("#reportsEmployeeSelect"), { includeBlank: true, saveKey: "reportsEmployeeId" });
        fillEmployeesSelect($("#adminUserSelect"), { includeBlank: false });
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
        if (meText) meText.textContent = `${me.full_name} (${me.role})`;
        showMsg(msg, "Профиль обновлен.", "success");
      } catch (e) {
        showMsg(msg, e.message || String(e), "error");
      }
    });

    $("#reportsList")?.addEventListener("input", (ev) => {
      const t = ev.target;
      if (!t?.classList?.contains?.("entry-minutes")) return;
      const card = t.closest(".report-card");
      if (card?.querySelector?.(".report-minutes-total-value")) updateReportMinutesTotal(card);
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
            <td><button type="button" class="btn danger" data-action="removeEntry">Удалить</button></td>
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
      if (dutyDateStr) await loadDuties(dutyDateStr);

      const reportsDateStr = $("#reportsDate").value;
      const employeeId = state.isAdmin ? $("#reportsEmployeeSelect")?.value : null;
      if (reportsDateStr) await loadReports(reportsDateStr, employeeId);
      await refreshSwapInbox();
      updateCurrentDutyNow();
    } catch (e) {
      const msg = state.isAdmin ? $("#reportsMsg") : $("#reportsMsg");
      showMsg(msg, e.message || String(e), "error");
    }

    if (!state.isAdmin) {
      if (state.swapInboxTimerId) clearInterval(state.swapInboxTimerId);
      state.swapInboxTimerId = setInterval(() => {
        refreshSwapInbox().catch(() => {});
      }, 30_000);
    }
    if (state.currentDutyTimerId) clearInterval(state.currentDutyTimerId);
    state.currentDutyTimerId = setInterval(() => {
      updateCurrentDutyNow();
    }, 30_000);
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

