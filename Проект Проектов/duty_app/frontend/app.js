(() => {
  const state = {
    me: null,
    isAdmin: false,
    employees: [],
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
    const start = 9 + Number(slot);
    const end = start + 1;
    return `${String(start).padStart(2, "0")}-${String(end).padStart(2, "0")}`;
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

  async function apiFetchJson(url, { method = "GET", body } = {}) {
    const res = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : null),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      const detail = data?.detail || data?.message;
      throw new Error(detail || `HTTP ${res.status}`);
    }
    return data;
  }

  async function apiGetMe() {
    return apiFetchJson("/api/me");
  }

  async function apiLogin({ username, password }) {
    return apiFetchJson("/api/login", { method: "POST", body: { username, password } });
  }

  async function apiLogout() {
    return apiFetchJson("/api/logout", { method: "POST" });
  }

  async function loadEmployees() {
    const users = await apiFetchJson("/api/admin/users");
    state.employees = Array.isArray(users) ? users : [];
    return state.employees;
  }

  function setAdminMode(isAdmin) {
    state.isAdmin = Boolean(isAdmin);

    const adminTabBtn = $("#adminTabBtn");
    if (adminTabBtn) adminTabBtn.hidden = !state.isAdmin;

    for (const el of $$(".admin-only")) {
      el.hidden = !state.isAdmin;
    }
  }

  function activateTab(tabName) {
    $$(".tab-btn").forEach((b) => {
      const isActive = b.dataset.tab === tabName;
      b.classList.toggle("active", isActive);
      b.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    $$(".tab-panel").forEach((p) => {
      p.classList.toggle("active", p.id === `tab-${tabName}`);
    });
  }

  function renderDutiesTable(dutiesOut) {
    const tbody = $("#dutiesTable tbody");
    tbody.innerHTML = "";

    const isAdmin = state.isAdmin;
    const slots = dutiesOut?.slots || [];

    for (let slot = 0; slot < 9; slot++) {
      const slotOut = slots.find((s) => Number(s.slot) === slot) || slots[slot];
      const user = slotOut?.user || null;

      const tr = document.createElement("tr");
      tr.dataset.slot = String(slot);
      if (window.__highlightDutySlot !== null && Number(window.__highlightDutySlot) === slot) {
        tr.style.background = "#fff4e6";
        tr.title = "Текущее дежурство";
      }

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

        for (const emp of state.employees) {
          const opt = document.createElement("option");
          opt.value = String(emp.id);
          opt.textContent = emp.full_name || emp.username;
          if (user && Number(user.id) === Number(emp.id)) opt.selected = true;
          select.appendChild(opt);
        }
        tdUser.appendChild(select);
      } else {
        tdUser.textContent = user ? (user.full_name || user.username) : "—";
      }

      tr.appendChild(tdTime);
      tr.appendChild(tdUser);
      tbody.appendChild(tr);
    }
  }

  function currentSlotForDate(dateStr) {
    if (!dateStr) return null;
    const now = new Date();
    const today = localISODate(now);
    if (dateStr !== today) return null;

    const minutes = now.getHours() * 60 + now.getMinutes();
    const start = 9 * 60; // 09:00
    const end = 18 * 60; // 18:00 exclusive
    if (minutes < start || minutes >= end) return null;

    return Math.floor((minutes - start) / 60); // 0..8
  }

  async function loadDuties(dateStr) {
    if (!dateStr) return;
    const duties = await apiFetchJson(`/api/duties?date=${encodeURIComponent(dateStr)}`);
    const highlightSlot = currentSlotForDate(dateStr);
    window.__highlightDutySlot = highlightSlot;

    renderDutiesTable(duties);

    if (highlightSlot === null) {
      showMsg($("#dutiesMsg"), "Сейчас вне рабочего времени (09:00–18:00) или выбрана не сегодняшняя дата.", "info");
    } else {
      const slotOut = (duties?.slots || []).find((s) => Number(s.slot) === highlightSlot) || null;
      const name = slotOut?.user?.full_name || slotOut?.user?.username;
      showMsg($("#dutiesMsg"), name ? `Сейчас дежурит: ${name}` : "Сейчас дежурство не назначено.", "info");
    }
  }

  async function saveDuties(dateStr) {
    if (!state.isAdmin) return;

    const assignments = [];
    const selects = $$(".duty-user-select");

    const seenSlots = new Set();
    for (const sel of selects) {
      const slot = Number(sel.dataset.slot);
      seenSlots.add(slot);
      const userId = sel.value ? Number(sel.value) : null;
      if (!userId) throw new Error(`Выберите сотрудника для слота ${slotRangeLabel(slot)}.`);
      assignments.push({ slot, user_id: userId });
    }

    if (seenSlots.size !== 9) throw new Error("Не удалось собрать все слоты графика.");

    await apiFetchJson("/api/duties/batch", {
      method: "POST",
      body: { date: dateStr, assignments },
    });
    await loadDuties(dateStr);
  }

  function renderEntriesTable(reportId, report, editable) {
    const entriesTbody = document.querySelector(`.report-card[data-report-id="${reportId}"] .entries-table tbody`);
    entriesTbody.innerHTML = "";

    const entries = Array.isArray(report.entries) ? report.entries : [];
    const rows = entries.length ? entries : [{ minutes: 0, description: "" }];

    rows.forEach((entry) => {
      const tr = document.createElement("tr");

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

      const tdDesc = document.createElement("td");
      const descInput = document.createElement("textarea");
      descInput.value = entry.description ?? "";
      descInput.className = "entry-description";
      descInput.disabled = !editable;
      tdDesc.appendChild(descInput);

      const tdActions = document.createElement("td");
      if (editable) {
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "btn danger";
        delBtn.textContent = "Удалить";
        delBtn.dataset.action = "removeEntry";
        delBtn.dataset.reportId = String(reportId);
        delBtn.addEventListener("click", () => tr.remove());
        tdActions.appendChild(delBtn);
      }

      tr.appendChild(tdMinutes);
      tr.appendChild(tdDesc);
      tr.appendChild(tdActions);
      entriesTbody.appendChild(tr);
    });
  }

  function getReportCard(reportId) {
    return document.querySelector(`.report-card[data-report-id="${reportId}"]`);
  }

  function gatherReportEntries(reportId) {
    const card = getReportCard(reportId);
    if (!card) return [];

    const rows = card.querySelectorAll(".entries-table tbody tr");
    const entries = [];
    for (const tr of rows) {
      const minutesEl = tr.querySelector(".entry-minutes");
      const descEl = tr.querySelector(".entry-description");
      entries.push({
        minutes: Number(minutesEl.value),
        description: (descEl.value || "").trim(),
      });
    }
    return entries;
  }

  function renderReportCard(report) {
    const reportsList = $("#reportsList");
    const reportId = report.report_id;
    const editable = report.status !== "final";

    const card = document.createElement("div");
    card.className = "report-card";
    card.setAttribute("data-report-id", String(reportId));

    const employeeName = report.employee?.full_name || report.employee?.username || `ID ${report.employee_id}`;
    const statusLabel = report.status === "draft" ? "draft" : "final";

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
              <th style="width: 140px;">Минуты</th>
              <th>Описание</th>
              <th style="width: 120px;"></th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>

        <div class="actions">
          <button class="btn" type="button" data-action="addEntry" data-report-id="${escapeHtml(String(reportId))}" ${
      editable ? "" : "disabled"
    }>Добавить запись</button>
        </div>
      </div>

      <div class="report-actions">
        <button class="btn primary save-draft" data-action="saveDraft" data-report-id="${escapeHtml(String(reportId))}" ${
      editable ? "" : "disabled"
    }>Сохранить черновик</button>
        <button class="btn primary" data-action="finalizeExcel" data-report-id="${escapeHtml(String(reportId))}">Сформировать Excel</button>
      </div>

      <div class="muted excel-area">
        <a class="excel-link" href="#" hidden>Скачать Excel</a>
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
      empty.textContent = "Нет отчетов на выбранную дату.";
      reportsList.appendChild(empty);
      return;
    }

    reports.forEach((r) => renderReportCard(r));
  }

  async function ensureReportExists(dateStr, employeeIdOrNull) {
    if (!dateStr) return;

    if (state.isAdmin) {
      const employeeId = Number(employeeIdOrNull);
      if (!employeeId) throw new Error("Выберите сотрудника для отчета.");
      await apiFetchJson("/api/reports", { method: "POST", body: { date: dateStr, employee_id: employeeId } });
    } else {
      await apiFetchJson("/api/reports", { method: "POST", body: { date: dateStr } });
    }
  }

  async function loadReports(dateStr, employeeIdOrNull) {
    if (!dateStr) return;

    const employeeId = state.isAdmin ? Number(employeeIdOrNull) : null;
    await ensureReportExists(dateStr, employeeIdOrNull);

    const query = new URLSearchParams();
    query.set("date", dateStr);
    if (state.isAdmin && employeeId) query.set("employee_id", String(employeeId));

    const list = await apiFetchJson(`/api/reports?${query.toString()}`);
    renderReportsList(Array.isArray(list) ? list : []);
    showMsg($("#reportsMsg"), "Отчеты загружены.", "success");
  }

  async function saveReportDraft(reportId) {
    const entries = gatherReportEntries(reportId);
    if (!entries.length) throw new Error("Добавьте хотя бы одну запись.");

    for (const [i, e] of entries.entries()) {
      if (!Number.isFinite(e.minutes)) throw new Error(`Минуты в записи ${i + 1} должны быть числом.`);
      if (e.minutes < 0 || e.minutes > 1440) throw new Error(`Минуты в записи ${i + 1} должны быть 0..1440.`);
      if (!e.description) throw new Error(`Описание в записи ${i + 1} не должно быть пустым.`);
      if (e.description.length > 2000) throw new Error(`Описание в записи ${i + 1} слишком длинное.`);
    }

    await apiFetchJson(`/api/reports/${reportId}`, {
      method: "PUT",
      body: { entries },
    });

    const date = $("#reportsDate")?.value;
    const selectedEmployeeId = state.isAdmin ? $("#reportsEmployeeSelect")?.value : null;
    await loadReports(date, selectedEmployeeId);
  }

  async function finalizeReportExcel(reportId) {
    const card = getReportCard(reportId);
    if (!card) return;

    const btn = card.querySelector('button[data-action="finalizeExcel"]');
    if (btn) btn.disabled = true;

    try {
      const out = await apiFetchJson(`/api/reports/${reportId}/finalize`, { method: "POST" });
      const excelUrl = out?.excel_url || "";
      if (!excelUrl) throw new Error("Не удалось получить ссылку на Excel.");

      const statusPill = card.querySelector(".status-pill");
      if (statusPill) statusPill.textContent = "final";

      // Disable editing inputs
      for (const input of card.querySelectorAll("input.entry-minutes, textarea.entry-description")) input.disabled = true;

      // Disable all buttons except finalize button
      const finalizeBtn = card.querySelector('button[data-action="finalizeExcel"]');
      for (const b of card.querySelectorAll("button")) {
        if (finalizeBtn && b === finalizeBtn) continue;
        b.disabled = true;
      }

      let link = card.querySelector("a.excel-link");
      if (!link) {
        link = document.createElement("a");
        link.className = "excel-link";
        card.appendChild(link);
      }
      link.href = excelUrl;
      link.textContent = "Скачать Excel";
      link.hidden = false;

      showMsg($("#reportsMsg"), "Excel сформирован.", "success");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function onIndexInit() {
    let me;
    try {
      me = await apiGetMe();
    } catch {
      window.location.href = "/login.html";
      return;
    }

    state.me = me;
    setAdminMode(me?.role === "admin");

    const meText = $("#meText");
    if (meText) meText.textContent = `${me.full_name} (${me.role})`;

    // Tabs
    $$(".tab-btn").forEach((tabBtn) => {
      tabBtn.addEventListener("click", () => activateTab(tabBtn.dataset.tab));
    });

    // Logout
    $("#logoutBtn")?.addEventListener("click", async () => {
      try {
        await apiLogout();
      } finally {
        window.location.href = "/login.html";
      }
    });

    // Defaults
    const dutiesDateEl = $("#dutiesDate");
    const reportsDateEl = $("#reportsDate");
    if (dutiesDateEl) dutiesDateEl.value = localISODate();
    if (reportsDateEl) reportsDateEl.value = localISODate();

    // Admin init
    if (state.isAdmin) {
      await loadEmployees();

      const reportsEmployeeSelect = $("#reportsEmployeeSelect");
      if (reportsEmployeeSelect) {
        reportsEmployeeSelect.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "—";
        reportsEmployeeSelect.appendChild(placeholder);

        for (const emp of state.employees) {
          const opt = document.createElement("option");
          opt.value = String(emp.id);
          opt.textContent = emp.full_name || emp.username;
          reportsEmployeeSelect.appendChild(opt);
        }
      }
    }

    // Duties
    $("#loadDutiesBtn")?.addEventListener("click", async () => {
      await loadDuties($("#dutiesDate").value);
    });
    $("#saveDutiesBtn")?.addEventListener("click", async () => {
      await saveDuties($("#dutiesDate").value);
    });

    // Reports
    $("#loadReportsBtn")?.addEventListener("click", async () => {
      const employeeId = state.isAdmin ? $("#reportsEmployeeSelect").value : null;
      await loadReports($("#reportsDate").value, employeeId);
    });
    $("#reportsDate")?.addEventListener("change", async () => {
      const employeeId = state.isAdmin ? $("#reportsEmployeeSelect").value : null;
      await loadReports($("#reportsDate").value, employeeId);
    });
    $("#reportsEmployeeSelect")?.addEventListener("change", async () => {
      await loadReports($("#reportsDate").value, $("#reportsEmployeeSelect").value);
    });

    // Admin: generate duties
    $("#genDutiesBtn")?.addEventListener("click", async () => {
      const start = $("#genStartDate").value;
      const end = $("#genEndDate").value;
      await apiFetchJson("/api/duties/generate", {
        method: "POST",
        body: { start_date: start, end_date: end, overwrite: $("#genOverwrite").checked },
      });
      if ($("#dutiesDate")?.value) await loadDuties($("#dutiesDate").value);
    });

    // Admin: create support user
    $("#createUserBtn")?.addEventListener("click", async () => {
      const payload = {
        username: $("#newUserUsername").value.trim(),
        full_name: $("#newUserFullName").value.trim(),
        password: $("#newUserPassword").value,
      };
      await apiFetchJson("/api/admin/users", { method: "POST", body: payload });
      await loadEmployees();
      // If schedule for some date is already shown, refresh it to update dropdown options.
      const dutiesDate = $("#dutiesDate")?.value;
      if (dutiesDate) await loadDuties(dutiesDate);
      // Refresh employees selection
      const reportsEmployeeSelect = $("#reportsEmployeeSelect");
      if (reportsEmployeeSelect) {
        const current = reportsEmployeeSelect.value;
        reportsEmployeeSelect.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "—";
        reportsEmployeeSelect.appendChild(placeholder);
        for (const emp of state.employees) {
          const opt = document.createElement("option");
          opt.value = String(emp.id);
          opt.textContent = emp.full_name || emp.username;
          if (current && String(emp.id) === current) opt.selected = true;
          reportsEmployeeSelect.appendChild(opt);
        }
      }
    });

    // Delegated report card actions
    $("#reportsList")?.addEventListener("click", async (ev) => {
      const btn = ev.target?.closest?.("button");
      if (!btn) return;
      const action = btn.dataset.action;
      const reportId = Number(btn.dataset.reportId);
      if (!action || !reportId) return;

      try {
        if (action === "saveDraft") {
          await saveReportDraft(reportId);
        } else if (action === "finalizeExcel") {
          await finalizeReportExcel(reportId);
        } else if (action === "addEntry") {
          const card = getReportCard(reportId);
          const tbody = card.querySelector(".entries-table tbody");
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><input type="number" min="0" max="1440" step="1" class="entry-minutes" value="0" /></td>
            <td><textarea class="entry-description"></textarea></td>
            <td><button type="button" class="btn danger" data-action="removeEntry">Удалить</button></td>
          `;
          tbody.appendChild(tr);
          tr.querySelector('button[data-action="removeEntry"]').addEventListener("click", () => tr.remove());
        }
      } catch (e) {
        showMsg($("#reportsMsg"), e?.message || String(e), "error");
      }
    });

    // Initial loads
    if ($("#dutiesDate")?.value) await loadDuties($("#dutiesDate").value);
    if ($("#reportsDate")?.value) {
      const employeeId = state.isAdmin ? $("#reportsEmployeeSelect")?.value : null;
      await loadReports($("#reportsDate").value, employeeId);
    }
  }

  async function initLoginPage() {
    const loginForm = $("#loginForm");
    if (!loginForm) return;

    const errEl = $("#loginError");
    loginForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        showMsg(errEl, "", "error");
        const username = $("#loginUsername").value.trim();
        const password = $("#loginPassword").value;
        await apiLogin({ username, password });
        window.location.href = "/index.html";
      } catch (e) {
        showMsg(errEl, e.message || String(e), "error");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    if ($("#loginForm")) initLoginPage();
    else if ($("#dutiesTable") || $("#reportsList")) onIndexInit();
  });
})();

