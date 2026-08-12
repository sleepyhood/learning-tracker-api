/**
 * Main Index Page Module (index_view.js)
 */
const CFG_MAIN = window.APP_CONFIG || (typeof CFG_MAIN !== "undefined" ? CFG_MAIN : {});
const userUuid = CFG_MAIN.userUuid || CFG_MAIN.viewUsername || (window.APP_CONFIG && (window.APP_CONFIG.userUuid || window.APP_CONFIG.viewUsername)) || "";

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

  const log = data.log || data.homework;
  if (!data || !data.ok || !log || (!log.id && !log.ts && !log.created_at)) {
    host.innerHTML = `
      <article class="card empty-state" style="border-radius:16px; border:1px solid #e2e8f0; box-shadow:0 4px 16px rgba(0,0,0,0.04); padding:36px 20px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; min-height:260px; height:100%; gap:12px; box-sizing:border-box;">
        <div style="font-size: 2.5rem; line-height: 1; margin-bottom: 2px;">📝</div>
        <div class="empty-title" style="font-weight: 800; font-size: 1.1rem; color: #1e293b; margin: 0;">등록된 숙제 및 피드백 기록이 없습니다</div>
        <div class="empty-desc" style="font-size: 0.85rem; color: #64748b; max-width: 360px; line-height: 1.5; margin: 0;">알림장 모달에서 학생에게 신규 숙제를 출제하거나 수업 피드백을 남겨주세요.</div>
        <div class="empty-actions" style="margin-top: 8px;">
          <button class="btn btn-primary" id="refresh-homework" style="padding: 9px 20px; border-radius: 10px; font-weight: 700; font-size: 0.83rem; background: #6c5ce7; color: white; border: none; cursor: pointer; box-shadow: 0 4px 12px rgba(108, 92, 231, 0.25);">🔄 새로고침</button>
        </div>
      </article>
    `;
    document.getElementById("refresh-homework")?.addEventListener("click", () => location.reload());
    return;
  }

  const mode = log.mode || (log.problems && log.problems.length > 0 ? "homework" : "comment");
  const pct = (log.counts && log.counts.total) ? Math.round((log.counts.passed / log.counts.total) * 100) : 0;

  // 한글 날짜 파싱 헬퍼
  const formatIsoDate = (isoStr) => {
    if (!isoStr) return "-";
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      const days = ["일", "월", "화", "수", "목", "금", "토"];
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      const dayName = days[d.getDay()];
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      return `${y}.${m}.${day}(${dayName}) ${hh}:${mm}`;
    } catch (e) {
      return isoStr;
    }
  };

  let displayTitle = log.title || "수업 피드백 & 숙제";
  const profileNameEl = document.querySelector(".profile-name");
  const profileName = profileNameEl ? profileNameEl.textContent.trim() : "";
  const uname = data.student_name || CFG_MAIN.viewUsername || profileName || "osw1110";
  displayTitle = displayTitle.replace(/수강생\s*학생/g, `${uname} 학생`);
  displayTitle = displayTitle.replace(/수강생/g, uname);
  displayTitle = displayTitle.replace(/학생\s+학생/g, `${uname} 학생`);
  displayTitle = displayTitle.replace(/([0-9a-f-]{36})\s*학생/gi, `${uname} 학생`);
  displayTitle = displayTitle.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, uname);

  const problemLis = (log.problems || [])
    .map((p) => {
      const st = p.status || "pending";
      let badge = `<span style="font-size:0.75rem; color:#64748b; background:#f1f5f9; border:1px solid #e2e8f0; padding:2px 8px; border-radius:12px; font-weight:700;">⚪ 대기</span>`;
      if (st === "passed") {
        badge = `<span style="font-size:0.75rem; color:#059669; background:#ecfdf5; border:1px solid #a7f3d0; padding:2px 8px; border-radius:12px; font-weight:700;">🟢 100점</span>`;
      } else if (st === "partial") {
        badge = `<span style="font-size:0.75rem; color:#d97706; background:#fffbeb; border:1px solid #fde68a; padding:2px 8px; border-radius:12px; font-weight:700;">🟡 ${p.score || "50"}점</span>`;
      } else if (st === "wrong") {
        badge = `<span style="font-size:0.75rem; color:#dc2626; background:#fef2f2; border:1px solid #fecaca; padding:2px 8px; border-radius:12px; font-weight:700;">🔴 0점</span>`;
      }
      const code = p.legacy_code ? `<code style="font-size:0.75rem; background:#f1f5f9; color:#475569; padding:2px 6px; border-radius:6px; font-family:monospace; border:1px solid #e2e8f0;">${p.legacy_code}</code>` : "";
      const title = p.title || p.title_at_issue || "";
      return `<li style="display:flex; align-items:center; gap:8px; padding:6px 0; font-size:0.83rem; border-bottom:1px solid #f1f5f9;">
        ${badge} ${code} <span style="flex:1; min-width:140px; color:#334155; font-weight:500;">${title}</span>
      </li>`;
    })
    .join("");

  let badgeHTML = `<span class="badge" style="background:#6c5ce7; color:white; font-size:0.75rem; padding:4px 10px; border-radius:8px; font-weight:700;">📘 숙제 출제</span>`;
  if (mode === "review") {
    badgeHTML = `<span class="badge" style="background:#10b981; color:white; font-size:0.75rem; padding:4px 10px; border-radius:8px; font-weight:700;">🔄 복습 안내</span>`;
  } else if (mode === "comment") {
    badgeHTML = `<span class="badge" style="background:#3b82f6; color:white; font-size:0.75rem; padding:4px 10px; border-radius:8px; font-weight:700;">📝 수업 피드백</span>`;
  }

  let progressHTML = "";
  if (mode === "homework") {
    const passedCnt = (log.counts && log.counts.passed) || 0;
    const partialCnt = (log.counts && log.counts.partial) || 0;
    const wrongCnt = (log.counts && log.counts.wrong) || 0;
    const pendingCnt = (log.counts && log.counts.pending) || 0;
    progressHTML = `
      <div style="margin-top: 10px; background:#f8fafc; border:1px solid #e2e8f0; padding:12px 14px; border-radius:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; font-size:0.8rem; font-weight:700; color:#334155;">
          <span>숙제 달성도</span>
          <span style="color:#6c5ce7; font-size:0.9rem;">${pct}%</span>
        </div>
        <div class="progress-track" style="height:8px; background:#e2e8f0; border-radius:4px; overflow:hidden;">
          <div class="progress-fill" style="width:${pct}%; height:100%; background:linear-gradient(90deg, #6c5ce7, #a855f7); border-radius:4px; transition:width 0.3s ease;"></div>
        </div>
        <div style="display:flex; gap:12px; margin-top:8px; font-size:0.75rem; color:#64748b; font-weight:600; flex-wrap:wrap;">
          <span>🟢 정답 ${passedCnt}</span>
          <span>🟡 부분점수 ${partialCnt}</span>
          <span>🔴 오답 ${wrongCnt}</span>
          <span>⚪ 대기 ${pendingCnt}</span>
        </div>
      </div>`;
  } else if (mode === "review") {
    progressHTML = `
      <div style="font-size: 0.82rem; color: #047857; font-weight: 700; background: #ecfdf5; border:1px solid #a7f3d0; padding: 8px 14px; border-radius: 10px; margin-top: 10px;">
        🔄 오늘 복습 ${log.problems ? log.problems.length : 0}개 문항 안내 완료
      </div>`;
  }

  const escHtml = (str) => String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  let commentHTML = "";
  const isHomeworkMode = (mode === "homework" && log.problems && log.problems.length > 0);

  if (isHomeworkMode) {
    if (log.comment) {
      commentHTML = `
        <div style="margin-top: 12px;">
          <button class="btn-small btn-secondary" style="font-size:0.78rem; padding:5px 12px; border-radius:8px; font-weight:600; cursor:pointer; display:inline-flex; align-items:center; gap:4px; border:1px solid #cbd5e1; background:#ffffff; color:#334155;" onclick="const el = this.nextElementSibling; const isHidden = el.style.display === 'none'; el.style.display = isHidden ? 'block' : 'none'; this.innerHTML = isHidden ? '🔓 강사 피드백 닫기' : '🔒 강사 피드백 보기';">🔒 강사 피드백 보기</button>
          <div style="display: none; margin-top: 8px; padding: 14px; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 12px; font-size: 0.85rem; color: #3b0764; line-height: 1.5; white-space: pre-wrap;">${escHtml(log.comment)}</div>
        </div>`;
    }
  } else {
    // 피드백/복습 모드 (숙제 문제 목록이 없는 경우): 피드백 메시지를 바로 기본 자동 펼침으로 시원하게 노출
    if (log.comment) {
      commentHTML = `
        <div style="margin-top: 14px; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 14px; padding: 16px; box-shadow: 0 2px 8px rgba(108, 92, 231, 0.05);">
          <div style="font-weight: 800; font-size: 0.88rem; color: #5b21b6; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
            <span>💬 오늘의 수업 피드백</span>
          </div>
          <div style="font-size: 0.88rem; color: #3b0764; line-height: 1.6; white-space: pre-wrap;">${escHtml(log.comment)}</div>
        </div>`;
    } else if (log.message) {
      commentHTML = `
        <div style="margin-top: 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px;">
          <div style="font-weight: 800; font-size: 0.88rem; color: #334155; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
            <span>📢 카카오톡 알림장 전송 내용</span>
          </div>
          <div style="font-size: 0.85rem; color: #475569; line-height: 1.6; white-space: pre-wrap;">${escHtml(log.message)}</div>
        </div>`;
    } else {
      commentHTML = `
        <div style="margin-top: 14px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 14px; padding: 20px; text-align: center; color: #64748b; font-size: 0.85rem;">
          📝 수업 피드백 알림장이 학생/학부모님께 정상 전송되었습니다.
        </div>`;
    }
  }

  const safeMsg = (log.message || "").replace(/'/g, "\\'").replace(/"/g, "&quot;").replace(/\n/g, "\\n");

  host.innerHTML = `
<article class="card" data-log-id="${log.key || ""}" data-id="${log.id || ""}" style="border-radius:16px; border:1px solid #e2e8f0; box-shadow:0 4px 16px rgba(0,0,0,0.04); padding:20px;">
  <div class="card-head" style="display:flex; justify-content:space-between; align-items:center; padding-bottom:12px; border-bottom:1px solid #f1f5f9;">
    <div class="card-title" style="font-weight:800; font-size:1.05rem; color:#1e293b;">${displayTitle}</div>
    ${badgeHTML}
  </div>

  ${progressHTML}
  ${commentHTML}

  <div class="meta" style="margin-top: 12px; font-size: 0.78rem; color: #64748b; display:flex; align-items:center; gap:12px;">
    <span>배정: <strong style="color:#334155;">${formatIsoDate(log.created_at || log.ts)}</strong></span>
    ${log.due_at ? `<span>마감: <strong style="color:#334155;">${formatIsoDate(log.due_at)}</strong></span>` : ""}
  </div>

  ${mode === "homework" && log.problems && log.problems.length ? `<ul class="problems" style="margin-top:12px; padding-left:0; list-style:none;">${problemLis}</ul>` : ""}

  <div class="actions" style="margin-top: 16px; display: flex; gap: 8px; justify-content: flex-end; align-items: center; flex-wrap: wrap;">
    ${log.message ? `<button class="btn btn-secondary" style="font-size:0.8rem; padding:8px 14px; border-radius:10px; font-weight:700; background:#6c5ce7; color:white; border:none; cursor:pointer;" onclick="navigator.clipboard.writeText('${safeMsg}'); alert('📋 카카오톡 알림장 메시지가 클립보드에 복사되었습니다!');">📋 카톡 알림장 재복사</button>` : ""}
    <button class="btn btn-quiet" style="font-size:0.8rem; padding:8px 14px; border-radius:10px; font-weight:700; background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; cursor:pointer;" onclick="if(typeof openHomeworkHistoryModal==='function') openHomeworkHistoryModal('${userUuid}'); else alert('히스토리 모달 로딩 중');">📜 전체 히스토리</button>
  </div>
</article>
`;
})();

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

  // ── 헬퍼: 과정 선택에 따라 드롭다운 옵션 재구성
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

  // ── 헬퍼: 현재 선택된 과정 키 반환
  function getSelectedCurr() {
    const r = document.querySelector("input[name='cm-curr']:checked");
    return r ? r.value : (window.APP_CONFIG?.currentCurr || "prog1");
  }

  // ── 헬퍼: 마지막 수집 뱃지 텍스트 갱신
  function applyLastCrawledBadge(lastCrawled, stats) {
    const statStr = stats && stats.total_problems
      ? ` · ${stats.total_problems}개 문제`
      : "";
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

  // ── 헬퍼: 콘솔에 로그 라인 추가
  function appendConsoleLog(msg, cls = "") {
    if (!consoleEl) return;
    const line = document.createElement("div");
    line.className = "cm-console-line" + (cls ? ` ${cls}` : "");
    line.textContent = msg;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }

  // ── 헬퍼: 프로그레스 바 업데이트
  function setProgress(idx, total, msg) {
    const pct = total > 0 ? Math.round((idx / total) * 100) : 0;
    if (progressFill) progressFill.style.width = `${pct}%`;
    if (progressText) progressText.textContent = `${pct}% (${idx}/${total})`;
  }

  // ── 초기 마지막 수집 시각 로드 (모달 열기 전에도 뱃지에 표시)
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

  // ── 모달 열기
  function openModal() {
    const currKey = getSelectedCurr();
    // 현재 과정 탭을 라디오에 반영
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

  // ── 모달 닫기
  function closeModal() {
    if (isCrawling) return; // 수집 중에는 닫기 방지
    modal.style.display = "none";
    backdrop.style.display = "none";
    document.body.style.overflow = "";
  }

  // ── 콘솔 초기화
  function resetConsole() {
    if (!consoleEl) return;
    consoleEl.innerHTML = '<div class="cm-console-line cm-muted">수집 시작 버튼을 누르면 여기에 실시간 로그가 표시됩니다.</div>';
    if (progressFill) progressFill.style.width = "0%";
    if (progressText) progressText.textContent = "대기 중";
  }

  // ── 라디오 레이블 active 동기화
  function syncRadioLabels() {
    document.querySelectorAll(".cm-radio-item").forEach(lbl => lbl.classList.remove("active"));
    const checked = document.querySelector("input[name='cm-curr']:checked");
    if (checked) checked.closest(".cm-radio-item")?.classList.add("active");
  }

  // ── 수집 시작
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
      try { localStorage.setItem("cm_saved_username", username); } catch(e){}
    }

    const params = new URLSearchParams();
    if (chapter) params.append("chapter", chapter);
    if (currKey) params.append("curr", currKey);
    if (showBrowser) params.append("show_browser", "true");
    if (timeoutSec) params.append("timeout_sec", timeoutSec);
    if (username) params.append("username", username);
    if (password) params.append("password", password);

    // 0.85초 폴링으로 실시간 상태 표시
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
        try {
          data = JSON.parse(text);
        } catch(e) {
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
            // 수집 건수가 0개인 경우 — 실패로 간주
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
            // 완료 후 2초 뒤 페이지 새로고침
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

  // ── 이벤트 연결
  if (openBtn) openBtn.addEventListener("click", openModal);
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (footerClose) footerClose.addEventListener("click", closeModal);
  if (backdrop) backdrop.addEventListener("click", closeModal);
  if (startBtn) startBtn.addEventListener("click", startCrawl);
  // ESC 키 닫기
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

  // 과정 라디오 변경 시 드롭다운 재구성
  document.querySelectorAll("input[name='cm-curr']").forEach(r => {
    r.addEventListener("change", () => {
      syncRadioLabels();
      populateCmChapterSelect(getSelectedCurr());
    });
  });

  // 페이지 로드 시 헤더 뱃지에 마지막 수집 시각 조용히 표시
  fetchAndApplyLastCrawled();
})();

// 하위 호환: 기존에 updateProblems()를 직접 호출하는 코드가 있을 경우를 위해 shim 유지
function updateProblems() {
  const openBtn = document.getElementById("btn-open-crawler-modal");
  if (openBtn) { openBtn.click(); }
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
  function toggleBasketDrawer(forceOpen = null) {
    const bBody = document.getElementById("basket-body");
    const bFooter = document.querySelector("#quick-homework-basket .basket-footer");
    const tBtn = document.getElementById("basket-toggle-btn");
    if (!bBody || !tBtn) return;

    const isCurrentlyHidden = bBody.style.display === "none";
    const shouldOpen = forceOpen !== null ? Boolean(forceOpen) : isCurrentlyHidden;

    bBody.style.display = shouldOpen ? "block" : "none";
    if (bFooter) {
      bFooter.style.display = shouldOpen ? "flex" : "none";
    }
    tBtn.textContent = shouldOpen ? "▼" : "▲";
    tBtn.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    tBtn.title = shouldOpen ? "장바구니 접기" : "장바구니 펼치기";
  }

  const toggleBtn = document.getElementById("basket-toggle-btn");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleBasketDrawer();
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

  window.getBasketItems = function() {
    return basketItems;
  };

  window.clearQuickBasket = function() {
    basketItems = [];
    updateBasketUI();
    if (typeof window.refreshDrilldownCheckboxes === "function") window.refreshDrilldownCheckboxes();
  };

  if (submitBtn) {
    submitBtn.addEventListener("click", () => {
      const targetUuid = (window.APP_CONFIG && window.APP_CONFIG.userUuid) || "";
      const targetUsername = (window.APP_CONFIG && (window.APP_CONFIG.viewUsername || window.APP_CONFIG.userUuid)) || "";
      if (typeof window.openFeedbackModal === "function") {
        window.openFeedbackModal(targetUsername, targetUsername, targetUuid);
      } else {
        if (typeof showToast === "function") showToast("⚠️ 피드백 모달을 불러올 수 없습니다.", true);
      }
    });
  }

  window.addProblemToBasket = function (probObj) {
    if (!probObj || (!probObj.pid && !probObj.legacy_code)) return;
    const pid = probObj.pid || probObj.legacy_code;
    if (!basketItems.some((item) => (item.pid || item.legacy_code) === pid)) {
      const itemToPush = {
        pid: pid,
        legacy_code: probObj.legacy_code || pid,
        title: probObj.title || "",
        url: probObj.url || "",
        chapter_code: probObj.chapter_code || "",
        group_title: probObj.group_title || ""
      };
      basketItems.push(itemToPush);
      updateBasketUI();
      toggleBasketDrawer(true);
    }
  };

  window.removeProblemFromBasket = function (pid) {
    basketItems = basketItems.filter((item) => item.pid !== pid && item.legacy_code !== pid);
    updateBasketUI();
  };

  window.isProblemInBasket = function (pid) {
    return basketItems.some((item) => item.pid === pid || item.legacy_code === pid);
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

  let currentSubFilter = "all"; // "all", "regular", "homework"

  function isHomeworkGroup(g) {
    if (!g) return false;
    const title = String(g.title || g.group_id || "").trim();

    // 구분선(:::) 항목은 헤더이므로 숙제/진도가 아님
    if (title.includes(":::")) return false;

    // SSTRLv 접두사 -> 숙제 (true)
    if (/^SSTRLv/i.test(title)) return true;

    // STRLv 접두사 -> 진도 (false)
    if (/^STRLv/i.test(title)) return false;

    // 일반 S 접두사 (SLv, SS, S1, S2 등) -> 숙제 (true)
    if (/^S/i.test(title)) return true;

    // 제목에 "숙제" 또는 "기출" 명시 시 -> 숙제 (true)
    if (title.includes("숙제") || title.includes("기출")) return true;

    return false;
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
    // ::: 구분선 헤더는 실제 선택 가능한 소단원이 아니므로 제거
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

  let showJsonView = false;

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

        const isUnmapped = (p.raw_status === null || p.raw_status === undefined);
        const jsonTagHtml = `
        <div class="prob-json-tag" style="margin-top: 3px; font-family: monospace; font-size: 0.68rem; color: ${isUnmapped ? '#991b1b' : '#6b21a8'}; background: ${isUnmapped ? '#fef2f2' : '#faf5ff'}; border: 1px solid ${isUnmapped ? '#fecaca' : '#e9d5ff'}; border-radius: 4px; padding: 1px 6px; display: ${showJsonView ? "block" : "none"}; width: fit-content; word-break: break-all;">
          🔍 JSON: {"pid": "${p.pid}", "status": "${p.status}", "raw_status": ${p.raw_status !== undefined && p.raw_status !== null ? p.raw_status : "null"}} ${isUnmapped ? '⚠️ (미매핑 감지)' : ''}
        </div>`;

        return `
        <div class="prob-row-item ${isChecked ? "checked-item" : ""}" style="border-left: 3px solid ${
          p.status === "solved"
            ? "#22c55e"
            : p.status === "wrong"
            ? "#ef4444"
            : p.status === "partial"
            ? "#f59e0b"
            : "#cbd5e1"
        }; flex-wrap: wrap;">
          <div style="display: flex; flex-direction: column; flex: 1; overflow: hidden; pointer-events: none;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <input type="checkbox" class="prob-homework-checkbox" data-pid="${p.pid}" data-title="${p.title}" data-url="${p.url}" ${
            isChecked ? "checked" : ""
          } style="cursor: pointer; width: 16px; height: 16px; flex-shrink: 0; pointer-events: auto;" />
              <span style="font-weight: 600; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.83rem;" title="${p.title}">${p.title}</span>
            </div>
            ${jsonTagHtml}
          </div>
          <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
            ${statusBadge}
            <a href="${p.url}" target="_blank" rel="noopener" style="text-decoration: none; color: #94a3b8; font-size: 0.85rem;" title="문제 링크 열기">🔗</a>
          </div>
        </div>
      `;
      })
      .join("");

    attachProblemSelectionEvents();
  }

  // ── 문제 동기화 헬퍼 함수
  function syncProblemCheckbox(cb, isChecked) {
    if (!cb) return;
    cb.checked = isChecked;
    const row = cb.closest(".prob-row-item");
    if (row) {
      row.classList.toggle("checked-item", isChecked);
    }
    const pid = cb.dataset.pid;
    const title = cb.dataset.title;
    const url = cb.dataset.url;
    const chapter_code = (selectedGroup && selectedGroup.chapter_code) || (selectedChapter && selectedChapter.chapter_id) || "p102";
    const group_title = (selectedGroup && selectedGroup.title) || (selectedChapter && selectedChapter.title) || "";
    if (isChecked) {
      if (window.addProblemToBasket) window.addProblemToBasket({ pid, legacy_code: pid, title, url, chapter_code, group_title });
    } else {
      if (window.removeProblemFromBasket) window.removeProblemFromBasket(pid);
    }
  }

  let lastCheckedIndex = null;

  // ── Row 클릭 & Shift 클릭 이벤트 바인딩
  function attachProblemSelectionEvents() {
    lastCheckedIndex = null;
    const rows = probListEl.querySelectorAll(".prob-row-item");

    rows.forEach((row, idx) => {
      row.addEventListener("click", (e) => {
        // 링크 아이콘 🔗 클릭 시 이벤트 제외
        if (e.target.closest("a")) return;

        const cb = row.querySelector(".prob-homework-checkbox");
        if (!cb) return;

        const isDirectCb = e.target.classList.contains("prob-homework-checkbox");

        // Shift + 클릭 범위 선택 (Range Selection)
        if (e.shiftKey && lastCheckedIndex !== null && lastCheckedIndex !== idx) {
          if (!isDirectCb) e.preventDefault();
          const allRows = Array.from(probListEl.querySelectorAll(".prob-row-item"));
          const targetState = isDirectCb ? cb.checked : !cb.checked;
          const start = Math.min(lastCheckedIndex, idx);
          const end = Math.max(lastCheckedIndex, idx);

          for (let i = start; i <= end; i++) {
            const r = allRows[i];
            const itemCb = r ? r.querySelector(".prob-homework-checkbox") : null;
            if (itemCb) syncProblemCheckbox(itemCb, targetState);
          }
          lastCheckedIndex = idx;
          return;
        }

        // 일반 클릭 (Row 또는 Checkbox)
        if (!isDirectCb) {
          e.preventDefault();
          syncProblemCheckbox(cb, !cb.checked);
        } else {
          syncProblemCheckbox(cb, cb.checked);
        }
        lastCheckedIndex = idx;
      });
    });
  }

  // ── 🖱️ 마우스 드래그 다중선택 Engine (Rubber-band Drag Selection)
  (function initDragToSelectEngine() {
    let isDragging = false;
    let dragBox = null;
    let startX = 0, startY = 0;

    probListEl.style.position = "relative";

    probListEl.addEventListener("mousedown", (e) => {
      // 🔗 링크 아이콘 또는 체크박스 직접 클릭 시 드래그 박스 미생성
      if (e.target.closest("a") || e.target.classList.contains("prob-homework-checkbox")) return;
      const rows = probListEl.querySelectorAll(".prob-row-item");
      if (!rows.length) return;

      const rect = probListEl.getBoundingClientRect();
      startX = e.clientX - rect.left + probListEl.scrollLeft;
      startY = e.clientY - rect.top + probListEl.scrollTop;

      dragBox = document.createElement("div");
      dragBox.className = "drag-select-box";
      dragBox.style.left = `${startX}px`;
      dragBox.style.top = `${startY}px`;
      dragBox.style.width = "0px";
      dragBox.style.height = "0px";
      probListEl.appendChild(dragBox);

      isDragging = false;

      function onMouseMove(evt) {
        const cRect = probListEl.getBoundingClientRect();
        const curX = evt.clientX - cRect.left + probListEl.scrollLeft;
        const curY = evt.clientY - cRect.top + probListEl.scrollTop;

        const diffX = curX - startX;
        const diffY = curY - startY;

        if (!isDragging && (Math.abs(diffX) > 5 || Math.abs(diffY) > 5)) {
          isDragging = true;
          probListEl.classList.add("is-dragging");
        }

        if (!isDragging || !dragBox) return;

        const boxLeft = diffX < 0 ? curX : startX;
        const boxTop = diffY < 0 ? curY : startY;
        const boxWidth = Math.abs(diffX);
        const boxHeight = Math.abs(diffY);

        dragBox.style.left = `${boxLeft}px`;
        dragBox.style.top = `${boxTop}px`;
        dragBox.style.width = `${boxWidth}px`;
        dragBox.style.height = `${boxHeight}px`;

        const bRect = dragBox.getBoundingClientRect();
        rows.forEach(r => {
          const rRect = r.getBoundingClientRect();
          const intersects = !(
            rRect.right < bRect.left ||
            rRect.left > bRect.right ||
            rRect.bottom < bRect.top ||
            rRect.top > bRect.bottom
          );
          r.classList.toggle("drag-selecting", intersects);
        });
      }

      function onMouseUp() {
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);

        if (dragBox && dragBox.parentNode) {
          dragBox.parentNode.removeChild(dragBox);
        }
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

  // ── 스마트 퀵 선택 칩 버튼 연동
  const btnSelectUnsolved = document.getElementById("btn-select-unsolved-problems");
  const btnSelectWrong = document.getElementById("btn-select-wrong-problems");
  const btnClearSelected = document.getElementById("btn-clear-selected-problems");

  function setBatchSelection(predicateFn) {
    if (!selectedGroup || !selectedGroup.problems) return;
    const checkboxes = probListEl.querySelectorAll(".prob-homework-checkbox");
    const probMap = new Map((selectedGroup.problems || []).map(p => [p.pid, p]));

    checkboxes.forEach(cb => {
      const p = probMap.get(cb.dataset.pid);
      const shouldSelect = predicateFn(p);
      syncProblemCheckbox(cb, shouldSelect);
    });
  }

  if (btnSelectAll) {
    btnSelectAll.addEventListener("click", () => setBatchSelection(() => true));
  }
  if (btnSelectUnsolved) {
    btnSelectUnsolved.addEventListener("click", () => setBatchSelection(p => p && p.status === "unsolved"));
  }
  if (btnSelectWrong) {
    btnSelectWrong.addEventListener("click", () => setBatchSelection(p => p && (p.status === "wrong" || p.status === "partial")));
  }
  if (btnClearSelected) {
    btnClearSelected.addEventListener("click", () => setBatchSelection(() => false));
  }

  const btnToggleJsonView = document.getElementById("btn-toggle-json-view");
  if (btnToggleJsonView) {
    btnToggleJsonView.addEventListener("click", () => {
      showJsonView = !showJsonView;
      btnToggleJsonView.style.background = showJsonView ? "#6b21a8" : "#faf5ff";
      btnToggleJsonView.style.color = showJsonView ? "#ffffff" : "#6b21a8";
      probListEl.querySelectorAll(".prob-json-tag").forEach(tag => {
        tag.style.display = showJsonView ? "block" : "none";
      });
    });
  }

  // 🎯 특정 문제/소단원 단원 목차로 1클릭 이동 & 스크롤 포커스 함수
  window.navigateToProblemChapter = function (pid, groupId) {
    const drillData = (window.APP_CONFIG && window.APP_CONFIG.drilldownData) || [];
    if (!drillData.length) {
      if (typeof showToast === "function") showToast("⚠️ 단원 목차 데이터가 없습니다.");
      return;
    }

    let foundChapter = null;
    let foundGroup = null;

    // 1. pid 또는 groupId로 해당 단원 및 소단원 탐색
    for (const ch of drillData) {
      for (const g of (ch.groups || [])) {
        if ((groupId && g.group_id === groupId) || (g.problems || []).some(p => p.pid === pid || p.legacy_code === pid)) {
          foundChapter = ch;
          foundGroup = g;
          break;
        }
      }
      if (foundChapter) break;
    }

    if (!foundChapter || !foundGroup) {
      if (typeof showToast === "function") {
        showToast("ℹ️ 해당 문제의 단원 위치를 목차에서 찾을 수 없습니다.");
      } else {
        alert("해당 문제의 단원 위치를 목차에서 찾을 수 없습니다.");
      }
      return;
    }

    // 2. 대단원 및 소단원 활성화 및 렌더링
    selectedChapter = foundChapter;
    selectedGroup = foundGroup;

    renderMainChapters();
    renderSubChapters();
    renderProblems();

    // 3. 문제 목록 3열에서 해당 문제 행 스크롤 포커스 & 노란색 하이라이트
    setTimeout(() => {
      const probListEl = document.getElementById("problems-list");
      if (!probListEl) return;
      const targetCheckbox = probListEl.querySelector(`.prob-homework-checkbox[data-pid="${pid}"]`);
      if (targetCheckbox) {
        const rowItem = targetCheckbox.closest(".prob-row-item");
        if (rowItem) {
          rowItem.style.transition = "background-color 0.5s ease";
          rowItem.style.backgroundColor = "#fef08a";
          rowItem.scrollIntoView({ behavior: "smooth", block: "center" });
          setTimeout(() => {
            rowItem.style.backgroundColor = "";
          }, 2200);
        }
      }
      if (typeof showToast === "function") {
        showToast(`🎯 '${foundGroup.title}' 단원으로 이동했습니다.`);
      }
    }, 150);
  };

  // Sync checkboxes when basket updates externally
  window.refreshDrilldownCheckboxes = function () {
    if (!selectedGroup) return;
    probListEl.querySelectorAll(".prob-homework-checkbox").forEach(cb => {
      const pid = cb.dataset.pid;
      cb.checked = window.isProblemInBasket ? window.isProblemInBasket(pid) : false;
    });
  };

  // Initial select first chapter and its first valid sub-chapter
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
