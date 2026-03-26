(() => {
  const state = {
    me: null,
    isAdmin: false,
    employees: [],
    dutiesLoadedForDate: null,
    reportsLoadedKey: null,
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

  async function apiFetchJson(url, { method = "GET", body, headers } = {}) {
    const res = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: {
        ...(headers || {}),
        ...(body !== undefined ? { "Content-Type": "application/json" } : null),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    // backend answers with JSON (for our listed endpoints)
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
    return apiFetchJson("/api/login", {
      method: "POST",
      body: { username, password },
    });
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
      // Elements in HTML can have "hidden" attribute; JS must control it.
      el.hidden = !state.isAdmin;
    }

    if (!state.isAdmin) {
      // Remove dropdown selection controls that are admin-specific from state.
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

  async function loadDuties(dateStr) {
    if (!dateStr) return;

    const duties = await apiFetchJson(`/api/duties?date=${encodeURIComponent(dateStr)}`);
    state.dutiesLoadedForDate = dateStr;

    renderDutiesTable(duties);
    showMsg($("#dutiesMsg"), "График загружен.", "success");
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

    // Ensure all 9 slots are present (defensive).
    if (seenSlots.size !== 9) {
      throw new Error("Не удалось собрать все слоты графика.");
    }

    await apiFetchJson("/api/duties/batch", {
      method: "POST",
      body: { date: dateStr, assignments },
    });

    await loadDuties(dateStr);
  }

  function renderEntriesTable(reportId, report, editable) {
    const entriesTbody = document.querySelector(
      `.report-card[data-report-id="${reportId}"] .entries-table tbody`
    );

    entriesTbody.innerHTML = "";

    const entries = Array.isArray(report.entries) ? report.entries : [];
    const rows = entries.length ? entries : [{ minutes: 0, description: "" }];

    rows.forEach((entry, idx) => {
      const tr = document.createElement("tr");
      tr.dataset.entry-index = String(idx);

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
        delBtn.addEventListener("click", () => {
          tr.remove();
        });
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

    const minutesInputs = $$(".entry-minutes", card);
    const descInputs = $$(".entry-description", card);
    const rows = card.querySelectorAll(".entries-table tbody tr");

    const entries = [];
    let idx = 0;
    for (const tr of rows) {
      const minutesEl = tr.querySelector(".entry-minutes");
      const descEl = tr.querySelector(".entry-description");
      const minutes = Number(minutesEl.value);
      const description = (descEl.value || "").trim();
      entries.push({ minutes, description });
      idx += 1;
    }
    return entries;
  }

  async function saveReportDraft(reportId) {
    const card = getReportCard(reportId);
    if (!card) return;

    const entries = gatherReportEntries(reportId);
    if (!entries.length) throw new Error("Добавьте хотя бы одну запись.");

    for (const [i, e] of entries.entries()) {
      if (!Number.isFinite(e.minutes)) throw new Error(`Минуты в записи ${i + 1} должны быть числом.`);
      if (e.minutes < 0 || e.minutes > 1440)
        throw new Error(`Минуты в записи ${i + 1} должны быть в диапазоне 0..1440.`);
      if (!e.description) throw new Error(`Описание в записи ${i + 1} не должно быть пустым.`);
      if (e.description.length > 2000) throw new Error(`Описание в записи ${i + 1} слишком длинное.`);
    }

    await apiFetchJson(`/api/reports/${reportId}`, {
      method: "PUT",
      body: { entries },
    });

    // Refresh UI from backend to keep it consistent.
    const date = $("#reportsDate")?.value;
    const selectedEmployeeId = state.isAdmin ? $("#reportsEmployeeSelect")?.value : null;
    await loadReports(date, selectedEmployeeId);
  }

  async function finalizeReportExcel(reportId) {
    const card = getReportCard(reportId);
    if (!card) return;

    const btn = card.querySelector(`button[data-action="finalizeExcel"]`);
    if (btn) btn.disabled = true;
    try {
      const out = await apiFetchJson(`/api/reports/${reportId}/finalize`, { method: "POST" });
      // Backend returns excel_url even if already finalized.
      const excelUrl = out?.excel_url || "";
      if (!excelUrl) throw new Error("Не удалось получить ссылку на Excel.");

      const statusPill = card.querySelector(".status-pill");
      if (statusPill) statusPill.textContent = "final";

      // После финализации редактирование должно быть отключено.
      const finalizeBtn = card.querySelector('button[data-action="finalizeExcel"]');
      for (const input of card.querySelectorAll("input.entry-minutes, textarea.entry-description")) {
        input.disabled = true;
      }
      for (const btn of card.querySelectorAll("button")) {
        if (finalizeBtn && btn === finalizeBtn) continue;
        btn.disabled = true;
      }

      const link = card.querySelector("a.excel-link");
      if (link) {
        link.href = excelUrl;
        link.hidden = false;
      } else {
        const a = document.createElement("a");
        a.className = "excel-link";
        a.href = excelUrl;
        a.textContent = "Скачать Excel";
        card.appendChild(a);
      }

      const msg = $("#reportsMsg");
      showMsg(msg, "Excel сформирован.", "success");
    } finally {
      if (btn) btn.disabled = false;
    }
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
    const editable = report.status !== "final";

    const card = document.createElement("div");
    card.className = "report-card";
    // Attribute used by query selectors in helper methods.
    card.setAttribute("data-report-id", String(reportId));

    const employeeName = report.employee?.full_name || report.employee?.username || `ID ${report.employee_id}`;
    const status = report.status;
    const statusLabel = status === "draft" ? "draft" : "final";

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
    for (const input of card.querySelectorAll("input.entry-minutes, textarea.entry-description")) {
      input.disabled = !editable;
    }
    for (const btn of card.querySelectorAll("button.save-draft")) {
      btn.disabled = !editable;
    }
    for (const btn of card.querySelectorAll('button[data-action="addEntry"]')) {
      btn.disabled = !editable;
    }
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

    // Dates defaults
    const dutiesDateEl = $("#dutiesDate");
    const reportsDateEl = $("#reportsDate");
    if (dutiesDateEl) dutiesDateEl.value = localISODate();
    if (reportsDateEl) reportsDateEl.value = localISODate();

    // Initialize admin-dependent dropdowns
    if (state.isAdmin) {
      await loadEmployees();

      const reportsEmployeeSelect = $("#reportsEmployeeSelect");
      if (reportsEmployeeSelect) {
        reportsEmployeeSelect.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "—";
        reportsEmployeeSelect.appendChild(placeholder);

        const saved = localStorage.getItem("reportsEmployeeId");
        let selectedFound = false;
        for (const emp of state.employees) {
          const opt = document.createElement("option");
          opt.value = String(emp.id);
          opt.textContent = emp.full_name || emp.username;
          if (saved && String(emp.id) === saved) {
            opt.selected = true;
            selectedFound = true;
          }
          reportsEmployeeSelect.appendChild(opt);
        }
        if (!selectedFound && state.employees.length) {
          reportsEmployeeSelect.value = String(state.employees[0].id);
          localStorage.setItem("reportsEmployeeId", String(state.employees[0].id));
        }
      }

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

    $("#saveDutiesBtn")?.addEventListener("click", async () => {
      try {
        const dateStr = $("#dutiesDate").value;
        await saveDuties(dateStr);
      } catch (e) {
        showMsg($("#dutiesMsg"), e.message || String(e), "error");
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
        await apiFetchJson("/api/admin/users", { method: "POST", body: payload });
        showMsg(msg, "Сотрудник добавлен.", "success");

        // Refresh employees for dropdowns.
        await loadEmployees();

        const reportsEmployeeSelect = $("#reportsEmployeeSelect");
        if (reportsEmployeeSelect) {
          const saved = localStorage.getItem("reportsEmployeeId");
          reportsEmployeeSelect.innerHTML = "";
          const placeholder = document.createElement("option");
          placeholder.value = "";
          placeholder.textContent = "—";
          reportsEmployeeSelect.appendChild(placeholder);

          let selectedFound = false;
          for (const emp of state.employees) {
            const opt = document.createElement("option");
            opt.value = String(emp.id);
            opt.textContent = emp.full_name || emp.username;
            if (saved && String(emp.id) === saved) {
              opt.selected = true;
              selectedFound = true;
            }
            reportsEmployeeSelect.appendChild(opt);
          }
          if (!selectedFound && state.employees.length) {
            reportsEmployeeSelect.value = String(state.employees[0].id);
            localStorage.setItem("reportsEmployeeId", String(state.employees[0].id));
          }
        }

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
            <td><input type="number" min="0" max="1440" step="1" class="entry-minutes" value="0" /></td>
            <td><textarea class="entry-description"></textarea></td>
            <td><button type="button" class="btn danger" data-action="removeEntry">Удалить</button></td>
          `;
          tbody.appendChild(tr);
          const delBtn = tr.querySelector('button[data-action="removeEntry"]');
          if (delBtn) delBtn.addEventListener("click", () => tr.remove());
        } else if (action === "saveDraft") {
          await saveReportDraft(Number(reportId));
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
    } catch (e) {
      const msg = state.isAdmin ? $("#reportsMsg") : $("#reportsMsg");
      showMsg(msg, e.message || String(e), "error");
    }
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

