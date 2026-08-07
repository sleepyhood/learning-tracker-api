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
    if (score === 100) {
      badgeEl.textContent = "정답 (100점)";
      badgeEl.className = "today-problem-badge pass";
    } else if (score > 0) {
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
}

function renderStreakGrid(streakData, { days = 7, prevData = [], summaryData = null } = {}) {
  if (!streakGrid) return;
  const data = normalizeStreakData(streakData);
  const frag = document.createDocumentFragment();
  const maxDaily = data.reduce((m, d) => Math.max(m, Number(d.count || 0)), 0);

  if (!data.length) {
    streakGrid.innerHTML = `<div class="streak-empty">조건에 맞는 활동일이 없습니다.</div>`;
    setStreakSummary(days, summaryData || data, prevData);
    updateTodayLatestProblem(summaryData || streakLatestCurrent || data);
    return;
  }

  data.forEach((day, idx) => {
    const c = Number(day.count || 0);
    const tier = calcTier(c);
    const prevCount = idx > 0 ? Number(data[idx - 1].count || 0) : 0;
    const state = getStreakState(day, c, prevCount, maxDaily);
    const ratio = maxDaily > 0 ? Math.max(0, Math.min(100, Math.round((c / maxDaily) * 100))) : 0;
    const ratioForUI = c === 0 ? 0 : Math.max(10, ratio);
    const isWeekend = day.weekday === "토" || day.weekday === "일";
    const dateLabel = formatDateLabel(day);

    const cell = document.createElement("div");
    cell.className = "streak-cell";
    if (isWeekend) cell.classList.add("weekend");
    if (day.details && day.details.length) {
      cell.classList.add("has-details");
    } else {
      cell.classList.add("no-details");
    }
    cell.dataset.count = String(c);
    if (tier) cell.dataset.tier = String(tier);
    if (day.date === TODAY_MMDD) cell.dataset.today = "1";
    cell.dataset.state = state.key;
    cell.style.setProperty("--streak-ratio", `${ratioForUI}%`);

    cell.innerHTML = `
<div class="date-info">
  <div class="date-full">${dateLabel}</div>
</div>
<div class="count-wrap">
  <span class="count">${c}</span>
  <span class="count-label">제출</span>
  <span class="streak-mini-track" aria-hidden="true"><span class="streak-mini-fill"></span></span>
</div>
<span class="streak-state-badge ${state.key}">${state.label}</span>
`;

    if (day.details && day.details.length) {
      cell.dataset.details = JSON.stringify(day.details);
    }

    frag.appendChild(cell);
  });

  streakGrid.replaceChildren(frag);
  setStreakSummary(days, summaryData || data, prevData);
  updateTodayLatestProblem(summaryData || streakLatestCurrent || data);
}

async function fetchStreakData(days) {
  const url = `/api/streak?viewMode=${viewMode}&viewUsername=${encodeURIComponent(viewUsername)}&username=${encodeURIComponent(viewUsername)}&days=${days}`;
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
