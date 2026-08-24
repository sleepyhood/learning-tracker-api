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

  const finalMemo = memoVal || "오늘 수업에 차분하고 성실하게 임함 (특이사항 없음)";

  const promptText = getAiPrompt(problemsSummary, finalMemo);

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

function showToast(message, duration = 2400) {
  document.querySelectorAll(".toast").forEach((el) => el.remove());

  const toast = document.createElement("div");
  toast.textContent = message;
  toast.className = "toast";
  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    const removeToast = () => {
      if (toast.parentNode) {
        toast.remove();
      }
    };
    toast.addEventListener("transitionend", removeToast, { once: true });
    setTimeout(removeToast, 400);
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

  const RECENT_VIEWED_KEY = "learning_tracker_recent_viewed_students_v2";
  const MAX_SUGGESTIONS = 8;
  const MAX_RECENT = 5;
  let studentList = [];
  let filteredSuggestions = [];
  let activeIndex = -1;
  let debounceTimer = null;

  // Korean Choseong (초성) Disassembler Engine
  const CHOSEONG_LIST = [
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ',
    'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
  ];

  const getChoseong = (text) => {
    if (!text || typeof text !== 'string') return '';
    let result = '';
    for (let i = 0; i < text.length; i++) {
      const code = text.charCodeAt(i);
      if (code >= 0xAC00 && code <= 0xD7A3) {
        const choseongIndex = Math.floor((code - 0xAC00) / 588);
        result += CHOSEONG_LIST[choseongIndex] || '';
      } else {
        result += text[i].toLowerCase();
      }
    }
    return result;
  };

  const getRelativeTimeStr = (timestamp) => {
    if (!timestamp) return '';
    const diffSec = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
    if (diffSec < 60) return '방금 전';
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}분 전`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}시간 전`;
    const diffDay = Math.floor(diffHour / 24);
    return `${diffDay}일 전`;
  };

  const getRecentViewed = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(RECENT_VIEWED_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  };

  const pushRecentViewed = (stObjOrString) => {
    if (!stObjOrString) return;
    const name = typeof stObjOrString === 'string' ? stObjOrString : (stObjOrString.name || stObjOrString.display_id || '');
    const displayId = typeof stObjOrString === 'string' ? stObjOrString : (stObjOrString.display_id || stObjOrString.name || '');
    const username = typeof stObjOrString === 'object' ? (stObjOrString.username || '') : '';
    const userUuid = typeof stObjOrString === 'object' ? (stObjOrString.user_uuid || '') : '';

    const currentList = getRecentViewed().filter(item => {
      if (typeof item === 'string') return item !== name && item !== displayId;
      return item.display_id !== displayId && item.name !== name;
    });

    const newEntry = {
      name: name,
      display_id: displayId,
      username: username,
      user_uuid: userUuid,
      timestamp: Date.now()
    };

    const next = [newEntry, ...currentList].slice(0, MAX_RECENT);
    localStorage.setItem(RECENT_VIEWED_KEY, JSON.stringify(next));
  };

  const removeRecentViewed = (displayIdToRemove) => {
    const next = getRecentViewed().filter(item => {
      const id = typeof item === 'string' ? item : item.display_id;
      return id !== displayIdToRemove;
    });
    localStorage.setItem(RECENT_VIEWED_KEY, JSON.stringify(next));
  };

  const clearAllRecentViewed = () => {
    localStorage.removeItem(RECENT_VIEWED_KEY);
  };

  const closeAutocomplete = () => {
    autocompleteList.innerHTML = "";
    filteredSuggestions = [];
    activeIndex = -1;
  };

  // Check standard academy ID format: {한글 이름 2~4자리 OR 영문 2~15자리}{생년월일 중 4자리}
  const isStandardAcademyId = (str) => {
    if (!str || typeof str !== 'string') return false;
    return /^([가-힣]{2,4}|[a-zA-Z]{2,15})\d{4}$/.test(str.trim());
  };

  let warningTooltipEl = null;
  const showSearchWarning = (msg) => {
    if (warningTooltipEl) warningTooltipEl.remove();
    warningTooltipEl = document.createElement("div");
    warningTooltipEl.className = "search-warning-tooltip";
    warningTooltipEl.innerHTML = `<span>⚠️</span> <span>${msg}</span>`;
    
    const wrapper = searchForm.querySelector(".search-wrapper");
    if (wrapper) {
      wrapper.style.position = "relative";
      wrapper.appendChild(warningTooltipEl);
    }

    setTimeout(() => {
      if (warningTooltipEl) {
        warningTooltipEl.remove();
        warningTooltipEl = null;
      }
    }, 3500);
  };

  const hideSearchWarning = () => {
    if (warningTooltipEl) {
      warningTooltipEl.remove();
      warningTooltipEl = null;
    }
  };

  const renderRecentViewed = (items) => {
    autocompleteList.innerHTML = "";
    filteredSuggestions = items;
    activeIndex = -1;

    if (!items || items.length === 0) {
      closeAutocomplete();
      return;
    }

    // Header with Clear All Button
    const headerLi = document.createElement("li");
    headerLi.className = "autocomplete-header-row";
    headerLi.innerHTML = `
      <span style="font-size:0.75rem; font-weight:700; color:var(--muted, #64748b);">🕒 최근 조회 수강생</span>
      <button type="button" class="btn-clear-recent-all" style="background:none; border:none; color:#f87171; font-size:0.72rem; cursor:pointer; padding:2px 4px;">전체 삭제</button>
    `;
    const btnClearAll = headerLi.querySelector(".btn-clear-recent-all");
    btnClearAll.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      clearAllRecentViewed();
      closeAutocomplete();
    });
    autocompleteList.appendChild(headerLi);

    items.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = "autocomplete-item-row recent-item-row";
      
      const name = typeof item === 'string' ? item : (item.name || item.display_id);
      const displayId = typeof item === 'string' ? item : (item.display_id || item.name);
      const timeStr = typeof item === 'object' && item.timestamp ? getRelativeTimeStr(item.timestamp) : '';
      const searchValue = displayId || name;
      const isCustomId = !isStandardAcademyId(displayId) && !isStandardAcademyId(name);

      li.innerHTML = `
        <div class="autocomplete-item-content" style="display:flex; justify-content:space-between; align-items:center; width:100%;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-weight:700; color:var(--text, #0f1f3a);">${name}</span>
            ${displayId && displayId !== name ? `<span style="font-size:0.78rem; color:var(--muted, #64748b);">(@${displayId})</span>` : ''}
            ${isCustomId ? `<span class="badge-custom-id">외부ID</span>` : ''}
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            ${timeStr ? `<span class="recent-time-pill" style="font-size:0.7rem; color:var(--accent, #1663e8); background:var(--surface-soft, #f2f6fd); padding:2px 6px; border-radius:6px; border:1px solid var(--border, #c9d6ea);">${timeStr}</span>` : ''}
            <button type="button" class="btn-remove-recent-item" title="최근 기록 삭제" style="background:none; border:none; font-size:0.8rem; cursor:pointer; padding:2px 4px;">✕</button>
          </div>
        </div>
      `;

      li.dataset.index = String(index);

      // Select student
      li.addEventListener("mousedown", (e) => {
        if (e.target.closest(".btn-remove-recent-item")) return;
        e.preventDefault();
        searchInput.value = searchValue;
        searchClearBtn?.classList.toggle("hidden", !searchInput.value.trim());
        pushRecentViewed(item);
        closeAutocomplete();
        searchForm.requestSubmit();
      });

      // Individual item delete
      const btnRemoveItem = li.querySelector(".btn-remove-recent-item");
      if (btnRemoveItem) {
        btnRemoveItem.addEventListener("mousedown", (e) => {
          e.preventDefault();
          e.stopPropagation();
          removeRecentViewed(displayId);
          updateSuggestions();
        });
      }

      autocompleteList.appendChild(li);
    });
  };

  const renderAutocomplete = (items) => {
    autocompleteList.innerHTML = "";
    filteredSuggestions = items;
    activeIndex = -1;

    if (!items || items.length === 0) {
      closeAutocomplete();
      return;
    }

    const currentQuery = (searchInput.value || "").trim().toLowerCase();
    const queryChoseong = getChoseong(currentQuery);

    items.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = "autocomplete-item-row";
      const name = typeof item === "string" ? item : (item.name || item.display_id);
      const displayId = typeof item === "string" ? item : (item.display_id || item.name);
      const birthMd = typeof item === "object" ? (item.birth_md || "") : "";
      const rawAccounts = typeof item === "object" && Array.isArray(item.accounts) ? item.accounts : [displayId];
      
      const cleanAccounts = [];
      rawAccounts.forEach(a => {
        const str = typeof a === "object" ? (a.username || "") : String(a);
        if (str && !cleanAccounts.includes(str)) cleanAccounts.push(str);
      });

      const primaryAcc = displayId || cleanAccounts[0] || name;
      const subAccounts = cleanAccounts.filter(a => a.toLowerCase() !== primaryAcc.toLowerCase());
      const isCustomId = !isStandardAcademyId(primaryAcc) && !isStandardAcademyId(name);

      const isMatchedAcc = (accStr) => {
        if (!currentQuery) return false;
        const lower = accStr.toLowerCase();
        const chos = getChoseong(accStr);
        return lower.includes(currentQuery) || chos.includes(currentQuery) || chos.includes(queryChoseong);
      };

      li.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:4px; width:100%;">
          <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
              <span style="font-weight:700; color:var(--text, #0f1f3a); font-size:0.92rem;">${name}</span>
              <span class="badge-primary-acc" data-acc="${primaryAcc}" title="본계정 (@${primaryAcc})으로 조회">⭐ @${primaryAcc}</span>
              ${birthMd ? `<span class="badge-birth-mini">🎂 ${birthMd}</span>` : ''}
              ${isCustomId ? `<span class="badge-custom-id">외부ID</span>` : ''}
            </div>
            <span style="font-size:0.72rem; color:var(--muted, #64748b);">선택 ➔</span>
          </div>
          ${subAccounts.length > 0 ? `
            <div style="display:flex; align-items:center; gap:5px; flex-wrap:wrap; font-size:0.75rem; color:var(--muted, #64748b);">
              <span style="font-weight:600; color:#4f46e5;">🔗 부계정:</span>
              ${subAccounts.map(subAcc => `
                <span class="badge-sub-acc ${isMatchedAcc(subAcc) ? 'is-matched' : ''}" data-acc="${subAcc}" title="부계정 (@${subAcc})으로 조회">@${subAcc}</span>
              `).join('')}
            </div>
          ` : ''}
        </div>
      `;

      li.dataset.index = String(index);

      // Sub-account chip direct click
      li.querySelectorAll(".badge-sub-acc").forEach(subChip => {
        subChip.addEventListener("mousedown", (e) => {
          e.preventDefault();
          e.stopPropagation();
          const targetSubAcc = subChip.dataset.acc || subChip.textContent.replace("@", "").trim();
          searchInput.value = targetSubAcc;
          searchClearBtn?.classList.toggle("hidden", !searchInput.value.trim());
          pushRecentViewed({
            name: name,
            display_id: targetSubAcc,
            username: targetSubAcc,
            user_uuid: item.user_uuid
          });
          closeAutocomplete();
          searchForm.requestSubmit();
        });
      });

      // Primary badge or entire row click
      li.addEventListener("mousedown", (e) => {
        if (e.target.closest(".badge-sub-acc")) return;
        e.preventDefault();
        const clickedPrimary = e.target.closest(".badge-primary-acc")?.dataset.acc || primaryAcc;
        searchInput.value = clickedPrimary;
        searchClearBtn?.classList.toggle("hidden", !searchInput.value.trim());
        pushRecentViewed(item);
        closeAutocomplete();
        searchForm.requestSubmit();
      });
      autocompleteList.appendChild(li);
    });
  };

  let remoteSearchTimer = null;

  const updateSuggestions = () => {
    const raw = searchInput.value.trim();
    searchClearBtn?.classList.toggle("hidden", raw.length === 0);

    if (!raw) {
      renderRecentViewed(getRecentViewed());
      return;
    }

    const query = raw.toLowerCase();
    const queryChoseong = getChoseong(raw);

    const matches = studentList
      .filter((st) => {
        if (typeof st === "string") {
          const sLower = st.toLowerCase();
          const sChoseong = getChoseong(st);
          return sLower.includes(query) || sChoseong.includes(query) || sChoseong.includes(queryChoseong);
        }
        const name = (st.name || "").toLowerCase();
        const displayId = (st.display_id || "").toLowerCase();
        const username = (st.username || "").toLowerCase();
        const nameChoseong = getChoseong(st.name || "");
        const displayChoseong = getChoseong(st.display_id || "");

        const textMatch = name.includes(query) || displayId.includes(query) || username.includes(query);
        const choseongMatch = nameChoseong.includes(query) || nameChoseong.includes(queryChoseong) ||
                              displayChoseong.includes(query) || displayChoseong.includes(queryChoseong);

        let subAccountMatch = false;
        if (Array.isArray(st.accounts)) {
          subAccountMatch = st.accounts.some(acc => {
            const accLower = String(acc).toLowerCase();
            return accLower.includes(query) || getChoseong(acc).includes(queryChoseong);
          });
        }

        return textMatch || choseongMatch || subAccountMatch;
      })
      .slice(0, MAX_SUGGESTIONS);

    renderAutocomplete(matches);

    // On-demand remote search if local matches are scarce
    if (matches.length < 3 && raw.length >= 2) {
      if (remoteSearchTimer) clearTimeout(remoteSearchTimer);
      remoteSearchTimer = setTimeout(() => {
        const currentQuery = searchInput.value.trim();
        if (currentQuery !== raw) return;

        fetch(`/api/students/search_suggestions?q=${encodeURIComponent(raw)}`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data && Array.isArray(data.suggestions) && data.suggestions.length > 0) {
              // Merge into studentList if not present
              const existingUuids = new Set(studentList.map(s => typeof s === 'object' ? s.user_uuid : s));
              data.suggestions.forEach(newItem => {
                if (!existingUuids.has(newItem.user_uuid)) {
                  studentList.push(newItem);
                  existingUuids.add(newItem.user_uuid);
                }
              });

              if (document.activeElement === searchInput && searchInput.value.trim() === raw) {
                const updatedMatches = data.suggestions.slice(0, MAX_SUGGESTIONS);
                renderAutocomplete(updatedMatches);
              }
            }
          })
          .catch((err) => console.error("[remoteSearch] error:", err));
      }, 250);
    }
  };

  const fetchStudentSuggestions = () => {
    fetch("/api/students/search_suggestions")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.suggestions) && data.suggestions.length > 0) {
          studentList = data.suggestions;
          if (document.activeElement === searchInput) {
            updateSuggestions();
          }
        }
      })
      .catch((err) => console.error("Error fetching search suggestions:", err));
  };

  window.refreshStudentSuggestions = fetchStudentSuggestions;
  fetchStudentSuggestions();

  searchInput.addEventListener("input", () => {
    hideSearchWarning();
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(updateSuggestions, 120);
  });

  searchInput.addEventListener("focus", updateSuggestions);

  // Search form submit guard against 500 errors
  searchForm.addEventListener("submit", (e) => {
    const rawVal = searchInput.value.trim();
    if (!rawVal) {
      e.preventDefault();
      return;
    }

    if (studentList && studentList.length > 0) {
      const qLower = rawVal.toLowerCase();
      const matched = studentList.find(st => {
        if (typeof st === "string") return st.toLowerCase() === qLower;
        const name = (st.name || "").toLowerCase();
        const displayId = (st.display_id || "").toLowerCase();
        const username = (st.username || "").toLowerCase();
        const hasSubAcc = Array.isArray(st.accounts) && st.accounts.some(acc => String(acc).toLowerCase() === qLower);
        return name === qLower || displayId === qLower || username === qLower || hasSubAcc;
      });

      if (!matched) {
        e.preventDefault();
        showSearchWarning("등록되지 않은 학생입니다. 추천 목록에서 선택해 주세요.");
        return;
      }
      pushRecentViewed(matched);
    }
  });

  searchInput.addEventListener("keydown", (e) => {
    if (!filteredSuggestions.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % filteredSuggestions.length;
      highlightActiveSuggestion();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex =
        (activeIndex - 1 + filteredSuggestions.length) % filteredSuggestions.length;
      highlightActiveSuggestion();
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      const selected = filteredSuggestions[activeIndex];
      if (selected) {
        const searchValue =
          typeof selected === "string" ? selected : (selected.display_id || selected.name);
        searchInput.value = searchValue;
        pushRecentViewed(selected);
        closeAutocomplete();
        searchForm.requestSubmit();
      }
      return;
    } else if (e.key === "Escape") {
      closeAutocomplete();
    }
  });

  const highlightActiveSuggestion = () => {
    const items = autocompleteList.querySelectorAll(".autocomplete-item-row");
    items.forEach((item, idx) => {
      if (idx === activeIndex) {
        item.classList.add("is-active");
      } else {
        item.classList.remove("is-active");
      }
    });
  };

  document.addEventListener("click", (e) => {
    if (!searchForm.contains(e.target)) {
      closeAutocomplete();
    }
  });

  searchClearBtn?.addEventListener("click", () => {
    searchInput.value = "";
    searchClearBtn.classList.add("hidden");
    searchInput.focus();
  });

  const urlParams = new URLSearchParams(window.location.search);
  const usernameParam = urlParams.get("username");
  const errorNoticeParam = urlParams.get("error_notice");

  if (usernameParam) {
    searchInput.value = decodeURIComponent(usernameParam);
    searchClearBtn?.classList.toggle("hidden", false);
  }

  if (errorNoticeParam) {
    // Instantly cleanse the address bar URL so messy query strings are not visible to the user
    const cleanUrl = window.location.pathname + (usernameParam ? `?username=${encodeURIComponent(usernameParam)}` : '');
    window.history.replaceState(null, '', cleanUrl);
  }
});


async function highlightTodaySolvedProblems() {
  const groupInfo = document.getElementById("groupInfo");
  if (!groupInfo) return;
  const username = groupInfo.dataset.username;
  if (!username) return;

  try {
    const res = await fetch(`/api/streak?viewMode=user&viewUsername=${encodeURIComponent(username)}&username=${encodeURIComponent(username)}&days=1`);
    if (!res.ok) return;
    const data = await res.json();
    const streakList = Array.isArray(data) ? data : (data.streak_data || []);
    if (!streakList || streakList.length === 0) return;
    
    const todayDetails = streakList[0].details || [];
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

