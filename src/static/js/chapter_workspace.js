(() => {
  const bootstrap = document.getElementById("workspaceBootstrap");
  if (!bootstrap) return;

  const state = {
    username: bootstrap.dataset.username,
    userUuid: bootstrap.dataset.userUuid,
    chapter: bootstrap.dataset.chapter,
    isAdmin: bootstrap.dataset.isAdmin === "1",
    selectedGroup: bootstrap.dataset.selectedGroup || "",
    selectedProblems: new Set(),
    filters: { mode: bootstrap.dataset.selectedFilter || "all" },
    draftMessage: "",
    subchapters: [],
    problemsByGroup: new Map(),
    latestHomework: null,
    userEditedMessage: false,
    sessionStartMs: Date.now(),
    sessionId:
      (typeof crypto !== "undefined" && crypto.randomUUID && crypto.randomUUID()) ||
      `ws-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  };

  const el = {
    subchapterList: document.getElementById("subchapterList"),
    subchapterCount: document.getElementById("subchapterCount"),
    problemList: document.getElementById("problemList"),
    problemPanelTitle: document.getElementById("problemPanelTitle"),
    problemCount: document.getElementById("problemCount"),
    selectedCount: document.getElementById("selectedCount"),
    selectedPreview: document.getElementById("selectedPreview"),
    basketSummary: document.getElementById("basketSummary"),
    draftTitle: document.getElementById("draftTitle"),
    draftDueAt: document.getElementById("draftDueAt"),
    draftMessage: document.getElementById("draftMessage"),
    latestHomework: document.getElementById("latestHomework"),
    copySelectedBtn: document.getElementById("copySelectedBtn"),
    copyMessageBtn: document.getElementById("copyMessageBtn"),
    saveHomeworkBtn: document.getElementById("saveHomeworkBtn"),
    selectVisibleBtn: document.getElementById("selectVisibleBtn"),
    clearSelectionBtn: document.getElementById("clearSelectionBtn"),
    legacyGroupLink: document.getElementById("legacyGroupLink"),
    basketPanel: document.getElementById("basketPanel"),
    mobileBasketToggle: document.getElementById("mobileBasketToggle"),
  };
  const filterButtons = Array.from(document.querySelectorAll("[data-filter]"));

  function escapeHtml(v) {
    return String(v || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function updateQuery() {
    const u = new URL(window.location.href);
    if (state.selectedGroup) u.searchParams.set("group", state.selectedGroup);
    if (state.filters.mode) u.searchParams.set("filter", state.filters.mode);
    window.history.replaceState({}, "", u.toString());
  }

  function setActiveFilterButton() {
    filterButtons.forEach((btn) => {
      btn.classList.toggle("active-filter", (btn.dataset.filter || "all") === state.filters.mode);
    });
  }

  function showToast(msg, ms = 1800) {
    const t = document.createElement("div");
    t.className = "toast show";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => {
      t.classList.remove("show");
      setTimeout(() => t.remove(), 220);
    }, ms);
  }

  function logEvent(eventName, detail = {}, useBeacon = false) {
    const body = JSON.stringify({
      event_name: eventName,
      user: state.username,
      chapter: state.chapter,
      group: state.selectedGroup,
      session_id: state.sessionId,
      detail,
    });
    if (useBeacon && navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon("/api/chapter_workspace/events", blob);
      return;
    }
    fetch("/api/chapter_workspace/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  }

  function getSelectedGroupMeta() {
    return state.subchapters.find((x) => x.group_id === state.selectedGroup) || null;
  }

  function currentProblems() {
    return state.problemsByGroup.get(state.selectedGroup) || [];
  }

  function filteredProblems() {
    const all = currentProblems();
    if (state.filters.mode === "unsolved") {
      return all.filter((p) => p.status === "unsolved" || p.status === "wrong");
    }
    if (state.filters.mode === "wrong") {
      return all.filter((p) => p.status === "wrong");
    }
    return all;
  }

  function syncLegacyGroupLink() {
    if (!el.legacyGroupLink || !state.selectedGroup) return;
    const href = `/user/${encodeURIComponent(state.username)}/chapter/${encodeURIComponent(
      state.chapter
    )}/group/${encodeURIComponent(state.selectedGroup)}?legacy=1`;
    el.legacyGroupLink.href = href;
  }

  function renderSubchapters() {
    el.subchapterCount.textContent = String(state.subchapters.length);
    el.subchapterList.innerHTML = state.subchapters
      .map((s) => {
        const c = s.counts || {};
        const cls = s.group_id === state.selectedGroup ? "subchapter-item active" : "subchapter-item";
        return `<button class="${cls}" data-group="${escapeHtml(s.group_id)}">
          <div><strong>${escapeHtml(s.group_id)}</strong> · ${escapeHtml(s.title || "")}</div>
          <div class="subchapter-meta">완료 ${c.solved || 0} / 부분 ${c.partial || 0} / 오답 ${
          c.wrong || 0
        } / 미해결 ${c.unsolved || 0}</div>
        </button>`;
      })
      .join("");

    el.subchapterList.querySelectorAll("button[data-group]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const next = btn.dataset.group;
        if (!next || next === state.selectedGroup) return;
        const prev = state.selectedGroup;
        state.selectedGroup = next;
        state.selectedProblems.clear();
        await ensureGroupLoaded(next);
        updateQuery();
        renderAll();
        logEvent("group_switch", { from: prev, to: next });
      });
    });
  }

  function renderProblemsChunked(rows) {
    el.problemList.innerHTML = "";
    if (!rows.length) {
      el.problemList.innerHTML = '<div class="empty">표시할 문제가 없습니다.</div>';
      return;
    }

    const chunk = 80;
    let i = 0;
    function draw() {
      const frag = document.createDocumentFragment();
      for (let n = 0; n < chunk && i < rows.length; n += 1, i += 1) {
        const p = rows[i];
        const item = document.createElement("div");
        item.className = `problem-row status-${p.status}`;
        item.innerHTML = `
          <input type="checkbox" data-pid="${escapeHtml(p.problem_id)}" />
          <a href="${escapeHtml(p.link)}" target="_blank" rel="noopener">${escapeHtml(p.title)}</a>
          <a href="${escapeHtml(p.link)}" target="_blank" rel="noopener" class="btn-ghost" style="padding:6px 8px;">문제</a>
          <span class="problem-status">${escapeHtml(p.status)}</span>
        `;
        const cb = item.querySelector('input[type="checkbox"]');
        cb.checked = state.selectedProblems.has(p.problem_id);
        item.classList.toggle("selected", cb.checked);
        cb.addEventListener("change", () => {
          if (cb.checked) state.selectedProblems.add(p.problem_id);
          else state.selectedProblems.delete(p.problem_id);
          item.classList.toggle("selected", cb.checked);
          updateBasket();
        });
        item.addEventListener("click", (e) => {
          if (e.target.closest("a") || e.target.closest("button") || e.target.closest("input")) return;
          cb.checked = !cb.checked;
          cb.dispatchEvent(new Event("change"));
        });
        frag.appendChild(item);
      }
      el.problemList.appendChild(frag);
      if (i < rows.length) requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
  }

  function renderProblems() {
    setActiveFilterButton();
    const list = filteredProblems();
    const g = getSelectedGroupMeta();
    el.problemPanelTitle.textContent = g
      ? `${g.group_id} · ${g.title || ""}`
      : "문제 목록";
    el.problemCount.textContent = `${list.length}개`;
    renderProblemsChunked(list);
  }

  function selectedProblemObjects() {
    const all = currentProblems();
    const set = state.selectedProblems;
    return all.filter((p) => set.has(p.problem_id));
  }

  function buildDraftMessage() {
    const g = getSelectedGroupMeta();
    const selected = selectedProblemObjects();
    const lines = [
      `📘 ${g ? `${g.group_id} ${g.title || ""}` : "숙제"}`,
      `🧩 챕터: ${state.chapter}`,
    ];
    if (g && g.chapter_url) lines.push(`🔗 ${g.chapter_url}`);
    if (el.draftDueAt.value) lines.push(`⏰ 마감: ${el.draftDueAt.value}`);
    lines.push("");
    selected.forEach((p) => lines.push(`- ${p.title}`));
    if (el.draftMessage.value.trim()) lines.push("", el.draftMessage.value.trim());
    return lines.join("\n");
  }

  function updateBasket() {
    const selected = selectedProblemObjects();
    el.selectedCount.textContent = `선택 ${selected.length}개`;
    el.basketSummary.textContent = `${selected.length}개`;
    el.selectedPreview.innerHTML = selected.length
      ? selected
          .map((p) => `<div>${escapeHtml(p.problem_id)} · ${escapeHtml(p.title)}</div>`)
          .join("")
      : '<div class="empty">선택된 문제가 없습니다.</div>';
    if (!el.draftTitle.value) {
      const g = getSelectedGroupMeta();
      el.draftTitle.value = g ? `${g.group_id} ${g.title || ""}` : `${state.chapter} 숙제`;
    }
    if (!state.userEditedMessage) {
      const draft = buildDraftMessage();
      state.draftMessage = draft;
      el.draftMessage.value = draft;
      autoResizeDraftMessage();
    }
  }

  function autoResizeDraftMessage() {
    if (!el.draftMessage) return;
    el.draftMessage.style.height = "auto";
    el.draftMessage.style.height = `${Math.min(Math.max(el.draftMessage.scrollHeight, 116), 320)}px`;
  }

  function renderLatestHomework() {
    const log = state.latestHomework;
    if (!log) {
      el.latestHomework.innerHTML = '<div class="empty">최근 숙제 로그가 없습니다.</div>';
      return;
    }
    const counts = log.counts || {};
    el.latestHomework.innerHTML = `
      <div style="border:1px solid rgba(0,0,0,.12); border-radius:8px; padding:8px; background:#fff;">
        <strong>최근 숙제</strong>
        <div style="font-size:12px; color:#5b6570;">${escapeHtml(log.title || "(제목 없음)")}</div>
        <div style="font-size:12px; color:#5b6570;">총 ${counts.total || 0}, 완료 ${counts.passed || 0}, 미해결 ${
      (counts.wrong || 0) + (counts.pending || 0)
    }</div>
      </div>
    `;
  }

  function renderAll() {
    renderSubchapters();
    renderProblems();
    renderLatestHomework();
    updateBasket();
    syncLegacyGroupLink();
  }

  async function ensureGroupLoaded(groupId) {
    if (state.problemsByGroup.has(groupId)) return;
    const url = `/api/chapter_workspace/group/${encodeURIComponent(groupId)}?user=${encodeURIComponent(
      state.username
    )}&chapter=${encodeURIComponent(state.chapter)}`;
    const res = await fetch(url);
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      throw new Error(payload.error || "group load failed");
    }
    state.problemsByGroup.set(groupId, payload.problems || []);
    if (payload.latest_homework) state.latestHomework = payload.latest_homework;
  }

  async function init() {
    el.problemList.innerHTML = '<div class="skeleton-row"></div><div class="skeleton-row"></div><div class="skeleton-row"></div>';
    el.subchapterList.innerHTML = '<div class="skeleton-row"></div><div class="skeleton-row"></div>';
    const q = `/api/chapter_workspace?user=${encodeURIComponent(state.username)}&chapter=${encodeURIComponent(
      state.chapter
    )}&group=${encodeURIComponent(state.selectedGroup || "")}`;
    const res = await fetch(q);
    const payload = await res.json();
    if (!res.ok || !payload.ok) {
      showToast(payload.error || "워크스페이스 로드 실패", 2800);
      logEvent("workspace_load_failed", { error: payload.error || "unknown" });
      return;
    }

    state.selectedGroup = payload.selected_group;
    state.subchapters = payload.subchapters || [];
    state.latestHomework = payload.latest_homework || null;
    state.problemsByGroup.set(payload.selected_group, payload.problems || []);

    updateQuery();
    renderAll();
    autoResizeDraftMessage();
    logEvent("workspace_load_succeeded", {
      subchapter_count: state.subchapters.length,
      problem_count: (payload.problems || []).length,
    });
  }

  async function copySelectedProblems() {
    const selected = selectedProblemObjects();
    if (!selected.length) {
      showToast("선택된 문제가 없습니다.");
      return;
    }
    const text = el.draftMessage.value.trim() || buildDraftMessage();
    await navigator.clipboard.writeText(text);
    showToast(`${selected.length}개 문제를 복사했습니다.`);
    logEvent("workspace_copy_selected", { selected_count: selected.length });
  }

  async function saveHomework() {
    if (!state.isAdmin) {
      showToast("관리자만 저장할 수 있습니다.");
      return;
    }
    const selected = selectedProblemObjects();
    if (!selected.length) {
      showToast("선택된 문제가 없습니다.");
      return;
    }
    const g = getSelectedGroupMeta();
    const payload = {
      title: el.draftTitle.value.trim() || (g ? g.title : ""),
      url: (g && g.chapter_url) || "",
      problems: selected.map((p) => ({ legacy_code: p.legacy_code, title: p.title })),
      message: el.draftMessage.value.trim() || buildDraftMessage(),
      channel: "kakao",
    };
    if (el.draftDueAt.value) payload.due_at = new Date(el.draftDueAt.value).toISOString();

    const res = await fetch(`/api/students/${encodeURIComponent(state.userUuid)}/homework_logs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok || body.ok === false) {
      showToast("저장 실패. 잠시 후 다시 시도하세요.", 2600);
      logEvent("workspace_save_failed", { selected_count: selected.length, status: res.status });
      return;
    }
    showToast("숙제를 저장했습니다.");
    logEvent("workspace_save_succeeded", { selected_count: selected.length });
    state.latestHomework = {
      title: payload.title,
      counts: { total: selected.length, passed: 0, wrong: 0, pending: selected.length },
    };
    renderLatestHomework();
  }

  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      state.filters.mode = btn.dataset.filter || "all";
      updateQuery();
      renderProblems();
    });
  });

  el.selectVisibleBtn.addEventListener("click", () => {
    filteredProblems().forEach((p) => state.selectedProblems.add(p.problem_id));
    updateBasket();
    renderProblems();
  });

  el.clearSelectionBtn.addEventListener("click", () => {
    state.selectedProblems.clear();
    updateBasket();
    renderProblems();
  });

  el.copySelectedBtn.addEventListener("click", () => {
    copySelectedProblems().catch((e) => showToast(e.message || "복사 실패"));
  });
  el.copyMessageBtn.addEventListener("click", () => {
    navigator.clipboard
      .writeText(el.draftMessage.value.trim() || buildDraftMessage())
      .then(() => showToast("메시지를 복사했습니다."))
      .catch(() => showToast("메시지 복사 실패"));
  });
  el.saveHomeworkBtn.addEventListener("click", () => {
    saveHomework().catch((e) => showToast(e.message || "저장 실패"));
  });
  el.draftMessage.addEventListener("input", () => {
    state.userEditedMessage = true;
    autoResizeDraftMessage();
  });

  el.mobileBasketToggle?.addEventListener("click", () => {
    const isOpen = el.basketPanel.classList.toggle("open");
    el.mobileBasketToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  window.addEventListener("beforeunload", () => {
    logEvent(
      "workspace_leave",
      {
        selected_count: state.selectedProblems.size,
        duration_ms: Date.now() - state.sessionStartMs,
      },
      true
    );
  });

  init().catch((e) => showToast(e.message || "초기화 실패"));
})();
