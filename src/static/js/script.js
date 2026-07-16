// 숙제 모드
let assignMode = false;

function copyToClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  } else {
    // Legacy fallback for insecure HTTP contexts (HTTP + IP address)
    return new Promise((resolve, reject) => {
      try {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand("copy");
        document.body.removeChild(textArea);
        
        if (successful) {
          resolve();
        } else {
          reject(new Error("document.execCommand('copy') failed"));
        }
      } catch (err) {
        reject(err);
      }
    });
  }
}

function getStorageKey() {
  const groupInfo = document.getElementById("groupInfo");
  if (!groupInfo) return "selectedProblems";
  const userUuid = groupInfo.dataset.userUuid || "default_user";
  const groupUrl = groupInfo.dataset.url || "default_group";
  return `selectedProblems_${userUuid}_${groupUrl}`;
}

let selectedProblems = []; // {title, link, chapter}
let lastChecked = null;

let isDragging = false;
let dragStartCheckedState = false;
let dragStartIndex = -1;
let initialStates = [];
let lastMouseX = 0;
let lastMouseY = 0;

let scrollIntervalId = null;
let scrollSpeed = 0;

function startAutoScroll(speed) {
  scrollSpeed = speed;
  if (scrollIntervalId) return;

  function scrollStep() {
    if (!isDragging) {
      stopAutoScroll();
      return;
    }
    window.scrollBy(0, scrollSpeed);
    
    // 스크롤하면서 마우스 아래에 새롭게 지나가는 문제 탐색
    const hoveredEl = document.elementFromPoint(lastMouseX, lastMouseY);
    if (hoveredEl) {
      const problemDiv = hoveredEl.closest(".problem");
      if (problemDiv) {
        const checkboxesArray = Array.from(document.querySelectorAll(".assign-checkbox"));
        const cb = problemDiv.querySelector(".assign-checkbox");
        const currIdx = checkboxesArray.indexOf(cb);
        if (currIdx !== -1) {
          updateDragRange(currIdx, checkboxesArray);
        }
      }
    }
    scrollIntervalId = requestAnimationFrame(scrollStep);
  }
  scrollIntervalId = requestAnimationFrame(scrollStep);
}

function stopAutoScroll() {
  if (scrollIntervalId) {
    cancelAnimationFrame(scrollIntervalId);
    scrollIntervalId = null;
  }
}

function updateDragRange(currentIndex, checkboxesArray) {
  const min = Math.min(dragStartIndex, currentIndex);
  const max = Math.max(dragStartIndex, currentIndex);

  for (let i = 0; i < checkboxesArray.length; i++) {
    let targetState;
    if (i >= min && i <= max) {
      targetState = dragStartCheckedState;
    } else {
      targetState = initialStates[i];
    }

    if (checkboxesArray[i].checked !== targetState) {
      checkboxesArray[i].checked = targetState;
      checkboxesArray[i].dispatchEvent(new Event("change"));
    }
  }
}

let updateAssignUI_scheduled = false;
function scheduleUISync() {
  if (updateAssignUI_scheduled) return;
  updateAssignUI_scheduled = true;
  queueMicrotask(() => {
    const key = getStorageKey();
    sessionStorage.setItem(key, JSON.stringify(selectedProblems));
    updateAssignUI();
    updateAssignUI_scheduled = false;
  });
}

async function postHomeworkLog({
  title,
  url,
  problems,
  message,
  dueAt = null,
  channel = "kakao",
}) {
  const groupInfo = document.getElementById("groupInfo");
  const userUuid = groupInfo?.dataset.userUuid;
  if (!userUuid) {
    console.error("[HW] user_uuid 없음: 로그 저장 불가");
    showToast("⚠️ 로그 저장 실패(user_uuid 없음)");
    throw new Error("user_uuid missing");
  }

  const payload = { title, url, problems, message, channel };
  if (dueAt != null) payload.due_at = dueAt; // null이면 아예 보내지 않음

  const res = await fetch(`/api/students/${userUuid}/homework_logs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const bodyText = await res.text();
  console.log("[HW] save response:", res.status, bodyText);

  if (!res.ok) {
    console.error("숙제 로그 저장 실패:", bodyText);
    showToast("⚠️ 로그 저장 실패(복사는 완료됨)");
    // 필요하면 여기서 throw 유지/제거 선택
  }
}

function goToParentPage() {
  const currentURL = window.location.href;

  // 레벨 3 ➝ 레벨 2
  if (currentURL.includes("/group/")) {
    const newURL = currentURL.split("/group/")[0];
    window.location.href = newURL;
    return;
  }

  // 레벨 2 ➝ 레벨 1 (/chapter/까지 포함된 경우)
  if (currentURL.includes("/chapter/")) {
    const newURL = currentURL.split("/chapter/")[0];
    window.location.href = newURL;
    return;
  }

  // 레벨 1 ➝ 루트 페이지 or 사용자 개요 페이지
  if (currentURL.includes("/user_overview/")) {
    window.location.href = "/"; // 홈으로 이동
    return;
  }

  // 예외 처리: 그래도 못 걸러졌다면 홈으로
  window.location.href = "/";
}

function toggleAll(checked) {
  document
    .querySelectorAll(".assign-checkbox")
    .forEach((cb) => {
      if (cb.checked !== checked) {
        cb.checked = checked;
        cb.dispatchEvent(new Event("change"));
      }
    });
}

function toggleAssignMode() {
  const checkboxes = document.querySelectorAll(".assign-checkbox-wrapper");
  const assignControls = document.getElementById("assignModeControls");
  const problemLinks = document.querySelectorAll(".problem-link");

  assignMode = !assignMode;

  document.body.classList.toggle("assign-mode-active", assignMode);

  checkboxes.forEach((checkbox) => {
    checkbox.style.display = assignMode ? "inline-flex" : "none";
  });

  if (assignControls) {
    assignControls.classList.toggle("hidden", !assignMode);
  }

  problemLinks.forEach((link) => {
    link.classList.toggle("disabled", assignMode);
  });
}

let __copying = false;
async function copySelectedProblems() {
  if (__copying) return;
  __copying = true;

  const selected = [...document.querySelectorAll(".assign-checkbox:checked")];
  if (selected.length === 0) {
    showToast("⚠️ 선택된 문제가 없습니다!");
    __copying = false;
    return;
  }

  const groupInfo = document.getElementById("groupInfo");
  const groupTitle = groupInfo.dataset.title;
  const groupUrl = groupInfo.dataset.url;

  const problemTitles = selected.map((cb) => cb.dataset.title);
  const now = new Date();
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  const assignedDateStr = `${now.getFullYear()}.${String(
    now.getMonth() + 1
  ).padStart(2, "0")}.${String(now.getDate()).padStart(2, "0")}(${
    days[now.getDay()]
  })`;

  const includeGreeting =
    document.getElementById("includeGreeting")?.checked ?? true;
  const greetingLine = includeGreeting ? "안녕하세요 두잉창의코딩학원입니다. 😊\n수업에 해당되는 숙제 부분 안내드립니다.\n" : null;

  const includeUsername =
    document.getElementById("includeUsername")?.checked ?? false;
  const usernameLine = (includeUsername && groupInfo.dataset.username) ? `👤 풀이 계정: ${groupInfo.dataset.username}` : null;

  const commentVal = document.getElementById("homeworkComment")?.value?.trim() ?? "";
  const commentLine = commentVal ? `📝 코멘트: ${commentVal}` : null;

  const textLines = [];
  if (greetingLine) textLines.push(greetingLine);
  textLines.push(`📘 ${groupTitle}`);
  textLines.push(`🔗 ${groupUrl}`);
  if (usernameLine) textLines.push(usernameLine);
  textLines.push(`🗓 출제일: ${assignedDateStr}`);
  textLines.push(`⏰ 마감: 다음 수업시간 전까지`);
  if (commentLine) textLines.push(commentLine);
  textLines.push("");
  textLines.push(...problemTitles);
  textLines.push("=========================");

  const text = textLines.join("\n");

  try {
    await copyToClipboard(text);
    showToast(`📘 ${groupTitle}\n✅ ${problemTitles.length}개 복사 완료`);

    const problemsPayload = selected.map((cb) => ({
      legacy_code: cb.dataset.pid || "",
      title: cb.dataset.title || "",
    }));

    await postHomeworkLog({
      title: groupTitle,
      url: groupUrl,
      problems: problemsPayload,
      message: text,
      // dueAt: 값이 있으면 넣고, 없으면 생략됨
    });
  } catch (err) {
    // 메시지 구분: 복사 실패인지, 로그 실패인지
    alert("작업 중 오류: " + err.message);
  } finally {
    __copying = false;
  }
}

function toggleProblemSelection(problemId) {
  if (!assignMode) return;

  const cb = document.querySelector(`.assign-checkbox[data-pid="${problemId}"]`);
  if (cb) {
    cb.checked = !cb.checked;
    cb.dispatchEvent(new Event("change"));
  }
}

function updateAssignUI() {
  document.querySelectorAll(".problem").forEach((el) => {
    const cb = el.querySelector(".assign-checkbox");
    if (!cb) return;
    const pid = cb.dataset.pid;
    if (selectedProblems.includes(pid)) {
      el.classList.add("assigned");
    } else {
      el.classList.remove("assigned");
    }
  });
}

async function copyAiPrompt() {
  const selected = [...document.querySelectorAll(".assign-checkbox:checked")];
  const memoVal = document.getElementById("teacherMemo")?.value?.trim() || "";

  if (selected.length === 0 && !memoVal) {
    showToast("⚠️ 문제를 선택하거나 관찰 메모를 작성해주세요!");
    return;
  }

  const groupInfo = document.getElementById("groupInfo");
  const username = groupInfo?.dataset.username || "학생";

  const wrong = [];
  const unsolved = [];
  const partial = [];
  const solved = [];

  selected.forEach(cb => {
    const problemDiv = cb.closest(".problem");
    if (!problemDiv) return;
    const title = cb.dataset.title || "";
    if (problemDiv.classList.contains("wrong")) {
      wrong.push(title);
    } else if (problemDiv.classList.contains("unsolved")) {
      unsolved.push(title);
    } else if (problemDiv.classList.contains("partial")) {
      partial.push(title);
    } else if (problemDiv.classList.contains("solved")) {
      solved.push(title);
    }
  });

  let problemsSummary = "";
  if (selected.length > 0) {
    if (wrong.length > 0) {
      problemsSummary += `  * 오답 문항 (${wrong.length}개): ${wrong.join(", ")}\n`;
    }
    if (unsolved.length > 0) {
      problemsSummary += `  * 미완료 문항 (${unsolved.length}개): ${unsolved.join(", ")}\n`;
    }
    if (partial.length > 0) {
      problemsSummary += `  * 부분 점수 문항 (${partial.length}개): ${partial.join(", ")}\n`;
    }
    if (solved.length > 0 && wrong.length === 0 && unsolved.length === 0 && partial.length === 0) {
      problemsSummary += `  * 복습 문항 (${solved.length}개): ${solved.join(", ")}\n`;
    }
    if (!problemsSummary) {
      problemsSummary = "  * 선택된 문항 전체 복습\n";
    }
  } else {
    problemsSummary = "  * (신규 숙제 및 복습용 지정 문항 없음)\n";
  }

  const finalMemo = memoVal || "(없음)";

  const promptText = `[역할]
너는 코딩학원 선생님의 알림장 피드백 코멘트를 작성해주는 전문 비서야.
아래 제공된 [숙제 내역], [교사 관찰 메모]를 바탕으로 학부모님께 알림장으로 보낼 정중하고 신뢰감 있는 코멘트(존댓말)를 작성해줘.

[작성 조건]
1. 과장되거나 상투적인 AI 어투(예: "한 단계 성장할 것입니다", "화이팅! 👍" 등)를 배제하고, 차분하고 담백한 전문 서술체(~했습니다, ~하고자 합니다)로 작성해줘.
2. 부드러운 격려나 친근한 감정 표현(예: ^^, ~, !)은 과하지 않게 아주 살짝만 허용해줘.
3. 코멘트는 총 2~3문장(약 200~300자) 내외의 적절한 길이로 구체적으로 작성해줘.
4. **학생의 학습 태도, 집중도, 진도율 및 학습 행동 분석**에 대해 교사 관찰 메모를 적극 반영하여 서술해줘.
5. **중요: 만약 숙제 정보에 '복습 문항'만 주어지고 오답/미완료 문항이 없다면**, 신규 숙제를 내주는 대신 **오늘 성공적으로 완료한 문제들을 집에서 복습(리뷰)하도록 안내했다는 맥락**으로 작성해줘.
6. **중요: 만약 숙제 정보가 '지정 문항 없음'으로 주어지면**, 신규 과제나 복습에 대한 언급을 완전히 제외하고, **오직 교사 관찰 메모의 내용을 상세하게 다듬어 오늘 수업 태도, 성향, 집중도 중심의 피드백 코멘트**로만 2~3문장을 채워줘.
7. **중요: 코멘트 작성 시 학생의 실제 이름을 직접 언급하지 마세요.** (예: 이름 대신 주어를 생략하거나 '학생은' 등으로 표현)
8. **중요: 다른 인사말이나 설명 없이 오직 복사해서 붙여넣을 '다듬어진 코멘트 텍스트'만 출력해줘.**

[정보]
- 숙제 정보:
${problemsSummary.trim()}
- 교사 관찰 메모: ${finalMemo}

[답변 예시 (참고용)]:
- 예시 A (신규 숙제가 있는 경우):
"오늘 학생은 딴짓 없이 차분하게 수업에 참여했으며, 정해진 시간 이후에도 문제를 더 풀고자 할 정도로 적극적인 학습 태도를 보였습니다. 금일 미완료된 '문자형 배열 및 인덱스 활용' 관련 4개 문항(15~18번)은 다음 시간까지 스스로 보완하며 학습 연속성을 이어갈 수 있도록 숙제로 안내했습니다."
- 예시 B (신규 숙제 없이 복습만 지시하는 경우):
"오늘 학생은 딴짓 없이 차분하게 수업에 참여했으며, 문제 본문에 제시된 조건을 정확히 파악하여 풀이를 완성했습니다. 별도의 신규 숙제는 없으며, 오늘 수업 중에 해결했던 '변수 출력' 문항들을 집에서 가볍게 복습하며 개념을 다질 수 있도록 안내했습니다."
- 예시 C (숙제/복습 지정 없이 수업 관찰 피드백만 하는 경우):
"오늘 학생은 딴짓 없이 차분하게 수업에 참여했으며, 모르는 부분이 나왔을 때 적극적으로 질문하며 해결하려는 자세를 보였습니다. 스스로 오답의 원인을 끝까지 찾아내어 논리적인 문제를 완전히 해결하려는 집중력이 돋보였습니다."`;

  try {
    await copyToClipboard(promptText);
    showToast("📋 AI 프롬프트 복사 완료!\nChatGPT나 Claude에 붙여넣으세요.");
  } catch (err) {
    alert("프롬프트 복사 실패: " + err.message);
  }
}

function selectUnsolved() {
  selectUnsolvedByParity(null); // 기존과 동일: 안 푼 것만 전체 선택
}

/*
  ✅ 안 푼 문제(unsolved + wrong) 중에서 홀/짝 선택
  - 기본: data-pid가 숫자면 그 pid의 홀/짝 사용
  - fallback: pid가 숫자가 아니면 '안 푼 문제' 목록에서의 표시 순서(1부터)를 번호로 사용
*/
function selectUnsolvedByParity(parity /* 'odd' | 'even' | null */) {
  const checkboxes = Array.from(document.querySelectorAll(".assign-checkbox"));
  let unsolvedOrder = 0;

  checkboxes.forEach((cb) => {
    const problemDiv = cb.closest(".problem");
    const isUnsolved =
      problemDiv?.classList.contains("unsolved") ||
      problemDiv?.classList.contains("wrong");

    if (!isUnsolved) {
      if (cb.checked) {
        cb.checked = false;
        cb.dispatchEvent(new Event("change"));
      }
      return;
    }

    unsolvedOrder += 1;

    let num = parseInt(cb.dataset.pid, 10);
    if (Number.isNaN(num)) num = unsolvedOrder;

    let targetChecked = false;
    if (parity === "odd") targetChecked = num % 2 === 1;
    else if (parity === "even") targetChecked = num % 2 === 0;
    else targetChecked = true; // null => 전부 선택

    if (cb.checked !== targetChecked) {
      cb.checked = targetChecked;
      cb.dispatchEvent(new Event("change"));
    }
  });

  // 쉬프트 범위선택 기준 초기화(예상치 못한 range 체크 방지)
  lastChecked = null;
}

function selectUnsolvedOdd() {
  selectUnsolvedByParity("odd");
}

function selectUnsolvedEven() {
  selectUnsolvedByParity("even");
}

document.addEventListener("DOMContentLoaded", () => {
  // 1. sessionStorage로부터 selectedProblems 복구
  try {
    const key = getStorageKey();
    const stored = sessionStorage.getItem(key);
    if (stored) {
      selectedProblems = JSON.parse(stored);
    }
  } catch (e) {
    console.error("Failed to load selectedProblems from sessionStorage", e);
  }

  const checkboxes = document.querySelectorAll(".assign-checkbox");

  // 2. 체크박스 상태 동기화 및 이벤트 리스너 연결
  checkboxes.forEach((checkbox) => {
    const pid = checkbox.dataset.pid;
    if (selectedProblems.includes(pid)) {
      checkbox.checked = true;
    }

    // 상태 변경 감지
    checkbox.addEventListener("change", function () {
      const pid = this.dataset.pid;
      if (this.checked) {
        if (!selectedProblems.includes(pid)) {
          selectedProblems.push(pid);
        }
      } else {
        selectedProblems = selectedProblems.filter((id) => id !== pid);
      }
      scheduleUISync();
    });

    // Shift 클릭 범위 선택 처리
    checkbox.addEventListener("click", function (e) {
      if (!lastChecked) {
        lastChecked = this;
        return;
      }

      if (e.shiftKey) {
        const checkboxesArray = Array.from(
          document.querySelectorAll(".assign-checkbox")
        );
        const start = checkboxesArray.indexOf(this);
        const end = checkboxesArray.indexOf(lastChecked);
        const [min, max] = [Math.min(start, end), Math.max(start, end)];
        const targetState = this.checked;

        for (let i = min; i <= max; i++) {
          if (checkboxesArray[i].checked !== targetState) {
            checkboxesArray[i].checked = targetState;
            checkboxesArray[i].dispatchEvent(new Event("change"));
          }
        }
      }

      lastChecked = this;
    });
  });

  // 3. 마우스 드래그 선택 (Drag-to-Select) 및 단일 클릭 토글 지원 (역순 해제 & 자동 스크롤 지원)
  document.addEventListener("mousedown", (e) => {
    if (!assignMode) return;

    const problemDiv = e.target.closest(".problem");
    if (!problemDiv) return;

    // 링크, 버튼, 입력필드 및 체크박스 자체 클릭은 무시 (브라우저 기본 동작에 위임)
    if (
      e.target.closest("a") ||
      e.target.closest("button") ||
      e.target.closest("input") ||
      e.target.closest(".custom-checkbox")
    ) {
      return;
    }

    const checkbox = problemDiv.querySelector(".assign-checkbox");
    if (!checkbox) return;

    const checkboxesArray = Array.from(
      document.querySelectorAll(".assign-checkbox")
    );
    dragStartIndex = checkboxesArray.indexOf(checkbox);
    if (dragStartIndex === -1) return;

    isDragging = true;
    dragStartCheckedState = !checkbox.checked;

    // 드래그 중 화면 전역 커서 고정을 위해 클래스 추가
    document.body.classList.add("is-dragging-active");

    // 복구용 초기 상태 스냅샷 저장
    initialStates = checkboxesArray.map((cb) => cb.checked);

    // 마우스 초기 위치 추적
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;

    // 드래그 범위 갱신 (첫 문항 반영)
    updateDragRange(dragStartIndex, checkboxesArray);

    // Shift 클릭 연동을 위해 lastChecked 업데이트
    lastChecked = checkbox;

    // 드래그 도중 브라우저 기본 텍스트 선택(블록 지정) 현상 차단
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging || !assignMode) return;

    lastMouseX = e.clientX;
    lastMouseY = e.clientY;

    // 화면 상단/하단 경계 접근 시 스크롤 처리
    const threshold = 60; // 경계선 반응 영역 (px)
    const bottomEdge = window.innerHeight - threshold;
    const topEdge = threshold;

    if (e.clientY > bottomEdge) {
      // 아래로 자동 스크롤 (경계선에 가까울수록 가속)
      const speed = Math.min(15, Math.max(3, (e.clientY - bottomEdge) / 3));
      startAutoScroll(speed);
    } else if (e.clientY < topEdge) {
      // 위로 자동 스크롤
      const speed = -Math.min(15, Math.max(3, (topEdge - e.clientY) / 3));
      startAutoScroll(speed);
    } else {
      stopAutoScroll();
    }
  });

  document.addEventListener("mouseover", (e) => {
    if (!isDragging || !assignMode) return;

    const problemDiv = e.target.closest(".problem");
    if (!problemDiv) return;

    // 링크, 버튼 등은 드래그 중에도 무시
    if (
      e.target.closest("a") ||
      e.target.closest("button") ||
      e.target.closest("input") ||
      e.target.closest(".custom-checkbox")
    ) {
      return;
    }

    const checkboxesArray = Array.from(
      document.querySelectorAll(".assign-checkbox")
    );
    const checkbox = problemDiv.querySelector(".assign-checkbox");
    const currentIndex = checkboxesArray.indexOf(checkbox);
    if (currentIndex !== -1) {
      updateDragRange(currentIndex, checkboxesArray);
      lastChecked = checkbox;
    }
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      stopAutoScroll();
    }
    document.body.classList.remove("is-dragging-active");
  });

  // 4. 단일 복사 버튼 이벤트 바인딩
  document.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const title = btn.dataset.title;
      const url = btn.dataset.url;
      const text = `${title}\n${url}`;

      try {
        await copyToClipboard(text);

        await postHomeworkLog({
          title,
          url,
          problems: [],
          message: text,
        });

        btn.disabled = true;
        showToast(`${text}\n\n복사되었습니다.`);
        setTimeout(() => (btn.disabled = false), 1000);
      } catch (err) {
        showToast("복사에 실패했습니다.");
      }
    });
  });

  // 5. 초기 UI 데코레이션 반영
  updateAssignUI();
  highlightTodaySolvedProblems();

  // 6. 자동 높이 조절 Textarea 설정
  const autoExpandTextarea = (el) => {
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 'px';
  };

  const panelTextareas = document.querySelectorAll(".panel-textarea");
  panelTextareas.forEach((ta) => {
    ta.addEventListener("input", function () {
      autoExpandTextarea(this);
    });
    ta.addEventListener("change", function () {
      autoExpandTextarea(this);
    });
  });
});

function showToast(message, duration = 3000) {
  const toast = document.createElement("div");
  toast.textContent = message;
  toast.classList.add("toast", "show");
  document.body.appendChild(toast); // ✅ DOM에 추가

  setTimeout(() => {
    toast.classList.remove("show");
    toast.addEventListener("transitionend", () => {
      toast.remove(); // ✅ 사라진 후 DOM에서 제거
    });
  }, duration);
}

function refreshUserProgress(username) {
  // const username = "{{ username }}"; // Jinja 템플릿에서 사용자 이름 삽입

  fetch(`/refresh_user/${encodeURIComponent(username)}`)
    .then((res) => res.json())
    .then((data) => {
      if (data.success) {
        showToast(`${username} 님\n✅ 풀이 데이터 갱신 완료!`);
        setTimeout(() => {
          location.reload(); // ✅ 토스트 잠깐 보여주고 새로고침
        }, 1500);
      } else {
        showToast("❌ 풀이 데이터 갱신에 실패했습니다.");
        console.error("Error:", data.error);
      }
    })
    .catch((err) => {
      showToast("⚠️ 네트워크 오류: 서버에 연결할 수 없습니다.");
      console.error("Fetch error:", err);
    });
}

// 헤더에 있는 기능

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("username-input");
  const searchForm = document.getElementById("search-form");
  const searchClearBtn = document.getElementById("search-clear-btn");
  const autocompleteList = document.getElementById("autocomplete-list");

  if (!searchInput || !searchForm || !autocompleteList) return;

  const RECENT_KEY = "learning_tracker_recent_usernames";
  const MAX_SUGGESTIONS = 8;
  const MAX_RECENT = 5;
  let usernameList = [];
  let filteredSuggestions = [];
  let activeIndex = -1;
  let debounceTimer = null;

  const getRecentSearches = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      console.error("recent parse error:", err);
      return [];
    }
  };

  const saveRecentSearches = (items) => {
    localStorage.setItem(RECENT_KEY, JSON.stringify(items));
  };

  const pushRecentSearch = (name) => {
    const value = (name || "").trim();
    if (!value) return;
    const next = [value, ...getRecentSearches().filter((item) => item !== value)].slice(
      0,
      MAX_RECENT
    );
    saveRecentSearches(next);
  };

  const closeAutocomplete = () => {
    autocompleteList.innerHTML = "";
    filteredSuggestions = [];
    activeIndex = -1;
  };

  const renderAutocomplete = (items) => {
    autocompleteList.innerHTML = "";
    filteredSuggestions = items;
    activeIndex = -1;

    items.forEach((name, index) => {
      const li = document.createElement("li");
      li.textContent = name;
      li.dataset.index = String(index);
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        searchInput.value = name;
        searchClearBtn?.classList.toggle("hidden", !searchInput.value.trim());
        pushRecentSearch(name);
        closeAutocomplete();
        searchForm.requestSubmit();
      });
      autocompleteList.appendChild(li);
    });
  };

  const updateSuggestions = () => {
    const raw = searchInput.value.trim();
    searchClearBtn?.classList.toggle("hidden", raw.length === 0);

    if (!raw) {
      renderAutocomplete(getRecentSearches());
      return;
    }

    const query = raw.toLowerCase();
    const matches = usernameList
      .filter((name) => name.toLowerCase().includes(query))
      .slice(0, MAX_SUGGESTIONS);
    renderAutocomplete(matches);
  };

  fetch("/proxy/user_rank")
    .then((res) => res.json())
    .then((data) => {
      usernameList = Array.isArray(data.usernames) ? data.usernames : [];
      updateSuggestions();
    })
    .catch((err) => console.error("Error:", err));

  searchInput.addEventListener("input", () => {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(updateSuggestions, 120);
  });

  searchInput.addEventListener("focus", updateSuggestions);

  searchInput.addEventListener("keydown", (e) => {
    if (!filteredSuggestions.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % filteredSuggestions.length;
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex =
        (activeIndex - 1 + filteredSuggestions.length) % filteredSuggestions.length;
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      const selected = filteredSuggestions[activeIndex];
      if (selected) {
        searchInput.value = selected;
        pushRecentSearch(selected);
        closeAutocomplete();
        searchForm.requestSubmit();
      }
      return;
    } else if (e.key === "Escape") {
      closeAutocomplete();
      return;
    } else {
      return;
    }

    const items = autocompleteList.querySelectorAll("li");
    items.forEach((item, idx) => {
      item.classList.toggle("active", idx === activeIndex);
      if (idx === activeIndex) item.scrollIntoView({ block: "nearest" });
    });
  });

  searchForm.addEventListener("submit", (e) => {
    const value = searchInput.value.trim();
    if (!value) {
      e.preventDefault();
      return;
    }
    searchInput.value = value;
    pushRecentSearch(value);
    closeAutocomplete();
  });

  searchClearBtn?.addEventListener("click", () => {
    searchInput.value = "";
    searchInput.focus();
    updateSuggestions();
  });

  document.addEventListener("click", (e) => {
    if (!searchForm.contains(e.target)) closeAutocomplete();
  });

  const urlParams = new URLSearchParams(window.location.search);
  const usernameParam = urlParams.get("username");

  if (usernameParam) {
    searchInput.value = decodeURIComponent(usernameParam);
    searchClearBtn?.classList.toggle("hidden", false);
  }
});

async function highlightTodaySolvedProblems() {
  const groupInfo = document.getElementById("groupInfo");
  if (!groupInfo) return;
  const username = groupInfo.dataset.username;
  if (!username) return;

  try {
    const res = await fetch(`/api/streak?viewMode=user&viewUsername=${encodeURIComponent(username)}&days=1`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.streak_data || data.streak_data.length === 0) return;
    
    const todayDetails = data.streak_data[0].details || [];
    const todaySolvedPids = new Set(todayDetails.map(item => String(item.problem)));

    if (todaySolvedPids.size === 0) return;

    document.querySelectorAll(".problem").forEach((el) => {
      if (!el.classList.contains("solved")) return;
      const cb = el.querySelector(".assign-checkbox");
      if (!cb) return;
      
      const pid = String(cb.dataset.pid);
      if (todaySolvedPids.has(pid)) {
        if (!el.querySelector(".badge-today")) {
          const badge = document.createElement("span");
          badge.className = "badge-today";
          badge.textContent = "오늘 해결 ✨";
          
          const problemLink = el.querySelector(".problem-link");
          if (problemLink) {
            problemLink.after(badge);
          } else {
            el.appendChild(badge);
          }
        }
      }
    });
  } catch (err) {
    console.error("Failed to highlight today solved problems:", err);
  }
}

