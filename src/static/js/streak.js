/**
 * Streak & Activity Grid Module (streak.js)
 */
const CFG = window.APP_CONFIG || {};
const INITIAL_STREAK_DATA = CFG.initialStreakData || [];
const SERVER_VIEW_MODE = CFG.viewMode || "";
const SERVER_VIEW_USERNAME = CFG.viewUsername || "";

const m = location.pathname.match(/^\/user\/([^\/]+)/);
const PATH_VIEW_MODE = m ? "user" : "me";
const PATH_VIEW_USERNAME = m ? decodeURIComponent(m[1]) : "";
const viewMode = SERVER_VIEW_MODE || PATH_VIEW_MODE;
const viewUsername = SERVER_VIEW_USERNAME || PATH_VIEW_USERNAME;

let streakCurrentDays = Number(CFG.streakDays || 7);
let streakLatestCurrent = normalizeStreakData(INITIAL_STREAK_DATA);
let streakLatestPrev = [];
let streakActiveOnly = false;
let timelineFilterMode = "all";

window.setTimelineFilterMode = function(mode) {
  timelineFilterMode = mode;
  const allBtn = document.getElementById("tl-filter-all");
  const wrongBtn = document.getElementById("tl-filter-wrong");
  if (allBtn && wrongBtn) {
    if (mode === "wrong") {
      allBtn.style.background = "#ffffff";
      allBtn.style.color = "#475569";
      allBtn.style.border = "1px solid #cbd5e1";
      wrongBtn.style.background = "#dc2626";
      wrongBtn.style.color = "#ffffff";
      wrongBtn.style.border = "none";
    } else {
      allBtn.style.background = "#6c5ce7";
      allBtn.style.color = "#ffffff";
      allBtn.style.border = "none";
      wrongBtn.style.background = "#ffffff";
      wrongBtn.style.color = "#dc2626";
      wrongBtn.style.border = "1px solid #fecaca";
    }
  }
  renderStreakByFilter();
};

const streakGrid = document.getElementById("streak-grid");
const streakSummaryEl = document.getElementById("streak-summary");
const streakCompareEl = document.getElementById("streak-compare");
const streakActiveOnlyToggle = document.getElementById("streak-active-only-toggle");

const TODAY_MMDD = (() => {
  const kst = new Date().toLocaleString("en-US", { timeZone: "Asia/Seoul" });
  const d = new Date(kst);
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
})();

function ensureEl(id, { className = "", style = "" } = {}) {
  let el = document.getElementById(id);
  if (!el) {
    el = document.createElement("div");
    el.id = id;
    if (className) el.className = className;
    if (style) el.style.cssText = style;
    document.body.appendChild(el);
  }
  return el;
}

const popover = ensureEl("streak-popover", {
  className: "streak-popover",
  style: "display:none;",
});
const overlayEl = ensureEl("overlay", {
  className: "details",
  style: "display:none;",
});

function mapLanguageToHljs(langStr) {
  if (!langStr) return "plaintext";
  const l = String(langStr).toLowerCase();
  if (l.includes("c++") || l.includes("cpp")) return "cpp";
  if (l === "c" || l.startsWith("c ")) return "c";
  if (l.includes("python") || l.includes("pypy")) return "python";
  if (l.includes("java") && !l.includes("script")) return "java";
  if (l.includes("javascript") || l.includes("js")) return "javascript";
  return "plaintext";
}

async function ensureHighlightJsLoaded() {
  if (window.hljs) return window.hljs;
  if (!document.getElementById("hljs-css")) {
    const link = document.createElement("link");
    link.id = "hljs-css";
    link.rel = "stylesheet";
    link.href = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css";
    document.head.appendChild(link);
  }
  if (!window.__hljs_promise) {
    window.__hljs_promise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js";
      script.onload = () => resolve(window.hljs);
      script.onerror = (e) => reject(e);
      document.head.appendChild(script);
    });
  }
  return window.__hljs_promise;
}

window.openSubmissionCodeModal = async function(subId, title) {
  let modal = document.getElementById("submissionCodeModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "submissionCodeModal";
    modal.style.cssText = "position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.45); backdrop-filter: blur(5px); display: none; justify-content: center; align-items: center; z-index: 10010;";
    modal.innerHTML = `
      <div style="background: #ffffff; border-radius: 18px; width: 780px; max-width: 92vw; max-height: 85vh; padding: 24px; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 20px 50px rgba(0,0,0,0.25);">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px;">
          <span style="font-weight: 800; font-size: 1.05rem; color: #1e293b; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span>💻 제출 코드 확인</span>
            <span id="scmCodeLangBadge" style="font-size: 0.75rem; background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 12px; font-weight: 700; display: none;"></span>
            <span id="scmCodeTitle" style="font-size: 0.85rem; color: #64748b; font-weight: 600;"></span>
          </span>
          <button style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #64748b;" onclick="document.getElementById('submissionCodeModal').style.display='none'">×</button>
        </div>
        <div id="scmCodeContainer" style="background: #0f172a; border-radius: 12px; max-height: 55vh; overflow: auto; padding: 14px;">
          <pre style="margin: 0;"><code id="scmCodeContent" class="hljs" style="font-family: Consolas, Monaco, 'Andale Mono', monospace; font-size: 0.83rem; line-height: 1.5; white-space: pre; word-break: normal;">⏳ 소스코드를 불러오는 중...</code></pre>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <button class="btn btn-secondary" style="font-size: 0.8rem; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; background: #ffffff; border: 1px solid #cbd5e1; color: #334155;" onclick="navigator.clipboard.writeText(document.getElementById('scmCodeContent').textContent); alert('📋 소스코드가 클립보드에 복사되었습니다!');">📋 코드 복사</button>
          <button class="btn btn-primary" style="font-size: 0.8rem; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; background: #64748b; color: white; border: none;" onclick="document.getElementById('submissionCodeModal').style.display='none'">닫기</button>
        </div>
      </div>
    `;
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.style.display = "none"; });
    document.body.appendChild(modal);
  }
  document.getElementById("scmCodeTitle").textContent = title ? `(${title})` : "";
  const langBadgeEl = document.getElementById("scmCodeLangBadge");
  if (langBadgeEl) langBadgeEl.style.display = "none";
  const codeContentEl = document.getElementById("scmCodeContent");
  if (codeContentEl) {
    codeContentEl.removeAttribute("data-highlighted");
    delete codeContentEl.dataset.highlighted;
    codeContentEl.className = "hljs";
    codeContentEl.textContent = "⏳ 소스코드를 불러오는 중...";
  }
  modal.style.display = "flex";

  try {
    const fetchPromise = fetch(`/api/submission_code?id=${encodeURIComponent(subId)}`).then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });
    const hljsPromise = ensureHighlightJsLoaded().catch(() => null);

    const [data, hljs] = await Promise.all([fetchPromise, hljsPromise]);

    const langName = data?.language || "";
    if (langBadgeEl) {
      if (langName) {
        langBadgeEl.textContent = langName;
        langBadgeEl.style.display = "inline-block";
      } else {
        langBadgeEl.style.display = "none";
      }
    }

    if (codeContentEl) {
      codeContentEl.removeAttribute("data-highlighted");
      delete codeContentEl.dataset.highlighted;

      if (data?.code) {
        codeContentEl.textContent = data.code;
        const targetLang = mapLanguageToHljs(langName);
        codeContentEl.className = `hljs language-${targetLang}`;
        if (hljs) {
          hljs.highlightElement(codeContentEl);
        }
      } else {
        codeContentEl.textContent = "// 저장된 제출 소스코드가 없습니다.";
      }
    }
  } catch (e) {
    if (codeContentEl) {
      codeContentEl.removeAttribute("data-highlighted");
      delete codeContentEl.dataset.highlighted;
      codeContentEl.textContent = `// 소스코드 로드 오류: ${e.message}`;
    }
  }
};

window.jumpToProblemLocation = function(pid, groupId) {
  if (typeof window.navigateToProblemChapter === "function") {
    window.navigateToProblemChapter(pid, groupId);
  } else {
    const chartsSec = document.querySelector(".charts-section") || document.getElementById("charts-container");
    if (chartsSec) {
      chartsSec.scrollIntoView({ behavior: "smooth" });
    }
  }
};

function normalizeStreakData(data) {
  if (!Array.isArray(data)) return [];
  return data.map((d) => ({
    date: d?.date || "",
    weekday: d?.weekday || "",
    count: Number(d?.count || 0),
    details: Array.isArray(d?.details) ? d.details : [],
  }));
}

function setStreakSummary(days, currentData, prevData = []) {
  if (!streakSummaryEl || !streakCompareEl) return;
  const currentTotal = currentData.reduce((s, d) => s + Number(d.count || 0), 0);

  let labelStr = "";
  if (days === 7) labelStr = `최근 7일 제출 수: ${currentTotal}회`;
  else if (days === 30) labelStr = `최근 30일 제출 수: ${currentTotal}회`;
  else if (days === 90) labelStr = `최근 90일 제출 수: ${currentTotal}회`;
  else labelStr = `${days}일간 제출 수: ${currentTotal}회`;
  streakSummaryEl.textContent = labelStr;

  if (!prevData.length) {
    streakCompareEl.textContent = "비교 데이터 준비 중";
    streakCompareEl.className = "streak-compare neutral";
    return;
  }

  const prevTotal = prevData.reduce((s, d) => s + Number(d.count || 0), 0);
  const diff = currentTotal - prevTotal;
  const unitStr = days === 7 ? "지난주" : days === 30 ? "지난달" : "이전 기간";

  if (diff > 0) {
    streakCompareEl.textContent = `${unitStr} 대비 +${diff}회 증가 🚀`;
    streakCompareEl.className = "streak-compare positive";
  } else if (diff < 0) {
    streakCompareEl.textContent = `${unitStr} 대비 ${diff}회 감소`;
    streakCompareEl.className = "streak-compare negative";
  } else {
    streakCompareEl.textContent = `${unitStr}와 동일 (${currentTotal}회)`;
    streakCompareEl.className = "streak-compare neutral";
  }
}

function parseMonthDay(mmdd) {
  const parts = String(mmdd || "").split("-");
  if (parts.length !== 2) return null;
  const m = Number(parts[0]);
  const d = Number(parts[1]);
  if (!m || !d) return null;
  return { m, d };
}

function formatDateLabel(day) {
  const parsed = parseMonthDay(day.date);
  if (!parsed) return day.date || "";
  const weekdayStr = day.weekday ? `(${day.weekday})` : "";
  return `${parsed.m}월 ${parsed.d}일 ${weekdayStr}`.trim();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function closeStreakPopover() {
  popover.style.display = "none";
  overlayEl.style.display = "none";
  document.querySelectorAll(".streak-cell.is-open").forEach((c) => c.classList.remove("is-open"));
  const owner = popover.__ownerCell;
  popover.__ownerCell = null;
  owner?.focus?.();
}

function positionPopoverForCell(cell) {
  if (!cell || popover.style.display !== "block") return;
  const rect = cell.getBoundingClientRect();

  popover.style.visibility = "hidden";
  popover.style.display = "block";
  const popRect = popover.getBoundingClientRect();
  popover.style.visibility = "";

  const margin = 10;
  let top = rect.bottom + margin;
  let left = rect.left + rect.width / 2 - popRect.width / 2;

  if (top + popRect.height > window.innerHeight - margin) {
    top = rect.top - popRect.height - margin;
  }
  top = Math.max(margin, top);

  if (left < margin) left = margin;
  if (left + popRect.width > window.innerWidth - margin) {
    left = window.innerWidth - popRect.width - margin;
  }

  popover.style.top = `${top}px`;
  popover.style.left = `${left}px`;
}

function repositionPopover() {
  if (popover.__ownerCell && popover.style.display === "block") {
    positionPopoverForCell(popover.__ownerCell);
  }
}

window.addEventListener("resize", repositionPopover);
window.addEventListener("scroll", repositionPopover, true);

if (streakGrid && !streakGrid.__bound) {
  streakGrid.addEventListener("click", (e) => {
    const cell = e.target.closest(".streak-cell");
    if (!cell || !cell.classList.contains("has-details")) return;

    const raw = cell.dataset.details;
    if (!raw) return;

    let list = [];
    try { list = JSON.parse(raw); } catch { list = []; }

    const same = popover.__ownerCell === cell && popover.style.display === "block";
    document.querySelectorAll(".streak-cell.is-open").forEach((c) => c.classList.remove("is-open"));
    document.body.appendChild(popover);
    if (same) {
      closeStreakPopover();
      return;
    }

    const normalized = Array.isArray(list)
      ? [...list]
          .map((p) => ({
            title: p?.title || p?.problem || "제목 없음",
            language: p?.language || "-",
            score: p?.score ?? "-",
            time: p?.time || "-",
            serverSubId: p?.server_sub_id,
            problem: p?.problem,
            problemUrl:
              p?.problem_url ||
              (p?.problem ? `http://edu.doingcoding.com/problem/${encodeURIComponent(String(p.problem))}` : ""),
            chapterUrl: p?.chapter_url || "",
          }))
          .sort((a, b) => String(b.time).localeCompare(String(a.time)))
      : [];

    const totalCount = normalized.length;
    const scored = normalized.map((p) => Number(p.score)).filter((n) => Number.isFinite(n));
    const avgScore = scored.length ? Math.round(scored.reduce((a, b) => a + b, 0) / scored.length) : null;
    const latestTitle = normalized[0]?.title || "";

    popover.innerHTML = `
<div class="streak-popover-head">
  <div>
    <h4 class="streak-popover-title">제출 ${totalCount}회${avgScore !== null ? ` · 평균 ${avgScore}점` : ""}</h4>
    <div class="streak-popover-sub">최근 풀이 제목을 빠르게 복사할 수 있습니다.</div>
  </div>
  ${latestTitle ? `<button type="button" class="btn-primary streak-inline-btn" data-copy-title="${escapeHtml(latestTitle)}">최근 제목 복사</button>` : ""}
</div>
<div class="streak-popover-list">
${
  normalized.length
    ? normalized
        .map(
          (p) => `
  <article class="streak-popover-item">
    <div class="streak-item-top">
      <h5 class="streak-item-title">${escapeHtml(p.title)}</h5>
      <button type="button" class="btn-quiet streak-inline-btn" data-copy-title="${escapeHtml(p.title)}">제목 복사</button>
    </div>
    <div class="streak-item-meta">${escapeHtml(p.language)} · ${escapeHtml(p.score)}점 · ${escapeHtml(p.time)}</div>
    <div class="streak-item-actions">
      ${p.serverSubId ? `<a class="btn-secondary streak-inline-btn" href="http://edu.doingcoding.com/status/${encodeURIComponent(String(p.serverSubId))}" target="_blank" rel="noopener">제출 내역</a>` : ""}
      ${p.problemUrl ? `<a class="btn-primary streak-inline-btn" href="${escapeHtml(p.problemUrl)}" target="_blank" rel="noopener">문제 본문</a>` : ""}
      ${p.chapterUrl ? `<a class="btn-quiet streak-inline-btn" href="${escapeHtml(p.chapterUrl)}" target="_blank" rel="noopener">챕터 열기</a>` : ""}
    </div>
  </article>
`
        )
        .join("")
    : `<div class="empty-inline">제출 내역 없음</div>`
}
</div>
`;

    const focusTarget =
      popover.querySelector("[data-copy-title]") ||
      popover.querySelector(".streak-item-actions a, .streak-item-actions button");

    popover.style.display = "block";
    overlayEl.style.display = "block";
    cell.classList.add("is-open");
    popover.__ownerCell = cell;

    positionPopoverForCell(cell);

    requestAnimationFrame(() => {
      focusTarget?.focus?.();
    });
  });

  popover.addEventListener("click", async (e) => {
    const copyBtn = e.target.closest("[data-copy-title]");
    if (!copyBtn) return;
    e.preventDefault();
    const titleToCopy = copyBtn.dataset.copyTitle || "";
    if (!titleToCopy) return;
    const ok = await copyTextSafe(titleToCopy);
    if (ok) {
      if (typeof showToast === "function") showToast(`복사됨: ${titleToCopy}`);
    } else {
      alert("제목 복사에 실패했습니다.");
    }
  });

  overlayEl.addEventListener("click", closeStreakPopover);
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || popover.style.display !== "block") return;
    e.preventDefault();
    closeStreakPopover();
  });

  streakGrid.__bound = true;
}

async function copyTextSafe(text) {
  const value = String(text ?? "");
  if (!value) return false;

  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {}
  }

  try {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "-9999px";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return !!ok;
  } catch {
    return false;
  }
}

function calcTier(c) {
  if (c <= 0) return 0;
  if (c <= 2) return 1;
  if (c <= 5) return 2;
  if (c <= 9) return 3;
  if (c <= 14) return 4;
  return 5;
}

function getStreakState(day, c, prevCount, maxDaily) {
  if (day.date === TODAY_MMDD) return { key: "today", label: "오늘" };
  if (c === 0) return { key: "inactive", label: "미접속" };
  if (maxDaily > 0 && c === maxDaily) return { key: "peak", label: "최고치" };
  if (prevCount > 0 && c <= prevCount * 0.4) return { key: "drop", label: "급감" };
  return { key: "active", label: "접속" };
}

function updateTodayLatestProblem(streakData) {
  const box = document.getElementById("today-latest-problem");
  if (!box) return;
  const labelEl = document.getElementById("today-problem-label");
  const linkEl = document.getElementById("today-problem-link");
  const badgeEl = document.getElementById("today-problem-status-badge");
  const metaEl = document.getElementById("today-problem-meta");
  const copyBtn = document.getElementById("today-problem-copy-btn");

  const normalized = normalizeStreakData(streakData);
  let targetDay = normalized.find((d) => d.date === TODAY_MMDD);
  let isToday = true;

  if (!targetDay || !targetDay.details || !targetDay.details.length) {
    for (let i = normalized.length - 1; i >= 0; i--) {
      if (normalized[i].details && normalized[i].details.length > 0) {
        targetDay = normalized[i];
        isToday = false;
        break;
      }
    }
  }

  const details = targetDay && targetDay.details ? targetDay.details : [];

  if (labelEl) {
    labelEl.textContent = isToday ? "오늘 마지막 풀이" : `최근 마지막 풀이 (${targetDay?.date || ""})`;
  }

  if (!details.length) {
    if (linkEl) {
      linkEl.textContent = "최근 제출 내역 없음";
      linkEl.removeAttribute("href");
      linkEl.style.pointerEvents = "none";
    }
    if (badgeEl) {
      badgeEl.textContent = "기록 없음";
      badgeEl.className = "today-problem-badge";
    }
    if (metaEl) metaEl.textContent = "-";
    if (copyBtn) copyBtn.style.display = "none";
    return;
  }

  const sorted = [...details].sort((a, b) => String(b.time || "").localeCompare(String(a.time || "")));
  const latest = sorted[0];

  const title = latest.title || latest.problem || "제목 없음";
  const score = Number(latest.score ?? 0);
  const timeStr = latest.time || "";
  const lang = latest.language || "";
  const problemUrl =
    latest.problem_url ||
    (latest.problem ? `http://edu.doingcoding.com/problem/${encodeURIComponent(String(latest.problem))}` : "#");

  if (linkEl) {
    linkEl.textContent = title;
    linkEl.href = problemUrl;
    linkEl.style.pointerEvents = "auto";
    linkEl.title = title;
  }

  if (badgeEl) {
    const isAC = latest.result === 0 || latest.status === "solved" || latest.status === "passed" || latest.passed === true || score >= 90;
    if (isAC) {
      badgeEl.textContent = `정답 (${score > 0 ? score + '점' : '100점'})`;
      badgeEl.className = "today-problem-badge pass";
    } else if (score > 0 && score < 90) {
      badgeEl.textContent = `부분점수 (${score}점)`;
      badgeEl.className = "today-problem-badge partial";
    } else {
      badgeEl.textContent = `오답 (${score}점)`;
      badgeEl.className = "today-problem-badge fail";
    }
  }

  if (metaEl) {
    const parts = [];
    if (lang && lang !== "-") parts.push(lang);
    if (timeStr) parts.push(timeStr);
    metaEl.textContent = parts.join(" · ");
  }

  if (copyBtn) {
    copyBtn.style.display = "inline-flex";
    copyBtn.dataset.copyTitle = title;
    if (!copyBtn.__bound) {
      copyBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        const text = copyBtn.dataset.copyTitle || "";
        if (!text) return;
        const ok = await copyTextSafe(text);
        if (ok) {
          if (typeof showToast === "function") showToast(`복사됨: ${text}`);
          else alert(`복사됨: ${text}`);
        } else {
          alert("제목 복사에 실패했습니다.");
        }
      });
      copyBtn.__bound = true;
    }
  }

  const jumpBtn = document.getElementById("today-problem-jump-btn");
  if (jumpBtn) {
    jumpBtn.style.display = "inline-flex";
    jumpBtn.dataset.pid = latest.pid || latest.problem || "";
    jumpBtn.dataset.groupId = latest.group_id || "";
    if (!jumpBtn.__bound) {
      jumpBtn.__bound = true;
      jumpBtn.addEventListener("click", (e) => {
        e.preventDefault();
        const pid = jumpBtn.dataset.pid || "";
        const groupId = jumpBtn.dataset.groupId || "";
        if (typeof window.navigateToProblemChapter === "function") {
          window.navigateToProblemChapter(pid, groupId);
        } else {
          if (typeof showToast === "function") showToast("단원 이동 기능을 준비하는 중입니다.");
        }
      });
    }
  }
}

function renderStreakGrid(streakData, { days = 7, prevData = [], summaryData = null } = {}) {
  if (!streakGrid) return;
  const data = normalizeStreakData(streakData);
  const activeDays = data.filter((d) => Number(d.count || 0) > 0 || (d.details && d.details.length > 0));

  setStreakSummary(days, summaryData || data, prevData);
  updateTodayLatestProblem(summaryData || streakLatestCurrent || data);

  if (!activeDays.length) {
    streakGrid.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 40px; font-size: 0.9rem; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 12px; grid-column: span 2;">🗓️ 선택된 기간(${days}일) 동안 등원 및 실습 기록이 없습니다.</div>`;
    return;
  }

  // 역순(최신 등원일 우선) 정렬
  const sortedDays = [...activeDays].reverse();
  const frag = document.createDocumentFragment();

  sortedDays.forEach((day) => {
    const details = Array.isArray(day.details) ? day.details : [];
    const dateLabel = formatDateLabel(day);
    const totalCnt = details.length || day.count || 0;

    let passedCnt = 0;
    let partialCnt = 0;
    let wrongCnt = 0;

    details.forEach((p) => {
      const score = Number(p.score ?? 0);
      const isAC = p.result === 0 || p.status === "solved" || p.status === "passed" || p.passed === true || score >= 90;
      if (isAC) passedCnt++;
      else if (score > 0 && score < 90) partialCnt++;
      else wrongCnt++;
    });

    let targetDetails = [...details];
    if (timelineFilterMode === "wrong") {
      targetDetails = targetDetails.filter((p) => {
        const score = Number(p.score ?? 0);
        const isAC = p.result === 0 || p.status === "solved" || p.status === "passed" || p.passed === true || score >= 90;
        return !isAC;
      });
    }

    // 기본 정렬: 제출 시간순 (최신순)
    const sortedDetails = targetDetails.sort((a, b) => String(b.time || "").localeCompare(String(a.time || "")));

    const card = document.createElement("div");
    card.className = "timeline-day-card";
    card.style.cssText = "background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px;";

    const headHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
        <div style="font-weight: 800; font-size: 0.95rem; color: #1e293b; display: flex; align-items: center; gap: 8px;">
          <span>📅 ${dateLabel} 등원</span>
          <span style="font-size: 0.75rem; background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 12px; font-weight: 700;">실습 ${totalCnt}건</span>
        </div>
        <div style="font-size: 0.78rem; font-weight: 600; display: flex; gap: 8px; color: #64748b;">
          <span style="color: #059669;">🟢 정답 ${passedCnt}</span>
          ${partialCnt > 0 ? `<span style="color: #d97706;">🟡 부분 ${partialCnt}</span>` : ""}
          ${wrongCnt > 0 ? `<span style="color: #dc2626; font-weight: 700;">🔴 오답 ${wrongCnt}</span>` : ""}
        </div>
      </div>
    `;

    // 40+ 문항 처리: 상위 4개 기본 표시, 나머지 숨김 토글
    const visibleItems = sortedDetails.slice(0, 4);
    const hiddenItems = sortedDetails.slice(4);

      const renderItemHTML = (p) => {
        const score = Number(p.score ?? 0);
        const isAC = p.result === 0 || p.status === "solved" || p.status === "passed" || p.passed === true || score >= 90;
        let statusBadge = `<span style="font-size:0.75rem; color:#059669; background:#ecfdf5; border:1px solid #a7f3d0; padding:2px 4px; border-radius:12px; font-weight:700; flex-shrink:0; width:72px; white-space:nowrap; text-align:center; display:inline-block;">🟢 100점</span>`;
        if (!isAC && score > 0) {
          statusBadge = `<span style="font-size:0.75rem; color:#d97706; background:#fffbeb; border:1px solid #fde68a; padding:2px 4px; border-radius:12px; font-weight:700; flex-shrink:0; width:72px; white-space:nowrap; text-align:center; display:inline-block;">🟡 ${score}점</span>`;
        } else if (!isAC) {
          statusBadge = `<span style="font-size:0.75rem; color:#dc2626; background:#fef2f2; border:1px solid #fecaca; padding:2px 4px; border-radius:12px; font-weight:700; flex-shrink:0; width:72px; white-space:nowrap; text-align:center; display:inline-block;">🔴 0점</span>`;
        }

        const pTitle = escapeHtml(p.title || p.problem || "제목 없음");
        const pUrl = p.problem_url || (p.problem ? `http://edu.doingcoding.com/problem/${encodeURIComponent(String(p.problem))}` : "#");
        const subId = p.server_sub_id || p.serverSubId || p.sub_id || p.id || "";
        const pid = p.pid || p.problem || p.problem_id || "";
        const groupId = p.group_id || p.groupId || "";
        const langStr = p.language ? escapeHtml(p.language) : "";

        // Phase 1: 개념 태그 칩
        const rawChapter = p.chapter_title || "";
        let chapterTagStr = rawChapter.replace(/^\d+\.\s*/, "").replace(/\s*\(.*?\)$/, "").trim();
        if (!chapterTagStr && rawChapter) chapterTagStr = rawChapter;
        const chapterBadge = chapterTagStr ? `<span style="font-size:0.72rem; color:#4338ca; background:#e0e7ff; border:1px solid #c7d2fe; padding:2px 7px; border-radius:6px; font-weight:700; flex-shrink:0;">🏷️ ${escapeHtml(chapterTagStr)}</span>` : "";

        // Phase 2: 시도 횟수 & 1-Try AC 뱃지
        let tryBadge = "";
        if (p.is_first_try_ac) {
          tryBadge = `<span style="font-size:0.72rem; color:#047857; background:#d1fae5; border:1px solid #6ee7b7; padding:2px 7px; border-radius:6px; font-weight:700; flex-shrink:0;">⚡ 1-Try 통과</span>`;
        } else if (p.attempt_number && p.attempt_number > 1) {
          tryBadge = `<span style="font-size:0.72rem; color:#b45309; background:#fef3c7; border:1px solid #fcd34d; padding:2px 7px; border-radius:6px; font-weight:700; flex-shrink:0;">🔄 ${p.attempt_number}회차 시도</span>`;
        }

        // Phase 3: AI / 초고속 복사 의심 경고 뱃지
        let aiWarningBadge = "";
        if (p.is_ai_suspected) {
          const reasonStr = escapeHtml(p.ai_suspicion_reason || "초고속 복사 제출 의심");
          aiWarningBadge = `<span style="font-size:0.72rem; color:#dc2626; background:#fef2f2; border:1px solid #fecaca; padding:2px 7px; border-radius:6px; font-weight:800; cursor:help; flex-shrink:0;" title="📌 의심 사유: ${reasonStr}">🤖 AI/복사 의심</span>`;
        }

        const codeBtn = subId ? `<button type="button" class="btn-quiet" style="font-size: 0.75rem; padding: 3px 8px; border-radius: 6px; border: 1px solid #6c5ce7; background: #faf5ff; color: #6c5ce7; font-weight: 700; cursor: pointer;" onclick="openSubmissionCodeModal('${subId}', '${pTitle.replace(/'/g, "\\'")}')">💻 코드</button>` : "";
        const jumpBtn = pid ? `<button type="button" class="btn-quiet" style="font-size: 0.75rem; padding: 3px 8px; border-radius: 6px; border: 1px solid #93c5fd; background: #eff6ff; color: #1d4ed8; font-weight: 700; cursor: pointer;" onclick="jumpToProblemLocation('${pid}', '${groupId}')">🎯 위치</button>` : "";
        const langBadge = langStr ? `<span style="font-size:0.72rem; color:#475569; background:#f1f5f9; border:1px solid #cbd5e1; padding:2px 6px; border-radius:6px; font-weight:600; flex-shrink:0;">${langStr}</span>` : "";

        return `
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 7px 12px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; font-size: 0.83rem; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; overflow: hidden;">
              ${statusBadge}
              <a href="${escapeHtml(pUrl)}" target="_blank" rel="noopener" style="color: #1e293b; font-weight: 700; text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0; max-width: 48%;" title="${pTitle}">${pTitle}</a>
              <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0; overflow: hidden;">
                ${langBadge}
                ${chapterBadge}
                ${tryBadge}
                ${aiWarningBadge}
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
              <span style="font-size: 0.75rem; color: #94a3b8;">${escapeHtml(p.time || "")}</span>
              ${codeBtn}
              ${jumpBtn}
              <button type="button" class="btn-quiet" style="font-size: 0.75rem; padding: 3px 8px; border-radius: 6px; border: 1px solid #cbd5e1; background: #fff; cursor: pointer; color: #475569; font-weight: 600;" onclick="navigator.clipboard.writeText('${pTitle.replace(/'/g, "\\'")}'); if(typeof showToast==='function') showToast('제목 복사됨: ${pTitle.replace(/'/g, "\\'")}');">복사</button>
            </div>
          </div>
        `;
      };

    let itemsHTML = `<div class="timeline-items-wrapper" style="display: flex; flex-direction: column; gap: 6px; max-height: 280px; overflow-y: auto; padding-right: 2px;">`;
    if (!sortedDetails.length && timelineFilterMode === "wrong") {
      itemsHTML += `<div style="text-align: center; color: #94a3b8; padding: 12px; font-size: 0.8rem;">🎉 해당 날짜에는 오답/부분점수 내역이 없습니다. (모두 정답통과)</div>`;
    } else {
      itemsHTML += visibleItems.map(renderItemHTML).join("");
    }

    if (hiddenItems.length > 0) {
      const hiddenHTML = hiddenItems.map(renderItemHTML).join("");
      itemsHTML += `
        <div class="timeline-more-items" style="display: none; flex-direction: column; gap: 6px; margin-top: 6px;">
          ${hiddenHTML}
        </div>
        <button type="button" class="btn-secondary timeline-more-btn" style="margin-top: 6px; font-size: 0.78rem; padding: 6px 12px; border-radius: 8px; border: 1px solid #cbd5e1; background: #ffffff; color: #475569; font-weight: 700; cursor: pointer; text-align: center;" onclick="const el = this.previousElementSibling; const isHidden = el.style.display === 'none'; el.style.display = isHidden ? 'flex' : 'none'; this.textContent = isHidden ? '🔼 ${hiddenItems.length}개 문제 접기' : '➕ 외 ${hiddenItems.length}개 문제 더보기';">
          ➕ 외 ${hiddenItems.length}개 문제 더보기
        </button>
      `;
    }
    itemsHTML += `</div>`;

    card.innerHTML = headHTML + itemsHTML;
    frag.appendChild(card);
  });

  streakGrid.replaceChildren(frag);
}

async function fetchStreakData(days) {
  const cfg = window.APP_CONFIG || (typeof CFG_MAIN !== "undefined" ? CFG_MAIN : (window.CFG_MAIN || {}));
  const user = (typeof viewUsername !== "undefined" && viewUsername) ? viewUsername : "";
  let targetUser = (user || cfg.userUuid || cfg.viewUsername || "").trim();
  if (!targetUser) {
    return [];
  }
  const url = `/api/streak?viewMode=${viewMode}&viewUsername=${encodeURIComponent(targetUser)}&username=${encodeURIComponent(targetUser)}&days=${days}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const txt = await res.text();
    console.error("streak api error:", res.status, txt);
    throw new Error(`API request failed (${res.status})`);
  }
  const payload = await res.json();
  const streakList = Array.isArray(payload) ? payload : (payload.streak_data || []);
  return normalizeStreakData(streakList);
}

async function refreshStreak(days) {
  const windowDays = Math.max(days * 2, 14);
  const full = await fetchStreakData(windowDays);
  const current = full.slice(-days);
  const prev = full.slice(Math.max(0, full.length - days * 2), full.length - days);
  streakCurrentDays = days;
  streakLatestCurrent = current;
  streakLatestPrev = prev;
  renderStreakByFilter();
}

function renderStreakByFilter() {
  const visible = streakActiveOnly
    ? streakLatestCurrent.filter((d) => Number(d.count || 0) > 0)
    : streakLatestCurrent;
  renderStreakGrid(visible, {
    days: streakCurrentDays,
    prevData: streakLatestPrev,
    summaryData: streakLatestCurrent,
  });
}

function setActiveOnlyFilter(next) {
  streakActiveOnly = Boolean(next);
  if (streakActiveOnlyToggle) {
    streakActiveOnlyToggle.setAttribute("aria-pressed", streakActiveOnly ? "true" : "false");
    streakActiveOnlyToggle.textContent = streakActiveOnly ? "전체 보기" : "활동일만";
  }
  renderStreakByFilter();
}

(function primeInitialGrid() {
  const initialDays = streakCurrentDays;
  document.querySelectorAll(".streak-btn").forEach((b) => {
    if (Number(b.dataset.days) === initialDays) b.classList.add("active");
  });
  setActiveOnlyFilter(false);
  streakActiveOnlyToggle?.addEventListener("click", () => {
    setActiveOnlyFilter(!streakActiveOnly);
  });
  document.querySelectorAll(".streak-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const days = Number(btn.dataset.days);
      if (!days) return;
      document.querySelectorAll(".streak-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      try {
        await refreshStreak(days);
      } catch (e) {
        console.error("Failed to switch streak days:", e);
      }
    });
  });
  refreshStreak(initialDays).catch((err) => {
    console.error("initial streak compare failed:", err);
  });
})();
