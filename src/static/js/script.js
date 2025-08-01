// 숙제 모드
let assignMode = false;

let selectedProblems = []; // {title, link, chapter}
let lastChecked = null;

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
  copyFab.style.display = copyFab.style.display === "block" ? "none" : "block";

  // 여기 추가: assignModeControls 토글
  if (assignControls.style.display === "block") {
    assignControls.style.display = "none";
  } else {
    assignControls.style.display = "block";
  }
}
function copySelectedProblems() {
  const selected = Array.from(
    document.querySelectorAll(".assign-checkbox:checked")
  );
  if (selected.length === 0) {
    showToast("⚠️ 선택된 문제가 없습니다!");
    return;
  }

  // 그룹 정보
  const groupInfo = document.getElementById("groupInfo");
  const groupTitle = groupInfo.dataset.title;
  const groupUrl = groupInfo.dataset.url;

  // 문제 제목 목록
  const problemTitles = selected.map((cb) => `${cb.dataset.title}`);

  const assignedDate = new Date(); // 출제일 예시
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  const y = assignedDate.getFullYear();
  const m = String(assignedDate.getMonth() + 1).padStart(2, "0");
  const d = String(assignedDate.getDate()).padStart(2, "0");
  const day = days[assignedDate.getDay()];

  const assignedDateStr = `${y}.${m}.${d}(${day})`;

  // 복사할 텍스트에 포함
  const lines = [
    `\n📘 ${groupTitle}`,
    `🔗 ${groupUrl}`,
    `🗓 출제일: ${assignedDateStr}`,
    `⏰ 마감: 다음 수업시간 전까지`,
    "",
    ...problemTitles,
    "=========================",
  ];

  const text = lines.join("\n");

  navigator.clipboard
    .writeText(text)
    .then(() =>
      showToast(
        `📘 ${groupTitle} 단원\n✅ 선택된 ${problemTitles.length} 문제가 복사되었습니다!`
      )
    )
    .catch((err) => alert("복사 실패: " + err));
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

  fetch(`/refresh_user/${username}`)
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
