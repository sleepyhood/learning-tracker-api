// 숙제 모드
let assignMode = false;

let selectedProblems = []; // {title, link, chapter}
let lastChecked = null;

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

  const res = await fetch(`/api/students/${userUuid}/homework_logs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title,
      url,
      problems,
      message,
      due_at: dueAt,
      channel,
    }),
  });
  const textRes = await res.text(); // ← 응답 본문 미리 찍어보기
  console.log("[HW] save response:", res.status, textRes);

  if (!res.ok) {
    const t = await res.text();
    console.error("숙제 로그 저장 실패:", t);
    showToast("⚠️ 로그 저장 실패(복사는 완료됨)");
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
    .forEach((cb) => (cb.checked = checked));
}

function toggleAssignMode() {
  const checkboxes = document.querySelectorAll(".assign-checkbox-wrapper");
  const copyFab = document.getElementById("copyFab");
  const assignControls = document.getElementById("assignModeControls");

  checkboxes.forEach((checkbox) => {
    checkbox.style.display =
      checkbox.style.display === "inline-flex" ? "none" : "inline-flex";
  });

  // 복사 버튼도 같이 보여줌
  copyFab.style.display = copyFab.style.display === "flex" ? "none" : "flex";

  // 여기 추가: assignModeControls 토글
  if (assignControls.style.display === "flex") {
    assignControls.style.display = "none";
  } else {
    assignControls.style.display = "flex";
  }
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

  const text = [
    `\n📘 ${groupTitle}`,
    `🔗 ${groupUrl}`,
    `🗓 출제일: ${assignedDateStr}`,
    `⏰ 마감: 다음 수업시간 전까지`,
    "",
    ...problemTitles,
    "=========================",
  ].join("\n");

  try {
    // 1) 복사 & 즉시 토스트
    await navigator.clipboard.writeText(text);
    showToast(`📘 ${groupTitle}\n✅ ${problemTitles.length}개 복사 완료`);

    // 2) 서버로 로그 (여기서 problemsPayload는 "이 자리에서" 만든다)
    const problemsPayload = selected.map((cb) => ({
      legacy_code: cb.dataset.pid || "", // 또는 code
      title: cb.dataset.title || "",
    }));

    // 실패해도 복사 토스트는 이미 떠있으니 UX 안전
    await postHomeworkLog({
      title: groupTitle,
      url: groupUrl,
      problems: problemsPayload,
      message: text,
    });
  } catch (err) {
    alert("복사 실패: " + err);
  } finally {
    __copying = false;
  }
}

function toggleProblemSelection(problemId) {
  if (!assignMode) return;

  const idx = selectedProblems.indexOf(problemId);
  if (idx > -1) {
    selectedProblems.splice(idx, 1);
  } else {
    selectedProblems.push(problemId);
  }

  sessionStorage.setItem("selectedProblems", JSON.stringify(selectedProblems));
  updateAssignUI();
}

function updateAssignUI() {
  // 예시: 문제 박스에 class 추가
  document.querySelectorAll(".problem-box").forEach((el) => {
    const pid = el.dataset.problemId;
    if (selectedProblems.includes(pid)) {
      el.classList.add("assigned");
    } else {
      el.classList.remove("assigned");
    }
  });
}

function selectUnsolved() {
  const checkboxes = document.querySelectorAll(".assign-checkbox");
  checkboxes.forEach((cb) => {
    const problemDiv = cb.closest(".problem");
    if (
      problemDiv.classList.contains("unsolved") ||
      problemDiv.classList.contains("wrong")
    ) {
      cb.checked = true;
    } else {
      cb.checked = false;
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".problem").forEach((problemDiv) => {
    problemDiv.addEventListener("click", (e) => {
      if (!assignMode) return;

      // a, button, input 클릭 무시
      if (
        e.target.closest("a") ||
        e.target.closest("button") ||
        e.target.closest("input")
      ) {
        return;
      }

      const checkbox = problemDiv.querySelector(".assign-checkbox");
      if (checkbox) {
        checkbox.checked = !checkbox.checked;
        toggleProblemSelection(checkbox.dataset.pid);
      }
    });
  });
});

document.addEventListener("DOMContentLoaded", updateAssignUI);

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
  let usernameList = [];

  fetch("/proxy/user_rank")
    .then((res) => res.json())
    .then((data) => {
      usernameList = data.usernames; // ✅ 누락된 부분

      console.log(usernameList); // ["설재경0216", "다른이름", ...]
    })
    .catch((err) => console.error("Error:", err));

  const searchBtn = document.getElementById("search-btn");
  const searchInput = document.getElementById("username-input");
  const searchForm = document.getElementById("search-form");

  const urlParams = new URLSearchParams(window.location.search);
  const usernameParam = urlParams.get("username");

  // 유저명 자동안성
  searchInput.addEventListener("input", () => {
    const inputValue = searchInput.value.toLowerCase();

    // usernameList에서 필터링
    const matches = usernameList.filter((name) =>
      name.toLowerCase().includes(inputValue)
    );

    showAutocomplete(matches, searchInput, searchForm); // 자동완성 박스 띄우기 (아래 함수 구현)
  });

  // URL 파라미터로 자동 submit될 경우
  if (usernameParam) {
    searchInput.classList.add("show");
    searchInput.value = decodeURIComponent(usernameParam);
    searchForm.submit();
  }

  // 버튼 클릭 시 input 슬라이드 토글
  searchBtn.addEventListener("click", (e) => {
    if (!searchInput.classList.contains("show")) {
      e.preventDefault(); // 처음 클릭 시 검색 막고 input만 보여주기
      searchInput.classList.add("show");
      searchInput.focus();
    }
  });
});

function showAutocomplete(matches, searchInput, searchForm) {
  const list = document.getElementById("autocomplete-list");
  list.innerHTML = ""; // 초기화

  matches.slice(0, 5).forEach((name) => {
    const li = document.createElement("li");
    li.textContent = name;
    li.addEventListener("click", () => {
      searchInput.value = name;
      list.innerHTML = "";
      searchForm.submit();
    });
    list.appendChild(li);
  });
}
