/**
 * drilldown_filter.js
 * 대시보드 하단 3열 계층형 드릴다운 패널 및 드래그 다중 선택 엔진
 * (index_view.js Line 727~1301 분리본)
 *
 * 의존성:
 *   - window.APP_CONFIG.drilldownData
 *   - window.addProblemToBasket / removeProblemFromBasket / isProblemInBasket (quick_basket.js)
 *   - showToast() (script.js)
 *
 * 전역 노출 함수:
 *   window.navigateToProblemChapter(pid, groupId) - 단원 목차 1클릭 이동
 *   window.refreshDrilldownCheckboxes()           - 장바구니 상태 동기화
 */
(function initDrilldownPanel() {
  const drillData = (window.APP_CONFIG && window.APP_CONFIG.drilldownData) || [];

  const mainListEl = document.getElementById("main-chapters-list");
  const subListEl  = document.getElementById("sub-chapters-list");
  const probListEl = document.getElementById("problems-list");
  const mainCountEl = document.getElementById("main-chapter-count");
  const subCountEl  = document.getElementById("sub-chapter-count");
  const btnSelectAll = document.getElementById("btn-select-all-problems");

  if (!mainListEl || !subListEl || !probListEl) return;

  let selectedChapter = null;
  let selectedGroup   = null;

  // ── 1. 대단원 렌더링
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
        <div class="drill-item ${isSel ? "active" : ""}" data-idx="${idx}">
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
        const validG = (selectedChapter && selectedChapter.groups)
          ? selectedChapter.groups.filter(g => !String(g.title || "").includes(":::"))
          : [];
        selectedGroup = validG.length > 0 ? validG[0] : null;
        renderMainChapters();
        renderSubChapters();
        renderProblems();
      });
    });
  }

  let currentSubFilter = "all";

  function isHomeworkGroup(g) {
    if (!g) return false;
    const title = String(g.title || g.group_id || "").trim();
    if (title.includes(":::")) return false;
    if (/^SSTRLv/i.test(title)) return true;
    if (/^STRLv/i.test(title)) return false;
    if (/^S/i.test(title)) return true;
    if (title.includes("숙제") || title.includes("기출")) return true;
    return false;
  }

  document.querySelectorAll(".sub-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sub-filter-btn").forEach((b) => {
        b.style.background = "#ffffff"; b.style.color = "#475569"; b.classList.remove("active");
      });
      btn.style.background = "#3b82f6"; btn.style.color = "#ffffff"; btn.classList.add("active");
      currentSubFilter = btn.dataset.subFilter || "all";
      renderSubChapters();
    });
  });

  // ── 2. 소단원 렌더링
  function renderSubChapters() {
    if (!selectedChapter) {
      if (subCountEl) subCountEl.textContent = "0개";
      subListEl.innerHTML = `<div class="col-placeholder">👈 좌측 대단원을 선택해주세요.</div>`;
      return;
    }

    const allGroups = selectedChapter.groups || [];
    const validGroups = allGroups.filter((g) => {
      const title = String(g.title || g.group_id || "").trim();
      return !title.includes("::: me") && !title.includes(":::");
    });
    const filteredGroups = validGroups.filter((g) => {
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

    subListEl.innerHTML = filteredGroups.map((g) => {
      const tone = g.percent >= 80 ? "high" : g.percent >= 40 ? "mid" : "low";
      const isSel = selectedGroup && selectedGroup.group_id === g.group_id;
      const isHw = isHomeworkGroup(g);
      const catBadge = isHw
        ? `<span style="font-size: 0.68rem; padding: 1px 5px; border-radius: 4px; background: #fef3c7; color: #b45309; font-weight: 700; flex-shrink: 0;">🛒 숙제</span>`
        : `<span style="font-size: 0.68rem; padding: 1px 5px; border-radius: 4px; background: #e0f2fe; color: #0369a1; font-weight: 700; flex-shrink: 0;">📖 진도</span>`;
      const unsolvedCount = Math.max(0, (g.total || 0) - (g.solved || 0));
      const unsolvedBadge = unsolvedCount > 0
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
    }).join("");

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
    const el = document.getElementById("prob-header-title");
    if (el) el.textContent = "📝 3. 문제 목록 (소단원을 선택해 주세요)";
    probListEl.innerHTML = `<div class="col-placeholder">👈 2열에서 소단원을 선택해 주세요.</div>`;
  }

  let currentProbFilter = "all";

  document.querySelectorAll(".prob-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".prob-filter-btn").forEach((b) => {
        b.style.background = "#ffffff"; b.style.color = "#475569"; b.classList.remove("active");
      });
      btn.style.background = "#3b82f6"; btn.style.color = "#ffffff"; btn.classList.add("active");
      currentProbFilter = btn.dataset.probFilter || "all";
      renderProblems();
    });
  });

  let showJsonView = false;

  // ── 3. 문제 목록 렌더링
  function renderProblems() {
    if (!selectedGroup) { renderProblemsPlaceholder(); return; }

    const el = document.getElementById("prob-header-title");
    if (el) el.textContent = `📝 3. 문제 목록 (${selectedGroup.title || selectedGroup.group_id} · 총 ${selectedGroup.total || 0}문제)`;

    const allProblems = selectedGroup.problems || [];
    const filteredProblems = allProblems.filter((p) => {
      if (currentProbFilter === "unsolved") return p.status === "unsolved";
      if (currentProbFilter === "solved")   return p.status === "solved";
      if (currentProbFilter === "wrong")    return p.status === "wrong" || p.status === "partial";
      return true;
    });

    probListEl.classList.remove("fade-in-list");
    void probListEl.offsetWidth;
    probListEl.classList.add("fade-in-list");

    if (filteredProblems.length === 0) {
      probListEl.innerHTML = `<div class="col-placeholder">선택한 필터 조건에 해당하는 문제가 없습니다.</div>`;
      return;
    }

    probListEl.innerHTML = filteredProblems.map((p) => {
      const isChecked = window.isProblemInBasket ? window.isProblemInBasket(p.pid) : false;
      const statusBadge =
        p.status === "solved"   ? '<span class="prob-status-badge solved">✅ 정답</span>' :
        p.status === "partial"  ? '<span class="prob-status-badge partial">⚠️ 부분</span>' :
        p.status === "wrong"    ? '<span class="prob-status-badge wrong">❌ 오답</span>' :
                                  '<span class="prob-status-badge unsolved">⬜ 미풀이</span>';

      const isUnmapped = (p.raw_status === null || p.raw_status === undefined);
      const jsonTagHtml = `
        <div class="prob-json-tag" style="margin-top: 3px; font-family: monospace; font-size: 0.68rem; color: ${isUnmapped ? "#991b1b" : "#6b21a8"}; background: ${isUnmapped ? "#fef2f2" : "#faf5ff"}; border: 1px solid ${isUnmapped ? "#fecaca" : "#e9d5ff"}; border-radius: 4px; padding: 1px 6px; display: ${showJsonView ? "block" : "none"}; width: fit-content; word-break: break-all;">
          🔍 JSON: {"pid": "${p.pid}", "status": "${p.status}", "raw_status": ${p.raw_status !== undefined && p.raw_status !== null ? p.raw_status : "null"}} ${isUnmapped ? "⚠️ (미매핑 감지)" : ""}
        </div>`;

      const escAttr = (str) => String(str || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#039;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      const currentGroupTitle = (selectedGroup && selectedGroup.title) || (p && p.group_title) || "";
      const currentChapterCode = (selectedGroup && (selectedGroup.chapter_code || selectedGroup.chapter_id)) || (p && (p.chapter_code || p.chapter_id)) || (selectedChapter && (selectedChapter.chapter_code || selectedChapter.chapter_id)) || "";

      const borderColor = p.status === "solved" ? "#22c55e" : p.status === "wrong" ? "#ef4444" : p.status === "partial" ? "#f59e0b" : "#cbd5e1";
      return `
        <div class="prob-row-item ${isChecked ? "checked-item" : ""}" style="border-left: 3px solid ${borderColor}; flex-wrap: wrap;">
          <div style="display: flex; flex-direction: column; flex: 1; overflow: hidden; pointer-events: none;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" class="prob-homework-checkbox" data-pid="${p.pid}" data-title="${escAttr(p.title)}" data-url="${escAttr(p.url)}" data-group-title="${escAttr(currentGroupTitle)}" data-chapter-code="${escAttr(currentChapterCode)}" ${isChecked ? "checked" : ""} style="cursor: pointer; width: 16px; height: 16px; flex-shrink: 0; pointer-events: auto;" />
              <span style="font-weight: 600; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.83rem;" title="${escAttr(p.title)}">${p.title}</span>
            </div>
            ${jsonTagHtml}
          </div>
          <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
            ${statusBadge}
            <a href="${p.url}" target="_blank" rel="noopener" style="text-decoration: none; color: #94a3b8; font-size: 0.85rem;" title="문제 링크 열기">🔗</a>
          </div>
        </div>
      `;
    }).join("");

    attachProblemSelectionEvents();
  }

  // ── 체크박스 동기화 헬퍼
  function syncProblemCheckbox(cb, isChecked) {
    if (!cb) return;
    cb.checked = isChecked;
    const row = cb.closest(".prob-row-item");
    if (row) row.classList.toggle("checked-item", isChecked);
    const pid = cb.dataset.pid;
    const title = cb.dataset.title;
    const url = cb.dataset.url;
    const chapter_code = cb.dataset.chapterCode || (selectedGroup && (selectedGroup.chapter_code || selectedGroup.chapter_id)) || (selectedChapter && (selectedChapter.chapter_code || selectedChapter.chapter_id)) || "";
    const group_title  = cb.dataset.groupTitle || (selectedGroup && selectedGroup.title) || (selectedChapter && selectedChapter.title) || "";
    if (isChecked) {
      if (window.addProblemToBasket) window.addProblemToBasket({ pid, legacy_code: pid, title, url, chapter_code, group_title });
    } else {
      if (window.removeProblemFromBasket) window.removeProblemFromBasket(pid);
    }
  }

  let lastCheckedIndex = null;

  // ── Row 클릭 & Shift 다중 선택
  function attachProblemSelectionEvents() {
    lastCheckedIndex = null;
    const rows = probListEl.querySelectorAll(".prob-row-item");
    rows.forEach((row, idx) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest("a")) return;
        const cb = row.querySelector(".prob-homework-checkbox");
        if (!cb) return;
        const isDirectCb = e.target.classList.contains("prob-homework-checkbox");

        if (e.shiftKey && lastCheckedIndex !== null && lastCheckedIndex !== idx) {
          if (!isDirectCb) e.preventDefault();
          const allRows = Array.from(probListEl.querySelectorAll(".prob-row-item"));
          const targetState = isDirectCb ? cb.checked : !cb.checked;
          const start = Math.min(lastCheckedIndex, idx);
          const end   = Math.max(lastCheckedIndex, idx);
          for (let i = start; i <= end; i++) {
            const itemCb = allRows[i]?.querySelector(".prob-homework-checkbox");
            if (itemCb) syncProblemCheckbox(itemCb, targetState);
          }
          lastCheckedIndex = idx;
          return;
        }

        if (!isDirectCb) { e.preventDefault(); syncProblemCheckbox(cb, !cb.checked); }
        else { syncProblemCheckbox(cb, cb.checked); }
        lastCheckedIndex = idx;
      });
    });
  }

  // ── 🖱️ 마우스 드래그 다중 선택 엔진
  (function initDragToSelectEngine() {
    let isDragging = false;
    let dragBox = null;
    let startX = 0, startY = 0;

    probListEl.style.position = "relative";

    probListEl.addEventListener("mousedown", (e) => {
      if (e.target.closest("a") || e.target.classList.contains("prob-homework-checkbox")) return;
      const rows = probListEl.querySelectorAll(".prob-row-item");
      if (!rows.length) return;

      const rect = probListEl.getBoundingClientRect();
      startX = e.clientX - rect.left + probListEl.scrollLeft;
      startY = e.clientY - rect.top  + probListEl.scrollTop;

      dragBox = document.createElement("div");
      dragBox.className = "drag-select-box";
      dragBox.style.cssText = `left:${startX}px; top:${startY}px; width:0px; height:0px;`;
      probListEl.appendChild(dragBox);
      isDragging = false;

      function onMouseMove(evt) {
        const cRect = probListEl.getBoundingClientRect();
        const curX = evt.clientX - cRect.left + probListEl.scrollLeft;
        const curY = evt.clientY - cRect.top  + probListEl.scrollTop;
        const diffX = curX - startX, diffY = curY - startY;

        if (!isDragging && (Math.abs(diffX) > 5 || Math.abs(diffY) > 5)) {
          isDragging = true;
          probListEl.classList.add("is-dragging");
        }
        if (!isDragging || !dragBox) return;

        const boxLeft = diffX < 0 ? curX : startX;
        const boxTop  = diffY < 0 ? curY : startY;
        dragBox.style.left   = `${boxLeft}px`;
        dragBox.style.top    = `${boxTop}px`;
        dragBox.style.width  = `${Math.abs(diffX)}px`;
        dragBox.style.height = `${Math.abs(diffY)}px`;

        const bRect = dragBox.getBoundingClientRect();
        rows.forEach(r => {
          const rRect = r.getBoundingClientRect();
          const intersects = !(rRect.right < bRect.left || rRect.left > bRect.right || rRect.bottom < bRect.top || rRect.top > bRect.bottom);
          r.classList.toggle("drag-selecting", intersects);
        });
      }

      function onMouseUp() {
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);

        if (dragBox && dragBox.parentNode) dragBox.parentNode.removeChild(dragBox);
        dragBox = null;
        probListEl.classList.remove("is-dragging");

        if (isDragging) {
          isDragging = false;
          const selectingRows = probListEl.querySelectorAll(".prob-row-item.drag-selecting");
          if (selectingRows.length > 0) {
            const firstCb = selectingRows[0].querySelector(".prob-homework-checkbox");
            const targetState = firstCb ? !firstCb.checked : true;
            selectingRows.forEach(r => {
              r.classList.remove("drag-selecting");
              const cb = r.querySelector(".prob-homework-checkbox");
              if (cb) syncProblemCheckbox(cb, targetState);
            });
          }
        }
      }

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    });
  })();

  // ── 배치 선택 칩 버튼
  const btnSelectUnsolved = document.getElementById("btn-select-unsolved-problems");
  const btnSelectWrong    = document.getElementById("btn-select-wrong-problems");
  const btnClearSelected  = document.getElementById("btn-clear-selected-problems");

  function setBatchSelection(predicateFn) {
    if (!selectedGroup || !selectedGroup.problems) return;
    const checkboxes = probListEl.querySelectorAll(".prob-homework-checkbox");
    const probMap = new Map((selectedGroup.problems || []).map(p => [p.pid, p]));
    checkboxes.forEach(cb => {
      const p = probMap.get(cb.dataset.pid);
      syncProblemCheckbox(cb, predicateFn(p));
    });
  }

  if (btnSelectAll)     btnSelectAll.addEventListener("click",     () => setBatchSelection(() => true));
  if (btnSelectUnsolved) btnSelectUnsolved.addEventListener("click", () => setBatchSelection(p => p && p.status === "unsolved"));
  if (btnSelectWrong)    btnSelectWrong.addEventListener("click",    () => setBatchSelection(p => p && (p.status === "wrong" || p.status === "partial")));
  if (btnClearSelected)  btnClearSelected.addEventListener("click",  () => setBatchSelection(() => false));

  // ── JSON 디버그 뷰 토글
  const btnToggleJsonView = document.getElementById("btn-toggle-json-view");
  if (btnToggleJsonView) {
    btnToggleJsonView.addEventListener("click", () => {
      showJsonView = !showJsonView;
      btnToggleJsonView.style.background = showJsonView ? "#6b21a8" : "#faf5ff";
      btnToggleJsonView.style.color      = showJsonView ? "#ffffff" : "#6b21a8";
      probListEl.querySelectorAll(".prob-json-tag").forEach(tag => {
        tag.style.display = showJsonView ? "block" : "none";
      });
    });
  }

  // ── 전역: 단원 목차 1클릭 이동
  window.navigateToProblemChapter = function(pid, groupId) {
    const data = (window.APP_CONFIG && window.APP_CONFIG.drilldownData) || [];
    if (!data.length) { if (typeof showToast === "function") showToast("⚠️ 단원 목차 데이터가 없습니다."); return; }

    let foundChapter = null, foundGroup = null;
    for (const ch of data) {
      for (const g of (ch.groups || [])) {
        if ((groupId && g.group_id === groupId) || (g.problems || []).some(p => p.pid === pid || p.legacy_code === pid)) {
          foundChapter = ch; foundGroup = g; break;
        }
      }
      if (foundChapter) break;
    }

    if (!foundChapter || !foundGroup) {
      if (typeof showToast === "function") showToast("ℹ️ 해당 문제의 단원 위치를 목차에서 찾을 수 없습니다.");
      else alert("해당 문제의 단원 위치를 목차에서 찾을 수 없습니다.");
      return;
    }

    selectedChapter = foundChapter;
    selectedGroup   = foundGroup;
    renderMainChapters();
    renderSubChapters();
    renderProblems();

    setTimeout(() => {
      const pListEl = document.getElementById("problems-list");
      if (!pListEl) return;
      const targetCheckbox = pListEl.querySelector(`.prob-homework-checkbox[data-pid="${pid}"]`);
      if (targetCheckbox) {
        const rowItem = targetCheckbox.closest(".prob-row-item");
        if (rowItem) {
          rowItem.style.transition = "background-color 0.5s ease";
          rowItem.style.backgroundColor = "#fef08a";
          rowItem.scrollIntoView({ behavior: "smooth", block: "center" });
          setTimeout(() => { rowItem.style.backgroundColor = ""; }, 2200);
        }
      }
      if (typeof showToast === "function") showToast(`🎯 '${foundGroup.title}' 단원으로 이동했습니다.`);
    }, 150);
  };

  // ── 전역: 장바구니 체크박스 상태 동기화
  window.refreshDrilldownCheckboxes = function() {
    if (!selectedGroup) return;
    probListEl.querySelectorAll(".prob-homework-checkbox").forEach(cb => {
      cb.checked = window.isProblemInBasket ? window.isProblemInBasket(cb.dataset.pid) : false;
    });
  };

  // ── 초기 렌더링 (첫 번째 대단원 자동 선택)
  if (drillData.length > 0) {
    selectedChapter = drillData[0];
    const validG = (selectedChapter && selectedChapter.groups)
      ? selectedChapter.groups.filter(g => !String(g.title || "").includes(":::"))
      : [];
    selectedGroup = validG.length > 0 ? validG[0] : null;
  }

  renderMainChapters();
  renderSubChapters();
  renderProblems();
})();
