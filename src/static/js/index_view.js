/**
 * Main Index Page Module (index_view.js)
 */
const CFG_MAIN = window.APP_CONFIG || {};
const userUuid = CFG_MAIN.userUuid || "";

(async function mountLatestHomeworkCard() {
  if (!userUuid) return;
  try {
    const ttlMs = 60_000;
    const first = await fetch(`/api/students/${userUuid}/homework_status`).then((r) => r.json());
    const updatedAt = first.updated_at ? Date.parse(first.updated_at) : 0;
    if (!updatedAt || Date.now() - updatedAt > ttlMs) {
      await fetch(`/api/students/${userUuid}/refresh`, { method: "POST" });
    }
  } catch (e) {}

  const data = await fetch(`/api/students/${userUuid}/homework_latest`)
    .then((r) => r.json())
    .catch(() => ({}));
  const host = document.querySelector("#latest-homework");
  if (!host) return;

  if (!data || !data.ok || !data.log) {
    host.innerHTML = `<div class="card empty-state"><div class="empty-title">숙제 데이터가 없습니다</div><div class="empty-desc">목록을 새로고침하거나 수업 일정을 확인해 주세요.</div><div class="empty-actions"><button class="btn btn-primary" id="refresh-homework">숙제 새로고침</button></div></div>`;
    document.getElementById("refresh-homework")?.addEventListener("click", updateProblems);
    return;
  }

  const { log } = data;
  const pct = log.counts.total ? Math.round((log.counts.passed / log.counts.total) * 100) : 0;

  const statusByLegacy = Object.fromEntries(
    (log.problem_status || []).map((p) => [p.legacy_code, p.status])
  );
  const statusById = Object.fromEntries(
    (log.problem_status || []).map((p) => [String(p.server_problem_id), p.status])
  );

  const problemLis = (log.problems || [])
    .map((p) => {
      const st = p.legacy_code
        ? statusByLegacy[p.legacy_code]
        : statusById[String(p.server_problem_id)];
      const icon = st === "passed" ? "✅" : st === "wrong" ? "❌" : "-";
      const cls = st || "pending";
      const code = p.legacy_code
        ? `<code>${p.legacy_code}</code>`
        : p.server_problem_id
        ? `<code>#${p.server_problem_id}</code>`
        : "";
      const title = p.title || p.title_at_issue || "";
      return `<li class="problem-row ${cls}" data-legacy-code="${p.legacy_code || ""}" data-server-problem-id="${p.server_problem_id || ""}">
  <span class="mark">${icon}</span> ${code} <span class="title">${title}</span>
</li>`;
    })
    .join("");

  host.innerHTML = `
<article class="card" data-log-id="${log.key || ""}" data-id="${log.id || ""}">
  <div class="card-head">
    <div class="card-title">${log.title || "제목 없는 숙제"}</div>
    <span class="badge">${(log.channel || "kakao").toUpperCase()}</span>
  </div>

  <div class="progress">
    <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
    <div class="progress-text">정답 ${log.counts.passed} | 오답 ${log.counts.wrong} | 미제출 ${log.counts.pending}</div>
  </div>

  <div class="meta">
    <span>배정: <span class="ts" data-iso="${log.ts}">${log.ts || "-"}</span></span>
    ${log.due_at ? `<span>마감: <span class="ts" data-iso="${log.due_at}">${log.due_at}</span></span>` : ""}
    ${log.url ? `<span>링크: <a href="${log.url}" target="_blank" rel="noopener">${log.url}</a></span>` : ""}
  </div>

  ${log.problems && log.problems.length ? `<ol class="problems">${problemLis}</ol>` : ""}

  <div class="actions">
    ${log.url ? `<a class="btn btn-secondary" href="${log.url}" target="_blank" rel="noopener">숙제 링크 열기</a>` : ""}
    <button class="btn btn-quiet" id="reopen-homework">숙제 전체 보기</button>
  </div>
</article>
`;

  document.getElementById("reopen-homework")?.addEventListener("click", () => {
    window.open(`/students/${userUuid}/homework`, "_blank");
  });
})();

function updateProblems() {
  const btn = document.getElementById("update-btn");
  const chapterSelect = document.getElementById("update-chapter-select");
  const timeDisplay = document.getElementById("update-time");
  const originalText = btn ? btn.innerHTML : "";

  if (btn) {
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    btn.innerHTML = `<span class="spinner" aria-hidden="true"></span> <span>갱신 중...</span>`;
  }

  const selectedChapter = chapterSelect ? chapterSelect.value : "";
  const params = new URLSearchParams();
  if (selectedChapter) params.append("chapter", selectedChapter);

  fetch(`/update_problems?${params.toString()}`, { method: "POST" })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === "success") {
        if (typeof showToast === "function") showToast("학습 데이터가 갱신되었습니다!");
        if (timeDisplay && data.last_updated) timeDisplay.textContent = `최근 갱신: ${data.last_updated}`;
        if (typeof refreshStreak === "function") refreshStreak(typeof streakCurrentDays !== "undefined" ? streakCurrentDays : 7);
      } else {
        if (typeof showToast === "function") showToast(data.message || "데이터 갱신 중 오류가 발생했습니다.", 3500);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      if (typeof showToast === "function") showToast("서버와 통신 중 오류가 발생했습니다.", 3500);
    })
    .finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
        btn.innerHTML = originalText;
      }
    });
}

const chartsSection = document.getElementById("charts-section");
const chartsToggleBtn = document.getElementById("charts-toggle-btn");
const chartsContainer = document.getElementById("charts-container");

function setChartsCollapsed(collapsed) {
  if (!chartsSection || !chartsToggleBtn || !chartsContainer) return;
  const isCollapsed = Boolean(collapsed);
  chartsSection.classList.toggle("is-collapsed", isCollapsed);
  chartsContainer.style.display = isCollapsed ? "none" : "";
  chartsToggleBtn.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
  chartsToggleBtn.textContent = isCollapsed ? "단원별 펼치기" : "접기";
  try { localStorage.setItem("charts_section_collapsed", isCollapsed ? "1" : "0"); } catch (e) {}
}

if (chartsToggleBtn) {
  let initialCollapsed = false;
  try { initialCollapsed = localStorage.getItem("charts_section_collapsed") === "1"; } catch (e) {}
  setChartsCollapsed(initialCollapsed);
  chartsToggleBtn.addEventListener("click", () => {
    const currentState = chartsSection.classList.contains("is-collapsed");
    setChartsCollapsed(!currentState);
  });
}

// --- 🧺 퀵 숙제 장바구니 (Quick Homework Basket) ---
(function initQuickHomeworkBasket() {
  let basketItems = [];

  const badgeEl = document.getElementById("basket-count-badge");
  const emptyMsgEl = document.getElementById("basket-empty-msg");
  const listEl = document.getElementById("basket-items-list");
  const clearBtn = document.getElementById("basket-clear-btn");
  const submitBtn = document.getElementById("basket-submit-btn");
  const toggleBtn = document.getElementById("basket-toggle-btn");
  const basketBody = document.getElementById("basket-body");

  if (toggleBtn && basketBody) {
    toggleBtn.addEventListener("click", () => {
      const isHidden = basketBody.style.display === "none";
      basketBody.style.display = isHidden ? "block" : "none";
      toggleBtn.textContent = isHidden ? "➖" : "➕";
    });
  }

  function updateBasketUI() {
    if (!badgeEl || !listEl || !emptyMsgEl) return;
    badgeEl.textContent = `${basketItems.length}개`;
    emptyMsgEl.style.display = basketItems.length === 0 ? "block" : "none";

    listEl.innerHTML = basketItems
      .map(
        (item, idx) => `
      <li style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 8px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.8rem;">
        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; color: #334155;" title="${item.title}">${item.title}</span>
        <button type="button" data-idx="${idx}" class="basket-remove-item-btn" style="background: none; border: none; color: #ef4444; cursor: pointer; font-weight: bold; font-size: 0.9rem;">✕</button>
      </li>
    `
      )
      .join("");

    listEl.querySelectorAll(".basket-remove-item-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        if (!isNaN(idx)) {
          basketItems.splice(idx, 1);
          updateBasketUI();
          if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
        }
      });
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      basketItems = [];
      updateBasketUI();
      if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
      if (typeof showToast === "function") showToast("🧹 장바구니를 비웠습니다.");
    });
  }

  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      if (basketItems.length === 0) {
        if (typeof showToast === "function") showToast("⚠️ 출제할 문제를 먼저 장바구니에 담아주세요.");
        return;
      }

      const targetUuid = (window.APP_CONFIG && window.APP_CONFIG.userUuid) || "";
      if (!targetUuid) {
        if (typeof showToast === "function") showToast("⚠️ 대상 수강생 정보를 찾을 수 없습니다.");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "⏳ 출제 중...";

      try {
        const res = await fetch("/api/workspace/save_homework_log", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_uuid: targetUuid,
            problems: basketItems,
            title: `대시보드 퀵 출제 (${basketItems.length}개)`
          })
        });

        const data = await res.json();
        if (res.ok && data.ok) {
          basketItems = [];
          updateBasketUI();
          if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
          if (typeof showToast === "function") {
            showToast("🚀 숙제가 성공적으로 즉시 출제/저장되었습니다!");
          }
        } else {
          if (typeof showToast === "function") {
            showToast(`❌ 출제 실패: ${data.error || '오류가 발생했습니다.'}`);
          }
        }
      } catch (err) {
        if (typeof showToast === "function") showToast(`❌ 출제 예외: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "🚀 숙제 즉시 출제하기";
      }
    });
  }

  window.addProblemToBasket = function (probObj) {
    if (!probObj || !probObj.pid) return;
    if (!basketItems.some((item) => item.pid === probObj.pid)) {
      basketItems.push(probObj);
      updateBasketUI();
    }
  };

  window.removeProblemFromBasket = function (pid) {
    basketItems = basketItems.filter((item) => item.pid !== pid);
    updateBasketUI();
  };

  window.isProblemInBasket = function (pid) {
    return basketItems.some((item) => item.pid === pid);
  };

  updateBasketUI();
})();

// --- 📱 3단 계층형 드릴다운 패널 (Hierarchical Drilldown Panel) ---
(function initDrilldownPanel() {
  const drillData = (window.APP_CONFIG && window.APP_CONFIG.drilldownData) || [];
  
  const mainListEl = document.getElementById("main-chapters-list");
  const subListEl = document.getElementById("sub-chapters-list");
  const probListEl = document.getElementById("problems-list");

  const mainCountEl = document.getElementById("main-chapter-count");
  const subCountEl = document.getElementById("sub-chapter-count");

  const btnSelectAll = document.getElementById("btn-select-all-problems");

  if (!mainListEl || !subListEl || !probListEl) return;

  let selectedChapter = null;
  let selectedGroup = null;

  // 1. Render Main Chapters List
  function renderMainChapters() {
    if (mainCountEl) mainCountEl.textContent = `${drillData.length}개`;

    if (drillData.length === 0) {
      mainListEl.innerHTML = `<div class="col-placeholder">등록된 대단원이 없습니다.</div>`;
      return;
    }

    mainListEl.innerHTML = drillData.map((ch, idx) => {
      const tone = ch.percent >= 80 ? "high" : (ch.percent >= 40 ? "mid" : "low");
      const isSel = selectedChapter && selectedChapter.chapter === ch.chapter;
      return `
        <div class="drill-item ${isSel ? 'active' : ''}" data-idx="${idx}">
          <div class="drill-item-head">
            <span class="drill-item-title">${ch.chapter}</span>
            <span style="font-size: 0.8rem; font-weight: 700; color: #2563eb;">${ch.percent}%</span>
          </div>
          <div class="drill-progress-track">
            <div class="drill-progress-fill ${tone}" style="width: ${ch.percent}%"></div>
          </div>
          <div class="drill-item-meta">
            <span>${ch.solved} / ${ch.total} 문제 완료</span>
            <span>오답 ${ch.wrong} · 부분 ${ch.partial}</span>
          </div>
        </div>
      `;
    }).join("");

    mainListEl.querySelectorAll(".drill-item").forEach(item => {
      item.addEventListener("click", () => {
        const idx = parseInt(item.dataset.idx, 10);
        selectedChapter = drillData[idx];
        selectedGroup = null;
        renderMainChapters();
        renderSubChapters();
        renderProblemsPlaceholder();
      });
    });
  }

  let currentSubFilter = "all"; // "all", "regular", "homework"

  function isHomeworkGroup(g) {
    if (!g) return false;
    const gid = String(g.group_id || "").trim();
    const title = String(g.title || "").trim();
    return /^SS?\d+/i.test(gid) || gid.startsWith("S") || gid.startsWith("SS") || title.includes("숙제");
  }

  // Handle Sub-chapter Filter Buttons
  document.querySelectorAll(".sub-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sub-filter-btn").forEach((b) => {
        b.style.background = "#ffffff";
        b.style.color = "#475569";
        b.classList.remove("active");
      });
      btn.style.background = "#3b82f6";
      btn.style.color = "#ffffff";
      btn.classList.add("active");
      currentSubFilter = btn.dataset.subFilter || "all";
      renderSubChapters();
    });
  });

  // 2. Render Sub Chapters List
  function renderSubChapters() {
    if (!selectedChapter) {
      if (subCountEl) subCountEl.textContent = "0개";
      subListEl.innerHTML = `<div class="col-placeholder">👈 좌측 대단원을 선택해주세요.</div>`;
      return;
    }

    const allGroups = selectedChapter.groups || [];
    const filteredGroups = allGroups.filter((g) => {
      const isHw = isHomeworkGroup(g);
      if (currentSubFilter === "regular") return !isHw;
      if (currentSubFilter === "homework") return isHw;
      return true;
    });

    if (subCountEl) subCountEl.textContent = `${filteredGroups.length}개`;

    if (filteredGroups.length === 0) {
      subListEl.innerHTML = `<div class="col-placeholder">선택한 필터 조건에 해당하는 소단원이 없습니다.</div>`;
      return;
    }

    subListEl.innerHTML = filteredGroups
      .map((g) => {
        const tone = g.percent >= 80 ? "high" : g.percent >= 40 ? "mid" : "low";
        const isSel = selectedGroup && selectedGroup.group_id === g.group_id;
        const isHw = isHomeworkGroup(g);
        const catBadge = isHw
          ? `<span style="font-size: 0.68rem; padding: 1px 5px; border-radius: 4px; background: #fef3c7; color: #b45309; font-weight: 700; flex-shrink: 0;">🛒 숙제</span>`
          : `<span style="font-size: 0.68rem; padding: 1px 5px; border-radius: 4px; background: #e0f2fe; color: #0369a1; font-weight: 700; flex-shrink: 0;">📖 진도</span>`;

        const unsolvedCount = Math.max(0, (g.total || 0) - (g.solved || 0));
        const unsolvedBadge =
          unsolvedCount > 0
            ? `<span style="font-size: 0.68rem; padding: 1px 6px; border-radius: 999px; background: #fee2e2; color: #dc2626; font-weight: 700; flex-shrink: 0;">미풀이 ${unsolvedCount}개</span>`
            : `<span style="font-size: 0.68rem; padding: 1px 6px; border-radius: 999px; background: #dcfce7; color: #15803d; font-weight: 700; flex-shrink: 0;">완료! 🎉</span>`;

        return `
        <div class="drill-item ${isSel ? "active" : ""}" data-gid="${g.group_id}">
          <div class="drill-item-head" style="gap: 6px;">
            <div style="display: flex; align-items: center; gap: 6px; overflow: hidden; flex: 1;">
              ${catBadge}
              <span class="drill-item-title" title="${g.title || g.group_id}">${g.title || g.group_id}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
              ${unsolvedBadge}
              <span style="font-size: 0.8rem; font-weight: 700; color: #2563eb;">${g.percent}%</span>
            </div>
          </div>
          <div class="drill-progress-track">
            <div class="drill-progress-fill ${tone}" style="width: ${g.percent}%"></div>
          </div>
          <div class="drill-item-meta">
            <span>${g.solved} / ${g.total} 문제 완료</span>
            <span>오답 ${g.wrong}</span>
          </div>
        </div>
      `;
      })
      .join("");

    subListEl.querySelectorAll(".drill-item").forEach((item) => {
      item.addEventListener("click", () => {
        const gid = item.dataset.gid;
        selectedGroup = allGroups.find((g) => g.group_id === gid);
        renderSubChapters();
        renderProblems();
      });
    });
  }

  function renderProblemsPlaceholder() {
    const probHeaderTitleEl = document.getElementById("prob-header-title");
    if (probHeaderTitleEl) {
      probHeaderTitleEl.textContent = "📝 3. 문제 목록 (소단원을 선택해 주세요)";
    }
    probListEl.innerHTML = `<div class="col-placeholder">👈 2열에서 소단원을 선택해 주세요.</div>`;
  }

  let currentProbFilter = "all"; // "all", "unsolved", "solved", "wrong"

  // Handle Problem Status Filter Buttons
  document.querySelectorAll(".prob-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".prob-filter-btn").forEach((b) => {
        b.style.background = "#ffffff";
        b.style.color = "#475569";
        b.classList.remove("active");
      });
      btn.style.background = "#3b82f6";
      btn.style.color = "#ffffff";
      btn.classList.add("active");
      currentProbFilter = btn.dataset.probFilter || "all";
      renderProblems();
    });
  });

  // 3. Render Problems List & Checkboxes
  function renderProblems() {
    if (!selectedGroup) {
      renderProblemsPlaceholder();
      return;
    }

    const probHeaderTitleEl = document.getElementById("prob-header-title");
    if (probHeaderTitleEl) {
      probHeaderTitleEl.textContent = `📝 3. 문제 목록 (${selectedGroup.title || selectedGroup.group_id} · 총 ${selectedGroup.total || 0}문제)`;
    }

    const allProblems = selectedGroup.problems || [];
    const filteredProblems = allProblems.filter((p) => {
      if (currentProbFilter === "unsolved") return p.status === "unsolved";
      if (currentProbFilter === "solved") return p.status === "solved";
      if (currentProbFilter === "wrong") return p.status === "wrong" || p.status === "partial";
      return true;
    });

    probListEl.classList.remove("fade-in-list");
    void probListEl.offsetWidth;
    probListEl.classList.add("fade-in-list");

    if (filteredProblems.length === 0) {
      probListEl.innerHTML = `<div class="col-placeholder">선택한 필터 조건에 해당하는 문제가 없습니다.</div>`;
      return;
    }

    probListEl.innerHTML = filteredProblems
      .map((p) => {
        const isChecked = window.isProblemInBasket ? window.isProblemInBasket(p.pid) : false;
        const statusBadge =
          p.status === "solved"
            ? '<span class="prob-status-badge solved">✅ 정답</span>'
            : p.status === "partial"
            ? '<span class="prob-status-badge partial">⚠️ 부분</span>'
            : p.status === "wrong"
            ? '<span class="prob-status-badge wrong">❌ 오답</span>'
            : '<span class="prob-status-badge unsolved">⬜ 미풀이</span>';

        return `
        <div class="prob-row-item" style="border-left: 3px solid ${
          p.status === "solved"
            ? "#22c55e"
            : p.status === "wrong"
            ? "#ef4444"
            : p.status === "partial"
            ? "#f59e0b"
            : "#cbd5e1"
        };">
          <div style="display: flex; align-items: center; gap: 8px; flex: 1; overflow: hidden;">
            <input type="checkbox" class="prob-homework-checkbox" data-pid="${p.pid}" data-title="${p.title}" data-url="${p.url}" ${
          isChecked ? "checked" : ""
        } style="cursor: pointer; width: 16px; height: 16px; flex-shrink: 0;" />
            <span style="font-weight: 600; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.83rem;" title="${p.title}">${p.title}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
            ${statusBadge}
            <a href="${p.url}" target="_blank" rel="noopener" style="text-decoration: none; color: #94a3b8; font-size: 0.85rem;" title="문제 링크 열기">🔗</a>
          </div>
        </div>
      `;
      })
      .join("");

    probListEl.querySelectorAll(".prob-homework-checkbox").forEach((cb) => {
      cb.addEventListener("change", (e) => {
        const pid = e.target.dataset.pid;
        const title = e.target.dataset.title;
        const url = e.target.dataset.url;
        if (e.target.checked) {
          if (window.addProblemToBasket) window.addProblemToBasket({ pid, title, url });
        } else {
          if (window.removeProblemFromBasket) window.removeProblemFromBasket(pid);
        }
      });
    });
  }

  // Select All button event
  if (btnSelectAll) {
    btnSelectAll.addEventListener("click", () => {
      if (!selectedGroup || !selectedGroup.problems) return;
      const checkboxes = probListEl.querySelectorAll(".prob-homework-checkbox");
      const allChecked = Array.from(checkboxes).every(cb => cb.checked);
      
      checkboxes.forEach(cb => {
        cb.checked = !allChecked;
        const pid = cb.dataset.pid;
        const title = cb.dataset.title;
        const url = cb.dataset.url;
        if (!allChecked) {
          if (window.addProblemToBasket) window.addProblemToBasket({ pid, title, url });
        } else {
          if (window.removeProblemFromBasket) window.removeProblemFromBasket(pid);
        }
      });
    });
  }

  // Sync checkboxes when basket updates externally
  window.refreshDrilldownCheckboxes = function () {
    if (!selectedGroup) return;
    probListEl.querySelectorAll(".prob-homework-checkbox").forEach(cb => {
      const pid = cb.dataset.pid;
      cb.checked = window.isProblemInBasket ? window.isProblemInBasket(pid) : false;
    });
  };

  // Initial select first chapter, keep sub-chapter unselected
  if (drillData.length > 0) {
    selectedChapter = drillData[0];
    selectedGroup = null;
  }

  renderMainChapters();
  renderSubChapters();
  renderProblems();
})();
