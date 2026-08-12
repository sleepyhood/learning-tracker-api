/**
 * latest_homework_card.js
 * 최근 숙제 & 수업 피드백 카드 비동기 렌더러
 * (index_view.js Line 1~270 분리본)
 *
 * 의존성:
 *   - window.APP_CONFIG (index.html 인라인 설정)
 *   - openHomeworkHistoryModal() (히스토리 모달, _homework_history_modal.html에서 선언)
 */

(async function mountLatestHomeworkCard() {
  const CFG = window.APP_CONFIG || {};
  const userUuid = CFG.userUuid || CFG.viewUsername || "";
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
  const uname = data.student_name || CFG.viewUsername || profileName || "osw1110";
  displayTitle = displayTitle.replace(/수강생\s*학생/g, `${uname} 학생`);
  displayTitle = displayTitle.replace(/수강생/g, uname);
  displayTitle = displayTitle.replace(/학생\s+학생/g, `${uname} 학생`);
  displayTitle = displayTitle.replace(/([0-9a-f-]{36})\s*학생/gi, `${uname} 학생`);
  displayTitle = displayTitle.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, uname);

  const escHtml = (str) => String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  const rawProblems = Array.isArray(log.problems) ? log.problems : [];

  const getProblemChapterInfo = (p) => {
    let chapterCode = p.chapter_code || p.chapter_id || p.curriculum || "";
    let subTitle = p.group_title || p.chapter_title || p.group_name || p.chapter_name || p.sub || "";
    const titleStr = p.title || p.title_at_issue || p.legacy_code || "";
    if (!subTitle && titleStr) {
      const match = titleStr.match(/\[(.*?)\]/);
      if (match && match[1]) subTitle = match[1].trim();
    }
    if (!subTitle) subTitle = "주요 학습 단원";
    return { chapterCode, subTitle };
  };

  const sortScore = (p) => {
    const st = p.status || "pending";
    if (st === "wrong") return 1;
    if (st === "partial") return 2;
    if (st === "pending") return 3;
    return 4;
  };

  const allOrderedProblems = [...rawProblems].sort((a, b) => sortScore(a) - sortScore(b));

  const renderSingleProblemLi = (p) => {
    const st = p.status || "pending";
    let badge = `<span style="font-size:0.72rem; color:#64748b; background:#f1f5f9; border:1px solid #cbd5e1; padding:1px 6px; border-radius:10px; font-weight:700; flex-shrink:0;">⚪ 대기</span>`;
    if (st === "passed") {
      badge = `<span style="font-size:0.72rem; color:#059669; background:#ecfdf5; border:1px solid #a7f3d0; padding:1px 6px; border-radius:10px; font-weight:700; flex-shrink:0;">🟢 100점</span>`;
    } else if (st === "partial") {
      badge = `<span style="font-size:0.72rem; color:#d97706; background:#fffbeb; border:1px solid #fde68a; padding:1px 6px; border-radius:10px; font-weight:700; flex-shrink:0;">🟡 ${p.score || "50"}점</span>`;
    } else if (st === "wrong") {
      badge = `<span style="font-size:0.72rem; color:#dc2626; background:#fef2f2; border:1px solid #fecaca; padding:1px 6px; border-radius:10px; font-weight:700; flex-shrink:0;">🔴 0점</span>`;
    }
    const code = p.legacy_code ? `<code style="font-size:0.72rem; background:#f1f5f9; color:#475569; padding:1px 5px; border-radius:4px; font-family:monospace; border:1px solid #e2e8f0; flex-shrink:0;">${p.legacy_code}</code>` : "";
    const rawTitle = p.title || p.title_at_issue || "";
    const pUrl = p.url || (p.legacy_code ? `http://edu.doingcoding.com/problem/${encodeURIComponent(String(p.legacy_code))}` : "#");
    return `
      <li style="display:flex; align-items:center; gap:8px; padding:5px 8px; font-size:0.82rem; background:#ffffff; border:1px solid #f1f5f9; border-radius:8px; margin-bottom:4px;">
        ${badge} ${code}
        <a href="${escHtml(pUrl)}" target="_blank" rel="noopener" style="flex:1; min-width:0; color:#1e293b; font-weight:600; text-decoration:none; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escHtml(rawTitle)}">${escHtml(rawTitle)}</a>
      </li>`;
  };

  const domain = "http://edu.doingcoding.com";
  const renderProblemsByChapterHTML = (probList) => {
    const gMap = new Map();
    probList.forEach((p) => {
      const { chapterCode, subTitle } = getProblemChapterInfo(p);
      const key = `${chapterCode || "nocode"}:::${subTitle}`;
      if (!gMap.has(key)) gMap.set(key, { chapterCode, subTitle, items: [] });
      gMap.get(key).items.push(p);
    });
    let html = "";
    gMap.forEach((grp) => {
      const chapterUrl = grp.chapterCode ? `${domain}/${grp.chapterCode}?tag=${encodeURIComponent(grp.subTitle)}` : domain;
      html += `
        <div class="homework-chapter-group" style="margin-bottom: 8px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px; padding-bottom: 2px; border-bottom: 1px dashed #cbd5e1;">
            <span style="font-weight: 800; font-size: 0.82rem; color: #1d4ed8; display: flex; align-items: center; gap: 4px;">
              <span>📘 ${escHtml(grp.subTitle)}</span>
            </span>
            <a href="${chapterUrl}" target="_blank" rel="noopener" style="font-size: 0.73rem; color: #2563eb; text-decoration: none; font-weight: 600;">🔗 단원 바로가기</a>
          </div>
          <ul style="padding-left:0; margin:0; list-style:none;">
            ${grp.items.map(renderSingleProblemLi).join("")}
          </ul>
        </div>`;
    });
    return html;
  };

  const visibleCount = 4;
  const visibleProblems = allOrderedProblems.slice(0, visibleCount);
  const hiddenProblems = allOrderedProblems.slice(visibleCount);

  let homeworkProblemsHTML = `<div class="homework-problems-container" style="margin-top: 6px; max-height: 280px; overflow-y: auto; padding-right: 2px;">`;
  homeworkProblemsHTML += renderProblemsByChapterHTML(visibleProblems);

  if (hiddenProblems.length > 0) {
    homeworkProblemsHTML += `
      <div class="homework-more-problems" style="display: none; margin-top: 6px;">
        ${renderProblemsByChapterHTML(hiddenProblems)}
      </div>
      <button type="button" class="btn-secondary homework-more-btn" style="margin-top: 6px; width: 100%; font-size: 0.78rem; padding: 7px 12px; border-radius: 8px; border: 1px solid #cbd5e1; background: #ffffff; color: #475569; font-weight: 700; cursor: pointer; text-align: center;" onclick="const el = this.previousElementSibling; const isHidden = el.style.display === 'none'; el.style.display = isHidden ? 'block' : 'none'; this.textContent = isHidden ? '🔼 ${hiddenProblems.length}개 숙제 문제 접기' : '➕ 외 ${hiddenProblems.length}개 숙제 문제 더보기';">
        ➕ 외 ${hiddenProblems.length}개 숙제 문제 더보기
      </button>
    `;
  }
  homeworkProblemsHTML += `</div>`;

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

  let commentHTML = "";
  const isHomeworkMode = (mode === "homework" && rawProblems.length > 0);

  if (isHomeworkMode) {
    if (log.comment) {
      commentHTML = `
        <div style="margin-top: 12px;">
          <button class="btn-small btn-secondary" style="font-size:0.78rem; padding:5px 12px; border-radius:8px; font-weight:600; cursor:pointer; display:inline-flex; align-items:center; gap:4px; border:1px solid #cbd5e1; background:#ffffff; color:#334155;" onclick="const el = this.nextElementSibling; const isHidden = el.style.display === 'none'; el.style.display = isHidden ? 'block' : 'none'; this.innerHTML = isHidden ? '🔓 강사 피드백 닫기' : '🔒 강사 피드백 보기';">🔒 강사 피드백 보기</button>
          <div style="display: none; margin-top: 8px; padding: 14px; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 12px; font-size: 0.85rem; color: #3b0764; line-height: 1.5; white-space: pre-wrap;">${escHtml(log.comment)}</div>
        </div>`;
    }
  } else {
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
<article class="card" data-log-id="${log.key || ""}" data-id="${log.id || ""}" style="border-radius:16px; border:1px solid #e2e8f0; box-shadow:0 4px 16px rgba(0,0,0,0.04); padding:20px; display:flex; flex-direction:column; gap:10px; justify-content:flex-start;">
  <div class="card-head" style="display:flex; justify-content:space-between; align-items:center; padding-bottom:10px; border-bottom:1px solid #f1f5f9;">
    <div class="card-title" style="font-weight:800; font-size:1.05rem; color:#1e293b;">${displayTitle}</div>
    ${badgeHTML}
  </div>

  ${progressHTML}
  ${commentHTML}

  <div class="meta" style="font-size: 0.78rem; color: #64748b; display:flex; align-items:center; gap:12px;">
    <span>배정: <strong style="color:#334155;">${formatIsoDate(log.created_at || log.ts)}</strong></span>
    ${log.due_at ? `<span>마감: <strong style="color:#334155;">${formatIsoDate(log.due_at)}</strong></span>` : ""}
  </div>

  ${mode === "homework" && rawProblems.length ? homeworkProblemsHTML : ""}

  <div class="actions" style="margin-top: 4px; display: flex; gap: 8px; justify-content: flex-end; align-items: center; flex-wrap: wrap;">
    ${log.message ? `<button class="btn btn-secondary" style="font-size:0.8rem; padding:8px 14px; border-radius:10px; font-weight:700; background:#6c5ce7; color:white; border:none; cursor:pointer;" onclick="navigator.clipboard.writeText('${safeMsg}'); alert('📋 카카오톡 알림장 메시지가 클립보드에 복사되었습니다!');">📋 카톡 알림장 재복사</button>` : ""}
    <button class="btn btn-quiet" style="font-size:0.8rem; padding:8px 14px; border-radius:10px; font-weight:700; background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; cursor:pointer;" onclick="if(typeof openHomeworkHistoryModal==='function') openHomeworkHistoryModal('${userUuid}'); else alert('히스토리 모달 로딩 중');">📜 전체 히스토리</button>
  </div>
</article>
`;
})();
