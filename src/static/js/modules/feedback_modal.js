/**
 * feedback_modal.js
 * 피드백 작성 모달 전용 JavaScript 모듈
 * (_feedback_modal.html 인라인 <script> 723줄 분리본)
 *
 * 의존성:
 *   - /static/js/ai_prompt.js  (getAiPrompt 함수 제공)
 *   - window.APP_CONFIG        (index.html 인라인 설정)
 *   - window.getBasketItems / window.WorkspaceBasket (장바구니 연동)
 */

/* ─── 전역 모달 상태 ─────────────────────────────────────── */

let feedbackModalState = {
  name: "",
  studentId: "",
  userUuid: "",
  solvedTitles: [],
  wrongTitles: [],
  todayProblems: [],
  basketProblems: [],
  submissionCodes: {}
};

/* ─── 토스트 알림 ───────────────────────────────────────── */

function showModalToast(message, duration = 3000) {
  let toast = document.getElementById("modalToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "modalToast";
    toast.classList.add("modal-toast");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, duration);
}

/* ─── 클립보드 복사 ─────────────────────────────────────── */

async function modalCopyToClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
  } else {
    let textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand("copy");
    } catch (err) {
      throw new Error("execCommand failed");
    } finally {
      textArea.remove();
    }
  }
}

/* ─── 텍스트에어리어 자동 높이 확장 ───────────────────────── */

function autoExpandModalTextarea(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = el.scrollHeight + "px";
}

/* ─── 빠른 태그 버튼 활성 상태 동기화 ─────────────────────── */

function updateQuickTagActiveStates() {
  const el = document.getElementById("modalTeacherMemo");
  const val = el ? el.value : "";
  document.querySelectorAll(".quick-tag-btn").forEach((btn) => {
    const tagText = btn.textContent.trim();
    if (val.includes(tagText)) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
}

/* ─── 카카오톡 실시간 미리보기 갱신 ───────────────────────── */

function updateLiveKakaoPreview() {
  const commentEl = document.getElementById("modalHomeworkComment");
  const comment = commentEl ? commentEl.value.trim() : "";
  const previewText = buildKakaoMessage(comment);
  const previewEl = document.getElementById("modalKakaoPreview");
  if (previewEl) {
    previewEl.textContent = previewText;
  }
}

/* ─── 빠른 태그 토글 ────────────────────────────────────── */

function toggleQuickTag(textareaId, tagText) {
  const el = document.getElementById(textareaId);
  if (!el) return;
  let val = el.value.trim();
  if (val.includes(tagText)) {
    val = val.replace(tagText, "").replace(/,\s*,/g, ",").replace(/^,\s*|\s*,\s*$/g, "").trim();
  } else {
    val = val ? `${val}, ${tagText}` : tagText;
  }
  el.value = val;
  autoExpandModalTextarea(el);
  updateQuickTagActiveStates();
  updateLiveKakaoPreview();
}

/* ─── 알림 모드 변경 핸들러 ─────────────────────────────── */

function handleNoticeModeChange(mode) {
  const hwWrapper = document.getElementById("wrapperShowHomeworkList");
  const rvWrapper = document.getElementById("wrapperShowReviewList");
  const homeworkCheck = document.getElementById("modalShowHomeworkList");
  const reviewCheck = document.getElementById("modalShowReviewList");

  if (mode === "homework") {
    if (hwWrapper) hwWrapper.style.display = "flex";
    if (rvWrapper) rvWrapper.style.display = "none";
    if (homeworkCheck) homeworkCheck.checked = true;
    if (reviewCheck) reviewCheck.checked = false;
  } else if (mode === "review") {
    if (hwWrapper) hwWrapper.style.display = "none";
    if (rvWrapper) rvWrapper.style.display = "flex";
    if (homeworkCheck) homeworkCheck.checked = false;
    if (reviewCheck) reviewCheck.checked = true;
  } else if (mode === "comment") {
    if (hwWrapper) hwWrapper.style.display = "none";
    if (rvWrapper) rvWrapper.style.display = "none";
    if (homeworkCheck) homeworkCheck.checked = false;
    if (reviewCheck) reviewCheck.checked = false;
  }
  updateLiveKakaoPreview();
}

/* ─── 텍스트에어리어 이벤트 바인딩 ─────────────────────────── */

document.querySelectorAll(".feedback-textarea").forEach((ta) => {
  ta.addEventListener("input", function () {
    autoExpandModalTextarea(this);
    if (this.id === "modalTeacherMemo") updateQuickTagActiveStates();
    if (this.id === "modalHomeworkComment") updateLiveKakaoPreview();
  });
  ta.addEventListener("change", function () {
    autoExpandModalTextarea(this);
    if (this.id === "modalTeacherMemo") updateQuickTagActiveStates();
    if (this.id === "modalHomeworkComment") updateLiveKakaoPreview();
  });
});

/* ─── 옵션 설정 로컬스토리지 복원 ──────────────────────────── */

function loadFeedbackOptionPreferences() {
  const savedGreeting = localStorage.getItem("feedback_opt_greeting");
  if (savedGreeting !== null) {
    const el = document.getElementById("modalIncludeGreeting");
    if (el) el.checked = (savedGreeting === "true");
  }
  const savedAccount = localStorage.getItem("feedback_opt_solve_account");
  if (savedAccount !== null) {
    const el = document.getElementById("modalShowSolveAccount");
    if (el) el.checked = (savedAccount === "true");
  }
}

/* ─── 옵션 변경 이벤트 → 로컬스토리지 저장 ─────────────────── */

document.querySelectorAll('input[name="modalNoticeMode"], #modalIncludeGreeting, #modalShowSolveAccount, #modalShowHomeworkList, #modalShowReviewList').forEach((el) => {
  el.addEventListener("change", () => {
    if (el.id === "modalIncludeGreeting") {
      localStorage.setItem("feedback_opt_greeting", el.checked);
    }
    if (el.id === "modalShowSolveAccount") {
      localStorage.setItem("feedback_opt_solve_account", el.checked);
    }
    updateLiveKakaoPreview();
  });
});

/* ─── 장바구니 문제 읽기 ─────────────────────────────────── */

function getActiveBasketProblems() {
  if (typeof window.getBasketItems === "function") {
    return window.getBasketItems() || [];
  }
  if (window.WorkspaceBasket && Array.isArray(window.WorkspaceBasket.basket)) {
    return window.WorkspaceBasket.basket;
  }
  if (Array.isArray(window.basket)) {
    return window.basket;
  }
  return [];
}

/* ─── 제출 결과 분류 (정답 / 부분점수 / 오답) ────────────── */

function classifySubmission(d) {
  if (!d) return { type: "wrong", icon: "🔴", label: "오답", tag: "오답(FAILED 0점)" };
  const score = Number(d.score);
  const result = d.result;
  const status = String(d.status || "").toLowerCase();

  if (result === 0 || status === "solved" || status === "passed" || d.passed === true || (!isNaN(score) && score >= 90)) {
    const scoreVal = !isNaN(score) && score > 0 ? `${score}점` : "100점";
    return { type: "solved", icon: "🟢", label: "정답", tag: `정답(AC ${scoreVal})` };
  } else if ((!isNaN(score) && score > 0 && score < 90) || status === "partial" || result === 8) {
    const scoreVal = !isNaN(score) && score > 0 ? `${score}점` : "부분점수";
    return { type: "partial", icon: "🟡", label: `부분점수 (${scoreVal})`, tag: `부분점수 (${scoreVal})` };
  } else {
    return { type: "wrong", icon: "🔴", label: "오답", tag: "오답(FAILED 0점)" };
  }
}

/* ─── 모달 열기 ─────────────────────────────────────────── */

async function openFeedbackModal(name, studentId, userUuid) {
  loadFeedbackOptionPreferences();
  const basket = getActiveBasketProblems();

  let cleanName = name || studentId || "";
  let cleanId = studentId || name || "";
  const appUsername = (window.APP_CONFIG && (window.APP_CONFIG.viewUsername || window.APP_CONFIG.userUsername)) || "";
  const profileNameEl = document.querySelector(".profile-name");
  const profileName = profileNameEl ? profileNameEl.textContent.trim() : "";
  const resolvedName = appUsername || profileName || "";

  if (cleanName.match(/[0-9a-f]{8}-[0-9a-f]{4}/i) || cleanName === "수강생" || !cleanName) {
    cleanName = resolvedName || "수강생";
  }
  if (cleanId.match(/[0-9a-f]{8}-[0-9a-f]{4}/i) || cleanId === "수강생" || !cleanId) {
    cleanId = resolvedName || cleanName;
  }

  feedbackModalState = {
    name: cleanName,
    studentId: cleanId,
    userUuid: userUuid || studentId,
    solvedTitles: [],
    wrongTitles: [],
    todayProblems: [],
    basketProblems: basket,
    submissionCodes: {}
  };

  document.getElementById("feedbackStudentName").textContent = feedbackModalState.name;
  document.getElementById("feedbackStudentId").textContent = feedbackModalState.studentId;

  // 🎯 숙제 문항 UI 렌더링
  const hwEl = document.getElementById("feedbackHomeworkProblems");
  if (hwEl) {
    if (basket.length > 0) {
      hwEl.innerHTML = basket.map((p, i) => `<strong>${i + 1}.</strong> ${p.title || p.legacy_code}`).join("<br>");
    } else {
      hwEl.innerHTML = "(장바구니 지정 숙제 없음)";
    }
  }

  // 기본 라디오 설정 및 체크박스 동기화
  const modeHwRadio = document.getElementById("modeNoticeHomework");
  const modeRvRadio = document.getElementById("modeNoticeReview");
  const labelHwRadio = document.getElementById("labelNoticeHomework");

  if (basket.length > 0) {
    if (modeHwRadio) { modeHwRadio.disabled = false; modeHwRadio.checked = true; }
    if (labelHwRadio) { labelHwRadio.style.opacity = "1"; labelHwRadio.style.cursor = "pointer"; labelHwRadio.title = ""; }
    handleNoticeModeChange("homework");
  } else {
    if (modeHwRadio) { modeHwRadio.disabled = true; modeHwRadio.checked = false; }
    if (labelHwRadio) { labelHwRadio.style.opacity = "0.45"; labelHwRadio.style.cursor = "not-allowed"; labelHwRadio.title = "장바구니에 출제할 숙제 문제가 없습니다."; }
    if (modeRvRadio) modeRvRadio.checked = true;
    handleNoticeModeChange("review");
  }

  document.getElementById("feedbackTodayLogSummary").innerHTML = "⏳ 풀이로그 및 제출 코드 페치 중...";
  document.getElementById("modalTeacherMemo").value = "";
  document.getElementById("modalHomeworkComment").value = "";
  autoExpandModalTextarea(document.getElementById("modalTeacherMemo"));
  autoExpandModalTextarea(document.getElementById("modalHomeworkComment"));
  updateQuickTagActiveStates();
  updateLiveKakaoPreview();

  document.getElementById("feedbackModal").style.display = "flex";

  // 오늘/최근 풀이로그 비동기 수집
  try {
    const targetQuery = encodeURIComponent(feedbackModalState.studentId || feedbackModalState.userUuid);
    const res = await fetch(`/api/streak?viewMode=user&username=${targetQuery}&viewUsername=${targetQuery}&days=7`);
    if (res.ok) {
      const data = await res.json();
      const streakData = data.streak_data || (Array.isArray(data) ? data : []);

      const nowKst = new Date(new Date().getTime() + (9 * 60 * 60 * 1000));
      const todayMmDd = nowKst.toISOString().slice(5, 10);

      let allDetails = [];
      [...streakData].reverse().forEach(dayObj => {
        const dDate = dayObj.date || "";
        (dayObj.details || []).reverse().forEach(item => {
          allDetails.push({ ...item, dateStr: dDate, weekday: dayObj.weekday || "", isToday: (dDate === todayMmDd) });
        });
      });

      if (allDetails.length > 0) {
        feedbackModalState.todayProblems = allDetails;

        const todayItems = allDetails.filter(d => d.isToday);
        const targetItems = todayItems.length > 0 ? todayItems : allDetails;

        const solvedList = [];
        const partialList = [];
        const wrongList = [];

        targetItems.forEach(d => {
          const cls = classifySubmission(d);
          const titleStr = d.title || d.problem;
          if (cls.type === "solved") solvedList.push(titleStr);
          else if (cls.type === "partial") partialList.push(titleStr);
          else wrongList.push(titleStr);
        });

        feedbackModalState.solvedTitles = Array.from(new Set(solvedList.length > 0 ? solvedList : targetItems.map(d => d.title)));
        feedbackModalState.wrongTitles = Array.from(new Set([...partialList, ...wrongList]));

        // 소스코드 수집 (오답/부분점수 우선, 최대 5개)
        const wrongAndPartialItems = targetItems.filter(d => { const cls = classifySubmission(d); return cls.type === "wrong" || cls.type === "partial"; });
        const solvedItems = targetItems.filter(d => { const cls = classifySubmission(d); return cls.type === "solved"; });

        const selectedForCode = [];
        const addedSubIds = new Set();

        wrongAndPartialItems.forEach(item => {
          if (selectedForCode.length < 5 && item.server_sub_id && !addedSubIds.has(item.server_sub_id)) {
            selectedForCode.push(item);
            addedSubIds.add(item.server_sub_id);
          }
        });
        solvedItems.forEach(item => {
          if (selectedForCode.length < 5 && item.server_sub_id && !addedSubIds.has(item.server_sub_id)) {
            selectedForCode.push(item);
            addedSubIds.add(item.server_sub_id);
          }
        });

        await Promise.all(selectedForCode.map(async (sub) => {
          if (sub.server_sub_id) {
            try {
              const codeRes = await fetch(`/api/submission_code?id=${encodeURIComponent(sub.server_sub_id)}`);
              if (codeRes.ok) {
                const codeData = await codeRes.json();
                if (codeData.code) { feedbackModalState.submissionCodes[sub.server_sub_id] = codeData.code; }
              }
            } catch(e) {}
          }
        }));

        let summaryHTML = "";
        if (todayItems.length > 0) {
          summaryHTML += `<strong style="color:#10b981;">✨ 오늘 수업 실습 ${todayItems.length}건</strong> (정답 ${solvedList.length}개 / 부분점수 ${partialList.length}개 / 오답 ${wrongList.length}개)<br><br>`;
        } else {
          summaryHTML += `<strong style="color:#64748b;">🗓 오늘 제출 없음 (최근 7일 실습 ${allDetails.length}건 - 정답 ${solvedList.length}개 / 부분 ${partialList.length}개 / 오답 ${wrongList.length}개)</strong><br><br>`;
        }

        summaryHTML += targetItems.slice(0, 8).map(d => {
          const cls = classifySubmission(d);
          const datePrefix = d.isToday ? `[오늘 ${d.time || ""}]` : `[${d.dateStr || ""} ${d.time || ""}]`;
          const codeBadge = d.server_sub_id && feedbackModalState.submissionCodes[d.server_sub_id] ? " <span style='font-size:0.7rem; color:#6c5ce7; background:#ede9fe; padding:1px 4px; border-radius:4px;'>💻 코드 포함</span>" : "";
          const statusDetail = cls.type === "partial" ? ` <span style="font-size:0.75rem; color:#d97706; font-weight:700;">(${cls.label})</span>` : "";
          return `${cls.icon} ${datePrefix.trim()} ${d.title || d.problem}${statusDetail}${codeBadge}`;
        }).join("<br>");

        document.getElementById("feedbackTodayLogSummary").innerHTML = summaryHTML;
        updateLiveKakaoPreview();
      } else {
        document.getElementById("feedbackTodayLogSummary").innerHTML = "(최근 7일간 실습 및 제출 기록이 없습니다)";
      }
    } else {
      document.getElementById("feedbackTodayLogSummary").innerHTML = "(풀이로그 API 응답 오류)";
    }
  } catch (e) {
    document.getElementById("feedbackTodayLogSummary").innerHTML = "(풀이로그 로드 예외 발생)";
  }
}

/* ─── 모달 닫기 ─────────────────────────────────────────── */

function closeFeedbackModal() {
  document.getElementById("feedbackModal").style.display = "none";
}

document.getElementById("feedbackModal")?.addEventListener("mousedown", (e) => {
  if (e.target.id === "feedbackModal") {
    closeFeedbackModal();
  }
});

/* ─── AI 피드백 직접 생성 (Gemini API) ─────────────────────── */

async function generateModalAiFeedback() {
  const btn = document.getElementById("modalGenerateAiBtn");
  const commentEl = document.getElementById("modalHomeworkComment");
  if (!commentEl) return;

  // ── 프롬프트 조립 (copyModalAiPrompt 와 동일한 방식) ──────
  const memoVal = document.getElementById("modalTeacherMemo").value.trim() || "";
  const basket = feedbackModalState.basketProblems || getActiveBasketProblems();
  const selectedMode = document.querySelector('input[name="modalNoticeMode"]:checked')?.value || "homework";

  let problemsSummary = "";
  if (selectedMode === "homework") {
    problemsSummary = basket.length > 0
      ? `  * 신규 출제 숙제 (${basket.length}개): ${basket.map(p => p.title || p.legacy_code).join(", ")}\n`
      : "  * (신규 숙제 지정 내역 없음)\n";
  } else if (selectedMode === "review") {
    problemsSummary = feedbackModalState.solvedTitles.length > 0
      ? `  * 복습 권장 문항 (${feedbackModalState.solvedTitles.length}개): ${feedbackModalState.solvedTitles.join(", ")}\n`
      : "  * (복습 권장 문항 지정 내역 없음)\n";
  }

  let todaySolvingLogStr = "";
  if (feedbackModalState.todayProblems && feedbackModalState.todayProblems.length > 0) {
    const items = [...feedbackModalState.todayProblems].sort((a, b) => {
      const ca = a.server_sub_id && feedbackModalState.submissionCodes[a.server_sub_id] ? 1 : 0;
      const cb = b.server_sub_id && feedbackModalState.submissionCodes[b.server_sub_id] ? 1 : 0;
      return cb - ca;
    }).slice(0, 8);
    todaySolvingLogStr = items.map((p, idx) => {
      const cls = classifySubmission(p);
      const datePrefix = p.isToday ? `[오늘 ${p.time || ""}]` : `[${p.dateStr || ""} ${p.time || ""}]`;
      const titleText = p.title || p.problem || "문제";
      const code = p.server_sub_id ? feedbackModalState.submissionCodes[p.server_sub_id] : null;
      let line = `${idx + 1}. ${datePrefix.trim()} ${titleText} | 결과: ${cls.tag}`;
      if (code) line += `\n   - 제출 코드:\n\`\`\`\n${code.trim()}\n\`\`\``;
      return line;
    }).join("\n\n");
  }

  const finalMemo = memoVal || "오늘 수업에 차분하고 성실하게 임함 (특이사항 없음)";
  let prompt = "";
  if (typeof getAiPrompt === "function") {
    prompt = getAiPrompt(problemsSummary, finalMemo, todaySolvingLogStr, selectedMode);
  }
  if (!prompt) {
    // Fallback: 기존 복사 방식으로 전환
    showModalToast("⚠️ 프롬프트 생성 실패 – 수동 복사 방식으로 전환합니다.");
    await copyModalAiPrompt();
    return;
  }

  // ── 버튼 로딩 상태 ────────────────────────────────────────
  const originalText = btn ? btn.innerHTML : "";
  if (btn) { btn.disabled = true; btn.innerHTML = "⏳ AI 작성 중..."; }

  try {
    const res = await fetch("/api/workspace/generate_ai_feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const data = await res.json();

    if (data.ok && data.feedback) {
      commentEl.value = data.feedback;
      commentEl.dispatchEvent(new Event("input"));  // 실시간 미리보기 갱신 트리거
      try { await navigator.clipboard.writeText(data.feedback); } catch (_) {}
      showModalToast("🪄 AI 피드백 생성 완료! (텍스트 영역에 자동 입력 & 클립보드 복사)");
    } else if (data.code === "NO_KEY") {
      showModalToast("⚠️ GEMINI_API_KEY 미설정 – 프롬프트 복사 방식으로 전환합니다.");
      await copyModalAiPrompt();
    } else {
      showModalToast(`⚠️ AI 생성 오류: ${data.error || "알 수 없는 오류"} – 프롬프트 복사 방식으로 전환합니다.`);
      await copyModalAiPrompt();
    }
  } catch (err) {
    showModalToast("⚠️ 네트워크 오류 – 프롬프트 복사 방식으로 전환합니다.");
    await copyModalAiPrompt();
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
  }
}

/* ─── AI 프롬프트 복사 ──────────────────────────────────── */

async function copyModalAiPrompt() {
  const memoVal = document.getElementById("modalTeacherMemo").value.trim() || "";
  const basket = feedbackModalState.basketProblems || getActiveBasketProblems();
  const selectedMode = document.querySelector('input[name="modalNoticeMode"]:checked')?.value || "homework";

  let problemsSummary = "";
  if (selectedMode === "homework") {
    if (basket.length > 0) {
      problemsSummary = `  * 신규 출제 숙제 (${basket.length}개): ${basket.map(p => p.title || p.legacy_code).join(", ")}\n`;
    } else {
      problemsSummary = "  * (신규 숙제 지정 내역 없음)\n";
    }
  } else if (selectedMode === "review") {
    if (feedbackModalState.solvedTitles.length > 0) {
      problemsSummary = `  * 복습 권장 문항 (${feedbackModalState.solvedTitles.length}개): ${feedbackModalState.solvedTitles.join(", ")}\n`;
    } else {
      problemsSummary = "  * (복습 권장 문항 지정 내역 없음)\n";
    }
  } else {
    // comment (코멘트만 모드): 숙제 및 복습 목록 제외
    problemsSummary = "";
  }

  let todaySolvingLogStr = "";
  if (feedbackModalState.todayProblems && feedbackModalState.todayProblems.length > 0) {
    const itemsForPrompt = [...feedbackModalState.todayProblems].sort((a, b) => {
      const codeA = a.server_sub_id && feedbackModalState.submissionCodes[a.server_sub_id] ? 1 : 0;
      const codeB = b.server_sub_id && feedbackModalState.submissionCodes[b.server_sub_id] ? 1 : 0;
      return codeB - codeA;
    }).slice(0, 8);

    todaySolvingLogStr = itemsForPrompt.map((p, idx) => {
      const cls = classifySubmission(p);
      const datePrefix = p.isToday ? `[오늘 ${p.time || ""}]` : `[${p.dateStr || ""} ${p.time || ""}]`;
      const titleText = p.title || p.problem || "문제";
      const code = p.server_sub_id ? feedbackModalState.submissionCodes[p.server_sub_id] : null;
      let logLine = `${idx + 1}. ${datePrefix.trim()} ${titleText} | 결과: ${cls.tag}`;
      if (code) {
        logLine += `\n   - 제출 코드 (${p.language || "c"}):\n\`\`\`\n${code.trim()}\n\`\`\``;
      }
      return logLine;
    }).join("\n\n");
  }

  const finalMemo = memoVal || "오늘 수업에 차분하고 성실하게 임함 (특이사항 없음)";
  
  let promptText = "";
  if (typeof getAiPrompt === "function") {
    promptText = getAiPrompt(problemsSummary, finalMemo, todaySolvingLogStr, selectedMode);
  } else {
    // 안전 fallback 프롬프트 (모드별 분기)
    if (selectedMode === "comment") {
      promptText = `[역할]
너는 코딩학원 전문 강사의 학부모 알림장 작성 전문 비서야.
아래 제공된 [오늘 수업 실습 로그 및 제출 코드], [교사 관찰 메모]를 바탕으로 학부모님께 오늘 수업의 실제 과정과 학생의 학습 태도를 명확히 전달하는 정중하고 차분한 피드백 코멘트(존댓말, 2~3문장, 약 150~250자)를 작성해줘.

[작성 조건]
1. 무조건적인 칭찬을 지양하고, [실제 겪은 시행착오/오류 탐색 ➔ 스스로 해결한 디버깅 과정 및 지도 ➔ 학습 태도 및 성취 피드백]의 흐름으로 사실에 기반하여 전문성 있게 서술해줘.
2. 오답, 부분점수, 컴파일에러 또는 관찰 메모의 특이사항이 있다면 이를 숨기지 말되, '오답 발생' 같은 부정적 단정 대신 '조건/예외 처리 오류를 마주했으나 디버깅을 통해 교정'과 같이 문제 해결 및 디버깅 경험으로 프레이밍해줘.
3. 과장되거나 상투적인 AI 어투 및 감탄사("눈부신 발전", "화이팅! 🚀")를 배제하고 담백한 서술체(~했습니다, ~하도록 지도했습니다)로 작성해줘.
4. 문장 끝에 '앞으로도 세심히 지도하겠습니다' 등의 상투적인 다짐이나 억지 숙제/복습 언급은 절대 하지 말고 깔끔하게 끝맺어줘.
5. 오직 복사해서 알림장에 바로 쓸 최종 코멘트 텍스트만 출력해줘.

[정보]
${todaySolvingLogStr ? `- 오늘 수업 실습 로그 및 학생 제출 코드:\n${todaySolvingLogStr}\n` : ""}- 교사 관찰 메모: ${finalMemo}`;
    } else if (selectedMode === "review") {
      promptText = `[역할]
너는 코딩학원 전문 강사의 학부모 알림장 작성 전문 비서야.
아래 제공된 [오늘 수업 실습 로그 및 제출 코드], [복습 권장 문항], [교사 관찰 메모]를 바탕으로 학부모님께 오늘 수업의 실제 과정과 복습 포인트를 명확히 전달하는 정중하고 차분한 피드백 코멘트(존댓말, 2~3문장, 약 150~250자)를 작성해줘.

[작성 조건]
1. 무조건적인 칭찬을 지양하고, [실제 겪은 시행착오/오류 탐색 ➔ 스스로 해결한 디버깅 과정 및 지도 ➔ 오늘 배운 개념 복습 권장]의 3단 인과관계로 사실에 기반하여 전문성 있게 서술해줘.
2. 오답, 부분점수, 컴파일에러 또는 관찰 메모의 특이사항이 있다면 이를 숨기지 말되, '오답 발생' 대신 '조건/예외 처리 오류 디버깅 및 교정 과정'으로 전문성 있게 프레이밍해줘.
3. 과장되거나 상투적인 AI 어투 및 감탄사를 배제하고 담백한 서술체(~했습니다, ~하도록 지도했습니다)로 작성해줘.
4. 문장 끝에 '앞으로도 세심히 지도하겠습니다' 등의 상투적인 다짐 멘트는 절대로 작성하지 말고 복습 안내로 깔끔하게 끝맺어줘.
5. 오직 복사해서 알림장에 바로 쓸 최종 코멘트 텍스트만 출력해줘.

[정보]
${todaySolvingLogStr ? `- 오늘 수업 실습 로그 및 학생 제출 코드:\n${todaySolvingLogStr}\n` : ""}- 복습 권장 문항:
${problemsSummary.trim()}
- 교사 관찰 메모: ${finalMemo}`;
    } else {
      promptText = `[역할]
너는 코딩학원 전문 강사의 학부모 알림장 작성 전문 비서야.
아래 제공된 [오늘 수업 실습 로그 및 제출 코드], [숙제 지정 내역], [교사 관찰 메모]를 바탕으로 학부모님께 오늘 수업의 실제 과정과 학습 보완점을 명확히 전달하는 정중하고 차분한 피드백 코멘트(존댓말, 2~3문장, 약 150~250자)를 작성해줘.

[작성 조건]
1. 무조건적인 칭찬을 지양하고, [실제 겪은 시행착오/오류 탐색 ➔ 스스로 해결한 디버깅 과정 및 지도 ➔ 앞으로의 보완점/과제 연계]의 3단 인과관계로 사실에 기반하여 전문성 있게 서술해줘.
2. 오답, 부분점수, 컴파일에러 또는 관찰 메모의 특이사항이 있다면 이를 숨기지 말되, '오답 발생' 대신 '조건/예외 처리 오류 디버깅 및 교정 과정'으로 전문성 있게 프레이밍해줘.
3. 과장되거나 상투적인 AI 어투 및 감탄사("눈부신 발전", "화이팅! 🚀")를 배제하고 담백한 서술체(~했습니다, ~하도록 지도했습니다)로 작성해줘.
4. 문장 끝에 '앞으로도 세심히 지도하겠습니다' 등의 상투적인 마무리 다짐 멘트는 절대로 작성하지 말고 2~3문장으로 깔끔하게 끝맺어줘.
5. 오직 복사해서 알림장에 바로 쓸 최종 코멘트 텍스트만 출력해줘.

[정보]
${todaySolvingLogStr ? `- 오늘 수업 실습 로그 및 학생 제출 코드:\n${todaySolvingLogStr}\n` : ""}- 숙제 지정 내역:
${problemsSummary.trim()}
- 교사 관찰 메모: ${finalMemo}`;
    }
  }

  try {
    await modalCopyToClipboard(promptText);
    showModalToast("📋 AI 프롬프트 복사 완료!\n(제출 코드 & 시간 기록이 포함되었습니다. ChatGPT/Claude에 붙여넣으세요)");
  } catch (err) {
    alert("프롬프트 복사 실패: " + err.message);
  }
}

/* ─── 카카오톡 알림장 메시지 생성 ──────────────────────────── */

function buildKakaoMessage(comment) {
  const { name, studentId, basketProblems, solvedTitles, todayProblems } = feedbackModalState;
  const basket = basketProblems && basketProblems.length > 0 ? basketProblems : getActiveBasketProblems();
  const includeGreeting = document.getElementById("modalIncludeGreeting")?.checked;
  const includeSolveAccount = document.getElementById("modalShowSolveAccount")?.checked;
  const selectedMode = document.querySelector('input[name="modalNoticeMode"]:checked')?.value || "homework";
  const showHomeworkList = document.getElementById("modalShowHomeworkList")?.checked;
  const showReviewList = document.getElementById("modalShowReviewList")?.checked;

  const todayObj = new Date();
  const daysKR = ["일", "월", "화", "수", "목", "금", "토"];
  const y = todayObj.getFullYear();
  const m = String(todayObj.getMonth() + 1).padStart(2, "0");
  const d = String(todayObj.getDate()).padStart(2, "0");
  const dateFormatted = `${y}.${m}.${d}(${daysKR[todayObj.getDay()]})`;

  let text = "";

  if (includeGreeting) {
    text += "안녕하세요 두잉창의코딩학원입니다. 😊\n";
  }
  if (includeSolveAccount && studentId) {
    const displayAcc = (name && name !== studentId) ? `${name} (${studentId})` : studentId;
    text += `🔑 로그인 계정: ${displayAcc}\n`;
  }

  if (selectedMode === "homework" && basket.length > 0) {
    text += "수업 피드백 및 숙제 안내드립니다.\n\n";
    if (comment) { text += `📝 [수업 피드백 & 태도]\n${comment}\n\n`; text += `---------------------------------\n`; }
    text += `📖 [숙제 안내]\n\n`;

    const groupsMap = new Map();
    basket.forEach((prob) => {
      let chapterCode = prob.chapter_code || prob.chapter_id || prob.curriculum || "";
      let subTitle = prob.group_title || prob.sub || prob.chapter_title || "코딩 실습 및 숙제";
      const groupKey = `${chapterCode || "nocode"}:::${subTitle}`;
      if (!groupsMap.has(groupKey)) groupsMap.set(groupKey, { chapterCode, subTitle, problems: [] });
      groupsMap.get(groupKey).problems.push(prob);
    });

    const formatDoingcodingTag = (str) => String(str || "").trim().replace(/^([A-Za-z]*Lv\d+)\.\s*/i, "$1 ").trim();

    const domain = "http://edu.doingcoding.com";
    const groupEntries = Array.from(groupsMap.values());
    groupEntries.forEach((grp, idx) => {
      text += `📘 ${grp.subTitle}\n`;
      if (grp.chapterCode) {
        const cleanTag = formatDoingcodingTag(grp.subTitle);
        text += `🔗 ${domain}/${grp.chapterCode}?tag=${encodeURIComponent(cleanTag)}\n`;
      } else if (grp.problems && grp.problems.length === 1 && (grp.problems[0].url || grp.problems[0].pid || grp.problems[0].legacy_code)) {
        const pUrl = grp.problems[0].url || `${domain}/problem/${grp.problems[0].pid || grp.problems[0].legacy_code}`;
        text += `🔗 ${pUrl}\n`;
      } else {
        text += `🔗 ${domain}\n`;
      }
      if (showHomeworkList) { grp.problems.forEach((p) => { text += `  ${p.title || p.legacy_code}\n`; }); }
      if (idx < groupEntries.length - 1) text += `\n`;
    });

    text += `\n🗓 출제일: ${dateFormatted}\n`;
    text += `⏰ 마감: 다음 수업시간 전까지\n`;
    text += "=========================";

  } else if (selectedMode === "review" && ((todayProblems && todayProblems.length > 0) || (solvedTitles && solvedTitles.length > 0))) {
    text += "오늘 수업 피드백 및 복습 안내드립니다.\n\n";

    if (!showReviewList) {
      text += `📝 [수업 피드백 & 태도]\n${comment || "오늘 수업에 집중하여 성실히 문제 풀이를 작성하였습니다."}\n\n`;
      text += `🗓 수업일: ${dateFormatted}\n`;
      text += "=========================";
    } else {
      if (comment) { text += `📝 [수업 피드백 & 태도]\n${comment}\n\n`; text += `---------------------------------\n`; }
      text += `🔄 [오늘 학습 복습 문제 목록]\n\n`;

      const groupsMap = new Map();
      const problemItems = (todayProblems && todayProblems.length > 0) ? todayProblems : (solvedTitles || []).map(t => ({ title: t }));
      problemItems.forEach((prob) => {
        let chapterCode = (typeof prob === "object" && (prob.chapter_code || prob.chapter_id || prob.curriculum)) || "";
        let subTitle = (typeof prob === "object" && (prob.group_title || prob.sub || prob.chapter_title)) || "기타 실습 문제";
        const probTitle = typeof prob === "object" ? (prob.title || prob.legacy_code || "") : String(prob || "");
        const groupKey = `${chapterCode || "nocode"}:::${subTitle}`;
        if (!groupsMap.has(groupKey)) groupsMap.set(groupKey, { chapterCode, subTitle, problems: [] });
        groupsMap.get(groupKey).problems.push(probTitle);
      });

      Array.from(groupsMap.values()).forEach((grp, idx) => {
        text += `📘 ${grp.subTitle}\n`;
        grp.problems.forEach((pTitle) => { text += `  ${pTitle}\n`; });
        if (idx < groupsMap.size - 1) text += `\n`;
      });
      text += `\n🗓 수업일: ${dateFormatted}\n`;
      text += "=========================";
    }

  } else {
    text += "오늘 수업 피드백 안내드립니다.\n\n";
    const displayName = (name && name !== studentId) ? `${name} 학생` : "오늘";
    text += `📝 [${displayName} 수업 피드백 & 태도]\n${comment || "오늘 수업에 집중하여 성실히 문제 풀이를 작성하였습니다."}\n\n`;
    text += `🗓 수업일: ${dateFormatted}\n`;
    text += "=========================";
  }

  return text;
}

/* ─── 피드백 최종 제출 (복사 + 서버 저장) ──────────────────── */

async function submitModalFeedback() {
  const comment = document.getElementById("modalHomeworkComment").value.trim();
  const selectedMode = document.querySelector('input[name="modalNoticeMode"]:checked')?.value || "homework";

  if (!comment && selectedMode === "comment") {
    showModalToast("⚠️ 3단계에 AI 답변이나 코멘트를 먼저 작성/붙여넣어 주세요!");
    return;
  }

  const { name, studentId, userUuid, basketProblems } = feedbackModalState;
  const basket = basketProblems && basketProblems.length > 0 ? basketProblems : getActiveBasketProblems();
  const finalMsg = buildKakaoMessage(comment);

  try {
    await modalCopyToClipboard(finalMsg);

    const btn = document.getElementById("modalCompleteBtn");
    const originalText = btn.textContent;
    const originalBg = btn.style.background;
    btn.textContent = "⏳ 저장 중...";
    btn.disabled = true;

    const payload = {
      display_id: studentId,
      user_uuid: userUuid,
      problems: basket,
      message: finalMsg,
      comment: comment,
      mode: selectedMode,
      title: selectedMode === "homework" && basket.length > 0
        ? `${name} 학생 숙제 및 피드백 (${basket.length}개)`
        : (selectedMode === "review" ? `${name} 학생 수업 복습 안내` : `${name} 학생 수업 피드백`)
    };

    const res = await fetch(`/api/workspace/save_homework_log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("서버 저장 실패");

    btn.textContent = "✅ 복사 & 저장 완료!";
    btn.style.background = "#10b981";
    showModalToast("📋 카카오톡 알림장 메시지가 복사되었습니다!\n(카카오톡에 Ctrl+V로 붙여넣기 하세요)", 4000);

    if (typeof window.clearQuickBasket === "function") window.clearQuickBasket();
    if (window.WorkspaceBasket && typeof window.WorkspaceBasket.clearBasket === "function") {
      window.WorkspaceBasket.clearBasket();
    }

    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = originalText;
      btn.style.background = originalBg;
      closeFeedbackModal();
    }, 2500);

  } catch (err) {
    showModalToast("저장에 실패했으나 클립보드 복사는 완료되었습니다.");
  }
}

/* ─── 숙제 즉시 출제 ─────────────────────────────────────── */

async function submitDirectHomework() {
  const { name, studentId, userUuid, basketProblems } = feedbackModalState;
  const basket = basketProblems && basketProblems.length > 0 ? basketProblems : getActiveBasketProblems();

  if (basket.length === 0) {
    showModalToast("⚠️ 출제할 문제를 먼저 장바구니에 담아주세요!");
    return;
  }

  const btn = document.getElementById("modalDirectSubmitBtn");
  const originalText = btn.textContent;
  const originalBg = btn.style.background;
  btn.textContent = "⏳ 출제 중...";
  btn.disabled = true;

  try {
    const payload = {
      display_id: studentId,
      user_uuid: userUuid,
      problems: basket,
      title: `${name} 학생 숙제 즉시 출제 (${basket.length}개)`
    };

    const res = await fetch(`/api/workspace/save_homework_log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("출제 실패");

    btn.textContent = "✅ 숙제 즉시 출제 완료!";
    btn.style.background = "#10b981";
    showModalToast(`🚀 [${name}] 학생에게 숙제가 즉시 출제되었습니다! (${basket.length}개)`, 4000);

    if (typeof window.clearQuickBasket === "function") window.clearQuickBasket();
    if (window.WorkspaceBasket && typeof window.WorkspaceBasket.clearBasket === "function") {
      window.WorkspaceBasket.clearBasket();
    }

    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = originalText;
      btn.style.background = originalBg;
      closeFeedbackModal();
    }, 2500);

  } catch (err) {
    btn.disabled = false;
    btn.textContent = originalText;
    btn.style.background = originalBg;
    showModalToast("⚠️ 숙제 출제 실패: " + err.message, 4000);
  }
}
