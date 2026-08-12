/**
 * crawler_modal.js
 * 문제 수집 크롤러 모달 제어 및 실시간 상태 폴링 모듈
 * (index_view.js Line 272~600 분리본)
 *
 * 의존성:
 *   - window.APP_CONFIG (index.html 인라인 설정)
 *   - showToast() (script.js에서 제공)
 *   - refreshStreak() (streak.js에서 제공)
 */

// ─────────────────────────────────────────────────────────────────
//  🔄 문제 수집 & 관리 모달 (Crawler Modal)
// ─────────────────────────────────────────────────────────────────
(function initCrawlerModal() {
  const modal       = document.getElementById("crawler-modal");
  const backdrop    = document.getElementById("crawler-modal-backdrop");
  const openBtn     = document.getElementById("btn-open-crawler-modal");
  const closeBtn    = document.getElementById("cm-close-btn");
  const footerClose = document.getElementById("cm-footer-close-btn");
  const startBtn    = document.getElementById("cm-start-btn");
  const cancelBtn   = document.getElementById("cm-cancel-btn");
  const chapterSel  = document.getElementById("cm-chapter-select");
  const progressFill = document.getElementById("cm-progress-fill");
  const progressText = document.getElementById("cm-progress-text");
  const consoleEl   = document.getElementById("cm-console");
  const lastCrawledEl = document.getElementById("cm-last-crawled");
  const statsBadgeEl  = document.getElementById("cm-stats-badge");
  const headerBadge   = document.getElementById("charts-last-crawled-badge");

  if (!modal) return; // 비관리자 페이지에는 모달이 없을 수 있음

  const CHAPTER_LISTS = {
    prog1: [
      { val: "all", label: "전체 8개 대단원 (추천)" },
      { val: "1", label: "1. 기초문법1" }, { val: "2", label: "2. 기초문법2" },
      { val: "3", label: "3. 알고리즘 초급" }, { val: "4", label: "4. 알고리즘 중급1" },
      { val: "5", label: "5. 알고리즘 중급2" }, { val: "6", label: "6. 알고리즘 중급3" },
      { val: "7", label: "7. 알고리즘 고급1" }, { val: "8", label: "8. 알고리즘 고급2" },
    ],
    prog2: [
      { val: "all", label: "전체 10개 대단원 (추천)" },
      { val: "1", label: "1. 알고리즘 기초" }, { val: "2", label: "2. 자료구조 브론즈1" },
      { val: "3", label: "3. 알고리즘 브론즈1" }, { val: "4", label: "4. 자료구조 브론즈2" },
      { val: "5", label: "5. 알고리즘 브론즈2" }, { val: "6", label: "6. 자료구조 실버" },
      { val: "7", label: "7. 알고리즘 실버1" }, { val: "8", label: "8. 알고리즘 실버2" },
      { val: "9", label: "9. 알고리즘 골드1" }, { val: "10", label: "10. 알고리즘 골드2" },
    ],
  };

  let statusTimer = null;
  let isCrawling  = false;

  function populateCmChapterSelect(currKey) {
    if (!chapterSel) return;
    const savedVal = chapterSel.value || "all";
    chapterSel.innerHTML = "";
    (CHAPTER_LISTS[currKey] || CHAPTER_LISTS.prog1).forEach(ch => {
      const opt = document.createElement("option");
      opt.value = ch.val;
      opt.textContent = ch.label;
      chapterSel.appendChild(opt);
    });
    if (Array.from(chapterSel.options).some(o => o.value === savedVal)) {
      chapterSel.value = savedVal;
    }
  }

  function getSelectedCurr() {
    const r = document.querySelector("input[name='cm-curr']:checked");
    return r ? r.value : (window.APP_CONFIG?.currentCurr || "prog1");
  }

  function applyLastCrawledBadge(lastCrawled, stats) {
    const statStr = stats && stats.total_problems ? ` · ${stats.total_problems}개 문제` : "";
    if (lastCrawledEl) {
      lastCrawledEl.textContent = lastCrawled ? `${lastCrawled}${statStr}` : "기록 없음";
    }
    if (headerBadge) {
      if (lastCrawled) {
        headerBadge.textContent = `🕒 ${lastCrawled}${statStr}`;
        headerBadge.style.display = "";
      } else {
        headerBadge.style.display = "none";
      }
    }
    if (statsBadgeEl) {
      if (stats && stats.total_chapters) {
        statsBadgeEl.textContent = `${stats.total_chapters}개 단원 · ${stats.total_subs || 0}개 소단원`;
        statsBadgeEl.style.display = "";
      } else {
        statsBadgeEl.style.display = "none";
      }
    }
  }

  function appendConsoleLog(msg, cls = "") {
    if (!consoleEl) return;
    const line = document.createElement("div");
    line.className = "cm-console-line" + (cls ? ` ${cls}` : "");
    line.textContent = msg;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }

  function setProgress(idx, total, msg) {
    const pct = total > 0 ? Math.round((idx / total) * 100) : 0;
    if (progressFill) progressFill.style.width = `${pct}%`;
    if (progressText) progressText.textContent = `${pct}% (${idx}/${total})`;
  }

  function fetchAndApplyLastCrawled() {
    const currKey = getSelectedCurr();
    fetch(`/api/crawl_status?curr=${currKey}`)
      .then(r => r.json())
      .then(st => {
        applyLastCrawledBadge(st.last_crawled || "", st.last_crawled_stats || {});
      })
      .catch(() => {
        if (lastCrawledEl) lastCrawledEl.textContent = "조회 실패";
      });
  }

  function resetConsole() {
    if (!consoleEl) return;
    consoleEl.innerHTML = '<div class="cm-console-line cm-muted">수집 시작 버튼을 누르면 여기에 실시간 로그가 표시됩니다.</div>';
    if (progressFill) progressFill.style.width = "0%";
    if (progressText) progressText.textContent = "대기 중";
  }

  function syncRadioLabels() {
    document.querySelectorAll(".cm-radio-item").forEach(lbl => lbl.classList.remove("active"));
    const checked = document.querySelector("input[name='cm-curr']:checked");
    if (checked) checked.closest(".cm-radio-item")?.classList.add("active");
  }

  function openModal() {
    const currKey = getSelectedCurr();
    const r = document.querySelector(`input[name='cm-curr'][value='${currKey}']`);
    if (r) r.checked = true;
    syncRadioLabels();
    populateCmChapterSelect(currKey);
    fetchAndApplyLastCrawled();
    resetConsole();

    try {
      const savedUser = localStorage.getItem("cm_saved_username") || window.APP_CONFIG?.viewUsername || window.APP_CONFIG?.userUsername || "";
      const usernameElem = document.getElementById("cm-username");
      if (usernameElem && !usernameElem.value && savedUser) {
        usernameElem.value = savedUser;
      }
    } catch(e) {}

    modal.style.display = "flex";
    backdrop.style.display = "block";
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    if (isCrawling) return;
    modal.style.display = "none";
    backdrop.style.display = "none";
    document.body.style.overflow = "";
  }

  function startCrawl() {
    if (isCrawling) return;
    isCrawling = true;
    const currKey = getSelectedCurr();
    const chapter = chapterSel ? chapterSel.value : "all";
    const currLabel = currKey === "prog2" ? "프로그래밍 II (심화)" : "프로그래밍 I";

    startBtn.style.display = "none";
    cancelBtn.style.display = "";
    if (footerClose) footerClose.disabled = true;
    if (closeBtn) closeBtn.disabled = true;

    resetConsole();
    appendConsoleLog(`🚀 [${currLabel}] 수집 시작... (범위: ${chapter})`, "cm-info");

    const showBrowserElem = document.getElementById("cm-show-browser");
    const showBrowser = showBrowserElem ? showBrowserElem.checked : false;
    const timeoutElem = document.getElementById("cm-timeout-select");
    const timeoutSec = timeoutElem ? timeoutElem.value : "60";
    const usernameElem = document.getElementById("cm-username");
    const passwordElem = document.getElementById("cm-password");
    const username = usernameElem ? usernameElem.value.trim() : "";
    const password = passwordElem ? passwordElem.value.trim() : "";

    if (username) {
      try { localStorage.setItem("cm_saved_username", username); } catch(e) {}
    }

    const params = new URLSearchParams();
    if (chapter) params.append("chapter", chapter);
    if (currKey) params.append("curr", currKey);
    if (showBrowser) params.append("show_browser", "true");
    if (timeoutSec) params.append("timeout_sec", timeoutSec);
    if (username) params.append("username", username);
    if (password) params.append("password", password);

    let lastLogMsg = "";
    statusTimer = setInterval(() => {
      fetch(`/api/crawl_status?curr=${currKey}`)
        .then(r => r.json())
        .then(st => {
          if (st && st.running && st.log_msg && st.log_msg !== lastLogMsg) {
            lastLogMsg = st.log_msg;
            appendConsoleLog(`🌐 ${st.log_msg}`);
            setProgress(st.current_index || 0, st.total_chapters || 0, st.log_msg);
          }
        })
        .catch(() => {});
    }, 850);

    fetch(`/update_problems?${params.toString()}`, { method: "POST" })
      .then(async r => {
        const text = await r.text();
        let data = {};
        try { data = JSON.parse(text); } catch(e) {
          throw new Error(`[HTTP ${r.status}] ${r.statusText || "서버 오류"}: ${text.substring(0, 120)}`);
        }
        if (!r.ok || data.ok === false) {
          throw new Error(data.error || data.message || `HTTP ${r.status} ${r.statusText}`);
        }
        return data;
      })
      .then(data => {
        clearInterval(statusTimer);
        statusTimer = null;
        if (data.status === "success" || data.ok) {
          const scrapedCount = (typeof data.scraped_count === "number") ? data.scraped_count : -1;
          if (scrapedCount === 0) {
            setProgress(1, 1, "경고");
            appendConsoleLog(`⚠️ ${currLabel} 수집 건수 0개 (페이지 접속 지연 또는 쿠키 세션 만료)`, "cm-error");
            appendConsoleLog(`💡 쿠키 세션이 만료되었거나 네트워크 연결을 확인해 주세요.`, "cm-error");
            if (typeof showToast === "function") showToast(`⚠️ ${currLabel} 수집 실패: 수집된 문제가 없습니다. 쿠키/네트워크를 확인해 주세요.`, 4000);
          } else {
            const countLabel = scrapedCount > 0 ? ` (총 ${scrapedCount}개 문제 수집)` : "";
            setProgress(1, 1, "완료");
            appendConsoleLog(`✅ ${currLabel} 수집 완료!${countLabel} (${data.last_updated || ""})`, "cm-success");
            fetchAndApplyLastCrawled();
            if (typeof showToast === "function") showToast(`✨ ${currLabel} 학습 데이터가 성공적으로 갱신되었습니다!`);
            if (typeof refreshStreak === "function") refreshStreak(typeof streakCurrentDays !== "undefined" ? streakCurrentDays : 7);
            setTimeout(() => { location.reload(); }, 2000);
          }
        } else {
          appendConsoleLog(`❌ 오류: ${data.error || data.message || "알 수 없는 오류"}`, "cm-error");
          if (typeof showToast === "function") showToast(data.error || "데이터 갱신 중 오류가 발생했습니다.", 3500);
        }
      })
      .catch(err => {
        clearInterval(statusTimer);
        statusTimer = null;
        appendConsoleLog(`❌ 오류 발생: ${err.message || err}`, "cm-error");
        if (typeof showToast === "function") showToast(err.message || "서버와 통신 중 오류가 발생했습니다.", 3500);
      })
      .finally(() => {
        isCrawling = false;
        startBtn.style.display = "";
        cancelBtn.style.display = "none";
        if (footerClose) footerClose.disabled = false;
        if (closeBtn) closeBtn.disabled = false;
      });
  }

  // 이벤트 연결
  if (openBtn) openBtn.addEventListener("click", openModal);
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (footerClose) footerClose.addEventListener("click", closeModal);
  if (backdrop) backdrop.addEventListener("click", closeModal);
  if (startBtn) startBtn.addEventListener("click", startCrawl);
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

  document.querySelectorAll("input[name='cm-curr']").forEach(r => {
    r.addEventListener("change", () => {
      syncRadioLabels();
      populateCmChapterSelect(getSelectedCurr());
    });
  });

  fetchAndApplyLastCrawled();
})();

// 하위 호환 shim: 기존 updateProblems() 직접 호출 코드 대응
function updateProblems() {
  const openBtn = document.getElementById("btn-open-crawler-modal");
  if (openBtn) { openBtn.click(); }
}

// ─────────────────────────────────────────────────────────────────
//  📊 차트 섹션 접기/펼치기 토글
// ─────────────────────────────────────────────────────────────────
(function initChartsToggle() {
  const chartsSection = document.getElementById("charts-section");
  const chartsToggleBtn = document.getElementById("charts-toggle-btn");
  const chartsContainer = document.getElementById("charts-container");

  window.setChartsCollapsed = function(collapsed) {
    if (!chartsSection || !chartsToggleBtn || !chartsContainer) return;
    const isCollapsed = Boolean(collapsed);
    chartsSection.classList.toggle("is-collapsed", isCollapsed);
    chartsContainer.style.display = isCollapsed ? "none" : "";
    chartsToggleBtn.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
    chartsToggleBtn.textContent = isCollapsed ? "단원별 펼치기" : "접기";
    try { localStorage.setItem("charts_section_collapsed", isCollapsed ? "1" : "0"); } catch (e) {}
  };

  if (chartsToggleBtn) {
    let initialCollapsed = false;
    try { initialCollapsed = localStorage.getItem("charts_section_collapsed") === "1"; } catch (e) {}
    window.setChartsCollapsed(initialCollapsed);
    chartsToggleBtn.addEventListener("click", () => {
      const currentState = chartsSection.classList.contains("is-collapsed");
      window.setChartsCollapsed(!currentState);
    });
  }
})();
